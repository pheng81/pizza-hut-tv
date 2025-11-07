import sqlite3

# Check database.db
print("=== Checking database.db ===")
try:
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    rows = cursor.execute("SELECT username, link_code FROM users LIMIT 5").fetchall()
    for row in rows:
        print(f"  User: {row[0]}, Code: {row[1]}")
    conn.close()
except Exception as e:
    print(f"  Error: {e}")

print("\n=== Checking users.sqlite ===")
try:
    conn = sqlite3.connect('users.sqlite')
    cursor = conn.cursor()
    rows = cursor.execute("SELECT username, link_code FROM users LIMIT 5").fetchall()
    for row in rows:
        print(f"  User: {row[0]}, Code: {row[1]}")
    conn.close()
except Exception as e:
    print(f"  Error: {e}")
