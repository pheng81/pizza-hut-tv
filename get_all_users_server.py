import sqlite3

conn = sqlite3.connect('/var/www/pizza-hut-tv/users.db')
cur = conn.cursor()
rows = cur.execute('SELECT username, link_code FROM users').fetchall()

print("All users:")
for username, code in rows:
    print(f"  {username} -> {code}")
