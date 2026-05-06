from email_service import send_low_stock_alert
import os
from collections import defaultdict
from datetime import datetime
import io
from flask import Blueprint, render_template, redirect, url_for, request, flash, make_response
from flask_login import login_required, current_user
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from app import db
from app.models import Product, Sale, SaleItem
from sqlalchemy import func
from sqlalchemy.orm import joinedload

sales = Blueprint('sales', __name__)

# How many sales to show per page in history
HISTORY_PAGE_SIZE = 40


@sales.route('/sales/new', methods=['GET', 'POST'])
@login_required
def new_sale():
    # Only load what POS needs: id, name, price, qty — no joins
    products = Product.query.filter(
        Product.quantity > 0
    ).with_entities(
        Product.id, Product.name, Product.unit_price, Product.quantity, Product.barcode
    ).order_by(Product.name).all()

    if request.method == 'POST':
        cart       = request.form.getlist('product_id')
        quantities = request.form.getlist('qty')
        discount   = float(request.form.get('discount', 0))
        payment    = request.form.get('payment_method', 'cash')

        if not cart:
            flash('Please add at least one product to the cart.', 'error')
            return redirect(url_for('sales.new_sale'))

        # FIX: Load ALL needed products in ONE query (bulk fetch by IDs)
        # Previously: Product.query.get(pid) inside a loop = N separate queries
        pids         = [int(pid) for pid in cart]
        products_map = {
            p.id: p
            for p in Product.query.filter(Product.id.in_(pids)).all()
        }

        sale = Sale(cashier_id=current_user.id, discount=discount, payment_method=payment)
        db.session.add(sale)
        db.session.flush()

        total      = 0
        sale_items = []
        low_stock_alerts = []  # collect and send AFTER commit

        for pid, qty_str in zip(cart, quantities):
            if not qty_str or not qty_str.strip():
                continue
            qty     = int(qty_str)
            pid_int = int(pid)
            if qty <= 0:
                continue

            product = products_map.get(pid_int)
            if not product or product.quantity < qty:
                pname = product.name if product else 'item'
                flash(f'Not enough stock for {pname}.', 'error')
                db.session.rollback()
                return redirect(url_for('sales.new_sale'))

            item = SaleItem(
                sale_id=sale.id,
                product_id=product.id,
                quantity=qty,
                unit_price=product.unit_price
            )
            sale_items.append(item)
            product.quantity -= qty
            total += item.subtotal

            # Queue low-stock alerts — send after commit, not inside loop
            if product.quantity <= product.reorder_level:
                low_stock_alerts.append(product)

        # Bulk-add all items in one shot
        db.session.bulk_save_objects(sale_items)
        sale.total_amount = round(total - discount, 2)
        db.session.commit()

        # Send alerts AFTER successful commit
        manager_email = os.getenv('MANAGER_EMAIL')
        for product in low_stock_alerts:
            sku = getattr(product, 'sku', None) or product.barcode or 'N/A'
            try:
                send_low_stock_alert(
                    product.name, sku,
                    product.quantity, product.reorder_level,
                    manager_email
                )
            except Exception:
                pass  # Never let email failure break a sale

        flash('Sale completed successfully!', 'success')
        return redirect(url_for('sales.receipt', sale_id=sale.id))

    return render_template('sales/new_sale.html', products=products)


@sales.route('/sales/receipt/<int:sale_id>')
@login_required
def receipt(sale_id):
    # Eagerly load items + product in one query to avoid N+1 on receipt render
    sale = Sale.query.options(
        joinedload(Sale.items).joinedload(SaleItem.product)
    ).get_or_404(sale_id)
    return render_template('sales/receipt.html', sale=sale)


