import sqlite3

db = sqlite3.connect('database.db')
cur = db.cursor()

# Get table schema
cur.execute("PRAGMA table_info(users)")
columns = cur.fetchall()

print("Users table schema:")
for col in columns:
    print(f"  {col[1]} ({col[2]}) - NOT NULL: {col[3]}, DEFAULT: {col[4]}, PK: {col[5]}")

db.close()
