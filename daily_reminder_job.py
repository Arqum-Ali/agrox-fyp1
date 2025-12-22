# daily_reminder_job.py - Resend API se emails bhejega (same as signup/forget)

from db import get_db_connection
from datetime import date
import os
import requests

# Railway environment variable se Resend API key le ga (jo tu ne signup ke liye add ki hai)
RESEND_API_KEY = os.getenv("RESEND_API_KEY")
FROM_EMAIL = "arhumdoger@gmail.com"  # Ya jo verified email hai Resend mein

def send_daily_reminders():
    today = date.today()
    print(f"[{today}] Daily Reminder Job Shuru Ho Gaya... (Resend se emails bhej raha hai)")

    if not RESEND_API_KEY:
        print("Error: RESEND_API_KEY nahi mili environment variables mein")
        return

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT 
                u.email,
                COALESCE(u.full_name, 'Farmer') as full_name,
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

        sent_count = 0
        for email, data in users.items():
            if not data["tasks"]:
                continue

            task_list = "<br>".join(data["tasks"])

            payload = {
                "from": f"AgroX <{FROM_EMAIL}>",
                "to": [email],
                "subject": "AgroX Reminder – Aaj Ke Zaroori Kaam!",
                "html": f"""
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
            }

            headers = {
                "Authorization": f"Bearer {RESEND_API_KEY}",
                "Content-Type": "application/json"
            }

            try:
                response = requests.post("https://api.resend.com/emails", json=payload, headers=headers)
                if response.status_code == 200:
                    print(f"Email Bheja → {email} ({len(data['tasks'])} tasks)")
                    sent_count += 1
                else:
                    print(f"Resend Error → {email} | {response.text}")
            except Exception as e:
                print(f"Email FAIL → {email} | Error: {e}")

        print(f"Job Khatam! Total Emails Bheje: {sent_count}")

    except Exception as e:
        print(f"CRITICAL ERROR: {e}")
    finally:
        cursor.close()
        conn.close()