"""
Main application entry point – 100% Railway + Local working
"""
from flask import Flask
from flask_cors import CORS
from config import DEBUG
from signup import signup_bp
from login import login_bp
from otp import otp_bp, configure_mail
from wheat_listing import wheat_listing
from machinery_rentals import machinery_rental
from pesticide_listing import pesticide_listing
from chat import chat_bp
from reminder_views import reminder_bp
from datetime import datetime
import os

def create_app():
    app = Flask(__name__)
    CORS(app, supports_credentials=True)
    app.secret_key = '123789'  # production mein env variable mein daal dena

    # Mail config
    configure_mail(app)

    # Register all blueprints
    app.register_blueprint(signup_bp, url_prefix='/signup')
    app.register_blueprint(login_bp, url_prefix='/login')
    app.register_blueprint(otp_bp, url_prefix='/otp')
    app.register_blueprint(wheat_listing, url_prefix='/wheat_listing')
    app.register_blueprint(machinery_rental, url_prefix='/machinery')
    app.register_blueprint(pesticide_listing, url_prefix='/pesticide_listing')
    app.register_blueprint(chat_bp, url_prefix='/chat')
    app.register_blueprint(reminder_bp, url_prefix='/reminder')

    # Reminder trigger route (cron-job ya manual test ke liye)
    @app.route("/trigger-reminder")
    def trigger_reminder():
        from daily_reminder_job import send_reminders
        send_reminders()
        return f"Reminder triggered successfully at {datetime.now()}!"

    # Health check – Railway ko pata chale app zinda hai
    @app.route("/")
    def home():
        return "Agri-Reminder Backend is LIVE & RUNNING on Railway!"

    return app


# ────────────────────────────────
# Yeh part Railway aur local dono ke liye perfect hai
# ────────────────────────────────
app = create_app()

# Railway ko ye 2 variables chahiye hoti hain (yeh daal dena zaroori hai)
application = app                    # Railway ke liye
wsgi_app = app.wsgi_app              # Extra safety ke liye

if __name__ == '__main__':
    # Sirf local mein chalega
    print("Running locally on http://127.0.0.1:5000")
    app.run(host="0.0.0.0", port=5000, debug=DEBUG)
else:
    # Railway / Render / Heroku / any production server
    print("Starting production server with Waitress on Railway...")
    from waitress import serve
    serve(app, host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))