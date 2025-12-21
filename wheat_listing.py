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

wheat_listing = Blueprint('wheat_listing', __name__)

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
    image_path = None  # Track image path for cleanup
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

        # Required fields
        if not all(key in data for key in ['title', 'price_per_kg', 'quantity_kg', 'description']):
            print("[WHEAT] Error: Missing required fields")
            return jsonify({'error': 'Missing required fields'}), 400

        title = data['title']
        price_per_kg = data['price_per_kg']
        quantity_kg = data['quantity_kg']
        description = data['description']
        wheat_variety = data.get('wheat_variety', '')
        grade_quality = data.get('grade_quality', '')
        harvest_season = data.get('harvest_season', '')
        protein_content = data.get('protein_content', None)
        moisture_level = data.get('moisture_level', None)
        organic_certified = data.get('organic_certified', False)
        pesticides_used = data.get('pesticides_used', False)
        local_delivery_available = data.get('local_delivery_available', False)
        image_file = data.get('image')

        # Validate numeric fields
        try:
            price_per_kg = float(price_per_kg)
            quantity_kg = float(quantity_kg)
        except (ValueError, TypeError):
            print("[WHEAT] Error: Invalid price or quantity format")
            return jsonify({'error': 'Invalid price or quantity format'}), 400

        # Handle image upload
        if image_file and isinstance(image_file, str):
            try:
                print("[WHEAT] Processing image...")
                image_data = image_file.strip()
                if 'data:' in image_data and ',' in image_data:
                    image_data = image_data.split(',', 1)[1]

                missing_padding = len(image_data) % 4
                if missing_padding:
                    image_data += '=' * (4 - missing_padding)

                image_bytes = base64.b64decode(image_data)
                print(f"[WHEAT] Image decoded, size: {len(image_bytes)} bytes")

                ext = imghdr.what(None, h=image_bytes)
                ext = ext if ext in ['jpeg', 'jpg', 'png', 'webp'] else 'jpeg'
                if ext == 'jpg':
                    ext = 'jpeg'

                # Use UUID to prevent duplicate filenames
                unique_id = str(uuid.uuid4())[:8]
                timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
                filename = secure_filename(f"wheat_{user_id}_{timestamp}_{unique_id}.{ext}")
                image_path = os.path.join(UPLOAD_FOLDER, 'wheat', filename)
                image_path = image_path.replace('\\', '/')

                os.makedirs(os.path.dirname(image_path), exist_ok=True)
                print(f"[WHEAT] Saving image to: {image_path}")

                with open(image_path, "wb") as f:
                    f.write(image_bytes)
                
                # Verify file was actually saved
                if os.path.exists(image_path):
                    file_size = os.path.getsize(image_path)
                    abs_path = os.path.abspath(image_path)
                    print(f"[WHEAT] Image saved successfully: {image_path}")
                    print(f"[WHEAT] Absolute path: {abs_path}")
                    print(f"[WHEAT] File size: {file_size} bytes")
                    print(f"[WHEAT] Image URL will be: {BASE_URL}/{image_path}")
                else:
                    print(f"[WHEAT] WARNING: Image file not found after saving: {image_path}")
                    raise Exception("Image file was not created")
            except Exception as e:
                print(f"[WHEAT] Image Error: {str(e)}")
                import traceback
                traceback.print_exc()
                return jsonify({'error': f'Invalid image data: {str(e)}'}), 400
        else:
            print("[WHEAT] No image provided or image is not a string")

        print("[WHEAT] Connecting to database...")
        conn = get_db_connection()
        cursor = conn.cursor()
        
        try:
            sql = '''
                INSERT INTO wheat_listings (
                    title, price_per_kg, quantity_kg, description, wheat_variety, grade_quality,
                    harvest_season, protein_content, moisture_level, organic_certified, pesticides_used,
                    local_delivery_available, user_id, image_path
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            '''
            print(f"[WHEAT] Inserting data: user_id={user_id}, title={title}, image_path={image_path}")
            cursor.execute(sql, (
                title, price_per_kg, quantity_kg, description, wheat_variety, grade_quality,
                harvest_season, protein_content, moisture_level, organic_certified, pesticides_used,
                local_delivery_available, user_id, image_path
            ))
            conn.commit()
            listing_id = cursor.lastrowid
            print(f"[WHEAT] Listing created with ID: {listing_id}")

            # Generate proper image URL
            image_url = f"{BASE_URL}/{image_path}" if image_path else None

            response_data = {
                'message': 'Wheat listing created successfully!',
                'listing_id': listing_id,
                'image_url': image_url,
                'image_path': image_path
            }
            print(f"[WHEAT] Success! Returning response: {response_data}")
            return jsonify(response_data), 201
            
        except Exception as db_error:
            # Rollback database transaction
            conn.rollback()
            print(f"[WHEAT] Database error: {str(db_error)}")
            
            # Clean up orphaned image file if database insert failed
            if image_path and os.path.exists(image_path):
                try:
                    os.remove(image_path)
                    print(f"[WHEAT] Cleaned up orphaned image: {image_path}")
                except Exception as cleanup_error:
                    print(f"[WHEAT] Failed to cleanup image: {str(cleanup_error)}")
            
            raise db_error  # Re-raise to be caught by outer exception handler

    except Exception as e:
        print(f"[WHEAT] CRITICAL ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        
        # Clean up orphaned image if it was saved but request failed
        if image_path and os.path.exists(image_path):
            try:
                os.remove(image_path)
                print(f"[WHEAT] Cleaned up orphaned image after error: {image_path}")
            except Exception as cleanup_error:
                print(f"[WHEAT] Failed to cleanup image: {str(cleanup_error)}")
        
        return jsonify({'error': f'Server error: {str(e)}'}), 500
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
        print("[WHEAT] Database connection closed")


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
