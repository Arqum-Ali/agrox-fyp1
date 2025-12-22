from flask import Blueprint, request, jsonify
from db import get_db_connection
from config import SECRET_KEY
import base64
import jwt
import uuid
from datetime import datetime
import cloudinary.uploader  # Cloudinary upload ke liye

machinery_rental = Blueprint('machinery_rental', __name__)


def verify_jwt_token(token):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
        return payload
    except:
        return None


@machinery_rental.route('/rent_machinery', methods=['POST'])
def rent_machinery():
    conn = None
    cursor = None
    image_url = None
    try:
        request_id = str(uuid.uuid4())[:8]
        print(f"[MACHINERY] Starting rent_machinery request... Request ID: {request_id}")
        
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            print("[MACHINERY] Error: Missing or invalid token")
            return jsonify({'error': 'Missing or invalid token'}), 401
        
        token = auth_header.split(' ')[1]
        payload = verify_jwt_token(token)
        if not payload:
            print("[MACHINERY] Error: Invalid or expired token")
            return jsonify({'error': 'Invalid or expired token'}), 401
        
        user_id = payload.get('user_id')
        print(f"[MACHINERY] User ID: {user_id}")

        data = request.get_json(force=True)
        print(f"[MACHINERY] Received data keys: {list(data.keys())}")

        machinery_type_id = data.get('machinery_type_id')
        name = data.get('name')
        description = data.get('description')
        daily_rate = data.get('daily_rate')
        min_days = data.get('min_days')
        start_date = data.get('start_date')
        end_date = data.get('end_date')
        image_file = data.get('image')  # Base64 string from Flutter

        if not all([machinery_type_id, name, description, daily_rate, min_days, start_date, end_date]):
            print("[MACHINERY] Error: Missing required fields")
            return jsonify({'error': 'Missing required fields'}), 400

        try:
            daily_rate = float(daily_rate)
            min_days = int(min_days)
            start_date = datetime.strptime(start_date, "%Y-%m-%d").date()
            end_date = datetime.strptime(end_date, "%Y-%m-%d").date()
        except Exception as e:
            print(f"[MACHINERY] Error: Invalid data format - {str(e)}")
            return jsonify({'error': f'Invalid data format: {str(e)}'}), 400

        if start_date > end_date:
            print("[MACHINERY] Error: End date must be after start date")
            return jsonify({'error': 'End date must be after start date'}), 400

        # <<< Final Safe Cloudinary Upload
        image_url = None
        if image_file and isinstance(image_file, str):
            try:
                print("[MACHINERY] Processing base64 image for Cloudinary...")
                
                image_data = image_file.strip()
                
                # Remove data URL prefix if present
                if 'data:' in image_data and ',' in image_data:
                    image_data = image_data.split(',', 1)[1]
                
                # Fix base64 padding
                missing_padding = len(image_data) % 4
                if missing_padding:
                    image_data += '=' * (4 - missing_padding)
                
                # Decode to bytes
                image_bytes = base64.b64decode(image_data)
                print(f"[MACHINERY] Decoded image bytes length: {len(image_bytes)}")
                
                if len(image_bytes) == 0:
                    raise ValueError("Empty image data after decoding")

                # Generate unique public_id
                unique_id = str(uuid.uuid4())[:8]
                timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
                public_id = f"machinery_{user_id}_{timestamp}_{unique_id}"

                # Upload to Cloudinary directly from bytes
                upload_result = cloudinary.uploader.upload(
                    image_bytes,
                    folder="agrox/machinery",
                    public_id=public_id,
                    overwrite=True,
                    resource_type="image"  # Force as image
                )
                
                image_url = upload_result['secure_url']
                print(f"[MACHINERY] SUCCESS: Image uploaded to Cloudinary → {image_url}")

            except base64.binascii.Error as e:
                print(f"[MACHINERY] Base64 decode error: {str(e)}")
                return jsonify({'error': 'Invalid base64 encoding in image'}), 400
            except Exception as e:
                print(f"[MACHINERY] Cloudinary upload failed: {str(e)}")
                import traceback
                traceback.print_exc()
                return jsonify({'error': f'Image upload failed: {str(e)}'}), 400
        else:
            print("[MACHINERY] No image provided or invalid type")

        # Database Insert
        conn = get_db_connection()
        cursor = conn.cursor()
        
        sql = '''
            INSERT INTO machinery_rentals 
            (user_id, machinery_type_id, name, description, daily_rate, min_days, start_date, end_date, image_path)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        '''
        cursor.execute(sql, (user_id, machinery_type_id, name, description, daily_rate, min_days, start_date, end_date, image_url))
        conn.commit()
        listing_id = cursor.lastrowid
        print(f"[MACHINERY] Listing created with ID: {listing_id}")

        response_data = {
            'message': 'Machinery listed successfully!',
            'listing_id': listing_id,
            'image_url': image_url
        }
        return jsonify(response_data), 201
            
    except Exception as e:
        if conn:
            conn.rollback()
        print(f"[MACHINERY] CRITICAL ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Server error: {str(e)}'}), 500
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


@machinery_rental.route('/rent_machinery', methods=['GET'])
def get_rent_machinery():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM machinery_rentals")
        listings = cursor.fetchall()
        
        formatted_listings = [dict(listing) for listing in listings]
        
        cursor.close()
        conn.close()
        return jsonify(formatted_listings), 200
    except Exception as e:
        print(f"[MACHINERY GET] Error: {str(e)}")
        return jsonify({'error': str(e)}), 500


@machinery_rental.route('/rent_machinery/<int:listing_id>', methods=['GET'])
def get_rent_machinery_by_id(listing_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM machinery_rentals WHERE id = %s", (listing_id,))
    listing = cursor.fetchone()
    cursor.close()
    conn.close()

    if not listing:
        return jsonify({'error': 'Machinery rental not found'}), 404

    return jsonify(dict(listing)), 200


@machinery_rental.route('/rent_machinery/user/<int:user_id>', methods=['GET'])
def get_rent_machinery_by_user(user_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM machinery_rentals WHERE user_id = %s", (user_id,))
        listings = cursor.fetchall()
        
        cursor.close()
        conn.close()

        if not listings:
            return jsonify({'message': 'No machinery listings found for this user'}), 404

        return jsonify([dict(l) for l in listings]), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@machinery_rental.route('/rent_machinery/<int:listing_id>', methods=['DELETE'])
def delete_machinery_rental(listing_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT image_url FROM machinery_rentals WHERE id = %s", (listing_id,))
        listing = cursor.fetchone()
        if not listing:
            return jsonify({'error': 'Machinery rental listing not found'}), 404

        cursor.execute("DELETE FROM machinery_rentals WHERE id = %s", (listing_id,))
        conn.commit()

        cursor.close()
        conn.close()

        return jsonify({'message': 'Machinery rental listing deleted successfully'}), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500