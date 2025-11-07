import sqlite3

conn = sqlite3.connect('database.db')
cursor = conn.cursor()

# Check exact value
row = cursor.execute("SELECT username, link_code, typeof(link_code) as type, length(link_code) as len FROM users WHERE username = 'toengpheng@gmail.com'").fetchone()
if row:
    print(f"Username: {row[0]}")
    print(f"Link Code: '{row[1]}'")
    print(f"Type: {row[2]}")
    print(f"Length: {row[3]}")
    print(f"Is None: {row[1] is None}")
    print(f"Is Empty: {row[1] == ''}")
    print(f"Truthy: {bool(row[1])}")
else:
    print("User not found!")

conn.close()
