"""
Configuration settings – Railway + Local dono ke liye safe
"""
import os

# Database Configuration that works on both local and Railway
DEBUG = os.environ.get("DEBUG", "False").lower() == "true"

# Email Configuration (same rahega)
MAIL_SERVER = 'smtp.gmail.com'
MAIL_PORT = 587
MAIL_USE_TLS = True
MAIL_USERNAME = 'arhumdoger@gmail.com'
MAIL_PASSWORD = 'auyb ccul xphy wpwh'  # agar expire ho gaya to naya app password bana lena
MAIL_DEFAULT_SENDER = 'arhumdoger@gmail.com'

# Flask-Mail instance
from flask_mail import Mail
mail = Mail()

# Database config – sirf tab load hogi jab environment variables milenge
DB_USER = os.environ.get('DB_USER', 'root')
DB_PASSWORD = os.environ.get('DB_PASSWORD', '1234')
DB_HOST = os.environ.get('DB_HOST', 'localhost')
DB_NAME = os.environ.get('DB_NAME', 'agrox_fyp')