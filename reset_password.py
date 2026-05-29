import sqlite3
from werkzeug.security import generate_password_hash

conn = sqlite3.connect("/var/www/everydayadvertise_tv/database.db")
cursor = conn.cursor()

# Reset password for test9@gmail.com
password_hash = generate_password_hash("test9")
cursor.execute("UPDATE users SET password_hash = ?, email_verified = 1 WHERE username = ?", 
               (password_hash, "test9@gmail.com"))
conn.commit()

# Verify
cursor.execute("SELECT id, username, link_code, email_verified FROM users WHERE username = 'test9@gmail.com'")
result = cursor.fetchone()
if result:
    print(f"✓ User updated: ID={result[0]}, Username={result[1]}, Code={result[2]}, Verified={result[3]}")
    print(f"✓ Login credentials: test9@gmail.com / test9")
else:
    print("✗ User not found!")
    
conn.close()
