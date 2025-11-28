# reminder_views.py - FULL ENGLISH + CLEAN + PROFESSIONAL
from flask import Blueprint, request, jsonify
from datetime import datetime, timedelta
from db import get_db_connection
import jwt
from functools import wraps

# Replace with your actual secret key (same as login)
SECRET_KEY = "your-super-secret-key-here"

reminder_bp = Blueprint("reminder", __name__)

# JWT Token Verification
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get("Authorization", "").replace("Bearer ", "")
        if not token:
            return jsonify({"error": "Token is missing"}), 401

        try:
            data = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
            current_user_id = data.get("user_id")
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Token expired"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"error": "Invalid token"}), 401
        except:
            return jsonify({"error": "Token error"}), 401

        return f(current_user_id, *args, **kwargs)
    return decorated


# Add New Crop Reminder
@reminder_bp.route("/add", methods=["POST"])
@token_required
def add_crop_reminder(current_user_id):
    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid JSON"}), 400

    crop_name = data.get("crop_name")
    planting_date_str = data.get("planting_date")
    field_name = data.get("field_name")

    if not all([crop_name, planting_date_str, field_name]):
        return jsonify({"error": "crop_name, planting_date, and field_name are required"}), 400

    try:
        planting_date = datetime.strptime(planting_date_str, "%Y-%m-%d").date()
    except ValueError:
        return jsonify({"error": "Invalid date format. Use YYYY-MM-DD"}), 400

    # Auto-calculate important dates
    first_irrigation = planting_date + timedelta(days=14)
    second_irrigation = planting_date + timedelta(days=28)
    urea_dose = planting_date + timedelta(days=35)

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            INSERT INTO crop_reminders (
                user_id, crop_name, planting_date, field_name,
                land_preparation_date, seed_sowing_date,
                first_irrigation_date, second_irrigation_date, urea_dose_date,
                created_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
        """, (
            current_user_id, crop_name, planting_date, field_name,
            planting_date, planting_date,
            first_irrigation, second_irrigation, urea_dose
        ))
        conn.commit()
        return jsonify({"message": "Crop reminder added successfully!"}), 201
    except Exception as e:
        conn.rollback()
        return jsonify({"error": f"Failed to save: {str(e)}"}), 500
    finally:
        cursor.close()
        conn.close()


# Get All My Reminders
@reminder_bp.route("/my_crops", methods=["GET"])
@token_required
def get_my_reminders(current_user_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT 
                id, crop_name, field_name,
                DATE_FORMAT(planting_date, '%Y-%m-%d') AS planting_date,
                DATE_FORMAT(first_irrigation_date, '%Y-%m-%d') AS first_irrigation,
                DATE_FORMAT(second_irrigation_date, '%Y-%m-%d') AS second_irrigation,
                DATE_FORMAT(urea_dose_date, '%Y-%m-%d') AS urea_dose
            FROM crop_reminders 
            WHERE user_id = %s 
            ORDER BY planting_date DESC
        """, (current_user_id,))
        
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        reminders = [dict(zip(columns, row)) for row in rows]

        return jsonify({"reminders": reminders}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()
        conn.close()


# Today's Tasks (For Mobile App)
@reminder_bp.route("/today-reminders", methods=["GET"])
@token_required
def today_tasks(current_user_id):
    today = datetime.today().date()
    conn = get_db_connection()
    cursor = conn.cursor()
    tasks = []

    try:
        # First Irrigation
        cursor.execute("""
            SELECT crop_name, field_name 
            FROM crop_reminders 
            WHERE user_id = %s AND first_irrigation_date = %s
        """, (current_user_id, today))
        for row in cursor.fetchall():
            tasks.append({
                "crop_name": row[0],
                "field_name": row[1],
                "task": "First Irrigation Needed"
            })

        # Second Irrigation
        cursor.execute("""
            SELECT crop_name, field_name 
            FROM crop_reminders 
            WHERE user_id = %s AND second_irrigation_date = %s
        """, (current_user_id, today))
        for row in cursor.fetchall():
            tasks.append({
                "crop_name": row[0],
                "field_name": row[1],
                "task": "Second Irrigation Needed"
            })

        # Urea Dose
        cursor.execute("""
            SELECT crop_name, field_name 
            FROM crop_reminders 
            WHERE user_id = %s AND urea_dose_date = %s
        """, (current_user_id, today))
        for row in cursor.fetchall():
            tasks.append({
                "crop_name": row[0],
                "field_name": row[1],
                "task": "Apply Urea Fertilizer"
            })

        if tasks:
            return jsonify({
                "success": True,
                "message": f"You have {len(tasks)} task(s) today!",
                "total_tasks": len(tasks),
                "tasks": tasks
            })
        else:
            return jsonify({
                "success": True,
                "message": "No tasks today! Enjoy your day",
                "total_tasks": 0,
                "tasks": []
            })

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()
        conn.close()