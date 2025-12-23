"""
API routes for chat functionality with JWT authentication.
Handles chat rooms and messages between buyers and sellers.
Optimized for production with connection pooling and timeout handling.
"""
from flask import Blueprint, request, jsonify
from db import get_db_connection
from auth import verify_token
from datetime import datetime
from functools import wraps
import signal

# Create a Blueprint for chat routes
chat_bp = Blueprint('chat', __name__)

def timeout_handler(signum, frame):
    raise TimeoutError("Request exceeded time limit")

def request_timeout(seconds=8):
    """Decorator to add timeout to request handlers"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Set signal alarm (Unix only - Flask handles this on other platforms)
            try:
                signal.signal(signal.SIGALRM, timeout_handler)
                signal.alarm(seconds)
            except:
                pass
            
            try:
                result = func(*args, **kwargs)
            finally:
                try:
                    signal.alarm(0)  # Disable the alarm
                except:
                    pass
            
            return result
        return wrapper
    return decorator

def safe_db_operation(query, params=None, fetch_one=False, fetch_all=False):
    """
    Safe database operation with automatic connection cleanup and error handling.
    Ensures connections are always returned to pool.
    """
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        if conn is None:
            return None, "Database connection failed"
        
        cursor = conn.cursor()
        
        if params:
            cursor.execute(query, params)
        else:
            cursor.execute(query)
        
        if fetch_one:
            result = cursor.fetchone()
        elif fetch_all:
            result = cursor.fetchall()
        else:
            result = None
            conn.commit()
        
        return result, None
    
    except Exception as e:
        if conn:
            try:
                conn.rollback()
            except:
                pass
        return None, str(e)
    
    finally:
        if cursor:
            try:
                cursor.close()
            except:
                pass
        if conn:
            try:
                conn.close()
            except:
                pass

# ==================== CREATE OR GET CHAT ROOM ====================
@chat_bp.route('/rooms', methods=['POST'])
@request_timeout(8)
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
       
        table_map = {
            'wheat': 'wheat_listings',
            'pesticide': 'pesticides',
            'machinery': 'machinery_rentals'
        }
       
        table_name = table_map[listing_type]
        
        query = f"SELECT user_id FROM {table_name} WHERE id = %s"
        listing, error = safe_db_operation(query, (listing_id,), fetch_one=True)
        
        if error:
            print(f"[CHAT ERROR] Database error fetching listing: {error}")
            return jsonify({'error': 'Database error'}), 500
        
        if not listing:
            return jsonify({'error': f'{listing_type.capitalize()} listing not found'}), 404
       
        seller_id = listing['user_id']
        buyer_id = user_id
       
        if buyer_id == seller_id:
            return jsonify({'error': 'Cannot chat with yourself'}), 400
       
        print(f"[CHAT] Buyer: {buyer_id}, Seller: {seller_id}")
       
        query = """
            SELECT id FROM chat_rooms
            WHERE listing_id = %s
            AND listing_type = %s
            AND ((buyer_id = %s AND seller_id = %s)
                 OR (buyer_id = %s AND seller_id = %s))
            LIMIT 1
        """
        existing_room, error = safe_db_operation(
            query, 
            (listing_id, listing_type, buyer_id, seller_id, seller_id, buyer_id),
            fetch_one=True
        )
        
        if error:
            print(f"[CHAT ERROR] Database error checking room: {error}")
            return jsonify({'error': 'Database error'}), 500
       
        if existing_room:
            room_id = existing_room['id']
            print(f"[CHAT] Existing room found: {room_id}")
            return jsonify({'room_id': room_id, 'other_user_id': seller_id}), 200
       
        conn = None
        cursor = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO chat_rooms (buyer_id, seller_id, listing_id, listing_type, updated_at)
                VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP)
                RETURNING id
            """, (buyer_id, seller_id, listing_id, listing_type))
            
            room_result = cursor.fetchone()
            room_id = room_result['id']
            
            conn.commit()
            print(f"[CHAT] New room created: {room_id}")
            
            return jsonify({'room_id': room_id, 'other_user_id': seller_id}), 201
        
        except Exception as e:
            if conn:
                try:
                    conn.rollback()
                except:
                    pass
            print(f"[CHAT ERROR] Failed to create room: {str(e)}")
            return jsonify({'error': 'Failed to create room'}), 500
        
        finally:
            if cursor:
                try:
                    cursor.close()
                except:
                    pass
            if conn:
                try:
                    conn.close()
                except:
                    pass
       
    except TimeoutError:
        return jsonify({'error': 'Request timeout'}), 504
    except Exception as e:
        print(f"[CHAT ERROR] create_or_get_room: {str(e)}")
        return jsonify({'error': 'Server error'}), 500

