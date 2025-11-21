import sqlite3

# Check all users with this phone number
db = sqlite3.connect('/var/www/pizza-hut-tv/database.db')
cursor = db.cursor()

# Find all users with this phone
cursor.execute("""
    SELECT username, phone_number, phone_verified 
    FROM users 
    WHERE phone_number LIKE '%0403666669%' OR phone_number LIKE '%61403666669%'
""")

users = cursor.fetchall()

if users:
    print("Found users with this phone:")
    for user in users:
        print(f"  - {user[0]}: {user[1]} (verified: {user[2]})")
    
    print("\nClearing all...")
    cursor.execute("""
        UPDATE users 
        SET phone_number = NULL, 
            phone_verified = 0, 
            phone_verification_code = NULL, 
            phone_code_sent_at = NULL 
        WHERE phone_number LIKE '%0403666669%' OR phone_number LIKE '%61403666669%'
    """)
    db.commit()
    print("All cleared!")
else:
    print("No users found with this phone number")

db.close()
