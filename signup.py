import random
from flask import Blueprint, request, jsonify
from werkzeug.security import generate_password_hash
from db import get_db_connection
import requests  # Resend ke liye
from config import RESEND_API_KEY, RESEND_FROM_EMAIL

signup_bp = Blueprint('signup', __name__)

def send_email_otp(recipient_email, otp_code):
    url = "https://api.resend.com/emails"
    payload = {
        "from": RESEND_FROM_EMAIL,
        "to": [recipient_email],
        "subject": "Your Email OTP Code",
        "html": f"<p>Your OTP code is: {otp_code}</p>"
    }
    headers = {
        "Authorization": f"Bearer {RESEND_API_KEY}",
        "Content-Type": "application/json"
    }
    response = requests.post(url, json=payload, headers=headers)
    if response.status_code == 200:
        print(f"OTP sent to {recipient_email}")
        return True
    else:
        print(f"Resend error: {response.text}")
        return False

@signup_bp.route('', methods=['POST'])
def signup():
    data = request.get_json()
    full_name = data.get('full_name')
    phone = data.get('phone')
    email = data.get('email')
    password = data.get('password')

    if not full_name or not phone or not email or not password:
        return jsonify({'error': 'Missing required fields'}), 400

    if len(password) < 6:
        return jsonify({'error': 'Password must be at least 6 characters long'}), 400

    email_otp = str(random.randint(1000, 9999))  # 4-digit OTP

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT * FROM users WHERE phone = %s OR email = %s", (phone, email))
        existing_user = cursor.fetchone()

        if existing_user:
            return jsonify({'error': 'Phone or email already registered'}), 409

        password_hash = generate_password_hash(password)

        cursor.execute(
            """
            INSERT INTO users (full_name, phone, email, password_hash, email_otp)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (full_name, phone, email, password_hash, email_otp)
        )

        conn.commit()
        user_id = cursor.lastrowid

        if send_email_otp(email, email_otp):
            return jsonify({'message': 'User registered successfully. OTP sent to email.', 'user_id': user_id}), 200
        else:
            conn.rollback()
            return jsonify({'error': 'Failed to send OTP'}), 500
    except Exception as e:
        conn.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        conn.close()

@signup_bp.route('/verify_otp', methods=['POST'])
def verify_otp():
    data = request.get_json()
    user_id = data.get('user_id')
    otp_code = data.get('otp')
    if not otp_code or not user_id:
        return jsonify({'error': 'OTP and user ID are required'}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
        user = cursor.fetchone()

        if not user:
            return jsonify({'error': 'User not found'}), 404

        if user['email_otp'] != otp_code:
            cursor.execute("UPDATE users SET otp_attempts = otp_attempts + 1 WHERE id = %s", (user_id,))
            conn.commit()

            cursor.execute("SELECT otp_attempts FROM users WHERE id = %s", (user_id,))
            attempts = cursor.fetchone()['otp_attempts']
            if attempts >= 2:
                cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
                conn.commit()
                return jsonify({'error': 'Too many failed attempts. Please register again.'}), 400

            return jsonify({'error': 'OTP does not match'}), 401

        cursor.execute("UPDATE users SET email_otp = NULL, otp_attempts = 0 WHERE id = %s", (user_id,))
        conn.commit()

        return jsonify({'message': 'OTP verified successfully, registration complete!'}), 200

    except Exception as e:
        conn.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        conn.close()