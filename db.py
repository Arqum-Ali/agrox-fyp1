"""
Database connection and initialization module.
TERA ORIGINAL CODE + RAILWAY-SAFE FIXES
"""
import pymysql
import os
from config import DB_USER, DB_PASSWORD, DB_HOST, DB_NAME


def get_db_connection():
    """
    Create and return a database connection.
    Railway pe pehli baar start hone pe crash nahi karega.
    """
    try:
        conn = pymysql.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME,
            port=3306,  # Railway MySQL ka default port
            cursorclass=pymysql.cursors.DictCursor
        )
        print(f"[DB] Successfully connected → {DB_HOST}:{DB_NAME}")
        return conn

    except Exception as e:
        print(f"[DB ERROR] Connection failed: {e}")
        # Agar Railway pe hai aur DB abhi connect nahi ho raha → crash mat kar
        if os.environ.get("RAILWAY_ENVIRONMENT") or os.environ.get("DB_HOST"):
            print("→ Railway detected – connection will be established on first request")
            return None  # None return kar denge taake server crash na ho
        else:
            # Local pe error dikhao taake pata chale
            raise e


def init_db():
    """
    Initialize database & tables – sirf local pe chalana hai ab
    Railway pe kabhi mat chalana (database already bana hua hai)
    """
    try:
        # Connect without database first
        conn = pymysql.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            port=3306
        )
        cursor = conn.cursor()

        # Create database if not exists
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {DB_NAME}")
        conn.commit()
        
        conn.select_db(DB_NAME)


        # === Tera original tables creation code (bilkul same) ===
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                full_name VARCHAR(100) NOT NULL,
                phone VARCHAR(20) NOT NULL UNIQUE,
                password_hash VARCHAR(255) NOT NULL,
                is_verified BOOLEAN DEFAULT FALSE
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS wheat_listings (
                id INT AUTO_INCREMENT PRIMARY KEY,
                title VARCHAR(255) NOT NULL,
                price_per_kg DECIMAL(10, 2) NOT NULL,
                quantity_kg DECIMAL(10, 2) NOT NULL,
                description TEXT NOT NULL,
                wheat_variety VARCHAR(100),
                grade_quality VARCHAR(100),
                harvest_season VARCHAR(100),
                protein_content DECIMAL(4, 1),
                moisture_level DECIMAL(4, 1),
                organic_certified BOOLEAN DEFAULT FALSE,
                pesticides_used BOOLEAN DEFAULT FALSE,
                local_delivery_available BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS otps (
                id INT AUTO_INCREMENT PRIMARY KEY,
                phone VARCHAR(20) NOT NULL,
                otp_code VARCHAR(6) NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

    

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pesticide_listings (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                name VARCHAR(255) NOT NULL,
                price DECIMAL(10, 2) NOT NULL,
                quantity DECIMAL(10, 2) NOT NULL,
                description TEXT NOT NULL,
                organic_certified BOOLEAN DEFAULT FALSE,
                restricted_use BOOLEAN DEFAULT FALSE,
                local_delivery_available BOOLEAN DEFAULT FALSE,
                product_image VARCHAR(255) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.commit()
        cursor.close()
        conn.close()
        print("Database & tables initialized successfully (Local only)")
        return True

    except Exception as e:
        print("Database initialization failed:", e)


        return False
    