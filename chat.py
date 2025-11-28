"""
API routes for chat functionality with JWT authentication.
Handles chat rooms and messages between buyers and sellers.
"""
from flask import Blueprint, request, jsonify
from db import get_db_connection
import jwt
from datetime import datetime

# Create a Blueprint for chat routes
chat_bp = Blueprint('chat', __name__)

# Secret key for JWT (must match login.py)
SECRET_KEY = 'your-secret-key'

def verify_token():
    """
    Verify JWT token from Authorization header.
    Returns user_id if valid, None otherwise.
    """
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return None
    
    token = auth_header.split(' ')[1]
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
        return payload.get('user_id')
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None

@chat_bp.route('/rooms', methods=['POST'])
def create_or_get_room():
    """
    Create a new chat room or get existing one between two users for a listing.
    
    Expects JSON with:
    - listing_id: The wheat listing ID
    
    Returns:
        JSON response with room_id
    """
    try:
        user_id = verify_token()
        print(f"[v0] Token verified, user_id: {user_id}")
        
        if not user_id:
            return jsonify({'error': 'Unauthorized'}), 401
        
        data = request.get_json()
        listing_id = data.get('listing_id')
        seller_id = data.get('seller_id')   # 👈 frontend se aa rahi value
        buyer_id = user_id  
        
        print(f"[v0] Request data - listing_id: {listing_id}")
        
        if not listing_id:
            return jsonify({'error': 'Missing listing_id'}), 400
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        print("[v0] Database connection established")
        
        cursor.execute("""
            SELECT user_id FROM wheat_listings WHERE id = %s
        """, (listing_id,))
        
        listing = cursor.fetchone()
        
        if not listing:
            cursor.close()
            conn.close()
            return jsonify({'error': 'Listing not found'}), 404
        
        seller_id = listing['user_id']
        buyer_id = user_id
        
        print(f"[v0] Listing found - seller_id: {seller_id}, buyer_id: {buyer_id}")
        
        # Prevent user from chatting with themselves
        if buyer_id == seller_id:
            cursor.close()
            conn.close()
            return jsonify({'error': 'Cannot chat with yourself'}), 400
        
        # Check if room already exists between these users for this listing
        cursor.execute("""
            SELECT id FROM chat_rooms 
            WHERE listing_id = %s 
            AND buyer_id = %s 
            AND seller_id = %s
        """, (listing_id, buyer_id, seller_id))
        
        existing_room = cursor.fetchone()
        print(f"[v0] Existing room check: {existing_room}")
        
        if existing_room:
            room_id = existing_room['id']
            print(f"[v0] Found existing room: {room_id}")
            cursor.close()
            conn.close()
            return jsonify({'room_id': room_id}), 200
        
        print("[v0] Creating new room")
        cursor.execute("""
            INSERT INTO chat_rooms (buyer_id, seller_id, listing_id)
            VALUES (%s, %s, %s)
        """, (buyer_id, seller_id, listing_id))
        conn.commit()
        
        room_id = cursor.lastrowid
        print(f"[v0] Created new room with id: {room_id}")
        
        cursor.close()
        conn.close()
        
        return jsonify({'room_id': room_id}), 201
        
    except Exception as e:
        print(f"[v0] ERROR in create_or_get_room: {str(e)}")
        print(f"[v0] Error type: {type(e).__name__}")
        import traceback
        print(f"[v0] Traceback: {traceback.format_exc()}")
        
        if 'conn' in locals():
            conn.rollback()
            if 'cursor' in locals():
                cursor.close()
            conn.close()
        
        return jsonify({'error': f'Failed to create room: {str(e)}'}), 500

