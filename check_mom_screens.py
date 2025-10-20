#!/usr/bin/env python3
import sqlite3

conn = sqlite3.connect('database.db')
c = conn.cursor()

print("\n" + "=" * 80)
print("SCREENS FOR mom.toeng@gmail.com (from playlists table):")
print("=" * 80)

c.execute('''
    SELECT DISTINCT store_id, screen_id 
    FROM playlists 
    WHERE username = ? 
    ORDER BY store_id, screen_id
''', ('mom.toeng@gmail.com',))

rows = c.fetchall()

if rows:
    for store_id, screen_id in rows:
        print(f"  Store {store_id} - Screen {screen_id}")
    print(f"\n{'=' * 80}")
    print(f"Total: {len(rows)} unique screen(s)")
else:
    print("  (No screens found in playlists table)")

print("=" * 80)
conn.close()
