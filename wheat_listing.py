from flask import Blueprint, request, jsonify
from flask_mail import Mail, Message
import random
import string
import time
from config import MAIL_SERVER, MAIL_PORT, MAIL_USE_TLS, MAIL_USERNAME, MAIL_PASSWORD
from db import get_db_connection

wheat_listing = Blueprint('wheat_listing', __name__)

@wheat_listing.route('/wheat-listings', methods=['POST'])
def create_wheat_listing():
    data = request.get_json()

    if not all(key in data for key in ['title', 'price_per_kg', 'quantity_kg', 'description', 'user_id']):
        return jsonify({'error': 'Missing required fields'}), 400

    title = data['title']
    price_per_kg = data['price_per_kg']
    quantity_kg = data['quantity_kg']
    description = data['description']
    user_id = data['user_id']
    wheat_variety = data.get('wheat_variety', '')
    grade_quality = data.get('grade_quality', '')
    harvest_season = data.get('harvest_season', '')
    protein_content = data.get('protein_content', None)
    moisture_level = data.get('moisture_level', None)
    organic_certified = data.get('organic_certified', False)
    pesticides_used = data.get('pesticides_used', False)
    local_delivery_available = data.get('local_delivery_available', False)

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO wheat_listings (
            title, price_per_kg, quantity_kg, description, wheat_variety, grade_quality,
            harvest_season, protein_content, moisture_level, organic_certified, pesticides_used,
            local_delivery_available, user_id
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, (
        title, price_per_kg, quantity_kg, description, wheat_variety, grade_quality,
        harvest_season, protein_content, moisture_level, organic_certified, pesticides_used,
        local_delivery_available, user_id
    ))
    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({'message': 'Wheat listing created successfully'}), 201


@wheat_listing.route('/wheat-listings', methods=['GET'])
def get_wheat_listings():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM wheat_listings")
    listings = cursor.fetchall()
    cursor.close()
    conn.close()
    return jsonify(listings), 200


@wheat_listing.route('/wheat-listings/<int:listing_id>', methods=['GET'])
def get_wheat_listing(listing_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM wheat_listings WHERE id = %s", (listing_id,))
    listing = cursor.fetchone()
    cursor.close()
    conn.close()

    if not listing:
        return jsonify({'error': 'Wheat listing not found'}), 404

    return jsonify(listing), 200


# ✅ New Route: Get all wheat listings by a specific user
@wheat_listing.route('/wheat-listings/user/<int:user_id>', methods=['GET'])
def get_wheat_listings_by_user(user_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM wheat_listings
            WHERE user_id = %s
        """, (user_id,))
        listings = cursor.fetchall()
        cursor.close()
        conn.close()

        if not listings:
            return jsonify({'message': 'No wheat listings found for this user'}), 404

        return jsonify(listings), 200

    except Exception as e:
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

        cursor.execute("DELETE FROM wheat_listings WHERE id = %s", (listing_id,))
        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({'message': 'Wheat listing deleted successfully'}), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500
