#!/usr/bin/env python3
import sqlite3
import json
import sys

conn = sqlite3.connect('pizza_hut_tv.db')
c = conn.cursor()

# First, list all tables
print("Available tables:")
c.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = c.fetchall()
for table in tables:
    print(f"  - {table[0]}")

print("\n" + "="*80)

# Find test9 in whatever user table exists
for table_name in ['users', 'user', 'accounts', 'store_users']:
    try:
        c.execute(f'SELECT * FROM {table_name} WHERE username=? OR code=?', ('test9', 'test9'))
        user = c.fetchone()
        if user:
            print(f"\nFound in table: {table_name}")
            print(f"User data: {user}")
            break
    except:
        continue

conn.close()
