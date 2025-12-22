# daily_reminder_job.py - FULL UPDATED VERSION (Land Preparation + Seed Sowing included + Resend API)

from db import get_db_connection
from datetime import date
import os
import requests

# Resend API key (Railway mein add ki hui hogi signup ke liye)
RESEND_API_KEY = os.getenv("RESEND_API_KEY")
RESEND_FROM_EMAIL = "reminders@resend.dev"  # ya jo tu ne banaya wo daal

def send_daily_reminders():
    today = date.today()
    print(f"[{today}] Daily Reminder Job Start — Resend se emails bhej raha hai")

    if not RESEND_API_KEY:
        print("Error: RESEND_API_KEY nahi mili — Railway variables mein check karo")
        return

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Sab 5 tasks check kar raha hai ab (Land Preparation + Seed Sowing bhi include)
        cursor.execute("""
            SELECT 
                u.email,
                COALESCE(u.full_name, 'Farmer') as full_name,
                c.crop_name,
                c.field_name,
                c.land_preparation_date,
                c.seed_sowing_date,
                c.first_irrigation_date,
                c.second_irrigation_date,
                c.urea_dose_date,
                c.land_preparation_done,
                c.seed_sowing_done,
                c.first_irrigation_done,
                c.second_irrigation_done,
                c.urea_dose_done
            FROM crop_reminders c
            JOIN users u ON c.user_id = u.id
            WHERE u.email IS NOT NULL AND u.email != ''
              AND (
                (c.land_preparation_date <= %s AND c.land_preparation_done = FALSE) OR
                (c.seed_sowing_date <= %s AND c.seed_sowing_done = FALSE) OR
                (c.first_irrigation_date <= %s AND c.first_irrigation_done = FALSE) OR
                (c.second_irrigation_date <= %s AND c.second_irrigation_done = FALSE) OR
                (c.urea_dose_date <= %s AND c.urea_dose_done = FALSE)
              )
        """, (today, today, today, today, today))

        rows = cursor.fetchall()

        if not rows:
            print("Aaj koi pending task nahi — email nahi bheji")
            return

        users = {}
        for row in rows:
            email = row["email"]
            if email not in users:
                users[email] = {
                    "name": row["full_name"],
                    "tasks": []
                }

            def add_task(name, date_col, done_col):
                if row[date_col] and row[date_col] <= today and not row[done_col]:
                    days = (today - row[date_col]).days
                    if days == 0:
                        status = "Aaj"
                    elif days == 1:
                        status = "Kal"
                    else:
                        status = f"{days} din pehle"
                    users[email]["tasks"].append(f"• {row['crop_name']} ({row['field_name']}) — {name} ({status})")

            # Sab 5 tasks add kar diye
            add_task("Land Preparation", "land_preparation_date", "land_preparation_done")
            add_task("Seed Sowing", "seed_sowing_date", "seed_sowing_done")
            add_task("Pehli Irrigation", "first_irrigation_date", "first_irrigation_done")
            add_task("Doosri Irrigation", "second_irrigation_date", "second_irrigation_done")
            add_task("Urea Dalna", "urea_dose_date", "urea_dose_done")

        sent_count = 0
        for email, data in users.items():
            if not data["tasks"]:
                continue

            task_list = "<br>".join(data["tasks"])

            payload = {
                "from": FROM_EMAIL,
                "to": [email],
                "subject": "AgroX Reminder — Aaj Ke Zaroori Kaam!",
                "html": f"""
                <div style="font-family: Arial, sans-serif; max-width: 600px; margin: auto; padding: 20px; border: 1px solid #e0e0e0; border-radius: 10px;">
                    <h2 style="color: #1e5d5e;">As-salāmu ʿalaikum {data['name']} bhai!</h2>
                    <p>Pending kaam:</p>
                    <div style="background: #f5f5f5; padding: 15px; border-radius: 8px;">
                        {task_list}
                    </div>
                    <br>
                    <p><strong>AgroX app kholo aur "Done" mark kar do!</strong></p>
                    <p>— AgroX Team</p>
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
                    print(f"Email successfully bheji → {email}")
                    sent_count += 1
                else:
                    print(f"Resend error → {email} | {response.text}")
            except Exception as e:
                print(f"Email send fail → {email} | {e}")

        print(f"Total emails bheji gayi: {sent_count}")

    except Exception as e:
        print(f"Database error: {e}")
    finally:
        cursor.close()
        conn.close()