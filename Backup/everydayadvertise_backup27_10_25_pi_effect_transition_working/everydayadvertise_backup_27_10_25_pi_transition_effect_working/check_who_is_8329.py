import sqlite3

db = sqlite3.connect('database.db')
c = db.cursor()

# Find user with pair code 8329
c.execute('SELECT username, link_code FROM users WHERE link_code = ?', ('8329',))
row = c.fetchone()
print('User with pair code 8329:', row if row else 'NOT FOUND')

# List all users with their codes
print('\nAll users:')
c.execute('SELECT username, link_code FROM users ORDER BY username')
for row in c.fetchall():
    print(f'  {row[0]:40} code: {row[1]}')

db.close()
