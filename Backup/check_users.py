"""
Check users in database and create test login
"""
import sqlite3
import os

# Check which database to use
db_path = os.environ.get('USERS_DB_PATH') or 'database.db'
print(f"Using database: {db_path}")
print()

try:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check if users table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
    if not cursor.fetchone():
        print("❌ Error: 'users' table does not exist in database!")
        conn.close()
        exit(1)
    
    # Get all users
    cursor.execute("SELECT id, username, email, is_active FROM users")
    users = cursor.fetchall()
    
    if users:
        print(f"✅ Found {len(users)} user(s) in database:")
        print()
        for user in users:
            user_id, username, email, is_active = user
            status = "🟢 Active" if is_active else "🔴 Inactive"
            print(f"   {status} - Username: {username}, Email: {email}, ID: {user_id}")
        print()
        print("You can login with any of these usernames and their passwords.")
        print()
    else:
        print("⚠️ No users found in database!")
        print()
        print("Creating a test user for you...")
        
        from werkzeug.security import generate_password_hash
        
        username = "admin"
        email = "admin@test.com"
        password = "admin123"
        password_hash = generate_password_hash(password)
        
        cursor.execute("""
            INSERT INTO users (username, email, password_hash, is_active)
            VALUES (?, ?, ?, 1)
        """, (username, email, password_hash))
        
        conn.commit()
        
        print(f"✅ Test user created successfully!")
        print()
        print(f"Login Credentials:")
        print(f"  Username: {username}")
        print(f"  Password: {password}")
        print()
    
    conn.close()
    
except Exception as e:
    print(f"❌ Database error: {e}")
    import traceback
    traceback.print_exc()
