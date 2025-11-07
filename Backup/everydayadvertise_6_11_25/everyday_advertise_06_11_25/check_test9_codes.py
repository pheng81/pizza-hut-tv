import sqlite3

db = sqlite3.connect('database.db')
c = db.cursor()

# Find user with pair code 8329
c.execute('SELECT username, link_code FROM users WHERE link_code = ?', ('8329',))
row = c.fetchone()
print('User with pair code 8329:', row)

# Find test9 user
c.execute('SELECT username, link_code FROM users WHERE username LIKE "%test9%"')
row = c.fetchone()
print('test9@gmail.com has pair code:', row)

db.close()
