# reminder_views.py - FIXED & FINAL VERSION (Lowercase column names for Supabase compatibility)

from flask import Blueprint, request, jsonify
from datetime import datetime, timedelta, date
from db import get_db_connection
import jwt
from functools import wraps
from config import SECRET_KEY

reminder_bp = Blueprint("reminder", __name__, url_prefix="/reminder")

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return jsonify({"error": "Token missing or invalid format"}), 401

        try:
            token = auth_header.split(" ")[1]
            payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
            current_user_id = payload["user_id"]
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Token expired"}), 401
        except:
            return jsonify({"error": "Invalid token"}), 401

        return f(current_user_id, *args, **kwargs)
    return decorated


# ADD CROP REMINDER
@reminder_bp.route("/add", methods=["POST"])
@token_required
def add_crop_reminder(current_user_id):
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    crop_name = data.get("crop_name")
    planting_date_str = data.get("planting_date")
    field_name = data.get("field_name")

    if not all([crop_name, planting_date_str, field_name]):
        return jsonify({"error": "Missing required fields"}), 400

    try:
        planting_date = datetime.strptime(planting_date_str, "%Y-%m-%d").date()
    except ValueError:
        return jsonify({"error": "Invalid date format. Use YYYY-MM-DD"}), 400

    # Auto dates
    land_preparation_date = planting_date + timedelta(days=0)
    seed_sowing_date      = planting_date + timedelta(days=14)
    first_irrigation_date = planting_date + timedelta(days=20)
    second_irrigation_date = planting_date + timedelta(days=28)
    urea_dose_date        = planting_date + timedelta(days=35)

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            INSERT INTO crop_reminders (
                user_id, crop_name, planting_date, field_name,
                land_preparation_date, seed_sowing_date,
                first_irrigation_date, second_irrigation_date, urea_dose_date,
                Land_preparation_done, seed_sowing_done,
                first_irrigation_done, second_irrigation_done, urea_dose_done,
                created_at
            ) VALUES (
                %s, %s, %s, %s,
                %s, %s,
                %s, %s, %s,
                FALSE, FALSE,
                FALSE, FALSE, FALSE,
                NOW()
            )
        """, (
            current_user_id, crop_name, planting_date, field_name,
            land_preparation_date, seed_sowing_date,
            first_irrigation_date, second_irrigation_date, urea_dose_date
        ))

        conn.commit()
        return jsonify({"message": "Crop reminder added successfully!"}), 201

    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()
        conn.close()


# MY CROPS
@reminder_bp.route("/my_crops", methods=["GET"])
@token_required
def get_my_reminders(current_user_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT 
                id, crop_name, field_name, planting_date,
                land_preparation_date, seed_sowing_date,
                first_irrigation_date, second_irrigation_date, urea_dose_date,
                Land_preparation_done, seed_sowing_done,
                first_irrigation_done, second_irrigation_done, urea_dose_done
            FROM crop_reminders 
            WHERE user_id = %s
            ORDER BY id DESC
        """, (current_user_id,))

        rows = cursor.fetchall()
        reminders = []

        for row in rows:
            all_tasks_done = (
                row["Land_preparation_done"] and 
                row["seed_sowing_done"] and 
                row["first_irrigation_done"] and 
                row["second_irrigation_done"] and 
                row["urea_dose_done"]
            )
            crop_status = "completed" if all_tasks_done else "pending"
            
            reminders.append({
                "id": row["id"],
                "crop_name": row["crop_name"],
                "field_name": row["field_name"],
                "planting_date": row["planting_date"].strftime("%Y-%m-%d"),
                "crop_status": crop_status,

                "land_preparation": {                                
                    "date": row["land_preparation_date"].strftime("%Y-%m-%d") if row["land_preparation_date"] else None,
                    "done": bool(row["Land_preparation_done"])
                },
                "seed_sowing": {
                    "date": row["seed_sowing_date"].strftime("%Y-%m-%d") if row["seed_sowing_date"] else None,
                    "done": bool(row["seed_sowing_done"])
                },
                "first_irrigation": {
                    "date": row["first_irrigation_date"].strftime("%Y-%m-%d") if row["first_irrigation_date"] else None,
                    "done": bool(row["first_irrigation_done"])
                },
                "second_irrigation": {
                    "date": row["second_irrigation_date"].strftime("%Y-%m-%d") if row["second_irrigation_date"] else None,
                    "done": bool(row["second_irrigation_done"])
                },
                "urea_dose": {
                    "date": row["urea_dose_date"].strftime("%Y-%m-%d") if row["urea_dose_date"] else None,
                    "done": bool(row["urea_dose_done"])
                }
            })

        return jsonify({"reminders": reminders}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()
        conn.close()


# MARK TASK DONE
@reminder_bp.route("/mark-task-done", methods=["POST"])
@token_required
def mark_task_done(current_user_id):
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    reminder_id = data.get("reminder_id")
    task_type = data.get("task_type")

    if not reminder_id or not task_type:
        return jsonify({"error": "Missing reminder_id or task_type"}), 400

    valid_tasks = ["land_preparation", "seed_sowing", "first_irrigation", "second_irrigation", "urea_dose"]
    if task_type not in valid_tasks:
        return jsonify({"error": f"Invalid task_type"}), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Check ownership
        cursor.execute("SELECT user_id FROM crop_reminders WHERE id = %s", (reminder_id,))
        row = cursor.fetchone()
        if not row or row["user_id"] != current_user_id:
            return jsonify({"error": "Not authorized"}), 404

        # Map task_type → correct column
        column_map = {
            "land_preparation": "Land_preparation_done",
            "seed_sowing": "seed_sowing_done",
            "first_irrigation": "first_irrigation_done",
            "second_irrigation": "second_irrigation_done",
            "urea_dose": "urea_dose_done"
        }
        column = column_map[task_type]

        cursor.execute(f"UPDATE crop_reminders SET {column} = TRUE WHERE id = %s", (reminder_id,))
        conn.commit()

        return jsonify({"success": True, "message": f"{task_type.replace('_', ' ').title()} marked as done!"}), 200

    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()
        conn.close()