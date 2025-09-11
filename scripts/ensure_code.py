import sqlite3, os, sys, json, random, time

DB = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'users.sqlite'))
if not os.path.exists(DB):
    print(json.dumps({'success': False, 'error': f'db not found: {DB}'}))
    sys.exit(0)

if len(sys.argv) < 2:
    print(json.dumps({'success': False, 'error': 'usage: ensure_code.py <username/email>'}))
    sys.exit(0)

username = sys.argv[1].strip().lower()

con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row
cur = con.cursor()

cur.execute('CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, username TEXT UNIQUE, password_hash TEXT)')
# Backfill link_code column if missing
cols = [r[1] for r in cur.execute('PRAGMA table_info(users)').fetchall()]
if 'link_code' not in cols:
    try:
        cur.execute('ALTER TABLE users ADD COLUMN link_code TEXT')
        cur.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_users_link_code ON users(link_code)')
        con.commit()
    except Exception:
        pass

# Ensure user row exists
try:
    cur.execute('INSERT OR IGNORE INTO users (username) VALUES (?)', (username,))
    con.commit()
except Exception:
    pass

# If user already has a code, return it
row = cur.execute('SELECT link_code FROM users WHERE username = ?', (username,)).fetchone()
if row and row['link_code']:
    print(json.dumps({'success': True, 'username': username, 'code': row['link_code'], 'db': DB}))
    sys.exit(0)

# Generate a unique 4-digit code not used
code = None
for _ in range(50):
    c = str(random.randint(1000, 9999))
    exists = cur.execute('SELECT 1 FROM users WHERE link_code = ?', (c,)).fetchone()
    if not exists:
        code = c
        break
if code is None:
    code = str(int(time.time()))[-4:]

cur.execute('UPDATE users SET link_code = ? WHERE username = ?', (code, username))
con.commit()
print(json.dumps({'success': True, 'username': username, 'code': code, 'db': DB}))
