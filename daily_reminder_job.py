# daily_reminder_job.py  ←←← YE PURA REPLACE KAR DO (TASK SCHEDULER KE LIYE PERFECT)
import sys
import os
# Project folder ko path mein add kar do (yeh zaroori hai Task Scheduler ke liye)
sys.path.append(r"D:\fyp\backend")

from app import create_app
from flask_mail import Message
from db import get_db_connection
from config import mail
from datetime import date

# App aur mail ko properly initialize karo
app = create_app()
with app.app_context():
    mail.init_app(app)

    def send_reminders():
        today = date.today()
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT u.email, COALESCE(u.full_name,'Farmer'), c.crop_name, c.field_name,
                   CASE WHEN c.first_irrigation_date=%s THEN 'First Irrigation'
                        WHEN c.second_irrigation_date=%s THEN 'Second Irrigation' 
                        WHEN c.urea_dose_date=%s THEN 'Apply Urea'
                   END as task
            FROM crop_reminders c
            JOIN users u ON c.user_id = u.id
            WHERE (c.first_irrigation_date=%s OR c.second_irrigation_date=%s OR c.urea_dose_date=%s)
              AND u.email IS NOT NULL AND u.email!=''
        """, (today, today, today, today, today, today))

        rows = cursor.fetchall()
        cursor.close()
        conn.close()

        if not rows:
            print(f"[{today}] No reminders today")
            return

        tasks_by_email = {}
        for r in rows:
            email = r['email']
            if email not in tasks_by_email:
                tasks_by_email[email] = []
            tasks_by_email[email].append(f"• {r['crop_name']} ({r['field_name']}) → {r['task']}")

        for email, tasks in tasks_by_email.items():
            msg = Message("Today's Farming Reminder", sender="arhumdoger@gmail.com", recipients=[email])
            msg.html = f"<h3>Hello!</h3><p>Today's tasks:</p><ul>" + "".join(f"<li>{t}</li>" for t in tasks) + "</ul><p>Good luck!</p>"
            try:
                mail.send(msg)
                print(f"EMAIL SENT → {email}")
            except Exception as e:
                print(f"FAILED → {email} | {e}")

    send_reminders()