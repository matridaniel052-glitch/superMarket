from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_user, logout_user, login_required, current_user
from functools import wraps
from app import db
from app.models import User, Product, Category, Sale
from datetime import date
from sqlalchemy import func

auth = Blueprint('auth', __name__)


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login'))
        if current_user.role not in ['admin', 'stock_manager']:
            flash('You do not have permission to access that page.', 'error')
            return redirect(url_for('auth.dashboard'))
        return f(*args, **kwargs)
    return decorated


@auth.route('/')
@auth.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('auth.dashboard'))
    if request.method == 'POST':
        email    = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        remember = True if request.form.get('remember') else False
        user = User.query.filter_by(email=email).first()
        if not user or not user.check_password(password):
            flash('Incorrect email or password. Please try again.', 'error')
            return redirect(url_for('auth.login'))
        login_user(user, remember=remember)
        return redirect(url_for('auth.dashboard'))
    return render_template('login.html')


@auth.route('/signup', methods=['GET', 'POST'])
def signup():
    if current_user.is_authenticated:
        return redirect(url_for('auth.dashboard'))
    if request.method == 'POST':
        full_name  = request.form.get('full_name', '').strip()
        email      = request.form.get('email', '').strip()
        password   = request.form.get('password', '')
        confirm    = request.form.get('confirm_password', '')
        staff_id   = request.form.get('staff_id', '').strip()
        department = request.form.get('department', 'Cashier')
        role       = 'cashier'

        if not full_name or not email or not password or not staff_id:
            flash('All required fields must be filled in.', 'error')
            return redirect(url_for('auth.signup'))
        if password != confirm:
            flash('Passwords do not match.', 'error')
            return redirect(url_for('auth.signup'))
        if len(password) < 6:
            flash('Password must be at least 6 characters.', 'error')
            return redirect(url_for('auth.signup'))
        if User.query.filter_by(email=email).first():
            flash('An account with that email already exists.', 'error')
            return redirect(url_for('auth.signup'))
        if User.query.filter_by(staff_id=staff_id).first():
            flash('That Staff ID is already registered.', 'error')
            return redirect(url_for('auth.signup'))

        new_user = User(
            full_name=full_name, email=email, role=role,
            staff_id=staff_id, department=department
        )
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()
        flash(f'Account created for {full_name}! You can now log in.', 'success')
        return redirect(url_for('auth.login'))
    return render_template('signup.html')


@auth.route('/dashboard')
@login_required
def dashboard():
    today = date.today()

    # ── Core counts — single cheap COUNT queries ─────────────
    product_count = Product.query.count()
    cat_count     = Category.query.count()
    low_stock_count = Product.query.filter(
        Product.quantity <= Product.reorder_level
    ).count()

    # ── Stock alerts — DB-filtered, no Python loops ──────────
    critical_products = Product.query.filter(
        Product.quantity < 5,
        Product.quantity > 0
    ).order_by(Product.quantity.asc()).limit(20).all()

    out_of_stock = Product.query.filter(
        Product.quantity == 0
    ).order_by(Product.name).limit(20).all()

    low_stock_products = Product.query.filter(
        Product.quantity <= Product.reorder_level,
        Product.quantity > 0
    ).order_by(Product.quantity.asc()).limit(20).all()

    # ── Sales stats — use SQL SUM instead of Python loops ────
    # FIX: Previously loaded ALL sales into memory, summed in Python.
    # Now: one aggregate query per stat — no objects loaded at all.
    if current_user.role == 'cashier':
        # All-time stats for this cashier
        row = db.session.query(
            func.count(Sale.id),
            func.coalesce(func.sum(Sale.total_amount), 0)
        ).filter(Sale.cashier_id == current_user.id).one()
        sale_count, total_revenue = int(row[0]), round(float(row[1]), 2)

        # Today stats for this cashier
        today_row = db.session.query(
            func.count(Sale.id),
            func.coalesce(func.sum(Sale.total_amount), 0)
        ).filter(
            Sale.cashier_id == current_user.id,
            func.date(Sale.sale_date) == today
        ).one()
    else:
        # All-time stats for all cashiers
        row = db.session.query(
            func.count(Sale.id),
            func.coalesce(func.sum(Sale.total_amount), 0)
        ).one()
        sale_count, total_revenue = int(row[0]), round(float(row[1]), 2)

        # Today stats for all cashiers
        today_row = db.session.query(
            func.count(Sale.id),
            func.coalesce(func.sum(Sale.total_amount), 0)
        ).filter(func.date(Sale.sale_date) == today).one()

    today_count   = int(today_row[0])
    today_revenue = round(float(today_row[1]), 2)

    # ── Recent 5 sales — lightweight, no change needed ───────
    recent_sales = Sale.query.order_by(
        Sale.sale_date.desc()
    ).limit(5).all()

    return render_template('dashboard.html',
        product_count      = product_count,
        low_stock_count    = low_stock_count,
        cat_count          = cat_count,
        sale_count         = sale_count,
        total_revenue      = total_revenue,
        critical_products  = critical_products,
        out_of_stock       = out_of_stock,
        low_stock_products = low_stock_products,
        today_count        = today_count,
        today_revenue      = today_revenue,
        recent_sales       = recent_sales,
    )


@auth.route('/logout', methods=['GET', 'POST'])
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.login'))


@auth.route('/staff')
@login_required
@admin_required
def staff():
    from datetime import datetime
    users = User.query.order_by(User.full_name).all()
    return render_template('staff/index.html', users=users, now=datetime.utcnow())


@auth.route('/staff/change-role/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def change_role(user_id):
    u = User.query.get_or_404(user_id)
    new_role = request.form.get('role', 'cashier')
    u.role = new_role
    db.session.commit()
    flash(f'{u.full_name} role updated to {new_role}.', 'success')
    return redirect(url_for('auth.staff'))


@auth.route('/staff/delete/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def delete_user(user_id):
    u = User.query.get_or_404(user_id)
    name = u.full_name
    db.session.delete(u)
    db.session.commit()
    flash(f'Staff member "{name}" deleted.', 'info')
    return redirect(url_for('auth.staff'))


@auth.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    if request.method == 'POST':
        current_pw = request.form.get('current_password', '')
        new_pw     = request.form.get('new_password', '')
        confirm_pw = request.form.get('confirm_password', '')

        if not current_user.check_password(current_pw):
            flash('Current password is incorrect.', 'error')
            return redirect(url_for('auth.change_password'))
        if len(new_pw) < 6:
            flash('New password must be at least 6 characters.', 'error')
            return redirect(url_for('auth.change_password'))
        if new_pw != confirm_pw:
            flash('New passwords do not match.', 'error')
            return redirect(url_for('auth.change_password'))

        current_user.set_password(new_pw)
        db.session.commit()
        flash('Password updated successfully!', 'success')
        return redirect(url_for('auth.dashboard'))

    return render_template('staff/change_password.html')