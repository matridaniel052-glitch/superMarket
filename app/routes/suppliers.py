from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_required
from app import db
from app.models import Supplier, PurchaseOrder, POItem, Product

suppliers = Blueprint('suppliers', __name__)

@suppliers.route('/suppliers')
@login_required
def index():
    all_suppliers = Supplier.query.order_by(Supplier.name).all()
    return render_template('suppliers/index.html', suppliers=all_suppliers)

@suppliers.route('/suppliers/add', methods=['GET', 'POST'])
@login_required
def add():
    if request.method == 'POST':
        name          = request.form.get('name', '').strip()
        contact       = request.form.get('contact', '').strip()
        email         = request.form.get('email', '').strip()
        phone         = request.form.get('phone', '').strip()
        address       = request.form.get('address', '').strip()
        payment_terms = request.form.get('payment_terms', '').strip()
        if not name:
            flash('Supplier name is required.', 'error')
            return redirect(url_for('suppliers.add'))
        s = Supplier(name=name, contact=contact, email=email,
                     phone=phone, address=address, payment_terms=payment_terms)
        db.session.add(s)
        db.session.commit()
        flash(f'Supplier "{name}" added successfully!', 'success')
        return redirect(url_for('suppliers.index'))
    return render_template('suppliers/add.html')

@suppliers.route('/suppliers/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit(id):
    s = Supplier.query.get_or_404(id)
    if request.method == 'POST':
        s.name          = request.form.get('name', '').strip()
        s.contact       = request.form.get('contact', '').strip()
        s.email         = request.form.get('email', '').strip()
        s.phone         = request.form.get('phone', '').strip()
        s.address       = request.form.get('address', '').strip()
        s.payment_terms = request.form.get('payment_terms', '').strip()
        db.session.commit()
        flash(f'Supplier "{s.name}" updated!', 'success')
        return redirect(url_for('suppliers.index'))
    return render_template('suppliers/edit.html', supplier=s)

@suppliers.route('/suppliers/delete/<int:id>', methods=['POST'])
@login_required
def delete(id):
    s = Supplier.query.get_or_404(id)
    name = s.name
    db.session.delete(s)
    db.session.commit()
    flash(f'Supplier "{name}" deleted.', 'info')
    return redirect(url_for('suppliers.index'))

@suppliers.route('/suppliers/<int:supplier_id>/orders')
@login_required
def orders(supplier_id):
    s = Supplier.query.get_or_404(supplier_id)
    products = Product.query.order_by(Product.name).all()
    return render_template('suppliers/orders.html', supplier=s, products=products)

@suppliers.route('/suppliers/<int:supplier_id>/orders/create', methods=['POST'])
@login_required
def create_order(supplier_id):
    s = Supplier.query.get_or_404(supplier_id)
    product_ids = request.form.getlist('product_id')
    quantities  = request.form.getlist('quantity')
    cost_prices = request.form.getlist('cost_price')
    notes       = request.form.get('notes', '').strip()

    if not product_ids:
        flash('Add at least one product to the order.', 'error')
        return redirect(url_for('suppliers.orders', supplier_id=supplier_id))

    po = PurchaseOrder(supplier_id=supplier_id, notes=notes)
    db.session.add(po)
    db.session.flush()

    for pid, qty, cp in zip(product_ids, quantities, cost_prices):
        qty = int(qty) if qty else 0
        cp  = float(cp) if cp else 0.0
        if qty <= 0:
            continue
        item = POItem(order_id=po.id, product_id=int(pid), quantity=qty, cost_price=cp)
        db.session.add(item)

    po.total_cost = po.computed_total
    db.session.commit()
    flash(f'Purchase order #{po.id} created successfully!', 'success')
    return redirect(url_for('suppliers.orders', supplier_id=supplier_id))

@suppliers.route('/orders/update-status/<int:order_id>', methods=['POST'])
@login_required
def update_status(order_id):
    po     = PurchaseOrder.query.get_or_404(order_id)
    status = request.form.get('status')
    po.status = status

    if status == 'delivered':
        for item in po.items:
            item.product.quantity += item.quantity
            item.product.cost_price = item.cost_price
        flash(f'Order #{po.id} marked as delivered — stock updated!', 'success')
    else:
        flash(f'Order #{po.id} status updated to {status}.', 'success')

    db.session.commit()
    return redirect(url_for('suppliers.orders', supplier_id=po.supplier_id))

@suppliers.route('/orders/delete/<int:order_id>', methods=['POST'])
@login_required
def delete_order(order_id):
    po = PurchaseOrder.query.get_or_404(order_id)
    sid = po.supplier_id
    db.session.delete(po)
    db.session.commit()
    flash('Purchase order deleted.', 'info')
    return redirect(url_for('suppliers.orders', supplier_id=sid))