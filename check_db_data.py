import sqlite3
import sys

db_path = sys.argv[1] if len(sys.argv) > 1 else 'database.db'

try:
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    
    # Check tables
    tables = c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    print("Tables:", [t[0] for t in tables])
    
    # Check counts
    try:
        media_count = c.execute("SELECT COUNT(*) FROM media").fetchone()[0]
        print(f"Media records: {media_count}")
    except:
        print("Media table doesn't exist or has no data")
    
    try:
        users_count = c.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        print(f"Users records: {users_count}")
        
        # Show users
        users = c.execute("SELECT email FROM users LIMIT 5").fetchall()
        print("Sample users:", [u[0] for u in users])
    except:
        print("Users table doesn't exist or has no data")
    
    try:
        stores_count = c.execute("SELECT COUNT(*) FROM stores").fetchone()[0]
        print(f"Stores records: {stores_count}")
    except:
        print("Stores table doesn't exist or has no data")
        
    conn.close()
except Exception as e:
    print(f"Error: {e}")
