from flask import Blueprint, request, jsonify
from db import get_db_connection
from config import SECRET_KEY, BASE_URL
import os
from werkzeug.utils import secure_filename
from datetime import datetime
import base64
import imghdr
import jwt
import uuid

pesticide_listing = Blueprint('pesticide_listing', __name__)

UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def verify_jwt_token(token):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
        return payload
    except:
        return None


@pesticide_listing.route('/add', methods=['POST'])
def add_pesticide():
    conn = None
    cursor = None
    image_path = None  # Track image path for cleanup
    try:
        request_id = str(uuid.uuid4())[:8]
        print(f"[PESTICIDE] Starting add_pesticide request... Request ID: {request_id}")
        
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            print("[PESTICIDE] Error: Missing or invalid token")
            return jsonify({'error': 'Missing or invalid token'}), 401
        
        token = auth_header.split(' ')[1]
        payload = verify_jwt_token(token)
        if not payload:
            print("[PESTICIDE] Error: Invalid or expired token")
            return jsonify({'error': 'Invalid or expired token'}), 401
        
        user_id = payload.get('user_id')
        print(f"[PESTICIDE] User ID: {user_id}")

        data = request.get_json(force=True)
        print(f"[PESTICIDE] Received data keys: {list(data.keys())}")

        # Validate required fields
        if not all(key in data for key in ['name', 'price', 'quantity', 'description']):
            print("[PESTICIDE] Error: Missing required fields")
            return jsonify({'error': 'Missing required fields: name, price, quantity, description'}), 400

        name = data.get('name')
        price = data.get('price')
        quantity = data.get('quantity')
        description = data.get('description')
        organic_certified = data.get('organic_certified', False)
        restricted_use = data.get('restricted_use', False)
        local_delivery_available = data.get('local_delivery_available', False)
        image_file = data.get('image')

        # Validate types
        try:
            user_id = int(user_id)
            price = float(price)
            quantity = int(quantity)
        except (ValueError, TypeError) as e:
            print(f"[PESTICIDE] Error: Invalid data format - {str(e)}")
            return jsonify({'error': f'Invalid data format: {str(e)}'}), 400

        # Handle image upload
        if image_file and isinstance(image_file, str):
            try:
                print("[PESTICIDE] Processing image...")
                image_data = image_file.strip()
                if 'data:' in image_data and ',' in image_data:
                    image_data = image_data.split(',', 1)[1]

                missing_padding = len(image_data) % 4
                if missing_padding:
                    image_data += '=' * (4 - missing_padding)

                image_bytes = base64.b64decode(image_data)
                print(f"[PESTICIDE] Image decoded, size: {len(image_bytes)} bytes")

                ext = imghdr.what(None, h=image_bytes)
                ext = ext if ext in ['jpeg', 'jpg', 'png', 'webp'] else 'jpeg'
                if ext == 'jpg':
                    ext = 'jpeg'

                # Use UUID to prevent duplicate filenames
                unique_id = str(uuid.uuid4())[:8]
                timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
                filename = secure_filename(f"pesticide_{user_id}_{timestamp}_{unique_id}.{ext}")
                image_path = os.path.join(UPLOAD_FOLDER, 'pesticides', filename)
                image_path = image_path.replace('\\', '/')

                os.makedirs(os.path.dirname(image_path), exist_ok=True)
                print(f"[PESTICIDE] Saving image to: {image_path}")

                with open(image_path, "wb") as f:
                    f.write(image_bytes)
                
                # Verify file was actually saved
                if os.path.exists(image_path):
                    file_size = os.path.getsize(image_path)
                    abs_path = os.path.abspath(image_path)
                    print(f"[PESTICIDE] Image saved successfully: {image_path}")
                    print(f"[PESTICIDE] Absolute path: {abs_path}")
                    print(f"[PESTICIDE] File size: {file_size} bytes")
                    print(f"[PESTICIDE] Image URL will be: {BASE_URL}/{image_path}")
                else:
                    print(f"[PESTICIDE] WARNING: Image file not found after saving: {image_path}")
                    raise Exception("Image file was not created")
            except Exception as e:
                print(f"[PESTICIDE] Image Error: {str(e)}")
                import traceback
                traceback.print_exc()
                return jsonify({'error': f'Invalid image data: {str(e)}'}), 400
        else:
            print("[PESTICIDE] No image provided or image is not a string")

        print("[PESTICIDE] Connecting to database...")
        conn = get_db_connection()
        cursor = conn.cursor()
        
        try:
            sql = '''
                INSERT INTO pesticides 
                (user_id, name, price, quantity, description, organic_certified, restricted_use, local_delivery_available, image_path)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            '''
            print(f"[PESTICIDE] Inserting data: user_id={user_id}, name={name}, image_path={image_path}")
            cursor.execute(sql, (user_id, name, price, quantity, description, organic_certified, restricted_use, local_delivery_available, image_path))
            conn.commit()
            listing_id = cursor.lastrowid
            print(f"[PESTICIDE] Listing created with ID: {listing_id}")

            # Generate proper image URL
            image_url = f"{BASE_URL}/{image_path}" if image_path else None

            response_data = {
                'message': 'Pesticide added successfully!',
                'listing_id': listing_id,
                'image_url': image_url,
                'image_path': image_path
            }
            print(f"[PESTICIDE] Success! Returning response: {response_data}")
            return jsonify(response_data), 201
            
        except Exception as db_error:
            # Rollback database transaction
            conn.rollback()
            print(f"[PESTICIDE] Database error: {str(db_error)}")
            
            # Clean up orphaned image file if database insert failed
            if image_path and os.path.exists(image_path):
                try:
                    os.remove(image_path)
                    print(f"[PESTICIDE] Cleaned up orphaned image: {image_path}")
                except Exception as cleanup_error:
                    print(f"[PESTICIDE] Failed to cleanup image: {str(cleanup_error)}")
            
            raise db_error  # Re-raise to be caught by outer exception handler

    except Exception as e:
        print(f"[PESTICIDE] CRITICAL ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        
        # Clean up orphaned image if it was saved but request failed
        if image_path and os.path.exists(image_path):
            try:
                os.remove(image_path)
                print(f"[PESTICIDE] Cleaned up orphaned image after error: {image_path}")
            except Exception as cleanup_error:
                print(f"[PESTICIDE] Failed to cleanup image: {str(cleanup_error)}")
        
        return jsonify({'error': f'Server error: {str(e)}'}), 500
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
        print("[PESTICIDE] Database connection closed")


@pesticide_listing.route('/all', methods=['GET'])
def get_all_pesticides():
    try:
        print("[PESTICIDE GET] Fetching all pesticide listings...")
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT user_id, id, name, price, quantity, description, 
                   organic_certified, restricted_use, local_delivery_available,
                   image_path, created_at
            FROM pesticides
        """)
        pesticides = cursor.fetchall()
        print(f"[PESTICIDE GET] Found {len(pesticides)} listings")
        
        # Format listings with proper image URLs
        formatted_pesticides = []
        for pesticide in pesticides:
            formatted_pesticide = dict(pesticide)
            if pesticide.get('image_path'):
                image_url = f"{BASE_URL}/{pesticide['image_path']}"
                formatted_pesticide['image_url'] = image_url
                print(f"[PESTICIDE GET] Listing {pesticide.get('id')}: image_url = {image_url}")
            else:
                formatted_pesticide['image_url'] = None
                print(f"[PESTICIDE GET] Listing {pesticide.get('id')}: No image_path")
            formatted_pesticides.append(formatted_pesticide)

        cursor.close()
        conn.close()
        print(f"[PESTICIDE GET] Returning {len(formatted_pesticides)} formatted listings")
        return jsonify(formatted_pesticides), 200
    except Exception as e:
        print(f"[PESTICIDE GET] Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@pesticide_listing.route('/user/<int:user_id>', methods=['GET'])
def get_pesticides_by_user(user_id):
    try:
        print(f"[PESTICIDE GET] Fetching listings for user {user_id}...")
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT user_id, id, name, price, quantity, description, 
                   organic_certified, restricted_use, local_delivery_available,
                   image_path, created_at
            FROM pesticides
            WHERE user_id = %s
        """, (user_id,))

        pesticides = cursor.fetchall()
        
        # Format listings with proper image URLs
        formatted_pesticides = []
        for pesticide in pesticides:
            formatted_pesticide = dict(pesticide)
            if pesticide.get('image_path'):
                formatted_pesticide['image_url'] = f"{BASE_URL}/{pesticide['image_path']}"
            else:
                formatted_pesticide['image_url'] = None
            formatted_pesticides.append(formatted_pesticide)

        cursor.close()
        conn.close()

        if not formatted_pesticides:
            return jsonify({'message': 'No pesticides found for this user'}), 404

        print(f"[PESTICIDE GET] Returning {len(formatted_pesticides)} listings for user {user_id}")
        return jsonify(formatted_pesticides), 200

    except Exception as e:
        print(f"[PESTICIDE GET] Error: {str(e)}")
        return jsonify({'error': str(e)}), 500
    

@pesticide_listing.route('/delete/<int:pesticide_id>', methods=['DELETE'])
def delete_pesticide(pesticide_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Check if pesticide exists
        cursor.execute("SELECT * FROM pesticides WHERE id = %s", (pesticide_id,))
        pesticide = cursor.fetchone()
        if not pesticide:
            cursor.close()
            conn.close()
            return jsonify({'error': 'Pesticide not found'}), 404

        # Delete associated image if exists
        image_path = pesticide.get('image_path')
        if image_path and os.path.exists(image_path):
            try:
                os.remove(image_path)
                print(f"[PESTICIDE DELETE] Deleted image: {image_path}")
            except Exception as e:
                print(f"[PESTICIDE DELETE] Failed to delete image: {str(e)}")

        # Delete the pesticide
        cursor.execute("DELETE FROM pesticides WHERE id = %s", (pesticide_id,))
        conn.commit()

        cursor.close()
        conn.close()

        return jsonify({'message': 'Pesticide deleted successfully'}), 200

    except Exception as e:
        print(f"[PESTICIDE DELETE] Error: {str(e)}")
        return jsonify({'error': str(e)}), 500
