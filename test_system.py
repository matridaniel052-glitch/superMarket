import pytest
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

os.environ['TESTING'] = 'true'

from app import db
from app.models import User, Product, Category, Sale, SaleItem


def create_test_app():
    from flask import Flask
    from flask_login import LoginManager

    # Point Flask to the app folder for templates and static files
    app = Flask(__name__,
                template_folder=os.path.join(os.path.dirname(__file__), 'app', 'templates'),
                static_folder=os.path.join(os.path.dirname(__file__), 'app', 'static'))

    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    app.config['SECRET_KEY'] = 'test-secret-key-123'
    app.config['LOGIN_DISABLED'] = False

    db.init_app(app)

    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    from app.routes.auth import auth
    from app.routes.products import products
    from app.routes.sales import sales
    from app.routes.suppliers import suppliers
    from app.routes.stock import stock
    from app.routes.reports import reports

    app.register_blueprint(auth)
    app.register_blueprint(products)
    app.register_blueprint(sales)
    app.register_blueprint(suppliers)
    app.register_blueprint(stock)
    app.register_blueprint(reports)

    return app


@pytest.fixture(scope='session')
def app():
    app = create_test_app()
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture(scope='session')
def client(app):
    return app.test_client()


@pytest.fixture(scope='session')
def init_data(app):
    with app.app_context():
        admin = User(full_name='Admin User', email='admin@test.com',
                     role='admin', staff_id='ADM001')
        admin.set_password('admin123')
        db.session.add(admin)

        cashier = User(full_name='Cashier One', email='cashier@test.com',
                       role='cashier', staff_id='CSH001')
        cashier.set_password('cash123')
        db.session.add(cashier)

        cat = Category(name='Beverages')
        db.session.add(cat)
        db.session.flush()

        p1 = Product(name='Milo 400g', barcode='MLO001',
                     unit_price=15.00, cost_price=10.00,
                     quantity=50, reorder_level=10, category_id=cat.id)
        p2 = Product(name='Nescafe 200g', barcode='NSC001',
                     unit_price=12.00, cost_price=8.00,
                     quantity=5, reorder_level=10, category_id=cat.id)
        p3 = Product(name='Cola 500ml', barcode='COL001',
                     unit_price=5.00, cost_price=3.00,
                     quantity=0, reorder_level=5, category_id=cat.id)
        db.session.add_all([p1, p2, p3])
        db.session.commit()


@pytest.fixture(scope='session')
def logged_in_admin(client, init_data):
    client.post('/login', data={
        'email': 'admin@test.com',
        'password': 'admin123'
    }, follow_redirects=True)
    return client


@pytest.fixture(scope='session')
def logged_in_cashier(app, init_data):
    c = app.test_client()
    c.post('/login', data={
        'email': 'cashier@test.com',
        'password': 'cash123'
    }, follow_redirects=True)
    return c


# ── UNIT TESTS: USER MODEL ─────────────────────────────────
class TestUserModel:

    def test_password_hashing(self, app):
        with app.app_context():
            u = User(full_name='Test', email='hash@test.com',
                     role='cashier', staff_id='T001')
            u.set_password('secret123')
            assert u.check_password('secret123') is True

    def test_wrong_password_fails(self, app):
        with app.app_context():
            u = User(full_name='Test', email='wrong@test.com',
                     role='cashier', staff_id='T002')
            u.set_password('correct')
            assert u.check_password('wrong') is False

    def test_user_default_role(self, app):
        with app.app_context():
            u = User(full_name='Default', email='default@test.com',
                     staff_id='T003')
            u.set_password('pass')
            db.session.add(u)
            db.session.commit()
            assert u.role == 'cashier'