# ==================== GET USER'S CHAT ROOMS ====================
@chat_bp.route('/rooms', methods=['GET'])
@request_timeout(8)
def get_user_rooms():
    """Get all chat rooms for current user"""
    try:
        user_id = verify_token()
        if not user_id:
            return jsonify({'error': 'Unauthorized'}), 401
       
        query = """
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
            LIMIT 100
        """
        
        rooms, error = safe_db_operation(
            query,
            (user_id, user_id, user_id, user_id, user_id),
            fetch_all=True
        )
        
        if error:
            print(f"[CHAT ERROR] Database error fetching rooms: {error}")
            return jsonify({'error': 'Database error'}), 500
        
        if not rooms:
            return jsonify({'rooms': []}), 200
        
        formatted_rooms = []
        conn = None
        cursor = None
        
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            table_map = {
                'wheat': ('wheat_listings', 'title as name, price_per_kg as price'),
                'pesticide': ('pesticides', 'name, price'),
                'machinery': ('machinery_rentals', 'name, daily_rate as price, image_path')
            }
            
            for room in rooms:
                room_dict = dict(room)
                listing_type = room_dict['listing_type']
                listing_id = room_dict['listing_id']
                
                listing_data = {}
                if listing_type in table_map:
                    table_name, fields = table_map[listing_type]
                    try:
                        cursor.execute(f"SELECT {fields} FROM {table_name} WHERE id = %s LIMIT 1", (listing_id,))
                        listing_result = cursor.fetchone()
                        if listing_result:
                            listing_data = dict(listing_result)
                    except Exception as e:
                        print(f"[CHAT WARNING] Could not fetch listing data: {e}")
                
                room_dict['listing_data'] = listing_data
                formatted_rooms.append(room_dict)
            
            return jsonify({'rooms': formatted_rooms}), 200
        
        except Exception as e:
            print(f"[CHAT ERROR] Error fetching listing data: {str(e)}")
            return jsonify({'rooms': formatted_rooms}), 200
        
        finally:
            if cursor:
                try:
                    cursor.close()
                except:
                    pass
            if conn:
                try:
                    conn.close()
                except:
                    pass
       
    except TimeoutError:
        return jsonify({'error': 'Request timeout'}), 504
    except Exception as e:
        print(f"[CHAT ERROR] get_user_rooms: {str(e)}")
        return jsonify({'error': 'Server error'}), 500

