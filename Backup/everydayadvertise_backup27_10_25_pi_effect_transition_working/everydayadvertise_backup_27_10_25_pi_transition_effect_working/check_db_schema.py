"""
Check database schema and users
"""
import sqlite3
import os

db_path = os.environ.get('USERS_DB_PATH') or 'database.db'
print(f"Using database: {db_path}")
print()

try:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Get table schema
    cursor.execute("PRAGMA table_info(users)")
    columns = cursor.fetchall()
    
    print("Users table columns:")
    for col in columns:
        print(f"  - {col[1]} ({col[2]})")
    print()
    
    # Get all users (without email field)
    cursor.execute("SELECT * FROM users LIMIT 5")
    users = cursor.fetchall()
    
    # Get column names
    cursor.execute("PRAGMA table_info(users)")
    col_names = [col[1] for col in cursor.fetchall()]
    
    print(f"Found {len(users)} user(s):")
    print()
    for user in users:
        user_dict = dict(zip(col_names, user))
        username = user_dict.get('username', 'N/A')
        user_id = user_dict.get('id', 'N/A')
        is_active = user_dict.get('is_active', 0)
        status = "🟢 Active" if is_active else "🔴 Inactive"
        print(f"{status} - ID: {user_id}, Username: {username}")
    print()
    
    conn.close()
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
