from flask import Blueprint, request, jsonify
from db import get_db_connection

pesticide_listing = Blueprint('pesticide_listing', __name__)

@pesticide_listing.route('/add', methods=['POST'])
def add_pesticide():
    # Check if request is JSON
    if request.is_json:
        data = request.get_json()
        user_id = data.get('user_id')
        name = data.get('name')
        price = data.get('price')
        quantity = data.get('quantity')
        description = data.get('description')
        organic_certified = data.get('organic_certified', False)
        restricted_use = data.get('restricted_use', False)
        local_delivery_available = data.get('local_delivery_available', False)
    else:
        # Fallback to form data
        user_id = request.form.get('user_id')
        name = request.form.get('name')
        price = request.form.get('price')
        quantity = request.form.get('quantity')
        description = request.form.get('description')
        organic_certified = request.form.get('organic_certified', 'False') == 'true'
        restricted_use = request.form.get('restricted_use', 'False') == 'true'
        local_delivery_available = request.form.get('local_delivery_available', 'False') == 'true'

    # Validate required fields
    if not user_id:
        return jsonify({'error': 'user_id is required'}), 400
    if not name:
        return jsonify({'error': 'name is required'}), 400
    if not price:
        return jsonify({'error': 'price is required'}), 400
    if not quantity:
        return jsonify({'error': 'quantity is required'}), 400

    try:
        # Validate types
        user_id = int(user_id)
        price = float(price)
        quantity = int(quantity)

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO pesticides 
            (user_id, name, price, quantity, description, organic_certified, restricted_use, local_delivery_available)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (user_id, name, price, quantity, description, organic_certified, restricted_use, local_delivery_available))

        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({'message': 'Pesticide added successfully'}), 201
    except ValueError:
        return jsonify({'error': 'Invalid input: user_id, price, or quantity must be valid numbers'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@pesticide_listing.route('/all', methods=['GET'])
def get_all_pesticides():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()  # DictCursor is already set in db.py

        cursor.execute("""
            SELECT user_id, id, name, price, quantity, description, 
                   organic_certified, restricted_use, local_delivery_available,
                    created_at
            FROM pesticides
        """)
        pesticides = cursor.fetchall()  # Will return list of dictionaries

        cursor.close()
        conn.close()

        return jsonify(pesticides), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@pesticide_listing.route('/user/<int:user_id>', methods=['GET'])
def get_pesticides_by_user(user_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()  # DictCursor returns dicts

        cursor.execute("""
            SELECT user_id, id, name, price, quantity, description, 
                   organic_certified, restricted_use, local_delivery_available,
                   created_at
            FROM pesticides
            WHERE user_id = %s
        """, (user_id,))

        pesticides = cursor.fetchall()

        cursor.close()
        conn.close()

        if not pesticides:
            return jsonify({'message': 'No pesticides found for this user'}), 404

        return jsonify(pesticides), 200

    except Exception as e:
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

        # Delete the pesticide
        cursor.execute("DELETE FROM pesticides WHERE id = %s", (pesticide_id,))
        conn.commit()

        cursor.close()
        conn.close()

        return jsonify({'message': 'Pesticide deleted successfully'}), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500

