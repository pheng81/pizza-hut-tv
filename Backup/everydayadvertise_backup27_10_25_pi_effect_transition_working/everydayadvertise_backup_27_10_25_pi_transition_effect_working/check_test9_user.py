#!/usr/bin/env python3
import sqlite3

conn = sqlite3.connect('database.db')
cur = conn.cursor()

# Check test9 user
row = cur.execute('SELECT username, link_code, email_verified FROM users WHERE username LIKE "%test9%" OR link_code = "6005"').fetchone()
if row:
    print(f'✓ User found: {row[0]}')
    print(f'  Pair Code: {row[1]}')
    print(f'  Email Verified: {row[2]}')
else:
    print('❌ test9 not found in database')

# List all users
print('\n' + '='*60)
print('ALL USERS IN DATABASE:')
print('='*60)
rows = cur.execute('SELECT username, link_code, email_verified FROM users ORDER BY username').fetchall()
for username, code, verified in rows:
    print(f'  {username:40} | code: {code:4} | verified: {verified}')

conn.close()
