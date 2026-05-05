import yagmail
import os
from dotenv import load_dotenv

load_dotenv()

MAIL_USERNAME = os.getenv('EMAIL_USER')
MAIL_PASSWORD = os.getenv('EMAIL_PASS')
MANAGER_EMAIL = os.getenv('MANAGER_EMAIL')

def send_email(to, subject, html_body):
    try:
        yag = yagmail.SMTP(MAIL_USERNAME, MAIL_PASSWORD)
        yag.send(to=to, subject=subject, contents=html_body)
        return True
    except Exception as e:
        print(f"Email error: {e}")
        return False

def send_low_stock_alert(product_name, sku, qty, level, manager_email):
    subject = f"⚠️ Low Stock Alert: {product_name}"
    body = f"""
    <h2 style="color:#c0392b;">Low Stock Alert — SuperMart IMS</h2>
    <p>The following product needs immediate restocking:</p>
    <table border="1" cellpadding="8" cellspacing="0" style="border-collapse:collapse;">
      <tr style="background:#f8d7da;"><td><b>Product</b></td><td>{product_name}</td></tr>
      <tr><td><b>Barcode</b></td><td>{sku}</td></tr>
      <tr style="background:#f8d7da;"><td><b>Current Stock</b></td><td><b style="color:red">{qty} units</b></td></tr>
      <tr><td><b>Reorder Level</b></td><td>{level} units</td></tr>
    </table>
    <br>
    <p style="color:#c0392b;"><b>Please restock this item immediately!</b></p>
    """
    return send_email(manager_email, subject, body)

def send_out_of_stock_alert(product_name, sku, manager_email):
    subject = f"🚨 OUT OF STOCK: {product_name}"
    body = f"""
    <h2 style="color:#c0392b;">OUT OF STOCK — SuperMart IMS</h2>
    <p><b>{product_name}</b> (Barcode: {sku}) is completely out of stock!</p>
    <p style="color:red;"><b>Immediate action required.</b></p>
    """
    return send_email(manager_email, subject, body)

def send_sale_receipt(customer_email, items, total, sale_id):
    rows = "".join([
        f"<tr><td>{i['name']}</td><td>{i['qty']}</td><td>GHS {i['subtotal']:.2f}</td></tr>"
        for i in items])
    body = f"""
    <h2>Receipt - Sale #{sale_id}</h2>
    <table border="1" cellpadding="8" cellspacing="0">
      <tr><th>Item</th><th>Qty</th><th>Subtotal</th></tr>
      {rows}
      <tr><td colspan="2"><b>Total</b></td><td><b>GHS {total:.2f}</b></td></tr>
    </table>
    <p>Thank you for shopping with SuperMart!</p>
    """
    return send_email(customer_email, f"Your Receipt - Sale #{sale_id}", body)

def send_daily_report(manager_email, total_sales, total_revenue, low_stock_count):
    subject = "📊 Daily Sales Report - SuperMart IMS"
    body = f"""
    <h2>Daily Sales Summary</h2>
    <table border="1" cellpadding="8" cellspacing="0">
      <tr><td><b>Total Transactions</b></td><td>{total_sales}</td></tr>
      <tr><td><b>Total Revenue</b></td><td>GHS {total_revenue:.2f}</td></tr>
      <tr><td><b>Low Stock Items</b></td><td>{low_stock_count}</td></tr>
    </table>
    """
    return send_email(manager_email, subject, body)