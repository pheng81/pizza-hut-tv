import sqlite3

db = sqlite3.connect('database.db')
cur = db.cursor()

# Add mom.toeng@gmail.com with pairing code 6364
try:
    cur.execute("INSERT INTO users (username, link_code, email_verified) VALUES (?, ?, ?)", 
                ('mom.toeng@gmail.com', '6364', 1))
    db.commit()
    print("✓ User mom.toeng@gmail.com added with code 6364")
except Exception as e:
    print(f"✗ Error: {e}")

# Verify
row = cur.execute("SELECT username, link_code FROM users WHERE username='mom.toeng@gmail.com'").fetchone()
if row:
    print(f"✓ Verified: {row[0]} -> {row[1]}")
else:
    print("✗ User NOT found after insert!")

db.close()
