import sqlite3

db = sqlite3.connect('database.db')
cur = db.cursor()
rows = cur.execute("SELECT username, link_code FROM users WHERE username IN ('mom.toeng@gmail.com', 'toengpheng@gmail.com')").fetchall()
for r in rows:
    print(f'{r[0]} -> code: {r[1] or "NO CODE"}')
db.close()
