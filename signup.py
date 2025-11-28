import random
import smtplib
from flask import Blueprint, request, jsonify
from werkzeug.security import generate_password_hash
from db import get_db_connection

signup_bp = Blueprint('signup', __name__)

def send_email_otp(recipient_email, otp_code):
    sender_email = 'arhumdoger@gmail.com' 
    sender_password = 'auyb ccul xphy wpwh'  # Use an app-specific password (keep secure)

    subject = "Your Email OTP Code"
    body = f"Your OTP code is: {otp_code}"
    message = f"Subject: {subject}\n\n{body}"

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(sender_email, sender_password)
            smtp.sendmail(sender_email, recipient_email, message)
    except Exception as e:
        print(f"Error sending email: {e}")
        raise

@signup_bp.route('', methods=['POST'])  # 👈 Changed from '/signup' to '/'
def signup():
    """
    Handle user registration and send OTP to email only.
    """
    data = request.get_json()
    full_name = data.get('full_name')
    phone = data.get('phone')
    email = data.get('email')
    password = data.get('password')

    if not full_name or not phone or not email or not password:
        return jsonify({'error': 'Missing required fields'}), 400

    if len(password) < 6:
        return jsonify({'error': 'Password must be at least  characters long'}), 400

    email_otp = str(random.randint(1000, 9999))  # 4-digit OTP

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Check for existing user
        cursor.execute("SELECT * FROM users WHERE phone = %s OR email = %s", (phone, email))
        existing_user = cursor.fetchone()

        if existing_user:
            return jsonify({'error': 'Phone or email already registered'}), 409

        password_hash = generate_password_hash(password)

        # Insert user
        cursor.execute(
            """
            INSERT INTO users (full_name, phone, email, password_hash, email_otp)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (full_name, phone, email, password_hash, email_otp)
        )

        conn.commit()
        user_id = cursor.lastrowid

        # Send email OTP
        send_email_otp(email, email_otp)

        return jsonify({
            'message': 'User registered successfully. OTP sent to email.',
            'user_id': user_id
        }), 201

    except Exception as e:
        conn.rollback()
        return jsonify({'error': f'Registration failed: {str(e)}'}), 500

    finally:
        cursor.close()
        conn.close()
        
@signup_bp.route('/verifyotp', methods=['POST'])
def verifyotp():
    """
    Verify OTP sent to the user's email.
    """
    data = request.get_json()
    otp_code = data.get('otp')  # OTP is required
    user_id = data.get('user_id')  # User ID is required to match with the OTP
    print("user_id-------------------------------------------------",user_id,"-------------otp_code",otp_code)
    if not otp_code or not user_id:
        return jsonify({'error': 'OTP and user ID are required'}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Step 1: Check if user exists by user_id
        cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
        user = cursor.fetchone()

        if not user:
            print(f"No user found with user_id: {user_id}")
            return jsonify({'error': 'User not found'}), 404

        # Step 2: Check if OTP matches
        if user['email_otp'] != otp_code:
            print(f"OTP does not match for user_id: {user_id}. Provided OTP: {otp_code}, Expected OTP: {user['email_otp']}")

            # Increment OTP attempts for this user
            cursor.execute("UPDATE users SET otp_attempts = otp_attempts + 1 WHERE id = %s", (user_id,))
            conn.commit()

            # Check the number of OTP attempts
            cursor.execute("SELECT otp_attempts FROM users WHERE id = %s", (user_id,))
            user_attempts = cursor.fetchone()
            if user_attempts and user_attempts['otp_attempts'] >= 2:
                print(f"Too many failed attempts. Deleting user with user_id: {user_id}")
                cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
                conn.commit()
                return jsonify({'error': 'Too many failed attempts. Please register again.'}), 400

            return jsonify({'error': 'OTP does not match'}), 401

        # If OTP is correct, proceed
        print(f"User found and OTP verified: {user['id']}")
        cursor.execute("UPDATE users SET email_otp = NULL, otp_attempts = 0 WHERE id = %s", (user_id,))
        conn.commit()

        return jsonify({'message': 'OTP verified successfully, registration complete!'}), 200

    except Exception as e:
        conn.rollback()
        return jsonify({'error': f'Error verifying OTP: {str(e)}'}), 500

    finally:
        cursor.close()
        conn.close()
