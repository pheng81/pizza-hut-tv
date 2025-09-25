import sqlite3

conn = sqlite3.connect('database.db')
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

try:
    cursor.execute('SELECT username, link_code FROM users WHERE username LIKE "%kayson5%"')
    results = cursor.fetchall()
    if results:
        for row in results:
            print(f'Username: {row["username"]}, Current Code: {row["link_code"]}')
    else:
        print('No kayson5 user found')
except Exception as e:
    print(f'Error: {e}')
    
conn.close()