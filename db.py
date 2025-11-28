"""
Database connection and initialization module.
"""
import pymysql
from config import DB_USER, DB_PASSWORD, DB_HOST, DB_NAME

def get_db_connection():
    """
    Create and return a database connection.
    
    Returns:
        pymysql.connections.Connection: Database connection object
    """
    try:
        conn = pymysql.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME,
            cursorclass=pymysql.cursors.DictCursor  # ✅ Important: returns dict rows instead of tuples
        )
        # ✅ Debug print to confirm connection success
        # (you can remove this after testing)
        print(f"[DB] Connected successfully to database '{DB_NAME}' with DictCursor.")
        return conn

    except Exception as e:
        print(f"[DB ERROR] Connection failed: {e}")
        raise e


def init_db():
    """
    Initialize the database and create required tables if they don't exist.
    
    Returns:
        bool: True if initialization was successful, False otherwise
    """
    try:
        # Connect to MySQL server (without selecting a database)
        conn = pymysql.connect(
            host=DB_HOST, 
            user=DB_USER, 
            password=DB_PASSWORD
        )
        cursor = conn.cursor()
        
        # Create database if it doesn't exist
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {DB_NAME}")
        conn.commit()
        
        # Select the database
        conn.select_db(DB_NAME)
        
        # Create users table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                full_name VARCHAR(100) NOT NULL,
                phone VARCHAR(20) NOT NULL UNIQUE,
                password_hash VARCHAR(255) NOT NULL,
                is_verified BOOLEAN DEFAULT FALSE
            )
        """)
        
        # Create wheat_listings table
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
        
        # Create OTPs table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS otps (
                id INT AUTO_INCREMENT PRIMARY KEY,
                phone VARCHAR(20) NOT NULL,
                otp_code VARCHAR(6) NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Create pesticide_listings table
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
        
        # Commit changes and close connection
        conn.commit()
        cursor.close()
        conn.close()
        
        print("Database initialized successfully ✅")
        return True
        
    except Exception as e: 
        print("Database initialization failed ❌:", e)
        return False
