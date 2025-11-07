"""
Create a test user for local database
"""
import sqlite3
from werkzeug.security import generate_password_hash

def create_test_user():
    """Create a test user in local database"""
    
    # User details
    username = "admin"
    email = "admin@test.com"
    password = "admin123"
    
    # Connect to local database
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    
    # Check if user already exists
    cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
    if cursor.fetchone():
        print(f"✅ User '{username}' already exists!")
        conn.close()
        return
    
    # Hash password
    password_hash = generate_password_hash(password)
    
    # Insert user
    cursor.execute("""
        INSERT INTO users (username, email, password_hash, is_active)
        VALUES (?, ?, ?, 1)
    """, (username, email, password_hash))
    
    conn.commit()
    user_id = cursor.lastrowid
    
    print(f"✅ Test user created successfully!")
    print(f"")
    print(f"Login Credentials:")
    print(f"  Username: {username}")
    print(f"  Password: {password}")
    print(f"  Email: {email}")
    print(f"")
    print(f"Use these credentials to login at: http://localhost:5002/login")
    
    conn.close()

if __name__ == "__main__":
    create_test_user()
