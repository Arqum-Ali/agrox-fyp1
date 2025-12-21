from flask import Blueprint, jsonify
from db import get_db_connection
from config import BASE_URL

machinery_display = Blueprint('machinery_display', __name__)

@machinery_display.route('/machinery/available', methods=['GET'])
def get_available_machinery():
    """
    Get all available machinery rentals with complete details including images
    Returns properly formatted JSON with image URLs
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)  # Returns dict instead of tuple
        
        cursor.execute("""
            SELECT 
                mr.id,
                mr.user_id,
                mr.machinery_type_id,
                mr.name,
                mr.description,
                mr.daily_rate,
                mr.min_days,
                mr.start_date,
                mr.end_date,
                mr.image_path,
                mr.created_at
            FROM machinery_rentals mr
            ORDER BY mr.created_at DESC
        """)
        
        listings = cursor.fetchall()
        cursor.close()
        conn.close()
        
        # Format the response with proper image URLs
        formatted_listings = []
        for listing in listings:
            formatted_listing = {
                'id': listing['id'],
                'user_id': listing['user_id'],
                'machinery_type_id': listing['machinery_type_id'],
                'name': listing['name'],
                'description': listing['description'],
                'daily_rate': float(listing['daily_rate']),
                'min_days': listing['min_days'],
                'start_date': str(listing['start_date']),
                'end_date': str(listing['end_date']),
                'image_url': f"{BASE_URL}/{listing['image_path']}" if listing.get('image_path') else None,
                'created_at': str(listing.get('created_at', ''))
            }
            formatted_listings.append(formatted_listing)
        
        return jsonify({
            'success': True,
            'count': len(formatted_listings),
            'machinery': formatted_listings
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@machinery_display.route('/machinery/details/<int:machinery_id>', methods=['GET'])
def get_machinery_details(machinery_id):
    """
    Get detailed information for a specific machinery rental
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("""
            SELECT 
                mr.id,
                mr.user_id,
                mr.machinery_type_id,
                mr.name,
                mr.description,
                mr.daily_rate,
                mr.min_days,
                mr.start_date,
                mr.end_date,
                mr.image_path,
                mr.created_at
            FROM machinery_rentals mr
            WHERE mr.id = %s
        """, (machinery_id,))
        
        listing = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if not listing:
            return jsonify({
                'success': False,
                'error': 'Machinery not found'
            }), 404
        
        # Format the response
        formatted_listing = {
            'id': listing['id'],
            'user_id': listing['user_id'],
            'machinery_type_id': listing['machinery_type_id'],
            'name': listing['name'],
            'description': listing['description'],
            'daily_rate': float(listing['daily_rate']),
            'min_days': listing['min_days'],
            'start_date': str(listing['start_date']),
            'end_date': str(listing['end_date']),
            'image_url': f"{BASE_URL}/{listing['image_path']}" if listing.get('image_path') else None,
            'created_at': str(listing.get('created_at', ''))
        }
        
        return jsonify({
            'success': True,
            'machinery': formatted_listing
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
