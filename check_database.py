import sqlite3

conn = sqlite3.connect('database.db')
c = conn.cursor()

# Check tables
print("=== DATABASE TABLES ===")
c.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = c.fetchall()
for table in tables:
    print(f"  - {table[0]}")

# Check if playlist_items table exists
if any('playlist' in str(t).lower() for t in tables):
    print("\n=== PLAYLIST ITEMS FOR STORE 1000 ===")
    try:
        c.execute("SELECT * FROM playlist_items WHERE store_id='1000' OR store_id=1000")
        items = c.fetchall()
        print(f"Total items: {len(items)}")
        for item in items[:10]:  # Show first 10
            print(item)
    except Exception as e:
        print(f"Error: {e}")

conn.close()
