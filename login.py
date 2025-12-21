"""
API routes for user login with JWT token generation and user details retrieval.
"""
from flask import Blueprint, request, jsonify
from werkzeug.security import check_password_hash
from db import get_db_connection
from config import SECRET_KEY
import jwt
import datetime
from flask import current_app

# Create a Blueprint for the login routes
login_bp = Blueprint('login', __name__)

@login_bp.route('', methods=['POST'])
def login():
    """
    Handle user login and generate JWT token.
    
    Expects JSON with:
    - phone: User's phone number
    - password: User's password
    
    Returns:
        JSON response with login status, user data, and JWT token if successful
    """
    # Get and validate request data
    data = request.get_json()
    phone = data.get('phone')
    password = data.get('password')

    # Check if all required fields are provided
    if not phone or not password:
        return jsonify({
            'error': 'Missing required fields'
        }), 400

    # Connect to database
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Check if user exists with the provided phone number
        cursor.execute("SELECT * FROM users WHERE phone = %s", (phone,))
        user = cursor.fetchone()
        
        if not user:
            return jsonify({
                'error': 'Invalid phone number'
            }), 401

        # Verify password
        if not check_password_hash(user['password_hash'], password):
            return jsonify({
                'error': 'Invalid password'
            }), 401

        # Generate JWT token
        token = jwt.encode({
            'user_id': user['id'],
            'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=24)  # Token expires in 24 hours
        }, SECRET_KEY, algorithm='HS256')

        # Return user data and token (excluding password hash for security)
        user_data = {
            'id': user['id'],
            'full_name': user['full_name'],
            'phone': user['phone'],
        }

        return jsonify({
            'message': 'Login successful',
            'user': user_data,
            'token': token
        }), 200
        
    except Exception as e:
        # Handle any errors
        return jsonify({
            'error': f'Login failed: {str(e)}'
        }), 500
        
    finally:
        # Close database connection
        cursor.close()
        conn.close()

@login_bp.route('/user_details', methods=['GET'])
def get_user_details():
    """
    Retrieve user details (full_name, phone, email) based on JWT token.
    
    Expects:
    - Authorization header with Bearer JWT token
    
    Returns:
        JSON response with user's full_name, phone, and email if authenticated
    """
    conn = None
    cursor = None
    
    try:
        print("[USER DETAILS] Request received")
        
        # Check for Authorization header
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            print("[USER DETAILS] Error: Missing or invalid Authorization header")
            return jsonify({'error': 'Missing or invalid Authorization header'}), 401

        # Extract and verify JWT token
        token = auth_header.split(' ')[1]
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
            user_id = payload.get('user_id')
            if not user_id:
                print("[USER DETAILS] Error: Invalid token payload")
                return jsonify({'error': 'Invalid token payload'}), 401
            print(f"[USER DETAILS] Token verified for user_id: {user_id}")
        except jwt.ExpiredSignatureError:
            print("[USER DETAILS] Error: Token expired")
            return jsonify({'error': 'Token expired'}), 401
        except jwt.InvalidTokenError as e:
            print(f"[USER DETAILS] Error: Invalid token - {str(e)}")
            return jsonify({'error': 'Invalid token'}), 401

        # Connect to database
        conn = get_db_connection()
        cursor = conn.cursor()

        # Fetch user details including full_name
        cursor.execute("SELECT full_name, phone, email FROM users WHERE id = %s", (user_id,))
        user = cursor.fetchone()
        
        if not user:
            print(f"[USER DETAILS] Error: User not found for user_id: {user_id}")
            return jsonify({'error': 'User not found'}), 404

        user_name = user['full_name'] or 'User'
        print(f"[USER DETAILS] Found user: {user_name} (ID: {user_id})")

        return jsonify({
            'full_name': user_name,
            'phone': user['phone'],
            'email': user['email'] or 'No email provided'
        }), 200

    except Exception as e:
        print(f"[USER DETAILS] Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Failed to fetch user details: {str(e)}'}), 500

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
        print("[USER DETAILS] Database connection closed")