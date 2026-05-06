"""
apply_indexes.py
────────────────
Run this ONCE after replacing your model files to add the new
database indexes to your existing MySQL database.

Usage (from your project root):
    python apply_indexes.py
"""

from app import create_app, db
from sqlalchemy import text

app = create_app()

INDEXES = [
    # products
    ("ix_product_name",     "CREATE INDEX IF NOT EXISTS ix_product_name     ON products (name)"),
    ("ix_product_category", "CREATE INDEX IF NOT EXISTS ix_product_category ON products (category_id)"),
    ("ix_product_quantity", "CREATE INDEX IF NOT EXISTS ix_product_quantity ON products (quantity)"),

    # sales
    ("ix_sale_date",         "CREATE INDEX IF NOT EXISTS ix_sale_date         ON sales (sale_date)"),
    ("ix_sale_cashier_date", "CREATE INDEX IF NOT EXISTS ix_sale_cashier_date ON sales (cashier_id, sale_date)"),

    # sale_items
    ("ix_saleitem_sale",    "CREATE INDEX IF NOT EXISTS ix_saleitem_sale    ON sale_items (sale_id)"),
    ("ix_saleitem_product", "CREATE INDEX IF NOT EXISTS ix_saleitem_product ON sale_items (product_id)"),

    # stock_logs
    ("ix_stocklog_product", "CREATE INDEX IF NOT EXISTS ix_stocklog_product ON stock_logs (product_id)"),
    ("ix_stocklog_created", "CREATE INDEX IF NOT EXISTS ix_stocklog_created ON stock_logs (created_at)"),
]

with app.app_context():
    with db.engine.connect() as conn:
        for name, sql in INDEXES:
            try:
                conn.execute(text(sql))
                print(f"  ✅  {name}")
            except Exception as e:
                print(f"  ⚠️  {name} — {e}")
        conn.commit()

print("\nDone. All indexes applied.")