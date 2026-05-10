# email_config.py
import os
from dotenv import load_dotenv

load_dotenv()

EMAIL_CONFIG = {
    'EMAIL_HOST': 'smtp.gmail.com',
    'EMAIL_PORT': 587,
    'EMAIL_USE_TLS': True,
    'EMAIL_HOST_USER': os.getenv('EMAIL_USER'),
    'EMAIL_HOST_PASSWORD': os.getenv('EMAIL_PASS'),
    'DEFAULT_FROM_EMAIL': f"Matri-Link IMS <{os.getenv('EMAIL_USER')}>",
    'ALERT_RECIPIENT_EMAIL': os.getenv('MANAGER_EMAIL'),
}