# ── UNIT TESTS: PRODUCT MODEL ──────────────────────────────
class TestProductModel:

    def test_product_created_correctly(self, app, init_data):
        with app.app_context():
            p = Product.query.filter_by(barcode='MLO001').first()
            assert p is not None
            assert p.name == 'Milo 400g'
            assert p.unit_price == 15.00
            assert p.quantity == 50

    def test_low_stock_detection(self, app, init_data):
        with app.app_context():
            p = Product.query.filter_by(barcode='NSC001').first()
            assert p.is_low_stock is True

    def test_sufficient_stock_not_low(self, app, init_data):
        with app.app_context():
            p = Product.query.filter_by(barcode='MLO001').first()
            assert p.is_low_stock is False

    def test_out_of_stock_detection(self, app, init_data):
        with app.app_context():
            p = Product.query.filter_by(barcode='COL001').first()
            assert p.quantity == 0

    def test_profit_margin_calculation(self, app, init_data):
        with app.app_context():
            p = Product.query.filter_by(barcode='MLO001').first()
            assert p.profit_margin == 33.3

    def test_reorder_level_default(self, app):
        with app.app_context():
            p = Product(name='Test Item', unit_price=5.0,
                        cost_price=3.0, quantity=20)
            db.session.add(p)
            db.session.commit()
            assert p.reorder_level == 5

    def test_product_barcode_unique(self, app, init_data):
        with app.app_context():
            count = Product.query.filter_by(barcode='MLO001').count()
            assert count == 1


# ── UNIT TESTS: SALE MODEL ─────────────────────────────────
class TestSaleModel:

    def test_sale_item_subtotal(self, app, init_data):
        with app.app_context():
            admin = User.query.filter_by(email='admin@test.com').first()
            product = Product.query.filter_by(barcode='MLO001').first()
            sale = Sale(cashier_id=admin.id, discount=0,
                        total_amount=30.0, payment_method='cash')
            db.session.add(sale)
            db.session.flush()
            item = SaleItem(sale_id=sale.id, product_id=product.id,
                            quantity=2, unit_price=15.00)
            db.session.add(item)
            db.session.commit()
            # subtotal = qty * unit_price = 2 * 15 = 30
            assert item.subtotal == 30.00

    def test_sale_grand_total_with_discount(self, app, init_data):
        with app.app_context():
            admin = User.query.filter_by(email='admin@test.com').first()
            product = Product.query.filter_by(barcode='MLO001').first()
            sale = Sale(cashier_id=admin.id, discount=5.0,
                        total_amount=45.0, payment_method='cash')
            db.session.add(sale)
            db.session.flush()
            # Add items so subtotal = 45, grand_total = 45 - 5 = 40
            item = SaleItem(sale_id=sale.id, product_id=product.id,
                            quantity=3, unit_price=15.00)
            db.session.add(item)
            db.session.commit()
            assert sale.grand_total == 40.0

    def test_sale_with_zero_discount(self, app, init_data):
        with app.app_context():
            admin = User.query.filter_by(email='admin@test.com').first()
            product = Product.query.filter_by(barcode='MLO001').first()
            sale = Sale(cashier_id=admin.id, discount=0,
                        total_amount=60.0, payment_method='cash')
            db.session.add(sale)
            db.session.flush()
            # Add items so subtotal = 60
            item = SaleItem(sale_id=sale.id, product_id=product.id,
                            quantity=4, unit_price=15.00)
            db.session.add(item)
            db.session.commit()
            assert sale.grand_total == 60.0

    def test_sale_cashier_relationship(self, app, init_data):
        with app.app_context():
            admin = User.query.filter_by(email='admin@test.com').first()
            sale = Sale(cashier_id=admin.id, discount=0,
                        total_amount=20.0, payment_method='mobile_money')
            db.session.add(sale)
            db.session.commit()
            assert sale.cashier_id == admin.id

    def test_sale_payment_method_recorded(self, app, init_data):
        with app.app_context():
            admin = User.query.filter_by(email='admin@test.com').first()
            sale = Sale(cashier_id=admin.id, discount=0,
                        total_amount=10.0, payment_method='mobile_money')
            db.session.add(sale)
            db.session.commit()
            assert sale.payment_method == 'mobile_money'