@sales.route('/sales/history')
@login_required
def history():
    page = request.args.get('page', 1, type=int)

    # Paginate — don't load thousands of sales into memory
    pagination = Sale.query.order_by(
        Sale.sale_date.desc()
    ).paginate(page=page, per_page=HISTORY_PAGE_SIZE, error_out=False)

    page_sales = pagination.items

    # Total revenue via SQL SUM — no Python loop over all records
    total_revenue = db.session.query(
        func.coalesce(func.sum(Sale.total_amount), 0)
    ).scalar()
    total_revenue = round(float(total_revenue), 2)

    # Monthly breakdown — SQL GROUP BY instead of Python defaultdict loop
    monthly_rows = db.session.query(
        func.strftime('%m-%Y', Sale.sale_date).label('month_key'),
        func.sum(Sale.total_amount).label('revenue')
    ).group_by('month_key').order_by('month_key').all()

    monthly_data = [
        {'month': _format_month(row.month_key), 'revenue': round(float(row.revenue), 2)}
        for row in monthly_rows
    ]

    return render_template('sales/history.html',
        sales         = page_sales,
        total_revenue = total_revenue,
        monthly_data  = monthly_data,
        pagination    = pagination,
    )


def _format_month(month_key):
    """Convert '01-2025' → 'Jan 2025'."""
    try:
        return datetime.strptime(month_key, '%m-%Y').strftime('%b %Y')
    except Exception:
        return month_key


@sales.route('/sales/download-pdf')
@login_required
def download_pdf():
    # For PDF export we need all sales — but only the columns needed for the table.
    # Use with_entities to avoid loading relationships until we need cashier names.
    # For small-to-medium stores this is acceptable; add date filters if needed.
    all_sales = Sale.query.options(
        joinedload(Sale.items)
    ).order_by(Sale.sale_date.desc()).all()

    total_revenue = sum(s.total_amount for s in all_sales)  # total_amount already stored

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4,
        rightMargin=2*cm, leftMargin=2*cm,
        topMargin=2*cm, bottomMargin=2*cm)

    green    = colors.HexColor('#1a5c2a')
    elements = []

    title_style = ParagraphStyle('title', fontSize=18, textColor=green,
        fontName='Helvetica-Bold', spaceAfter=4)
    sub_style = ParagraphStyle('sub', fontSize=10, textColor=colors.grey,
        fontName='Helvetica', spaceAfter=16)

    elements.append(Paragraph("SuperMart IMS — Sales History Report", title_style))
    elements.append(Paragraph(
        f"Generated: {datetime.now().strftime('%d %B %Y, %I:%M %p')}  |  "
        f"Total Revenue: GHS {total_revenue:.2f}  |  Transactions: {len(all_sales)}",
        sub_style))
    elements.append(Spacer(1, 0.3*cm))

    data = [['Receipt #', 'Date & Time', 'Cashier', 'Items', 'Subtotal', 'Discount', 'Total Paid', 'Payment']]
    for s in all_sales:
        data.append([
            f'#{s.id:04d}',
            s.sale_date.strftime('%d %b %Y %I:%M %p'),
            s.cashier.full_name,
            str(len(s.items)),
            f'GHS {s.total_amount:.2f}',
            f'GHS {s.discount:.2f}' if s.discount > 0 else '-',
            f'GHS {s.grand_total:.2f}',
            s.payment_method.capitalize()
        ])

    table = Table(data, colWidths=[2*cm, 4*cm, 3.5*cm, 1.5*cm, 2.8*cm, 2.5*cm, 2.8*cm, 2.5*cm])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), green),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,0), 9),
        ('FONTSIZE', (0,1), (-1,-1), 8),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#f0f7f2')]),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#cccccc')),
        ('ALIGN', (3,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
    ]))
    elements.append(table)
    doc.build(elements)

    buffer.seek(0)
    response = make_response(buffer.read())
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = \
        f'attachment; filename=sales_report_{datetime.now().strftime("%Y%m%d")}.pdf'
    return response


@sales.route('/sales/delete/<int:sale_id>', methods=['POST'])
@login_required
def delete_sale(sale_id):
    sale = Sale.query.get_or_404(sale_id)
    db.session.delete(sale)
    db.session.commit()
    flash('Sale record deleted.', 'info')
    return redirect(url_for('sales.history'))