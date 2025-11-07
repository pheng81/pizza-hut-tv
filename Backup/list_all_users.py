import sqlite3

db = sqlite3.connect('database.db')
cur = db.cursor()
rows = cur.execute("SELECT username, link_code FROM users ORDER BY username").fetchall()
print(f"Total users: {len(rows)}\n")
for r in rows:
    code = r[1] if r[1] else "NO CODE"
    print(f"{r[0]:40} -> {code}")
db.close()
