import sqlite3
import sys

username_to_check = sys.argv[1] if len(sys.argv) > 1 else "toengpheng@gmail.com"

conn = sqlite3.connect('/home/ubuntu/pizza-hut-tv/database.db')
cursor = conn.cursor()

# Check with exact username
print(f"Checking for username: '{username_to_check}'")
row = cursor.execute("SELECT username, link_code FROM users WHERE username = ?", (username_to_check,)).fetchone()
if row:
    print(f"✅ FOUND: Username='{row[0]}', Code='{row[1]}'")
else:
    print(f"❌ NOT FOUND")
    print("\nAll usernames in database:")
    all_users = cursor.execute("SELECT username FROM users").fetchall()
    for u in all_users:
        print(f"  - '{u[0]}'")

# Check case-insensitive
print(f"\nChecking lowercase: '{username_to_check.lower()}'")
row2 = cursor.execute("SELECT username, link_code FROM users WHERE LOWER(username) = ?", (username_to_check.lower(),)).fetchone()
if row2:
    print(f"✅ FOUND: Username='{row2[0]}', Code='{row2[1]}'")
else:
    print(f"❌ NOT FOUND")

conn.close()
