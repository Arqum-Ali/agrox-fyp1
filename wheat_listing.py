from flask import Blueprint, request, jsonify
from db import get_db_connection
from config import SECRET_KEY, BASE_URL
import os
from werkzeug.utils import secure_filename
from datetime import datetime
import base64
from PIL import Image  # imghdr ki jagah Pillow se type detect
import io
import jwt
import uuid
import cloudinary.uploader  # Cloudinary upload

wheat_listing = Blueprint('wheat_listing', __name__)

# Cloudinary use kar rahe hain, local uploads folder optional
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def verify_jwt_token(token):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
        return payload
    except:
        return None

@wheat_listing.route('/wheat-listings', methods=['POST'])
def create_wheat_listing():
    conn = None
    cursor = None
    image_url = None
    try:
        request_id = str(uuid.uuid4())[:8]
        print(f"[WHEAT] Starting create_wheat_listing request... Request ID: {request_id}")
        
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            print("[WHEAT] Error: Missing or invalid token")
            return jsonify({'error': 'Missing or invalid token'}), 401
        
        token = auth_header.split(' ')[1]
        payload = verify_jwt_token(token)
        if not payload:
            print("[WHEAT] Error: Invalid or expired token")
            return jsonify({'error': 'Invalid or expired token'}), 401
        
        user_id = payload.get('user_id')
        print(f"[WHEAT] User ID: {user_id}")

        data = request.get_json(force=True)
        print(f"[WHEAT] Received data keys: {list(data.keys())}")

        title = data.get('title')
        price_per_kg = data.get('price_per_kg')
        quantity_kg = data.get('quantity_kg')
        description = data.get('description')
        wheat_variety = data.get('wheat_variety')
        grade_quality = data.get('grade_quality')
        harvest_season = data.get('harvest_season')
        protein_content = data.get('protein_content')
        moisture_level = data.get('moisture_level')
        organic_certified = data.get('organic_certified', False)
        pesticides_used = data.get('pesticides_used', False)
        local_delivery_available = data.get('local_delivery_available', False)
        image_file = data.get('image')  # Base64 string

        if not all([title, price_per_kg, quantity_kg, description]):
            return jsonify({'error': 'Missing required fields'}), 400

        # Cloudinary Upload (imghdr ki jagah Pillow se format detect)
        image_url = None
        if image_file and isinstance(image_file, str):
            try:
                print("[WHEAT] Processing base64 image for Cloudinary...")
                
                image_data = image_file.strip()
                if 'data:' in image_data and ',' in image_data:
                    image_data = image_data.split(',', 1)[1]
                
                missing_padding = len(image_data) % 4
                if missing_padding:
                    image_data += '=' * (4 - missing_padding)
                
                image_bytes = base64.b64decode(image_data)
                print(f"[WHEAT] Decoded bytes length: {len(image_bytes)}")
                
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
                public_id = f"wheat_{user_id}_{timestamp}_{unique_id}"

                upload_result = cloudinary.uploader.upload(
                    image_bytes,
                    folder="agrox/wheat",
                    public_id=public_id,
                    format=ext
                )
                
                image_url = upload_result['secure_url']
                print(f"[WHEAT] SUCCESS: Uploaded to Cloudinary → {image_url}")

            except Exception as e:
                print(f"[WHEAT] Cloudinary upload failed: {str(e)}")
                import traceback
                traceback.print_exc()
                return jsonify({'error': f'Image upload failed: {str(e)}'}), 400
        else:
            print("[WHEAT] No image provided")

        conn = get_db_connection()
        cursor = conn.cursor()
        
        sql = '''
            INSERT INTO wheat_listings 
            (user_id, title, price_per_kg, quantity_kg, description, wheat_variety, grade_quality, 
             harvest_season, protein_content, moisture_level, organic_certified, pesticides_used, 
             local_delivery_available, image_url)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        '''
        cursor.execute(sql, (user_id, title, price_per_kg, quantity_kg, description, wheat_variety, grade_quality,
                             harvest_season, protein_content, moisture_level, organic_certified, pesticides_used,
                             local_delivery_available, image_url))
        conn.commit()
        listing_id = cursor.lastrowid
        print(f"[WHEAT] Listing created with ID: {listing_id}")

        response_data = {
            'message': 'Wheat listed successfully!',
            'listing_id': listing_id,
            'image_url': image_url
        }
        return jsonify(response_data), 201
            
    except Exception as e:
        if conn:
            conn.rollback()
        print(f"[WHEAT] CRITICAL ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Server error: {str(e)}'}), 500
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


@wheat_listing.route('/wheat-listings', methods=['GET'])
def get_wheat_listings():
    try:
        print("[WHEAT GET] Fetching all wheat listings...")
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM wheat_listings")
        listings = cursor.fetchall()
        print(f"[WHEAT GET] Found {len(listings)} listings")
        
        # Format listings with proper image URLs
        formatted_listings = []
        for listing in listings:
            formatted_listing = dict(listing)
            if listing.get('image_path'):
                image_url = f"{BASE_URL}/{listing['image_path']}"
                formatted_listing['image_url'] = image_url
                print(f"[WHEAT GET] Listing {listing.get('id')}: image_url = {image_url}")
            else:
                formatted_listing['image_url'] = None
                print(f"[WHEAT GET] Listing {listing.get('id')}: No image_path")
            formatted_listings.append(formatted_listing)
        
        cursor.close()
        conn.close()
        print(f"[WHEAT GET] Returning {len(formatted_listings)} formatted listings")
        return jsonify(formatted_listings), 200
    except Exception as e:
        print(f"[WHEAT GET] Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@wheat_listing.route('/wheat-listings/<int:listing_id>', methods=['GET'])
def get_wheat_listing(listing_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM wheat_listings WHERE id = %s", (listing_id,))
        listing = cursor.fetchone()
        cursor.close()
        conn.close()

        if not listing:
            return jsonify({'error': 'Wheat listing not found'}), 404

        # Format listing with proper image URL
        formatted_listing = dict(listing)
        if listing.get('image_path'):
            formatted_listing['image_url'] = f"{BASE_URL}/{listing['image_path']}"
        else:
            formatted_listing['image_url'] = None

        return jsonify(formatted_listing), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@wheat_listing.route('/wheat-listings/user/<int:user_id>', methods=['GET'])
def get_wheat_listings_by_user(user_id):
    try:
        print(f"[WHEAT GET] Fetching listings for user {user_id}...")
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM wheat_listings
            WHERE user_id = %s
        """, (user_id,))
        listings = cursor.fetchall()
        
        # Format listings with proper image URLs
        formatted_listings = []
        for listing in listings:
            formatted_listing = dict(listing)
            if listing.get('image_path'):
                formatted_listing['image_url'] = f"{BASE_URL}/{listing['image_path']}"
            else:
                formatted_listing['image_url'] = None
            formatted_listings.append(formatted_listing)
        
        cursor.close()
        conn.close()

        if not formatted_listings:
            return jsonify({'message': 'No wheat listings found for this user'}), 404

        print(f"[WHEAT GET] Returning {len(formatted_listings)} listings for user {user_id}")
        return jsonify(formatted_listings), 200

    except Exception as e:
        print(f"[WHEAT GET] Error: {str(e)}")
        return jsonify({'error': str(e)}), 500
    

@wheat_listing.route('/wheat-listings/<int:listing_id>', methods=['DELETE'])
def delete_wheat_listing(listing_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM wheat_listings WHERE id = %s", (listing_id,))
        listing = cursor.fetchone()
        if not listing:
            cursor.close()
            conn.close()
            return jsonify({'error': 'Wheat listing not found'}), 404

        # Delete associated image if exists
        image_path = listing.get('image_path')
        if image_path and os.path.exists(image_path):
            try:
                os.remove(image_path)
                print(f"[WHEAT DELETE] Deleted image: {image_path}")
            except Exception as e:
                print(f"[WHEAT DELETE] Failed to delete image: {str(e)}")

        cursor.execute("DELETE FROM wheat_listings WHERE id = %s", (listing_id,))
        conn.commit()

        cursor.close()
        conn.close()

        return jsonify({'message': 'Wheat listing deleted successfully'}), 200

    except Exception as e:
        print(f"[WHEAT DELETE] Error: {str(e)}")
        return jsonify({'error': str(e)}), 500
