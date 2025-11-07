#!/usr/bin/env python3
import sqlite3

conn = sqlite3.connect('database.db')
cur = conn.cursor()

username = 'test9@gmail.com'
desired_code = '6005'

# Check if test9 exists
row = cur.execute('SELECT username, link_code FROM users WHERE username = ?', (username,)).fetchone()

if row:
    print(f'✓ {username} already exists with code: {row[1]}')
    if row[1] != desired_code:
        print(f'⚠ Updating code from {row[1]} to {desired_code}')
        cur.execute('UPDATE users SET link_code = ? WHERE username = ?', (desired_code, username))
        conn.commit()
        print(f'✓ Updated to code: {desired_code}')
else:
    # Check if code 6005 is already taken
    code_owner = cur.execute('SELECT username FROM users WHERE link_code = ?', (desired_code,)).fetchone()
    if code_owner:
        print(f'❌ Code {desired_code} is already used by {code_owner[0]}')
    else:
        # Insert test9 with code 6005
        cur.execute('INSERT INTO users (username, link_code, email_verified) VALUES (?, ?, 1)', (username, desired_code))
        conn.commit()
        print(f'✓ Added {username} with pair code: {desired_code}')

# Final verification
row = cur.execute('SELECT username, link_code, email_verified FROM users WHERE username = ?', (username,)).fetchone()
if row:
    print(f'\n✓ VERIFIED: {row[0]} → code:{row[1]}, verified:{row[2]}')
else:
    print(f'\n❌ FAILED: {username} not found after operation')

conn.close()
