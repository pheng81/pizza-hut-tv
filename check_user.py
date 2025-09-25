import sqlite3

try:
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute('SELECT username, link_code FROM users WHERE username LIKE "%kayson5%"')
    results = cursor.fetchall()
    for row in results:
        print(f'User: {row["username"]}, Code: {row["link_code"]}')
    if not results:
        print('No kayson5 user found in database')
    conn.close()
except Exception as e:
    print(f'Database error: {e}')