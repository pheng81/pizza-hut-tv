"""The eligibility gate must say what to do, not only what is wrong."""
import sqlite3, sys, tempfile, os
sys.path.insert(0, r'c:\Users\toeng\Pizza Hut TV')
import app as srv

PASS, FAIL = [], []
def check(n, c, d=''):
    (PASS if c else FAIL).append(n)
    print(('PASS  ' if c else 'FAIL  ') + n + (('  -- ' + d) if d and not c else ''))

tmp = tempfile.mkdtemp(); _n = [0]
def db_with(_no_user=False, **cols):
    _n[0] += 1
    path = os.path.join(tmp, 'e%d.db' % _n[0])
    db = sqlite3.connect(path)
    db.execute('CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT, '
               'email_verified INT, phone_number TEXT, phone_verified INT, role TEXT)')
    if not _no_user:
        db.execute('INSERT INTO users VALUES (1,?,?,?,?,?)',
                   (cols.get('username', 'a@b.com'), cols.get('email_verified', 1),
                    cols.get('phone_number', '+61400000000'), cols.get('phone_verified', 1),
                    cols.get('role', 'user')))
    db.commit(); db.close()
    srv._db_path = lambda: path
    return path

print('--- the reported case: phone present but unverified ---')
db_with(phone_number='+61403666669', phone_verified=0)
ok, msg, action = srv._subscription_eligibility(1)
check('blocked', ok is False)
check('action is verify_phone', action == 'verify_phone', str(action))
check('message mentions the phone', 'phone' in (msg or '').lower(), str(msg))

print('')
print('--- no phone at all is a different job ---')
db_with(phone_number='', phone_verified=0)
ok, msg, action = srv._subscription_eligibility(1)
check('action is add_phone, not verify_phone', action == 'add_phone', str(action))
check('message says add', 'add' in (msg or '').lower(), str(msg))

print('')
print('--- email comes first ---')
db_with(email_verified=0, phone_number='', phone_verified=0)
ok, msg, action = srv._subscription_eligibility(1)
check('action is verify_email', action == 'verify_email', str(action))

print('')
print('--- eligible and admin ---')
db_with()
ok, msg, action = srv._subscription_eligibility(1)
check('eligible user: no message, no action', ok and msg is None and action is None, str((ok, msg, action)))
db_with(role='admin', email_verified=0, phone_number='', phone_verified=0)
ok, msg, action = srv._subscription_eligibility(1)
check('admin bypasses everything', ok and action is None, str((ok, action)))

print('')
print('--- missing user ---')
db_with()
ok, msg, action = srv._subscription_eligibility(999)
check('unknown user -> login', action == 'login', str(action))

print('')
print('--- the old wrapper still works for existing callers ---')
db_with(phone_verified=0)
res = srv._check_subscription_eligibility(1)
check('returns a 2-tuple', isinstance(res, tuple) and len(res) == 2, str(res))
check('same verdict', res[0] is False and 'phone' in (res[1] or '').lower(), str(res))

print('')
print('=' * 60)
print('%d passed, %d failed' % (len(PASS), len(FAIL)))
for f in FAIL: print('  FAILED:', f)
print('=' * 60)
sys.exit(1 if FAIL else 0)
