# email_config.py
import os

EMAIL_CONFIG = {
    'EMAIL_BACKEND': 'django.core.mail.backends.smtp.EmailBackend',
    'EMAIL_HOST': 'smtp.gmail.com',
    'EMAIL_PORT': 587,
    'EMAIL_USE_TLS': True,
    'EMAIL_HOST_USER': os.environ.get('SUPERMART_EMAIL', 'your_gmail@gmail.com'),
    'EMAIL_HOST_PASSWORD': os.environ.get('SUPERMART_EMAIL_PASSWORD', 'your_app_password_here'),
    'DEFAULT_FROM_EMAIL': 'SuperMart IMS <your_gmail@gmail.com>',
    'ALERT_RECIPIENT_EMAIL': 'your_gmail@gmail.com',  # where alerts get sent to
}