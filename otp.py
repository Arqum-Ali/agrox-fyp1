from flask import Blueprint, request, jsonify
from flask_mail import Mail, Message
import random
import string
import hashlib
import secrets
from werkzeug.security import generate_password_hash  # Added for password hashing
from config import MAIL_SERVER, MAIL_PORT, MAIL_USE_TLS, MAIL_USERNAME, MAIL_PASSWORD
from db import get_db_connection

otp_bp = Blueprint('otp', __name__)

# Secret key for token generation (should be stored securely, e.g., in config)
SECRET_KEY = "your-secure-secret-key"  # Replace with a strong, unique key

# Mail setup
mail = Mail()

def configure_mail(app):
    app.config['MAIL_SERVER'] = MAIL_SERVER
    app.config['MAIL_PORT'] = MAIL_PORT
    app.config['MAIL_USE_TLS'] = MAIL_USE_TLS
    app.config['MAIL_USERNAME'] = MAIL_USERNAME
    app.config['MAIL_PASSWORD'] = MAIL_PASSWORD
    mail.init_app(app)

# Function to generate OTP
def generate_otp():
    return ''.join(random.choices(string.digits, k=4))

# Function to generate a token based on OTP
def generate_token(otp):
    # Create a token by hashing OTP with a secret key
    token_input = f"{otp}:{SECRET_KEY}"
    return hashlib.sha256(token_input.encode()).hexdigest()

@otp_bp.route('/send_otp', methods=['POST'])
def send_otp():
    data = request.get_json()
    email = data.get('email')
    if not email:
        return jsonify({'error': 'Email is required'}), 400
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()
        if not user:
            return jsonify({'error': 'Email not registered'}), 400
        otp = generate_otp()
        token = generate_token(otp)
        msg = Message('Your OTP Code', sender=MAIL_USERNAME, recipients=[email])
        msg.body = f'Your OTP code is: {otp}'
        mail.send(msg)
        cursor.execute("UPDATE users SET email_otp = %s, created_at = NOW() WHERE email = %s", (otp, email))
        conn.commit()
        return jsonify({'message': 'OTP sent successfully', 'token': token}), 200
    except Exception as e:
        return jsonify({'error': f'Database error: {str(e)}'}), 500
    finally:
        cursor.close()
        conn.close()

@otp_bp.route('/verify_otp', methods=['POST'])
def verify_otp():
    data = request.get_json()
    otp = data.get('otp')
    email = data.get('email')
    token = data.get('token')
    if not otp or not email or not token:
        return jsonify({'error': 'OTP, email, and token are required'}), 400
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT email_otp, created_at FROM users WHERE email = %s ORDER BY created_at DESC LIMIT 1", (email,))
        record = cursor.fetchone()
        if not record:
            return jsonify({'error': 'No OTP found for this email'}), 400
        expected_token = generate_token(record['email_otp'])
        if token != expected_token or otp != record['email_otp']:
            return jsonify({'error': 'Invalid OTP or token'}), 400
        cursor.execute("UPDATE users SET created_at = NOW() WHERE email = %s", (email,))
        conn.commit()
        return jsonify({'message': 'OTP verified successfully'}), 200
    except Exception as e:
        return jsonify({'error': f'Error verifying OTP: {str(e)}'}), 500
    finally:
        cursor.close()
        conn.close()

@otp_bp.route('/reset_password', methods=['POST'])
def reset_password():
    data = request.get_json()
    email = data.get('email')
    new_password = data.get('new_password')
    if not email or not new_password:
        return jsonify({'error': 'Email and new password are required'}), 400
    if len(new_password) < 6:
        return jsonify({'error': 'Password must be at least 6 characters'}), 400
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT email_otp, created_at FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()
        if not user:
            return jsonify({'error': 'Email not registered'}), 400
        cursor.execute("SELECT COUNT(*) > 0 AS is_recent FROM users WHERE email = %s AND email_otp IS NOT NULL AND created_at > NOW() - INTERVAL 5 MINUTE", (email,))
        is_recent = cursor.fetchone()['is_recent']
        if not is_recent:
            return jsonify({'error': 'OTP verification expired. Please verify OTP again'}), 400
        # Hash the new password using werkzeug.security
        hashed_password = generate_password_hash(new_password, method='pbkdf2:sha256')
        cursor.execute("UPDATE users SET password_hash = %s, email_otp = NULL, created_at = NULL WHERE email = %s", (hashed_password, email))
        conn.commit()
        return jsonify({'message': 'Password reset successfully'}), 200
    except Exception as e:
        return jsonify({'error': f'Database error: {str(e)}'}), 500
    finally:
        cursor.close()
        conn.close()