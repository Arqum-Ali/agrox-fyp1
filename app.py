"""
Main application entry point.
"""
from flask import Flask, jsonify
from flask_cors import CORS
from config import DEBUG, CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, CLOUDINARY_API_SECRET
from db import init_db
from signup import signup_bp
from login import login_bp
from otp import otp_bp
from wheat_listing import wheat_listing
from machinery_rentals import machinery_rental
from pesticide_listing import pesticide_listing
from reminder_views import reminder_bp
from chat import chat_bp
from machinery_rentals_display import machinery_display
import cloudinary
import cloudinary.uploader
from daily_reminder_job import send_daily_reminders

def create_app():
    app = Flask(__name__)

    CORS(app, resources={r"/*": {
        "origins": "*",
        "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"],
        "expose_headers": ["Content-Type", "Authorization"],
        "supports_credentials": True
    }})

    app.secret_key = '123789'

    # Cloudinary init
    cloudinary.config(
        cloud_name=CLOUDINARY_CLOUD_NAME,
        api_key=CLOUDINARY_API_KEY,
        api_secret=CLOUDINARY_API_SECRET,
        secure=True
    )

    # Blueprints
    app.register_blueprint(signup_bp, url_prefix='/signup')
    app.register_blueprint(login_bp, url_prefix='/login')
    app.register_blueprint(otp_bp, url_prefix='/otp')
    app.register_blueprint(wheat_listing, url_prefix='/wheat_listing')
    app.register_blueprint(machinery_rental, url_prefix='/machinery')
    app.register_blueprint(pesticide_listing, url_prefix='/pesticide_listing')
    app.register_blueprint(reminder_bp, url_prefix="/reminder")
    app.register_blueprint(chat_bp, url_prefix='/chat')
    app.register_blueprint(machinery_display, url_prefix='')
    @app.route('/reminder/daily_job')
    def daily_reminder_route():
        send_daily_reminders()
        return "Daily reminders sent successfully!", 200

    @app.route('/')
    def home():
        return "Backend is running! Go to /machinery/rent_machinery to list machinery"

    return app
if __name__ == '__main__':
    import os
    port = int(os.getenv('PORT', 5000))  # Railway $PORT use karega
    if init_db():
        app = create_app()
        print("Starting server...")
        app.run(host="0.0.0.0", port=port, debug=DEBUG)
    else:
        print("Database connection failed!")