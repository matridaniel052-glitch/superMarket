from flask import Blueprint, render_template
from flask_login import login_required
from app.models import Sale, SaleItem, Product
from app import db
from datetime import datetime, timedelta
from sqlalchemy import func

reports = Blueprint('reports', __name__)

@reports.route('/reports')
@login_required
def index():
    today = datetime.utcnow().date()

    # Last 7 days chart data
    days_labels = []
    days_totals = []
    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        total = db.session.query(func.sum(Sale.total_amount)).filter(
            func.date(Sale.sale_date) == day
        ).scalar() or 0
        days_labels.append(day.strftime('%d %b'))
        days_totals.append(round(float(total), 2))

    # Top 5 selling products
    top_products = db.session.query(
        Product.name,
        func.sum(SaleItem.quantity).label('total_qty'),
        func.sum(SaleItem.quantity * SaleItem.unit_price).label('total_revenue')
    ).join(SaleItem, SaleItem.product_id == Product.id)\
     .group_by(Product.id)\
     .order_by(func.sum(SaleItem.quantity).desc())\
     .limit(5).all()

    # All products for margin table
    products = Product.query.order_by(Product.name).all()

    # All sales
    all_sales     = Sale.query.order_by(Sale.sale_date.desc()).all()
    total_sales   = len(all_sales)
    total_revenue = round(sum(s.grand_total for s in all_sales), 2)
    total_cost    = round(sum(
        item.quantity * item.product.cost_price
        for s in all_sales for item in s.items
    ), 2)
    gross_profit  = round(total_revenue - total_cost, 2)

    return render_template('reports/index.html',
        days_labels=days_labels,
        days_totals=days_totals,
        top_products=top_products,
        products=products,
        sales=all_sales,
        total_sales=total_sales,
        total_revenue=total_revenue,
        total_products=Product.query.count(),
        gross_profit=gross_profit
    )