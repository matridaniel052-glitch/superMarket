import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import os
from dotenv import load_dotenv

load_dotenv()

MAIL_SERVER = 'smtp.gmail.com'
MAIL_PORT = 587
MAIL_USERNAME = os.getenv('EMAIL_USER')
MAIL_PASSWORD = os.getenv('EMAIL_PASS')

def send_email(to, subject, html_body):
    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = MAIL_USERNAME
    msg['To'] = to
    msg.attach(MIMEText(html_body, 'html'))
    try:
        with smtplib.SMTP(MAIL_SERVER, MAIL_PORT) as s:
            s.starttls()
            s.login(MAIL_USERNAME, MAIL_PASSWORD)
            s.sendmail(MAIL_USERNAME, to, msg.as_string())
        return True
    except Exception as e:
        print(f"Email error: {e}")
        return False

def send_low_stock_alert(product_name, sku, qty, level, manager_email):
    subject = f"Low Stock Alert: {product_name}"
    body = f"""
    <h2 style="color:#c0392b;">Low Stock Alert</h2>
    <p>The following product needs restocking:</p>
    <table border="1" cellpadding="8" cellspacing="0">
      <tr><td><b>Product</b></td><td>{product_name}</td></tr>
      <tr><td><b>SKU</b></td><td>{sku}</td></tr>
      <tr><td><b>Current Stock</b></td><td>{qty} units</td></tr>
      <tr><td><b>Reorder Level</b></td><td>{level} units</td></tr>
    </table>
    <p>Please restock immediately.</p>
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
    <p>Thank you for shopping with us!</p>
    """
    return send_email(customer_email, f"Your Receipt - Sale #{sale_id}", body)

def send_daily_report(manager_email, total_sales, total_revenue, low_stock_count):
    subject = "Daily Sales Report - SuperMart IMS"
    body = f"""
    <h2>Daily Sales Summary</h2>
    <table border="1" cellpadding="8" cellspacing="0">
      <tr><td><b>Total Transactions</b></td><td>{total_sales}</td></tr>
      <tr><td><b>Total Revenue</b></td><td>GHS {total_revenue:.2f}</td></tr>
      <tr><td><b>Low Stock Items</b></td><td>{low_stock_count}</td></tr>
    </table>
    """
    return send_email(manager_email, subject, body)