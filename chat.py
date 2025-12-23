"""
API routes for chat functionality with JWT authentication.
Handles chat rooms and messages between buyers and sellers.
"""
from flask import Blueprint, request, jsonify
from db import get_db_connection
from auth import verify_token
from datetime import datetime

# Create a Blueprint for chat routes
chat_bp = Blueprint('chat', __name__)

# ==================== CREATE OR GET CHAT ROOM ====================
@chat_bp.route('/rooms', methods=['POST'])
def create_or_get_room():
    """Create new chat room or get existing one"""
    try:
        user_id = verify_token()
        if not user_id:
            return jsonify({'error': 'Unauthorized'}), 401
       
        data = request.get_json()
        listing_id = data.get('listing_id')
        listing_type = data.get('listing_type', 'wheat')
       
        print(f"[CHAT] User {user_id} requesting chat for {listing_type} listing {listing_id}")
       
        if not listing_id:
            return jsonify({'error': 'listing_id is required'}), 400
       
        if listing_type not in ['wheat', 'pesticide', 'machinery']:
            return jsonify({'error': 'Invalid listing_type'}), 400
       
        try:
            listing_id = int(listing_id)
        except ValueError:
            return jsonify({'error': 'Invalid listing_id format'}), 400
       
        conn = get_db_connection()
        cursor = conn.cursor()
       
        table_map = {
            'wheat': 'wheat_listings',
            'pesticide': 'pesticides',
            'machinery': 'machinery_rentals'
        }
       
        table_name = table_map[listing_type]
       
        cursor.execute(f"""
            SELECT user_id FROM {table_name} WHERE id = %s
        """, (listing_id,))
       
        listing = cursor.fetchone()
       
        if not listing:
            cursor.close()
            conn.close()
            return jsonify({'error': f'{listing_type.capitalize()} listing not found'}), 404
       
        seller_id = listing['user_id']
        buyer_id = user_id
       
        if buyer_id == seller_id:
            cursor.close()
            conn.close()
            return jsonify({'error': 'Cannot chat with yourself'}), 400
       
        print(f"[CHAT] Buyer: {buyer_id}, Seller: {seller_id}")
       
        cursor.execute("""
            SELECT id FROM chat_rooms
            WHERE listing_id = %s
            AND listing_type = %s
            AND ((buyer_id = %s AND seller_id = %s)
                 OR (buyer_id = %s AND seller_id = %s))
        """, (listing_id, listing_type, buyer_id, seller_id, seller_id, buyer_id))
       
        existing_room = cursor.fetchone()
       
        if existing_room:
            room_id = existing_room['id']
            print(f"[CHAT] Existing room found: {room_id}")
            cursor.close()
            conn.close()
            return jsonify({'room_id': room_id, 'other_user_id': seller_id}), 200
       
        cursor.execute("""
            INSERT INTO chat_rooms (buyer_id, seller_id, listing_id, listing_type, updated_at)
            VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP)
            RETURNING id
        """, (buyer_id, seller_id, listing_id, listing_type))
        
        room_result = cursor.fetchone()
        room_id = room_result['id']
        
        conn.commit()
        print(f"[CHAT] New room created: {room_id}")
       
        cursor.close()
        conn.close()
       
        return jsonify({'room_id': room_id, 'other_user_id': seller_id}), 201
       
    except Exception as e:
        print(f"[CHAT ERROR] create_or_get_room: {str(e)}")
        if 'conn' in locals():
            conn.rollback()
            if 'cursor' in locals():
                cursor.close()
            conn.close()
        return jsonify({'error': str(e)}), 500

