import sqlite3
import sys

db_file = sys.argv[1] if len(sys.argv) > 1 else 'users.sqlite'
print(f"Checking {db_file}...")

try:
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    
    # Check if link_code column exists
    cursor.execute("PRAGMA table_info(users)")
    columns = cursor.fetchall()
    print(f"\nColumns in users table:")
    for col in columns:
        print(f"  {col[1]} ({col[2]})")
    
    # Try to get users with link_code
    rows = cursor.execute("SELECT username, link_code FROM users").fetchall()
    print(f"\nUsers with link_codes:")
    for row in rows:
        print(f"  User: {row[0]}, Code: {row[1]}")
    
    conn.close()
except Exception as e:
    print(f"Error: {e}")
