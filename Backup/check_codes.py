#!/usr/bin/env python3
import sqlite3

conn = sqlite3.connect('database.db')
cur = conn.cursor()

codes = ['6005', '6364', '8624']
rows = cur.execute(f'SELECT username, link_code FROM users WHERE link_code IN ({",".join(["?"] * len(codes))})', codes).fetchall()

print("User codes:")
for username, code in rows:
    print(f'  {username}: {code}')

conn.close()
