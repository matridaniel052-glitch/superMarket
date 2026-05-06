from app import db, login_manager
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from sqlalchemy import Index


class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id            = db.Column(db.Integer, primary_key=True)
    full_name     = db.Column(db.String(120), nullable=False)
    email         = db.Column(db.String(120), unique=True, nullable=False)
    role          = db.Column(db.String(30), default='cashier')
    password_hash = db.Column(db.String(256), nullable=False)
    staff_id      = db.Column(db.String(50), unique=True, nullable=True)
    department    = db.Column(db.String(100), nullable=True)
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)
    sales         = db.relationship('Sale', backref='cashier', lazy='select')
    stock_logs    = db.relationship('StockLog', backref='user', lazy='select')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


class Category(db.Model):
    __tablename__ = 'categories'
    id       = db.Column(db.Integer, primary_key=True)
    name     = db.Column(db.String(100), nullable=False, unique=True)
    products = db.relationship('Product', backref='category', lazy='select')


class Product(db.Model):
    __tablename__ = 'products'
    id            = db.Column(db.Integer, primary_key=True)
    name          = db.Column(db.String(150), nullable=False)
    barcode       = db.Column(db.String(60), unique=True, nullable=True)
    category_id   = db.Column(db.Integer, db.ForeignKey('categories.id'), nullable=True)
    unit_price    = db.Column(db.Float, default=0.0)
    cost_price    = db.Column(db.Float, default=0.0)
    quantity      = db.Column(db.Integer, default=0)
    reorder_level = db.Column(db.Integer, default=5)
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)

    # ── Indexes for fast lookups ─────────────────────────────
    __table_args__ = (
        Index('ix_product_name',     'name'),        # fast ILIKE search
        Index('ix_product_category', 'category_id'), # fast category filter
        Index('ix_product_quantity', 'quantity'),    # fast low-stock queries
    )

    @property
    def is_low_stock(self):
        return self.quantity <= self.reorder_level

    @property
    def profit_margin(self):
        if self.unit_price > 0:
            return round(((self.unit_price - self.cost_price) / self.unit_price) * 100, 1)
        return 0


class Sale(db.Model):
    __tablename__ = 'sales'
    id             = db.Column(db.Integer, primary_key=True)
    cashier_id     = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    sale_date      = db.Column(db.DateTime, default=datetime.utcnow, index=True)  # indexed
    discount       = db.Column(db.Float, default=0.0)
    total_amount   = db.Column(db.Float, default=0.0)
    payment_method = db.Column(db.String(30), default='cash')

    # ── Indexes for fast date/cashier queries ────────────────
    __table_args__ = (
        Index('ix_sale_cashier_date', 'cashier_id', 'sale_date'),  # composite
        Index('ix_sale_date',         'sale_date'),
    )

    # Use joined loading to avoid N+1 on items in receipts/history
    items = db.relationship(
        'SaleItem', backref='sale', lazy='select',
        cascade='all, delete-orphan'
    )

    @property
    def subtotal(self):
        return sum(item.subtotal for item in self.items)

    @property
    def grand_total(self):
        return round(self.subtotal - self.discount, 2)


class SaleItem(db.Model):
    __tablename__ = 'sale_items'
    id         = db.Column(db.Integer, primary_key=True)
    sale_id    = db.Column(db.Integer, db.ForeignKey('sales.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    quantity   = db.Column(db.Integer, nullable=False)
    unit_price = db.Column(db.Float, nullable=False)

    # ── Index for fast JOIN in reports ───────────────────────
    __table_args__ = (
        Index('ix_saleitem_sale',    'sale_id'),
        Index('ix_saleitem_product', 'product_id'),
    )

    product = db.relationship('Product')

    @property
    def subtotal(self):
        return round(self.quantity * self.unit_price, 2)


class Supplier(db.Model):
    __tablename__ = 'suppliers'
    id            = db.Column(db.Integer, primary_key=True)
    name          = db.Column(db.String(150), nullable=False)
    contact       = db.Column(db.String(120), nullable=True)
    email         = db.Column(db.String(120), nullable=True)
    phone         = db.Column(db.String(30), nullable=True)
    address       = db.Column(db.String(250), nullable=True)
    payment_terms = db.Column(db.String(100), nullable=True)
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)
    orders        = db.relationship('PurchaseOrder', backref='supplier', lazy='select')


class PurchaseOrder(db.Model):
    __tablename__ = 'purchase_orders'
    id          = db.Column(db.Integer, primary_key=True)
    supplier_id = db.Column(db.Integer, db.ForeignKey('suppliers.id'), nullable=False)
    order_date  = db.Column(db.DateTime, default=datetime.utcnow)
    status      = db.Column(db.String(30), default='draft')
    total_cost  = db.Column(db.Float, default=0.0)
    notes       = db.Column(db.String(300), nullable=True)
    items       = db.relationship('POItem', backref='order', lazy='select', cascade='all, delete-orphan')

    @property
    def computed_total(self):
        return round(sum(i.subtotal for i in self.items), 2)

    @property
    def status_color(self):
        return {'draft': 'gray', 'sent': 'blue', 'delivered': 'green', 'paid': 'green'}.get(self.status, 'gray')


class POItem(db.Model):
    __tablename__ = 'po_items'
    id         = db.Column(db.Integer, primary_key=True)
    order_id   = db.Column(db.Integer, db.ForeignKey('purchase_orders.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    quantity   = db.Column(db.Integer, nullable=False)
    cost_price = db.Column(db.Float, nullable=False)
    product    = db.relationship('Product')

    @property
    def subtotal(self):
        return round(self.quantity * self.cost_price, 2)


class StockLog(db.Model):
    __tablename__ = 'stock_logs'
    id          = db.Column(db.Integer, primary_key=True)
    product_id  = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    user_id     = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    action      = db.Column(db.String(10), nullable=False)
    quantity    = db.Column(db.Integer, nullable=False)
    reason      = db.Column(db.String(200), nullable=True)
    expiry_date = db.Column(db.DateTime, nullable=True)
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)

    # ── Index for fast per-product log lookup ─────────────────
    __table_args__ = (
        Index('ix_stocklog_product', 'product_id'),
        Index('ix_stocklog_created', 'created_at'),
    )

    product = db.relationship('Product')