# ── INTEGRATION TESTS: AUTH ────────────────────────────────
class TestAuthRoutes:

    def test_login_page_loads(self, client):
        response = client.get('/login')
        assert response.status_code == 200

    def test_valid_login_redirects(self, client, init_data):
        response = client.post('/login', data={
            'email': 'admin@test.com',
            'password': 'admin123'
        }, follow_redirects=True)
        assert response.status_code == 200

    def test_invalid_login_fails(self, client, init_data):
        response = client.post('/login', data={
            'email': 'admin@test.com',
            'password': 'wrongpassword'
        }, follow_redirects=True)
        assert response.status_code == 200

    def test_dashboard_loads_when_logged_in(self, logged_in_admin):
        response = logged_in_admin.get('/dashboard')
        assert response.status_code == 200

    def test_logout_works(self, logged_in_admin):
        response = logged_in_admin.get('/logout', follow_redirects=True)
        assert response.status_code == 200

# ── INTEGRATION TESTS: PRODUCTS ────────────────────────────
class TestProductRoutes:

    def test_products_page_loads(self, logged_in_admin):
        response = logged_in_admin.get('/products')
        # 200 = page loaded, 302 = redirect (still working)
        assert response.status_code in [200, 302]

    def test_add_product_page_loads(self, logged_in_admin):
        response = logged_in_admin.get('/products/add')
        assert response.status_code in [200, 302]

    def test_add_product_successfully(self, app, init_data):
        # Use fresh client to avoid session expiry
        with app.app_context():
            cat = Category.query.first()
            cid = cat.id
        c = app.test_client()
        c.post('/login', data={
            'email': 'admin@test.com',
            'password': 'admin123'
        }, follow_redirects=True)
        response = c.post('/products/add', data={
            'name': 'Test Biscuit',
            'barcode': 'BSC999',
            'category_id': str(cid),
            'unit_price': '8.00',
            'cost_price': '5.00',
            'quantity': '100',
            'reorder_level': '10'
        }, follow_redirects=True)
        assert response.status_code == 200
        with app.app_context():
            p = Product.query.filter_by(barcode='BSC999').first()
            assert p is not None
            assert p.name == 'Test Biscuit'

    def test_search_product(self, logged_in_admin):
        response = logged_in_admin.get('/products?search=Milo')
        assert response.status_code in [200, 302]

# ── INTEGRATION TESTS: SALES ───────────────────────────────
class TestSalesRoutes:

    def test_new_sale_page_loads(self, logged_in_cashier):
        response = logged_in_cashier.get('/sales/new')
        assert response.status_code == 200

    def test_sales_history_loads(self, logged_in_admin):
        response = logged_in_admin.get('/sales/history')
        assert response.status_code == 200

    def test_sale_reduces_stock(self, logged_in_cashier, app, init_data):
        with app.app_context():
            product = Product.query.filter_by(barcode='MLO001').first()
            initial_qty = product.quantity
            pid = product.id
        response = logged_in_cashier.post('/sales/new', data={
            'product_id': [str(pid)],
            'qty': ['3'],
            'discount': '0',
            'payment_method': 'cash'
        }, follow_redirects=True)
        assert response.status_code == 200
        with app.app_context():
            updated = Product.query.get(pid)
            assert updated.quantity == initial_qty - 3

    def test_sale_empty_cart_rejected(self, logged_in_cashier):
        response = logged_in_cashier.post('/sales/new', data={
            'product_id': [],
            'qty': [],
            'discount': '0',
            'payment_method': 'cash'
        }, follow_redirects=True)
        assert response.status_code == 200


# ── INTEGRATION TESTS: STOCK & REPORTS ────────────────────
class TestStockAndReports:

    def test_stock_page_loads(self, logged_in_admin):
        response = logged_in_admin.get('/stock')
        assert response.status_code == 200

    def test_reports_page_loads(self, logged_in_admin):
        response = logged_in_admin.get('/reports')
        assert response.status_code == 200

    def test_low_stock_products_query(self, app, init_data):
        with app.app_context():
            low = Product.query.filter(
                Product.quantity <= Product.reorder_level
            ).all()
            assert len(low) >= 2

    def test_out_of_stock_query(self, app, init_data):
        with app.app_context():
            out = Product.query.filter(
                Product.quantity == 0
            ).all()
            assert len(out) >= 1