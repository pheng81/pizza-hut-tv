#!/usr/bin/env python3
import sqlite3

conn = sqlite3.connect('database.db')
cur = conn.cursor()

print("="*60)
print("ALL USERS IN DATABASE:")
print("="*60)
rows = cur.execute('SELECT username, link_code, email_verified, full_name FROM users ORDER BY username').fetchall()
for username, code, verified, full_name in rows:
    print(f'{username:40} | code: {code:4} | verified: {verified} | name: {full_name}')

print("\n" + "="*60)
print("CHECKING CODE 6005:")
print("="*60)
row = cur.execute('SELECT username, link_code FROM users WHERE link_code = ?', ('6005',)).fetchone()
if row:
    print(f'✓ Code 6005 belongs to: {row[0]}')
else:
    print('✗ Code 6005 NOT FOUND in database')

conn.close()