# ==================== GET CHAT MESSAGES ====================
@chat_bp.route('/rooms/<int:room_id>/messages', methods=['GET'])
@request_timeout(8)
def get_messages(room_id):
    """Get all messages in a chat room"""
    try:
        user_id = verify_token()
        if not user_id:
            return jsonify({'error': 'Unauthorized'}), 401
        
        query = """
            SELECT buyer_id, seller_id FROM chat_rooms WHERE id = %s LIMIT 1
        """
        room, error = safe_db_operation(query, (room_id,), fetch_one=True)
        
        if error:
            print(f"[CHAT ERROR] Database error verifying room: {error}")
            return jsonify({'error': 'Database error'}), 500
       
        if not room:
            return jsonify({'error': 'Room not found'}), 404
       
        if user_id not in [room['buyer_id'], room['seller_id']]:
            return jsonify({'error': 'Access denied'}), 403
       
        query = """
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
            LIMIT 1000
        """
        
        messages, error = safe_db_operation(query, (room_id,), fetch_all=True)
        
        if error:
            print(f"[CHAT ERROR] Database error fetching messages: {error}")
            return jsonify({'error': 'Database error'}), 500
        
        messages_list = [dict(msg) for msg in messages] if messages else []
        print(f"[CHAT] Retrieved {len(messages_list)} messages for room {room_id}")
       
        conn = None
        cursor = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                UPDATE chat_messages
                SET is_read = TRUE
                WHERE room_id = %s AND sender_id != %s AND is_read = FALSE
            """, (room_id, user_id))
            
            cursor.execute("""
                UPDATE chat_rooms SET updated_at = CURRENT_TIMESTAMP WHERE id = %s
            """, (room_id,))
            
            conn.commit()
        except Exception as e:
            print(f"[CHAT WARNING] Could not update read status: {e}")
            if conn:
                try:
                    conn.rollback()
                except:
                    pass
        finally:
            if cursor:
                try:
                    cursor.close()
                except:
                    pass
            if conn:
                try:
                    conn.close()
                except:
                    pass
       
        return jsonify({'messages': messages_list}), 200
       
    except TimeoutError:
        return jsonify({'error': 'Request timeout'}), 504
    except Exception as e:
        print(f"[CHAT ERROR] get_messages: {str(e)}")
        return jsonify({'error': 'Server error'}), 500

# ==================== SEND MESSAGE ====================
@chat_bp.route('/rooms/<int:room_id>/messages', methods=['POST'])
@request_timeout(8)
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
       
        query = "SELECT buyer_id, seller_id FROM chat_rooms WHERE id = %s LIMIT 1"
        room, error = safe_db_operation(query, (room_id,), fetch_one=True)
        
        if error:
            print(f"[CHAT ERROR] Database error verifying room: {error}")
            return jsonify({'error': 'Database error'}), 500
       
        if not room:
            return jsonify({'error': 'Room not found'}), 404
       
        if user_id not in [room['buyer_id'], room['seller_id']]:
            return jsonify({'error': 'Access denied'}), 403
       
        conn = None
        cursor = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
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
            
            print(f"[CHAT] Message sent successfully to room {room_id}")
            
            return jsonify({'message': new_message}), 201
        
        except Exception as e:
            if conn:
                try:
                    conn.rollback()
                except:
                    pass
            print(f"[CHAT ERROR] Failed to send message: {str(e)}")
            return jsonify({'error': 'Failed to send message'}), 500
        
        finally:
            if cursor:
                try:
                    cursor.close()
                except:
                    pass
            if conn:
                try:
                    conn.close()
                except:
                    pass
       
    except TimeoutError:
        return jsonify({'error': 'Request timeout'}), 504
    except Exception as e:
        print(f"[CHAT ERROR] send_message: {str(e)}")
        return jsonify({'error': 'Server error'}), 500

# ==================== DELETE CHAT ROOM ====================
@chat_bp.route('/rooms/<int:room_id>', methods=['DELETE'])
@request_timeout(8)
def delete_room(room_id):
    """Delete a chat room"""
    try:
        user_id = verify_token()
        if not user_id:
            return jsonify({'error': 'Unauthorized'}), 401
       
        query = "SELECT buyer_id, seller_id FROM chat_rooms WHERE id = %s LIMIT 1"
        room, error = safe_db_operation(query, (room_id,), fetch_one=True)
        
        if error:
            print(f"[CHAT ERROR] Database error verifying room: {error}")
            return jsonify({'error': 'Database error'}), 500
       
        if not room:
            return jsonify({'error': 'Room not found'}), 404
       
        if user_id not in [room['buyer_id'], room['seller_id']]:
            return jsonify({'error': 'Access denied'}), 403
       
        conn = None
        cursor = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute("DELETE FROM chat_rooms WHERE id = %s", (room_id,))
            conn.commit()
            
            return jsonify({'message': 'Chat deleted successfully'}), 200
        
        except Exception as e:
            if conn:
                try:
                    conn.rollback()
                except:
                    pass
            print(f"[CHAT ERROR] Failed to delete room: {str(e)}")
            return jsonify({'error': 'Failed to delete room'}), 500
        
        finally:
            if cursor:
                try:
                    cursor.close()
                except:
                    pass
            if conn:
                try:
                    conn.close()
                except:
                    pass
       
    except TimeoutError:
        return jsonify({'error': 'Request timeout'}), 504
    except Exception as e:
        print(f"[CHAT ERROR] delete_room: {str(e)}")
        return jsonify({'error': 'Server error'}), 500

# ==================== GET UNREAD COUNT ====================
@chat_bp.route('/unread-count', methods=['GET'])
@request_timeout(8)
def get_unread_count():
    """Get total unread message count for the authenticated user"""
    try:
        user_id = verify_token()
        if not user_id:
            return jsonify({'error': 'Unauthorized'}), 401
       
        query = """
            SELECT COUNT(*) as unread_count
            FROM chat_messages cm
            JOIN chat_rooms cr ON cm.room_id = cr.id
            WHERE (cr.buyer_id = %s OR cr.seller_id = %s)
            AND cm.sender_id != %s
            AND cm.is_read = FALSE
        """
        
        result, error = safe_db_operation(query, (user_id, user_id, user_id), fetch_one=True)
        
        if error:
            print(f"[CHAT ERROR] Database error fetching unread count: {error}")
            return jsonify({'unread_count': 0}), 200
        
        unread_count = result['unread_count'] if result else 0
       
        return jsonify({'unread_count': unread_count}), 200
       
    except TimeoutError:
        return jsonify({'error': 'Request timeout'}), 504
    except Exception as e:
        print(f"[CHAT ERROR] get_unread_count: {str(e)}")
        return jsonify({'unread_count': 0}), 200
