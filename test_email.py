import os
from dotenv import load_dotenv
from email_service import send_low_stock_alert

load_dotenv()

manager_email = os.getenv('MANAGER_EMAIL')

result = send_low_stock_alert(
    product_name="Milo 400g",
    sku="SKU-001",
    qty=3,
    level=10,
    manager_email=manager_email
)

if result:
    print("SUCCESS - Check your email inbox now!")
else:
    print("FAILED - Check your .env credentials") 