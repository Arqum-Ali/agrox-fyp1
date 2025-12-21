"""
JWT authentication utilities for the application.
Provides token verification for protected routes.
"""
from flask import request, jsonify
from config import SECRET_KEY
import jwt


def verify_token():
    """
    Verify JWT token from Authorization header.
    
    Returns:
        int: User ID if token is valid, None otherwise
    """
    try:
        # Get token from Authorization header
        auth_header = request.headers.get('Authorization')
        
        if not auth_header:
            print("[AUTH] No Authorization header found")
            return None
        
        # Expected format: "Bearer <token>"
        parts = auth_header.split()
        
        if len(parts) != 2 or parts[0].lower() != 'bearer':
            print("[AUTH] Invalid Authorization header format")
            return None
        
        token = parts[1]
        
        # Decode and verify token
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
            user_id = payload.get('user_id')
            
            if not user_id:
                print("[AUTH] No user_id in token payload")
                return None
            
            print(f"[AUTH] Token verified for user_id: {user_id}")
            return user_id
            
        except jwt.ExpiredSignatureError:
            print("[AUTH] Token has expired")
            return None
        except jwt.InvalidTokenError as e:
            print(f"[AUTH] Invalid token: {str(e)}")
            return None
            
    except Exception as e:
        print(f"[AUTH ERROR] verify_token: {str(e)}")
        return None
