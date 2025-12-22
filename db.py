"""
Database connection using Supabase Pooler (IPv4 compatible for Railway)
"""
import psycopg2
from psycopg2.extras import DictCursor
import os

# Railway se environment variable se load
DATABASE_URL = os.getenv('DATABASE_URL')

def get_db_connection():
    try:
        return psycopg2.connect(
            DATABASE_URL,
            cursor_factory=DictCursor,
            sslmode='require'
        )
    except Exception as e:
        print(f"Connection error: {e}")
        return None

def init_db():
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