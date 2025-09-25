import sqlite3
import time

# Create the database and users table if they don't exist
try:
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Create users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY, 
            username TEXT UNIQUE, 
            password_hash TEXT, 
            link_code TEXT, 
            verify_token TEXT, 
            verify_sent_at INTEGER
        )
    ''')
    
    # Insert kayson5@gmail.com with pairing code 1000
    cursor.execute('''
        INSERT OR REPLACE INTO users (username, link_code) 
        VALUES (?, ?)
    ''', ('kayson5@gmail.com', '1000'))
    
    conn.commit()
    
    # Verify the insertion
    cursor.execute('SELECT username, link_code FROM users')
    results = cursor.fetchall()
    for row in results:
        print(f'User: {row["username"]}, Code: {row["link_code"]}')
    
    conn.close()
    print('Database setup completed!')
    
except Exception as e:
    print(f'Database error: {e}')