@chat_bp.route('/rooms', methods=['GET'])
def get_user_rooms():
    """
    Get all chat rooms for the authenticated user.
    
    Returns:
        JSON response with list of rooms including other user's name and listing title
    """
    user_id = verify_token()
    if not user_id:
        return jsonify({'error': 'Unauthorized'}), 401
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            SELECT 
                cr.id,
                cr.buyer_id,
                cr.seller_id,
                cr.listing_id,
                cr.created_at,
                cr.updated_at,
                wl.title as listing_title,
                wl.price_per_kg,
                CASE 
                    WHEN cr.buyer_id = %s THEN u_seller.full_name
                    ELSE u_buyer.full_name
                END as other_user_name,
                CASE 
                    WHEN cr.buyer_id = %s THEN cr.seller_id
                    ELSE cr.buyer_id
                END as other_user_id,
                (SELECT message FROM chat_messages 
                 WHERE room_id = cr.id 
                 ORDER BY created_at DESC LIMIT 1) as last_message,
                (SELECT created_at FROM chat_messages 
                 WHERE room_id = cr.id 
                 ORDER BY created_at DESC LIMIT 1) as last_message_time,
                (SELECT COUNT(*) FROM chat_messages 
                 WHERE room_id = cr.id 
                 AND sender_id != %s 
                 AND is_read = FALSE) as unread_count
            FROM chat_rooms cr
            JOIN wheat_listings wl ON cr.listing_id = wl.id
            JOIN users u_buyer ON cr.buyer_id = u_buyer.id
            JOIN users u_seller ON cr.seller_id = u_seller.id
            WHERE cr.buyer_id = %s OR cr.seller_id = %s
            ORDER BY cr.updated_at DESC
        """, (user_id, user_id, user_id, user_id, user_id))
        
        rooms = cursor.fetchall()
        return jsonify(rooms), 200
        
    except Exception as e:
        return jsonify({'error': f'Failed to fetch rooms: {str(e)}'}), 500
    finally:
        cursor.close()
        conn.close()

@chat_bp.route('/rooms/<int:room_id>/messages', methods=['GET'])
def get_messages(room_id):
    """
    Get all messages for a specific chat room.
    
    Returns:
        JSON response with list of messages
    """
    user_id = verify_token()
    if not user_id:
        return jsonify({'error': 'Unauthorized'}), 401
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Verify user is part of this room
        cursor.execute("""
            SELECT * FROM chat_rooms 
            WHERE id = %s AND (buyer_id = %s OR seller_id = %s)
        """, (room_id, user_id, user_id))
        
        room = cursor.fetchone()
        if not room:
            return jsonify({'error': 'Room not found or unauthorized'}), 404
        
        # Mark messages as read
        cursor.execute("""
            UPDATE chat_messages 
            SET is_read = TRUE 
            WHERE room_id = %s AND sender_id != %s
        """, (room_id, user_id))
        conn.commit()
        
        # Get all messages
        cursor.execute("""
            SELECT 
                cm.id,
                cm.room_id,
                cm.sender_id,
                cm.message,
                cm.created_at,
                cm.is_read,
                u.full_name as sender_name
            FROM chat_messages cm
            JOIN users u ON cm.sender_id = u.id
            WHERE cm.room_id = %s
            ORDER BY cm.created_at ASC
        """, (room_id,))
        
        messages = cursor.fetchall()
        return jsonify(messages), 200
        
    except Exception as e:
        return jsonify({'error': f'Failed to fetch messages: {str(e)}'}), 500
    finally:
        cursor.close()
        conn.close()

@chat_bp.route('/rooms/<int:room_id>/messages', methods=['POST'])
def send_message(room_id):
    """
    Send a message in a chat room.
    
    Expects JSON with:
    - message: The message text
    
    Returns:
        JSON response with message details
    """
    user_id = verify_token()
    if not user_id:
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.get_json()
    message = data.get('message')
    
    if not message or not message.strip():
        return jsonify({'error': 'Message cannot be empty'}), 400
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Verify user is part of this room
        cursor.execute("""
            SELECT * FROM chat_rooms 
            WHERE id = %s AND (buyer_id = %s OR seller_id = %s)
        """, (room_id, user_id, user_id))
        
        room = cursor.fetchone()
        if not room:
            return jsonify({'error': 'Room not found or unauthorized'}), 404
        
        # Insert message
        cursor.execute("""
            INSERT INTO chat_messages (room_id, sender_id, message)
            VALUES (%s, %s, %s)
        """, (room_id, user_id, message.strip()))
        
        # Update room's updated_at timestamp
        cursor.execute("""
            UPDATE chat_rooms 
            SET updated_at = CURRENT_TIMESTAMP 
            WHERE id = %s
        """, (room_id,))
        
        conn.commit()
        message_id = cursor.lastrowid
        
        # Get the created message
        cursor.execute("""
            SELECT 
                cm.id,
                cm.room_id,
                cm.sender_id,
                cm.message,
                cm.created_at,
                cm.is_read,
                u.full_name as sender_name
            FROM chat_messages cm
            JOIN users u ON cm.sender_id = u.id
            WHERE cm.id = %s
        """, (message_id,))
        
        created_message = cursor.fetchone()
        return jsonify(created_message), 201
        
    except Exception as e:
        conn.rollback()
        return jsonify({'error': f'Failed to send message: {str(e)}'}), 500
    finally:
        cursor.close()
        conn.close()

@chat_bp.route('/unread-count', methods=['GET'])
def get_unread_count():
    """
    Get total unread message count for the authenticated user.
    
    Returns:
        JSON response with unread count
    """
    user_id = verify_token()
    if not user_id:
        return jsonify({'error': 'Unauthorized'}), 401
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            SELECT COUNT(*) as unread_count
            FROM chat_messages cm
            JOIN chat_rooms cr ON cm.room_id = cr.id
            WHERE (cr.buyer_id = %s OR cr.seller_id = %s)
            AND cm.sender_id != %s
            AND cm.is_read = FALSE
        """, (user_id, user_id, user_id))
        
        result = cursor.fetchone()
        return jsonify({'unread_count': result['unread_count']}), 200
        
    except Exception as e:
        return jsonify({'error': f'Failed to fetch unread count: {str(e)}'}), 500
    finally:
        cursor.close()
        conn.close()

@chat_bp.route('/debug/check-tables', methods=['GET'])
def check_tables():
    """
    Debug endpoint to check if chat tables exist in database.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check if chat_rooms table exists
        cursor.execute("SHOW TABLES LIKE 'chat_rooms'")
        chat_rooms_exists = cursor.fetchone() is not None
        
        # Check if chat_messages table exists
        cursor.execute("SHOW TABLES LIKE 'chat_messages'")
        chat_messages_exists = cursor.fetchone() is not None
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'chat_rooms_table_exists': chat_rooms_exists,
            'chat_messages_table_exists': chat_messages_exists,
            'message': 'If both are False, please run the SQL script: scripts/create_chat_tables.sql'
        }), 200
        
    except Exception as e:
        return jsonify({'error': f'Database check failed: {str(e)}'}), 500
