from email_service import send_low_stock_alert
import os
from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_required, current_user
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
                sku = getattr(product, 'sku', None) or getattr(product, 'code', None) or 'N/A'
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
    return render_template('sales/history.html', sales=all_sales, total_revenue=round(total_revenue, 2))


@sales.route('/sales/delete/<int:sale_id>', methods=['POST'])
@login_required
def delete_sale(sale_id):
    sale = Sale.query.get_or_404(sale_id)
    db.session.delete(sale)
    db.session.commit()
    flash('Sale record deleted.', 'info')
    return redirect(url_for('sales.history'))