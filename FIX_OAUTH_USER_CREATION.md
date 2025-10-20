# Fix OAuth User Creation

## Problem
OAuth users not being created automatically in database. Silent failures due to:
1. `INSERT OR IGNORE` masks errors
2. Empty `except: pass` blocks swallow all exceptions
3. No logging of failures

## Solution

Replace the user creation logic in `app.py` around lines 1067-1083:

### Current (Broken) Code:
```python
try:
    db = get_db()
    uname = (email or '').strip().lower()
    if uname:
        try:
            # Try inserting with full_name if column exists
            db.execute('INSERT OR IGNORE INTO users (username, full_name) VALUES (?, ?)', (uname, userinfo.get('name') or uname))
        except Exception:
            try:
                db.execute('INSERT OR IGNORE INTO users (username) VALUES (?)', (uname,))
            except Exception:
                pass
        db.commit()
        # Mark verified for OAuth sources
        try:
            db.execute('UPDATE users SET email_verified = 1 WHERE username = ?', (uname,))
            db.commit()
        except Exception:
            pass
        _ensure_user_link_code(uname)
except Exception:
    pass
```

### Fixed Code:
```python
try:
    db = get_db()
    uname = (email or '').strip().lower()
    if uname:
        try:
            # Check if user exists
            existing = db.execute('SELECT username FROM users WHERE username = ?', (uname,)).fetchone()
            
            if existing:
                # User exists - update full_name and email_verified
                logging.info(f'OAuth: User {uname} exists, updating info')
                db.execute(
                    'UPDATE users SET full_name = ?, email_verified = 1 WHERE username = ?',
                    (userinfo.get('name') or uname, uname)
                )
            else:
                # New user - insert
                logging.info(f'OAuth: Creating new user {uname}')
                db.execute(
                    'INSERT INTO users (username, full_name, email_verified) VALUES (?, ?, 1)',
                    (uname, userinfo.get('name') or uname)
                )
            
            db.commit()
            logging.info(f'✓ OAuth: User {uname} saved successfully')
            _ensure_user_link_code(uname)
            
        except Exception as e:
            logging.error(f'✗ OAuth: Failed to save user {uname}: {e}')
            db.rollback()
            # Don't fail the login - user can still use the system
            
except Exception as e:
    logging.error(f'✗ OAuth: User creation failed completely: {e}')
```

## Key Changes:
1. **Check if user exists first** - explicit SELECT query
2. **UPDATE existing users** instead of ignoring duplicates
3. **Proper error logging** - shows exactly what went wrong
4. **Set email_verified=1 in INSERT** - one statement instead of two
5. **Rollback on error** - maintain database integrity
6. **Don't fail login on db error** - user can still access dashboard

## Testing:
1. Delete mom.toeng@gmail.com from database
2. Log in via Google OAuth
3. Check logs for "✓ OAuth: User ... saved successfully"
4. Verify user in database with correct code
