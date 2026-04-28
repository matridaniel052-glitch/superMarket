from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_required, current_user
from app import db
from app.models import Product, StockLog, Supplier
from datetime import datetime

stock = Blueprint('stock', __name__)

@stock.route('/stock')
@login_required
def index():
    logs      = StockLog.query.order_by(StockLog.created_at.desc()).all()
    products  = Product.query.order_by(Product.name).all()
    low_stock = Product.query.filter(Product.quantity <= Product.reorder_level).all()
    return render_template('stock/index.html',
        logs=logs, products=products,
        low_stock=low_stock, now=datetime.utcnow())

@stock.route('/stock/adjust', methods=['GET', 'POST'])
@login_required
def adjust():
    products = Product.query.order_by(Product.name).all()
    if request.method == 'POST':
        product_id  = request.form.get('product_id')
        action      = request.form.get('action')
        quantity    = int(request.form.get('quantity', 0))
        reason      = request.form.get('reason', '').strip()
        expiry_date = request.form.get('expiry_date', '').strip()

        if not product_id or quantity <= 0:
            flash('Please select a product and enter a valid quantity.', 'error')
            return redirect(url_for('stock.adjust'))

        product = Product.query.get_or_404(int(product_id))

        if action == 'out' and product.quantity < quantity:
            flash(f'Not enough stock. Only {product.quantity} available.', 'error')
            return redirect(url_for('stock.adjust'))

        if action == 'in':
            product.quantity += quantity
        else:
            product.quantity -= quantity

        exp = None
        if expiry_date:
            try:
                exp = datetime.strptime(expiry_date, '%Y-%m-%d')
            except:
                exp = None

        log = StockLog(
            product_id=product.id,
            action=action,
            quantity=quantity,
            reason=reason,
            expiry_date=exp,
            user_id=current_user.id
        )
        db.session.add(log)
        db.session.commit()
        flash(f'Stock {"added to" if action == "in" else "removed from"} {product.name} successfully!', 'success')
        return redirect(url_for('stock.index'))

    return render_template('stock/adjust.html', products=products)


@stock.route('/alerts')
@login_required
def alerts():
    low_stock  = Product.query.filter(Product.quantity <= Product.reorder_level).order_by(Product.quantity).all()
    out_stock  = [p for p in low_stock if p.quantity == 0]
    suppliers  = Supplier.query.order_by(Supplier.name).all()
    return render_template('alerts/index.html',
        low_stock=low_stock,
        out_stock=out_stock,
        suppliers=suppliers)