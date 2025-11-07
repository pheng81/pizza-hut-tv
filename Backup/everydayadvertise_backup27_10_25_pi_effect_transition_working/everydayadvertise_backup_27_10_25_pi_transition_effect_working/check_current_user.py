#!/usr/bin/env python3
import sqlite3

conn = sqlite3.connect('database.db')
c = conn.cursor()

print("\n" + "=" * 60)
print("ALL USERS IN DATABASE:")
print("=" * 60)
c.execute('SELECT username, link_code FROM users ORDER BY username')
for username, code in c.fetchall():
    print(f"{username:40} | code: {code}")

conn.close()
