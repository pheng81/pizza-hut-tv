import sqlite3

# Check /var/www database
db = sqlite3.connect('/var/www/pizza-hut-tv/database.db')
c = db.cursor()
c.execute('SELECT username, link_code FROM users WHERE username LIKE "%test9%"')
row = c.fetchone()
print('test9 in /var/www/pizza-hut-tv/database.db:', row)
db.close()

# Check /home/ubuntu database
try:
    db = sqlite3.connect('/home/ubuntu/pizza-hut-tv/database.db')
    c = db.cursor()
    c.execute('SELECT username, link_code FROM users WHERE username LIKE "%test9%"')
    row = c.fetchone()
    print('test9 in /home/ubuntu/pizza-hut-tv/database.db:', row)
    db.close()
except Exception as e:
    print('/home/ubuntu database error:', e)
