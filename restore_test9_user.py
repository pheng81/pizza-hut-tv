import sqlite3
from werkzeug.security import generate_password_hash

# Connect to database
conn = sqlite3.connect("/var/www/pizza-hut-tv/database.db")
cursor = conn.cursor()

# Create test9@gmail.com user
cursor.execute("""
    INSERT OR REPLACE INTO users (id, username, password_hash, link_code, email_verified, is_blocked, full_name)
    VALUES (?, ?, ?, ?, ?, ?, ?)
""", (1, "test9@gmail.com", generate_password_hash("test9"), "8329", 1, 0, "Test 9"))

conn.commit()
print("✓ User test9@gmail.com created with link code 8329")

# Verify
cursor.execute("SELECT id, username, link_code FROM users WHERE username = 'test9@gmail.com'")
result = cursor.fetchone()
print(f"✓ Verified: ID={result[0]}, Username={result[1]}, Code={result[2]}")

conn.close()
