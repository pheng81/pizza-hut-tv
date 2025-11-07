import sqlite3

db = sqlite3.connect('database.db')
cur = db.cursor()
row = cur.execute("SELECT username, link_code FROM users WHERE username='mom.toeng@gmail.com'").fetchone()
if row:
    print(f"✓ User found: {row[0]}")
    print(f"✓ Pairing code: {row[1]}")
else:
    print("✗ User NOT found in database")
db.close()
