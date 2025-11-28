"""
API routes for user login with JWT token generation and user details retrieval.
"""
from flask import Blueprint, request, jsonify
from werkzeug.security import check_password_hash
from db import get_db_connection
import jwt
import datetime
from flask import current_app

# Create a Blueprint for the login routes
login_bp = Blueprint('login', __name__)

# Secret key for JWT (in production, store this in environment variables)
SECRET_KEY = 'your-secret-key'  # Replace with a secure key

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
    if conn is None:
        return jsonify({
            'error': 'Database connection failed'
        }), 500

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
            'is_verified': user['is_verified']
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
    Retrieve user details (phone and email) based on JWT token.
    
    Expects:
    - Authorization header with Bearer JWT token
    
    Returns:
        JSON response with user's phone and email if authenticated
    """
    # Check for Authorization header
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({'error': 'Missing or invalid Authorization header'}), 401

    # Extract and verify JWT token
    token = auth_header.split(' ')[1]
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
        user_id = payload.get('user_id')
        if not user_id:
            return jsonify({'error': 'Invalid token payload'}), 401
    except jwt.ExpiredSignatureError:
        return jsonify({'error': 'Token expired'}), 401
    except jwt.InvalidTokenError:
        return jsonify({'error': 'Invalid token'}), 401

    # Connect to database
    conn = get_db_connection()
    if conn is None:
        return jsonify({
            'error': 'Database connection failed'
        }), 500

    cursor = conn.cursor()

    try:
        # Fetch user details
        cursor.execute("SELECT phone, email FROM users WHERE id = %s", (user_id,))
        user = cursor.fetchone()
        
        if not user:
            return jsonify({'error': 'User not found'}), 404

        return jsonify({
            'phone': user['phone'],
            'email': user['email'] or 'No email provided'
        }), 200

    except Exception as e:
        return jsonify({'error': f'Failed to fetch user details: {str(e)}'}), 500

    finally:
        cursor.close()
        conn.close()