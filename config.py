"""
Configuration settings for the application.
"""

# Database Configuration
DB_USER = 'root'
DB_PASSWORD = '1234'
DB_HOST = 'localhost'
DB_NAME = 'agrox_fyp'

# App Settings
DEBUG = True

# Email Configuration
MAIL_SERVER = 'smtp.gmail.com'
MAIL_PORT = 587
MAIL_USE_TLS = True
MAIL_USERNAME = 'arhumdoger@gmail.com'
MAIL_PASSWORD = 'auyb ccul xphy wpwh'  # ← Agar nahi chal raha to naya App Password daal dena
MAIL_DEFAULT_SENDER = 'arhumdoger@gmail.com'

# Flask-Mail Instance
from flask_mail import Mail
mail = Mail()