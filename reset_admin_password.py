#!/usr/bin/env python3
"""Reset admin password for test9@gmail.com"""
import sqlite3
from werkzeug.security import generate_password_hash

# New password
NEW_PASSWORD = "admin123"  # Change this to whatever you want

# Connect to database
db = sqlite3.connect('database.db')

# Update password
hashed = generate_password_hash(NEW_PASSWORD)
db.execute('UPDATE users SET password = ? WHERE username = ?', (hashed, 'test9@gmail.com'))
db.commit()

print(f"✅ Password reset successfully!")
print(f"Username: test9@gmail.com")
print(f"Password: {NEW_PASSWORD}")
print(f"\n🔒 Make sure to change the password after logging in!")

db.close()
