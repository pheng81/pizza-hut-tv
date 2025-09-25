import sqlite3

conn = sqlite3.connect('database.db')
cursor = conn.cursor()

# Update the pairing code to 7844
cursor.execute('UPDATE users SET link_code = ? WHERE username = ?', ('7844', 'kayson5@gmail.com'))
conn.commit()

# Verify the update
cursor.execute('SELECT username, link_code FROM users WHERE username = ?', ('kayson5@gmail.com',))
result = cursor.fetchone()
if result:
    print(f'Updated: Username: {result[0]}, Code: {result[1]}')
else:
    print('User not found')

conn.close()