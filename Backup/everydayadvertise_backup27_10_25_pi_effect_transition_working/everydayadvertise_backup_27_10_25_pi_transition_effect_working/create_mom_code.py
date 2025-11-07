import sqlite3
import random

db = sqlite3.connect('database.db')
cur = db.cursor()

# Generate a unique 4-digit code
while True:
    code = str(random.randint(1000, 9999))
    existing = cur.execute("SELECT username FROM users WHERE link_code=?", (code,)).fetchone()
    if not existing:
        break

# Update or insert mom.toeng@gmail.com with the new code
username = 'mom.toeng@gmail.com'
cur.execute("UPDATE users SET link_code=? WHERE username=?", (code, username))
if cur.rowcount == 0:
    # User doesn't exist, insert them
    cur.execute("INSERT INTO users (username, link_code) VALUES (?, ?)", (username, code))

db.commit()
db.close()

print(f"✅ Created pairing code for {username}: {code}")
