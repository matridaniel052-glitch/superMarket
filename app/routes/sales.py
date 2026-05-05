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

sales = Blueprint('sales', __name__)


@sales.route('/sales/new', methods=['GET', 'POST'])
@login_required
def new_sale():
    products = Product.query.filter(Product.quantity > 0).order_by(Product.name).all()

    if request.method == 'POST':
        cart       = request.form.getlist('product_id')
        quantities = request.form.getlist('qty')
        discount   = float(request.form.get('discount', 0))
        payment    = request.form.get('payment_method', 'cash')

        if not cart:
            flash('Please add at least one product to the cart.', 'error')
            return redirect(url_for('sales.new_sale'))

        sale = Sale(cashier_id=current_user.id, discount=discount, payment_method=payment)
        db.session.add(sale)
        db.session.flush()

        total = 0
        for pid, qty in zip(cart, quantities):
            if not qty or not qty.strip():
                continue
            qty = int(qty)
            if qty <= 0:
                continue
            product = Product.query.get(int(pid))
            if not product or product.quantity < qty:
                flash(f'Not enough stock for {product.name if product else "item"}.', 'error')
                db.session.rollback()
                return redirect(url_for('sales.new_sale'))
            item = SaleItem(sale_id=sale.id, product_id=product.id, quantity=qty, unit_price=product.unit_price)
            db.session.add(item)
            product.quantity -= qty
            total += item.subtotal
            if hasattr(product, 'reorder_level') and product.quantity <= product.reorder_level:
                manager_email = os.getenv('MANAGER_EMAIL')
                sku = getattr(product, 'sku', None) or getattr(product, 'barcode', None) or 'N/A'
                send_low_stock_alert(
                    product.name,
                    sku,
                    product.quantity,
                    product.reorder_level,
                    manager_email
                )

        sale.total_amount = round(total - discount, 2)
        db.session.commit()
        flash('Sale completed successfully!', 'success')
        return redirect(url_for('sales.receipt', sale_id=sale.id))

    return render_template('sales/new_sale.html', products=products)


@sales.route('/sales/receipt/<int:sale_id>')
@login_required
def receipt(sale_id):
    sale = Sale.query.get_or_404(sale_id)
    return render_template('sales/receipt.html', sale=sale)


@sales.route('/sales/history')
@login_required
def history():
    all_sales = Sale.query.order_by(Sale.sale_date.desc()).all()
    total_revenue = sum(s.grand_total for s in all_sales)

    monthly = defaultdict(float)
    for s in all_sales:
        key = s.sale_date.strftime('%b %Y')
        monthly[key] += float(s.grand_total)
    monthly_data = [{'month': k, 'revenue': round(v, 2)} for k, v in monthly.items()]

    return render_template('sales/history.html',
        sales=all_sales,
        total_revenue=round(total_revenue, 2),
        monthly_data=monthly_data
    )


@sales.route('/sales/download-pdf')
@login_required
def download_pdf():
    all_sales = Sale.query.order_by(Sale.sale_date.desc()).all()
    total_revenue = sum(s.grand_total for s in all_sales)

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4,
        rightMargin=2*cm, leftMargin=2*cm,
        topMargin=2*cm, bottomMargin=2*cm)

    green = colors.HexColor('#1a5c2a')
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