import sqlite3, json, os, sys
DB = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'users.sqlite'))
if not os.path.exists(DB):
    print(json.dumps({'success': False, 'error': f'db not found: {DB}'}))
    sys.exit(0)
con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row
rows = con.execute('SELECT username, link_code FROM users WHERE link_code IS NOT NULL AND link_code <> "" LIMIT 10').fetchall()
print(json.dumps({'success': True, 'db': DB, 'rows': [dict(r) for r in rows]}))
