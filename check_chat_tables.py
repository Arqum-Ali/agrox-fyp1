import mysql.connector

DB_CONFIG = {
    'user': 'root',
    'password': '1234',
    'host': 'localhost',
    'database': 'agrox_fyp'
}

try:
    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor()
    
    # Check for chat tables
    cursor.execute("SHOW TABLES LIKE 'chat%'")
    tables = cursor.fetchall()
    
    print("Chat tables found:", tables)
    
    if not tables:
        print("\n❌ ERROR: No chat tables found!")
        print("You need to run the SQL schema to create chat_rooms and chat_messages tables")
    else:
        print(f"\n✅ Found {len(tables)} chat table(s)")
        
        # Check structure
        for table in tables:
            table_name = table[0]
            print(f"\nTable: {table_name}")
            cursor.execute(f"DESCRIBE {table_name}")
            columns = cursor.fetchall()
            for col in columns:
                print(f"  - {col[0]} ({col[1]})")
    
    cursor.close()
    conn.close()
    
except Exception as e:
    print(f"Error: {e}")
