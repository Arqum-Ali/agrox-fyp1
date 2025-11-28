from flask import Blueprint, request, jsonify
from db import get_db_connection
import os
from werkzeug.utils import secure_filename
from datetime import datetime
import base64
import jwt

machinery_rental = Blueprint('machinery_rental', __name__)
UPLOAD_FOLDER = 'Uploads'
SECRET_KEY = 'your-secret-key'  # Should match the key in login.py, store in environment variables in production


def verify_jwt_token(token):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


@machinery_rental.route('/rent_machinery', methods=['POST'])
def rent_machinery():
    try:
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({'error': 'Missing or invalid Authorization header'}), 401

        token = auth_header.split(' ')[1]
        payload = verify_jwt_token(token)
        if not payload:
            return jsonify({'error': 'Invalid or expired token'}), 401

        user_id = payload.get('user_id')
        if not user_id:
            return jsonify({'error': 'Invalid token payload'}), 401

        data = request.get_json()

        machinery_type_id = data.get('machinery_type_id')
        name = data.get('name')
        description = data.get('description')
        daily_rate = data.get('daily_rate')
        min_days = data.get('min_days')
        start_date = data.get('start_date')
        end_date = data.get('end_date')
        image_file = data.get('image')

        if not all([machinery_type_id, name, description, daily_rate, min_days, start_date, end_date]):
            return jsonify({'error': 'Missing required fields'}), 400

        try:
            daily_rate = float(daily_rate)
        except (ValueError, TypeError):
            return jsonify({'error': 'Invalid daily_rate, must be a number'}), 400

        try:
            min_days = int(min_days)
        except (ValueError, TypeError):
            return jsonify({'error': 'Invalid min_days, must be an integer'}), 400

        try:
            start_date = datetime.strptime(start_date, "%Y-%m-%d").date()
        except (ValueError, TypeError):
            return jsonify({'error': 'Invalid start_date format, expected YYYY-MM-DD'}), 400

        try:
            end_date = datetime.strptime(end_date, "%Y-%m-%d").date()
        except (ValueError, TypeError):
            return jsonify({'error': 'Invalid end_date format, expected YYYY-MM-DD'}), 400

        if start_date > end_date:
            return jsonify({'error': 'End date must be after start date'}), 400

        image_path = None
        if image_file:
            if image_file.startswith('data:image/'):
                image_data = image_file.split(",")[1]
                image_bytes = base64.b64decode(image_data)

                filename = secure_filename(f"machinery_{user_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}.png")
                image_path = os.path.join(UPLOAD_FOLDER, filename)
                if not os.path.exists(UPLOAD_FOLDER):
                    os.makedirs(UPLOAD_FOLDER)
                with open(image_path, "wb") as f:
                    f.write(image_bytes)
            else:
                return jsonify({'error': 'Unsupported image format'}), 400

        conn = get_db_connection()
        cursor = conn.cursor()

        sql = '''
            INSERT INTO machinery_rentals 
            (user_id, machinery_type_id, name, description, daily_rate, min_days, start_date, end_date, image_path)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        '''
        cursor.execute(sql, (
            user_id, machinery_type_id, name, description,
            daily_rate, min_days, start_date, end_date, image_path
        ))
        conn.commit()

        return jsonify({'message': 'Machinery rental listed successfully'}), 201

    except Exception as e:
        print(f"Error: {e}")
        return jsonify({'error': str(e)}), 500

    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()


@machinery_rental.route('/rent_machinery', methods=['GET'])
def get_rent_machinery():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM machinery_rentals")
    listings = cursor.fetchall()
    cursor.close()
    conn.close()
    return jsonify(listings), 200


@machinery_rental.route('/rent_machinery/<int:listing_id>', methods=['GET'])
def get_rent_machinery_by_id(listing_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, user_id, machinery_type_id, name, description, daily_rate, min_days, start_date, end_date, image_path FROM machinery_rentals WHERE id = %s",
        (listing_id,))
    listing = cursor.fetchone()
    cursor.close()
    conn.close()

    if not listing:
        return jsonify({'error': 'Machinery rental not found'}), 404

    return jsonify(listing), 200


@machinery_rental.route('/rent_machinery/user/<int:user_id>', methods=['GET'])
def get_rent_machinery_by_user(user_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, user_id, machinery_type_id, name, description, daily_rate, min_days, start_date, end_date, image_path
            FROM machinery_rentals
            WHERE user_id = %s
        """, (user_id,))
        listings = cursor.fetchall()
        cursor.close()
        conn.close()

        if not listings:
            return jsonify({'message': 'No machinery listings found for this user'}), 404

        return jsonify(listings), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@machinery_rental.route('/rent_machinery/<int:listing_id>', methods=['DELETE'])
def delete_machinery_rental(listing_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Check if the listing exists
        cursor.execute("SELECT * FROM machinery_rentals WHERE id = %s", (listing_id,))
        listing = cursor.fetchone()
        if not listing:
            cursor.close()
            conn.close()
            return jsonify({'error': 'Machinery rental listing not found'}), 404

        # Delete the listing
        cursor.execute("DELETE FROM machinery_rentals WHERE id = %s", (listing_id,))
        conn.commit()

        cursor.close()
        conn.close()

        return jsonify({'message': 'Machinery rental listing deleted successfully'}), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500
