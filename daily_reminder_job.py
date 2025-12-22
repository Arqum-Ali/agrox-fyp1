# daily_reminder_job.py → FINAL 100% WORKING VERSION (November 2025)
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))  # Agar backend folder mein hai to

from app import create_app
from db import get_db_connection
from config import mail
from datetime import date
from flask_mail import Message

# Flask app context banate hain
app = create_app()
with app.app_context():
    mail.init_app(app)

    def send_daily_reminders():
        today = date.today()
        print(f"[{today}] Daily Reminder Job Shuru Ho Gaya...")

        conn = get_db_connection()
        cursor = conn.cursor()

        try:
            # Sirf pending tasks (done nahi hue) + date aaj ya pehle ki
            cursor.execute("""
                SELECT 
                    u.id as user_id,
                    u.email,
                    COALESCE(u.full_name, 'Farmer') as full_name,
                    c.id as reminder_id,
                    c.crop_name,
                    c.field_name,
                    
                    c.first_irrigation_date,
                    c.second_irrigation_date,
                    c.urea_dose_date,
                    c.first_irrigation_done,
                    c.second_irrigation_done,
                    c.urea_dose_done
                FROM crop_reminders c
                JOIN users u ON c.user_id = u.id
                WHERE u.email IS NOT NULL AND u.email != ''
                  AND (
                    (c.first_irrigation_date <= %s AND c.first_irrigation_done = FALSE) OR
                    (c.second_irrigation_date <= %s AND c.second_irrigation_done = FALSE) OR
                    (c.urea_dose_date <= %s AND c.urea_dose_done = FALSE)
                  )
                ORDER BY u.email
            """, (today, today, today))

            rows = cursor.fetchall()
            if not rows:
                print("Aaj koi pending task nahi → Email nahi bheja.")
                return

            # Group by user email
            users = {}
            for row in rows:
                email = row["email"]
                if email not in users:
                    users[email] = {
                        "name": row["full_name"],
                        "tasks": []
                    }

                def add_task(task_name, date_col, done_col):
                    if row[date_col] and row[date_col] <= today and not row[done_col]:
                        days_ago = (today - row[date_col]).days
                        if days_ago == 0:
                            status = "Aaj"
                        elif days_ago == 1:
                            status = "Kal"
                        else:
                            status = f"{days_ago} din pehle"

                        users[email]["tasks"].append(
                            f"• {row['crop_name']} ({row['field_name']}) → {task_name} ({status})"
                        )

                add_task("Pehli Irrigation", "first_irrigation_date", "first_irrigation_done")
                add_task("Doosri Irrigation", "second_irrigation_date", "second_irrigation_done")
                add_task("Urea Dalna Hai", "urea_dose_date", "urea_dose_done")

            # Ab emails bhejo
            sent_count = 0
            for email, data in users.items():
                if not data["tasks"]:
                    continue

                msg = Message(
                    subject="AgroX Reminder – Aaj Ke Zaroori Kaam!",
                    sender="arhumdoger@gmail.com",
                    recipients=[email]
                )

                task_list = "<br>".join(data["tasks"])
                msg.html = f"""
                <div style="font-family: Arial; max-width: 600px; margin: auto; padding: 20px; border: 1px solid #ddd; border-radius: 10px;">
                    <h2 style="color: #2e7d32;">As-salāmu ʿalaikum {data['name']}!</h2>
                    <p>Yeh kaam abhi tak pending hain:</p>
                    <div style="background:#f9f9f9; padding:15px; border-radius:8px; font-size:16px;">
                        {task_list}
                    </div>
                    <br>
                    <p><strong>Jaldi se AgroX app kholo aur "Done" mark kar do!</strong></p>
                    <hr>
                    <small>— AgroX Team<br>
                </div>
                """

                try:
                    mail.send(msg)
                    print(f"Email Bheja → {email} ({len(data['tasks'])} tasks)")
                    sent_count += 1
                except Exception as e:
                    print(f"Email FAIL → {email} | Error: {e}")

            print(f"Job Khatam! Total Emails Bheje: {sent_count}")

        except Exception as e:
            print(f"CRITICAL ERROR: {e}")
        finally:
            cursor.close()
            conn.close()

    # Run karo!
    send_daily_reminders()