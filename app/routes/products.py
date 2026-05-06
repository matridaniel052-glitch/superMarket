from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify
from flask_login import login_required, current_user
from app import db
from app.models import Product, Category

products = Blueprint('products', __name__)

# How many products to show per page
PAGE_SIZE = 30


@products.route('/products')
@login_required
def index():
    search      = request.args.get('search', '').strip()
    category_id = request.args.get('category', '').strip()
    page        = request.args.get('page', 1, type=int)

    query = Product.query

    # Filtered on the DB side — not in Python
    if search:
        query = query.filter(Product.name.ilike(f'%{search}%'))
    if category_id:
        query = query.filter_by(category_id=int(category_id))

    # Paginate — never load all rows into memory
    pagination   = query.order_by(Product.name).paginate(
        page=page, per_page=PAGE_SIZE, error_out=False
    )
    all_products = pagination.items
    categories   = Category.query.order_by(Category.name).all()

    return render_template(
        'products/index.html',
        products     = all_products,
        categories   = categories,
        search       = search,
        selected_cat = category_id,
        pagination   = pagination,   # pass to template for page controls
    )


@products.route('/products/barcode/<barcode>')
@login_required
def by_barcode(barcode):
    """Fast barcode lookup for POS — returns JSON, uses indexed column."""
    p = Product.query.filter_by(barcode=barcode).first()
    if not p:
        return jsonify({'error': 'Not found'}), 404
    return jsonify({
        'id':         p.id,
        'name':       p.name,
        'unit_price': p.unit_price,
        'quantity':   p.quantity,
    })


@products.route('/products/add', methods=['GET', 'POST'])
@login_required
def add():
    categories = Category.query.order_by(Category.name).all()
    if request.method == 'POST':
        name          = request.form.get('name', '').strip()
        barcode       = request.form.get('barcode', '').strip()
        category_id   = request.form.get('category_id')
        unit_price    = request.form.get('unit_price', 0)
        cost_price    = request.form.get('cost_price', 0)
        quantity      = request.form.get('quantity', 0)
        reorder_level = request.form.get('reorder_level', 5)

        if not name:
            flash('Product name is required.', 'error')
            return redirect(url_for('products.add'))

        # Indexed column — fast lookup
        if barcode and Product.query.filter_by(barcode=barcode).first():
            flash('A product with that barcode already exists.', 'error')
            return redirect(url_for('products.add'))

        p = Product(
            name=name, barcode=barcode or None,
            category_id=category_id or None,
            unit_price=float(unit_price), cost_price=float(cost_price),
            quantity=int(quantity), reorder_level=int(reorder_level)
        )
        db.session.add(p)
        db.session.commit()
        flash(f'Product "{name}" added successfully!', 'success')
        return redirect(url_for('products.index'))

    return render_template('products/add.html', categories=categories)


@products.route('/products/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit(id):
    p          = Product.query.get_or_404(id)
    categories = Category.query.order_by(Category.name).all()
    if request.method == 'POST':
        p.name        = request.form.get('name', '').strip()
        p.barcode     = request.form.get('barcode', '').strip() or None
        p.category_id = request.form.get('category_id') or None
        p.unit_price  = float(request.form.get('unit_price', 0))
        p.cost_price  = float(request.form.get('cost_price', 0))
        p.quantity    = int(request.form.get('quantity', 0))
        reorder_val   = request.form.get('reorder_level', '').strip()
        p.reorder_level = int(reorder_val) if reorder_val else 5
        db.session.commit()
        flash(f'Product "{p.name}" updated!', 'success')
        return redirect(url_for('products.index'))
    return render_template('products/edit.html', product=p, categories=categories)


@products.route('/products/delete/<int:id>', methods=['POST'])
@login_required
def delete(id):
    p    = Product.query.get_or_404(id)
    name = p.name
    db.session.delete(p)
    db.session.commit()
    flash(f'Product "{name}" deleted.', 'info')
    return redirect(url_for('products.index'))


@products.route('/categories', methods=['GET', 'POST'])
@login_required
def categories():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        if name:
            db.session.add(Category(name=name))
            db.session.commit()
            flash(f'Category "{name}" added!', 'success')
        return redirect(url_for('products.categories'))
    all_cats = Category.query.order_by(Category.name).all()
    return render_template('products/categories.html', categories=all_cats)


@products.route('/categories/delete/<int:id>', methods=['POST'])
@login_required
def delete_category(id):
    c = Category.query.get_or_404(id)
    db.session.delete(c)
    db.session.commit()
    flash('Category deleted.', 'info')
    return redirect(url_for('products.categories'))