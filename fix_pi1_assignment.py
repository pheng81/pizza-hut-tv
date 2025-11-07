#!/usr/bin/env python3
import sqlite3
import json

# Connect to database
conn = sqlite3.connect('database.db')
cursor = conn.cursor()

# Check table structure
cursor.execute("PRAGMA table_info(users)")
columns = cursor.fetchall()
print("Users table columns:")
for col in columns:
    print(f"  {col[1]} ({col[2]})")

# Get all columns
cursor.execute("SELECT * FROM users LIMIT 1")
if cursor.description:
    col_names = [desc[0] for desc in cursor.description]
    print(f"\nActual columns: {col_names}")

# Try to find user with configuration
cursor.execute("SELECT username FROM users")
users = cursor.fetchall()
print(f"\nFound {len(users)} users:")
for user in users:
    print(f"  - {user[0]}")

conn.close()
