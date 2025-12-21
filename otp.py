from flask import Blueprint, request, jsonify
import random
import string
import hashlib
from werkzeug.security import generate_password_hash
from db import get_db_connection
import requests
from config import RESEND_API_KEY, RESEND_FROM_EMAIL

otp_bp = Blueprint('otp', __name__)

SECRET_KEY = "your-secure-secret-key"  # Replace with a strong, unique key

def generate_otp():
    return ''.join(random.choices(string.digits, k=4))

def generate_token(otp):
    token_input = f"{otp}:{SECRET_KEY}"
    return hashlib.sha256(token_input.encode()).hexdigest()

def send_otp_email(email, otp):
    """Send OTP using Resend API"""
    url = "https://api.resend.com/emails"
    payload = {
        "from": RESEND_FROM_EMAIL,
        "to": [email],
        "subject": "Your OTP Code",
        "html": f"<p>Your OTP code is: <strong>{otp}</strong></p>"
    }
    headers = {
        "Authorization": f"Bearer {RESEND_API_KEY}",
        "Content-Type": "application/json"
    }
    response = requests.post(url, json=payload, headers=headers)
    if response.status_code == 200:
        print(f"OTP sent to {email}")
        return True
    else:
        print(f"Resend error: {response.text}")
        return False

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
        if send_otp_email(email, otp):
            cursor.execute("UPDATE users SET email_otp = %s, created_at = NOW() WHERE email = %s", (otp, email))
            conn.commit()
            return jsonify({'message': 'OTP sent successfully', 'token': token}), 200
        else:
            return jsonify({'error': 'Failed to send OTP'}), 500
    except Exception as e:
        return jsonify({'error': f'Database error: {str(e)}'}), 500
    finally:
        cursor.close()
        conn.close()

@otp_bp.route('/verify_otp', methods=['POST'])
def verify_otp():
    data = request.get_json()
    email = data.get('email')
    otp = data.get('otp')
    token = data.get('token')
    if not email or not otp or not token:
        return jsonify({'error': 'Email, OTP, and token are required'}), 400
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT email_otp FROM users WHERE email = %s", (email,))
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
        hashed_password = generate_password_hash(new_password, method='pbkdf2:sha256')
        cursor.execute("UPDATE users SET password_hash = %s, email_otp = NULL, created_at = NULL WHERE email = %s", (hashed_password, email))
        conn.commit()
        return jsonify({'message': 'Password reset successfully'}), 200
    except Exception as e:
        return jsonify({'error': f'Database error: {str(e)}'}), 500
    finally:
        cursor.close()
        conn.close()