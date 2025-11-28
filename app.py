"""
Main application entry point.
"""
from flask import Flask
from flask_cors import CORS
from config import DEBUG
# from db import init_db
from signup import signup_bp
from login import login_bp
from otp import otp_bp, configure_mail
from wheat_listing import wheat_listing
from machinery_rentals import machinery_rental
from pesticide_listing import pesticide_listing
from chat import chat_bp
from reminder_views import reminder_bp  # Import the blueprint
from datetime import datetime  # sirf datetime import rakha

def create_app():
    app = Flask(__name__)
    CORS(app, supports_credentials=True)
    app.secret_key = '123789'
    configure_mail(app)

    # Register blueprints
    app.register_blueprint(signup_bp, url_prefix='/signup')
    app.register_blueprint(login_bp, url_prefix='/login')
    app.register_blueprint(otp_bp, url_prefix='/otp')
    app.register_blueprint(wheat_listing, url_prefix='/wheat_listing')
    app.register_blueprint(machinery_rental, url_prefix='/machinery')
    app.register_blueprint(pesticide_listing, url_prefix='/pesticide_listing')
    app.register_blueprint(chat_bp, url_prefix='/chat')
    app.register_blueprint(reminder_bp, url_prefix='/reminder')

    # ←←← YE FIX HAI – IMPORT ANDAR HI KIYA (CIRCULAR IMPORT KHATAM!)
    @app.route("/trigger-reminder")
    def trigger_reminder():
        from daily_reminder_job import send_reminders  # ab yahan import kar rahe hain
        send_reminders()
        return f"Reminder triggered successfully at {datetime.now()}!"

    return app

if __name__ == '__main__':
    # Local pe chalega, Railway pe nahi
    app.run(host="0.0.0.0", port=5000, debug=DEBUG)
else:
    # Railway pe ye chalega
    from waitress import serve
    serve(app, host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))