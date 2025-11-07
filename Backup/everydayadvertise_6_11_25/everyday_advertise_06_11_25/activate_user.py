"""
Activate user and reset password
"""
import sqlite3
import os
from werkzeug.security import generate_password_hash

db_path = os.environ.get('USERS_DB_PATH') or 'database.db'
print(f"Using database: {db_path}")
print()

try:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    username = "kayson5@gmail.com"
    new_password = "test123"  # Temporary password for testing
    
    # Activate user and reset password
    password_hash = generate_password_hash(new_password)
    
    # Check if is_active column exists
    cursor.execute("PRAGMA table_info(users)")
    columns = [col[1] for col in cursor.fetchall()]
    
    if 'is_active' in columns:
        cursor.execute("""
            UPDATE users 
            SET password_hash = ?, is_active = 1 
            WHERE username = ?
        """, (password_hash, username))
    else:
        cursor.execute("""
            UPDATE users 
            SET password_hash = ?
            WHERE username = ?
        """, (password_hash, username))
    
    conn.commit()
    
    if cursor.rowcount > 0:
        print(f"✅ User activated and password reset successfully!")
        print()
        print(f"Login Credentials:")
        print(f"  Username: {username}")
        print(f"  Password: {new_password}")
        print()
        print(f"Login at: http://localhost:5002/login")
        print()
    else:
        print(f"⚠️ User not found: {username}")
    
    conn.close()
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