# ==================== GET USER'S CHAT ROOMS ====================
@chat_bp.route('/rooms', methods=['GET'])
def get_user_rooms():
    """Get all chat rooms for current user"""
    try:
        user_id = verify_token()
        if not user_id:
            return jsonify({'error': 'Unauthorized'}), 401
       
        conn = get_db_connection()
        cursor = conn.cursor()
       
        cursor.execute("""
            SELECT
                cr.id as room_id,
                cr.listing_id,
                cr.listing_type,
                cr.created_at,
                COALESCE(cr.updated_at, cr.created_at) as updated_at,
                CASE
                    WHEN cr.buyer_id = %s THEN cr.seller_id
                    ELSE cr.buyer_id
                END as other_user_id,
                u.full_name as other_user_name,
                'placeholder.jpg' as other_user_image,
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
            JOIN users u ON u.id = CASE
                WHEN cr.buyer_id = %s THEN cr.seller_id
                ELSE cr.buyer_id
            END
            WHERE cr.buyer_id = %s OR cr.seller_id = %s
            ORDER BY COALESCE(cr.updated_at, cr.created_at) DESC
        """, (user_id, user_id, user_id, user_id, user_id))
       
        rooms = cursor.fetchall()
        
        formatted_rooms = []
        for room in rooms:
            room_dict = dict(room)
            
            # Get listing details from appropriate table
            listing_type = room_dict['listing_type']
            listing_id = room_dict['listing_id']
            
            table_map = {
                'wheat': 'wheat_listings',
                'pesticide': 'pesticides',
                'machinery': 'machinery_rentals'
            }
            
            table_name = table_map.get(listing_type)
            
            listing_data = {}
            if table_name:
                try:
                    if listing_type == 'machinery':
                        cursor.execute(f"""
                            SELECT id, name, dailyRate, imagePath FROM {table_name} WHERE id = %s
                        """, (listing_id,))
                    elif listing_type == 'pesticide':
                        cursor.execute(f"""
                            SELECT id, name, price FROM {table_name} WHERE id = %s
                        """, (listing_id,))
                    elif listing_type == 'wheat':
                        cursor.execute(f"""
                            SELECT id, title, pricePerKg FROM {table_name} WHERE id = %s
                        """, (listing_id,))
                    
                    listing_result = cursor.fetchone()
                    if listing_result:
                        listing_data = dict(listing_result)
                except Exception as e:
                    print(f"[CHAT WARNING] Could not fetch listing data: {e}")
            
            room_dict['listing_data'] = listing_data
            formatted_rooms.append(room_dict)
       
        cursor.close()
        conn.close()
       
        return jsonify({'rooms': formatted_rooms}), 200
       
    except Exception as e:
        print(f"[CHAT ERROR] get_user_rooms: {str(e)}")
        if 'conn' in locals():
            if 'cursor' in locals():
                cursor.close()
            conn.close()
        return jsonify({'error': str(e)}), 500

# ==================== GET CHAT MESSAGES ====================
@chat_bp.route('/rooms/<int:room_id>/messages', methods=['GET'])
def get_messages(room_id):
    """Get all messages in a chat room"""
    try:
        user_id = verify_token()
        if not user_id:
            return jsonify({'error': 'Unauthorized'}), 401
       
        conn = get_db_connection()
        cursor = conn.cursor()
       
        cursor.execute("""
            SELECT buyer_id, seller_id FROM chat_rooms WHERE id = %s
        """, (room_id,))
       
        room = cursor.fetchone()
       
        if not room:
            cursor.close()
            conn.close()
            return jsonify({'error': 'Room not found'}), 404
       
        if user_id not in [room['buyer_id'], room['seller_id']]:
            cursor.close()
            conn.close()
            return jsonify({'error': 'Access denied'}), 403
       
        cursor.execute("""
            SELECT
                cm.id,
                cm.sender_id,
                cm.message,
                cm.is_read,
                cm.created_at,
                u.full_name as sender_name,
                'placeholder.jpg' as sender_image
            FROM chat_messages cm
            JOIN users u ON u.id = cm.sender_id
            WHERE cm.room_id = %s
            ORDER BY cm.created_at ASC
        """, (room_id,))
       
        messages = cursor.fetchall()
       
        cursor.execute("""
            UPDATE chat_messages
            SET is_read = TRUE
            WHERE room_id = %s AND sender_id != %s AND is_read = FALSE
        """, (room_id, user_id))
        
        cursor.execute("""
            UPDATE chat_rooms SET updated_at = CURRENT_TIMESTAMP WHERE id = %s
        """, (room_id,))
        
        conn.commit()
       
        cursor.close()
        conn.close()
       
        return jsonify({'messages': messages}), 200
       
    except Exception as e:
        print(f"[CHAT ERROR] get_messages: {str(e)}")
        if 'conn' in locals():
            conn.rollback()
            if 'cursor' in locals():
                cursor.close()
            conn.close()
        return jsonify({'error': str(e)}), 500

