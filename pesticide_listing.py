from flask import Blueprint, request, jsonify
from db import get_db_connection
from config import SECRET_KEY
import os
from datetime import datetime
import base64
from PIL import Image  # imghdr ki jagah Pillow se type detect
import io
import jwt
import uuid
import cloudinary.uploader  # Cloudinary upload

pesticide_listing = Blueprint('pesticide_listing', __name__)

# Local folder optional (Cloudinary use kar rahe hain)
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
    image_url = None
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

        name = data.get('name')
        price = data.get('price')
        quantity = data.get('quantity')
        description = data.get('description')
        organic_certified = data.get('organic_certified', False)
        restricted_use = data.get('restricted_use', False)
        local_delivery_available = data.get('local_delivery_available', False)
        image_file = data.get('image')  # Base64 string

        if not all([name, price, quantity, description]):
            return jsonify({'error': 'Missing required fields'}), 400

        # Cloudinary Upload (imghdr ki jagah Pillow se format detect)
        image_url = None
        if image_file and isinstance(image_file, str):
            try:
                print("[PESTICIDE] Processing base64 image for Cloudinary...")
                
                image_data = image_file.strip()
                if 'data:' in image_data and ',' in image_data:
                    image_data = image_data.split(',', 1)[1]
                
                missing_padding = len(image_data) % 4
                if missing_padding:
                    image_data += '=' * (4 - missing_padding)
                
                image_bytes = base64.b64decode(image_data)
                print(f"[PESTICIDE] Decoded bytes length: {len(image_bytes)}")
                
                if len(image_bytes) == 0:
                    raise ValueError("Empty image data")

                # Pillow se format detect
                try:
                    with Image.open(io.BytesIO(image_bytes)) as img:
                        ext = img.format.lower() if img.format else 'jpeg'
                except Exception:
                    ext = 'jpeg'  # fallback

                unique_id = str(uuid.uuid4())[:8]
                timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
                public_id = f"pesticide_{user_id}_{timestamp}_{unique_id}"

                upload_result = cloudinary.uploader.upload(
                    image_bytes,
                    folder="agrox/pesticide",
                    public_id=public_id,
                    format=ext
                )
                
                image_url = upload_result['secure_url']
                print(f"[PESTICIDE] SUCCESS: Uploaded to Cloudinary → {image_url}")

            except Exception as e:
                print(f"[PESTICIDE] Cloudinary upload failed: {str(e)}")
                import traceback
                traceback.print_exc()
                return jsonify({'error': f'Image upload failed: {str(e)}'}), 400
        else:
            print("[PESTICIDE] No image provided")

        conn = get_db_connection()
        cursor = conn.cursor()
        
        sql = '''
            INSERT INTO pesticides 
            (user_id, name, price, quantity, description, organic_certified, 
             restricted_use, local_delivery_available, image_url)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        '''
        cursor.execute(sql, (user_id, name, price, quantity, description, organic_certified,
                             restricted_use, local_delivery_available, image_url))
        conn.commit()
        pesticide_id = cursor.lastrowid
        print(f"[PESTICIDE] Listing created with ID: {pesticide_id}")

        response_data = {
            'message': 'Pesticide listed successfully!',
            'pesticide_id': pesticide_id,
            'image_url': image_url
        }
        return jsonify(response_data), 201
            
    except Exception as e:
        if conn:
            conn.rollback()
        print(f"[PESTICIDE] CRITICAL ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Server error: {str(e)}'}), 500
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@pesticide_listing.route('/user/<int:user_id>', methods=['GET'])
def get_pesticides_by_user(user_id):
    try:
        print(f"[PESTICIDE GET] Fetching listings for user {user_id}...")
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT user_id, id, name, price, quantity, description, 
                   organic_certified, restricted_use, local_delivery_available,
                   image_url, created_at
            FROM pesticides
            WHERE user_id = %s
        """, (user_id,))

        pesticides = cursor.fetchall()
        
        # Format listings with proper image URLs
        formatted_pesticides = []
        for pesticide in pesticides:
            formatted_pesticide = dict(pesticide)
            if pesticide.get('image_url'):
                formatted_pesticide['image_url'] = f"{BASE_URL}/{pesticide['image_url']}"
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
        image_url = pesticide.get('image_url')
        if image_url and os.path.exists(image_url):
            try:
                os.remove(image_url)
                print(f"[PESTICIDE DELETE] Deleted image: {image_url}")
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
