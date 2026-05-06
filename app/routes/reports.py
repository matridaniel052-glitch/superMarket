from flask import Blueprint, render_template, request
from flask_login import login_required
from app.models import Sale, SaleItem, Product
from app import db
from datetime import datetime, timedelta
from sqlalchemy import func
from sqlalchemy.orm import joinedload

reports = Blueprint('reports', __name__)


@reports.route('/reports')
@login_required
def index():
    today = datetime.utcnow().date()

    # ── Last 7 days chart — 7 queries is fine, each hits the index ──
    days_labels = []
    days_totals = []
    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        total = db.session.query(
            func.coalesce(func.sum(Sale.total_amount), 0)
        ).filter(func.date(Sale.sale_date) == day).scalar()
        days_labels.append(day.strftime('%d %b'))
        days_totals.append(round(float(total), 2))

    # ── Top 5 selling products — single aggregate query, unchanged ──
    top_products = db.session.query(
        Product.name,
        func.sum(SaleItem.quantity).label('total_qty'),
        func.sum(SaleItem.quantity * SaleItem.unit_price).label('total_revenue')
    ).join(SaleItem, SaleItem.product_id == Product.id)\
     .group_by(Product.id)\
     .order_by(func.sum(SaleItem.quantity).desc())\
     .limit(5).all()

    # ── Margin table — only product data needed, no sales join ──────
    products = Product.query.order_by(Product.name).all()

    # ── Revenue & profit — pure SQL, no Python loops ─────────────────
    # FIX: Previously loaded ALL sales + ALL items into Python memory,
    # then looped over every item accessing item.product.cost_price
    # (which triggered a lazy query per item = massive N+1 problem).
    # Now: two aggregate SQL queries, zero objects loaded.

    total_sales, total_revenue = db.session.query(
        func.count(Sale.id),
        func.coalesce(func.sum(Sale.total_amount), 0)
    ).one()
    total_sales   = int(total_sales)
    total_revenue = round(float(total_revenue), 2)

    # Cost = SUM(sale_item.quantity * product.cost_price) via JOIN
    total_cost = db.session.query(
        func.coalesce(
            func.sum(SaleItem.quantity * Product.cost_price), 0
        )
    ).join(Product, SaleItem.product_id == Product.id).scalar()
    total_cost   = round(float(total_cost), 2)
    gross_profit = round(total_revenue - total_cost, 2)

    return render_template('reports/index.html',
        days_labels   = days_labels,
        days_totals   = days_totals,
        top_products  = top_products,
        products      = products,
        sales         = [],           # template should use aggregates, not raw sales list
        total_sales   = total_sales,
        total_revenue = total_revenue,
        total_products= Product.query.count(),
        gross_profit  = gross_profit,
    )