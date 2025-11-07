import sqlite3

db = sqlite3.connect('database.db')
cur = db.cursor()
row = cur.execute("SELECT username FROM users WHERE link_code='6640'").fetchone()
print(row[0] if row else 'NO USER WITH CODE 6640')
db.close()
