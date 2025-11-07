import sqlite3

conn = sqlite3.connect('database.db')
cursor = conn.cursor()

# Add your user
cursor.execute("""
    INSERT OR REPLACE INTO users (username, password_hash, link_code, full_name) 
    VALUES ('toengpheng@gmail.com', '$2b$12$LKnUj3i9V.DqBcJOy4.8l.DeMjVJVPHtR.H9i/Xhow2g2gQ6kn.3u', '3204', 'Toeng Pheng')
""")

conn.commit()
print("✅ User added successfully!")

# Verify
rows = cursor.execute("SELECT username, link_code, full_name FROM users").fetchall()
print("\nAll users:")
for row in rows:
    print(f"  {row[0]} | Code: {row[1]} | Name: {row[2]}")

conn.close()
