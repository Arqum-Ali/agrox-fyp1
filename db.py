"""
Database connection for Supabase (PostgreSQL) - Windows friendly
"""
import psycopg2
from psycopg2.extras import DictCursor
from config import SUPABASE_DB_HOST, SUPABASE_DB_PORT, SUPABASE_DB_NAME, SUPABASE_DB_USER, SUPABASE_DB_PASSWORD

def get_db_connection():
    """Supabase Postgres connection with separate parameters (Windows safe)"""
    try:
        return psycopg2.connect(
            host=SUPABASE_DB_HOST,
            port=SUPABASE_DB_PORT,
            database=SUPABASE_DB_NAME,
            user=SUPABASE_DB_USER,
            password=SUPABASE_DB_PASSWORD,
            cursor_factory=DictCursor
        )
    except Exception as e:
        print(f"Connection error: {e}")
        return None

def init_db():
    """Test connection only"""
    try:
        conn = get_db_connection()
        if conn:
            conn.close()
            print("Supabase database connection successful!")
            return True
        else:
            return False
    except Exception as e:
        print(f"Database initialization failed: {e}")
        return False