# ==================== SEND MESSAGE ====================
@chat_bp.route('/rooms/<int:room_id>/messages', methods=['POST'])
def send_message(room_id):
    """Send a message in chat room"""
    try:
        user_id = verify_token()
        if not user_id:
            return jsonify({'error': 'Unauthorized'}), 401
       
        data = request.get_json()
        message = data.get('message', '').strip()
       
        if not message:
            return jsonify({'error': 'Message cannot be empty'}), 400
       
        conn = get_db_connection()
        cursor = conn.cursor()
       
        cursor.execute("""
            SELECT buyer_id, seller_id FROM chat_rooms WHERE id = %s
        """, (room_id,))
       
        room = cursor.fetchone()
       
        if not room:
            cursor.close()
            conn.close()
            return jsonify({'error': 'Room not found'}), 404
       
        if user_id not in [room['buyer_id'], room['seller_id']]:
            cursor.close()
            conn.close()
            return jsonify({'error': 'Access denied'}), 403
       
        cursor.execute("""
            INSERT INTO chat_messages (room_id, sender_id, message)
            VALUES (%s, %s, %s)
            RETURNING id, sender_id, message, is_read, created_at
        """, (room_id, user_id, message))
        
        message_result = cursor.fetchone()
        
        cursor.execute("""
            UPDATE chat_rooms SET updated_at = CURRENT_TIMESTAMP WHERE id = %s
        """, (room_id,))
        
        conn.commit()
        
        new_message = {
            'id': message_result['id'],
            'sender_id': message_result['sender_id'],
            'message': message_result['message'],
            'is_read': message_result['is_read'],
            'created_at': message_result['created_at'].isoformat(),
            'sender_name': 'Current User',
            'sender_image': 'placeholder.jpg'
        }
        
        cursor.close()
        conn.close()
       
        return jsonify({'message': new_message}), 201
       
    except Exception as e:
        print(f"[CHAT ERROR] send_message: {str(e)}")
        if 'conn' in locals():
            conn.rollback()
            if 'cursor' in locals():
                cursor.close()
            conn.close()
        return jsonify({'error': str(e)}), 500

# ==================== DELETE CHAT ROOM ====================
@chat_bp.route('/rooms/<int:room_id>', methods=['DELETE'])
def delete_room(room_id):
    """Delete a chat room"""
    try:
        user_id = verify_token()
        if not user_id:
            return jsonify({'error': 'Unauthorized'}), 401
       
        conn = get_db_connection()
        cursor = conn.cursor()
       
        cursor.execute("""
            SELECT buyer_id, seller_id FROM chat_rooms WHERE id = %s
        """, (room_id,))
       
        room = cursor.fetchone()
       
        if not room:
            cursor.close()
            conn.close()
            return jsonify({'error': 'Room not found'}), 404
       
        if user_id not in [room['buyer_id'], room['seller_id']]:
            cursor.close()
            conn.close()
            return jsonify({'error': 'Access denied'}), 403
       
        cursor.execute("DELETE FROM chat_rooms WHERE id = %s", (room_id,))
        conn.commit()
       
        cursor.close()
        conn.close()
       
        return jsonify({'message': 'Chat deleted successfully'}), 200
       
    except Exception as e:
        print(f"[CHAT ERROR] delete_room: {str(e)}")
        if 'conn' in locals():
            conn.rollback()
            if 'cursor' in locals():
                cursor.close()
            conn.close()
        return jsonify({'error': str(e)}), 500

# ==================== GET UNREAD COUNT ====================
@chat_bp.route('/unread-count', methods=['GET'])
def get_unread_count():
    """Get total unread message count for the authenticated user"""
    try:
        user_id = verify_token()
        if not user_id:
            return jsonify({'error': 'Unauthorized'}), 401
       
        conn = get_db_connection()
        cursor = conn.cursor()
       
        cursor.execute("""
            SELECT COUNT(*) as unread_count
            FROM chat_messages cm
            JOIN chat_rooms cr ON cm.room_id = cr.id
            WHERE (cr.buyer_id = %s OR cr.seller_id = %s)
            AND cm.sender_id != %s
            AND cm.is_read = FALSE
        """, (user_id, user_id, user_id))
       
        result = cursor.fetchone()
        unread_count = result['unread_count'] if result else 0
       
        cursor.close()
        conn.close()
       
        return jsonify({'unread_count': unread_count}), 200
       
    except Exception as e:
        print(f"[CHAT ERROR] get_unread_count: {str(e)}")
        if 'conn' in locals():
            if 'cursor' in locals():
                cursor.close()
            conn.close()
        return jsonify({'error': str(e)}), 500
