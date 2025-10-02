import os
import sqlite3

db_path = os.environ.get('USERS_DB_PATH') or 'users.sqlite'
print(f"Environment USERS_DB_PATH: {os.environ.get('USERS_DB_PATH')}")
print(f"Effective DB path: {db_path}")

try:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    rows = cursor.execute("SELECT username, link_code FROM users").fetchall()
    print(f"Found {len(rows)} users in {db_path}")
    for row in rows:
        print(f"  {row[0]}: {row[1]}")
    conn.close()
except Exception as e:
    print(f"Error: {e}")
