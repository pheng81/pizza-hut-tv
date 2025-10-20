#!/usr/bin/env python3
import sqlite3
import sys

db_path = 'database.db'
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print("=" * 60)
print("CHECKING UNIQUE CONSTRAINTS AND INDEXES")
print("=" * 60)

# Check for UNIQUE constraints
cursor.execute("""
    SELECT sql FROM sqlite_master 
    WHERE type='table' AND name='users'
""")
table_sql = cursor.fetchone()
if table_sql:
    print("\nTable creation SQL:")
    print(table_sql[0])

# Check for indexes
cursor.execute("""
    SELECT name, sql FROM sqlite_master 
    WHERE type='index' AND tbl_name='users'
""")
indexes = cursor.fetchall()
print("\nIndexes on users table:")
for idx_name, idx_sql in indexes:
    print(f"  {idx_name}: {idx_sql}")

# Check current users
cursor.execute("SELECT username, link_code, email_verified, full_name FROM users ORDER BY username")
users = cursor.fetchall()
print(f"\nCurrent users ({len(users)} total):")
for username, code, verified, full_name in users:
    print(f"  {username:40} | code: {code:4} | verified: {verified} | name: {full_name}")

conn.close()
print("\n" + "=" * 60)
