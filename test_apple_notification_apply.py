"""Exercise _apply_apple_notification against a throwaway database."""
import os
import sqlite3
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import app as srv

PASS, FAIL = [], []
NOW = int(time.time())
MONTH = 30 * 86400


def check(name, cond, detail=''):
    (PASS if cond else FAIL).append(name)
    print(f'{"PASS" if cond else "FAIL"}  {name}{("  -- " + detail) if detail and not cond else ""}')


tmpdir = tempfile.mkdtemp()
DB = os.path.join(tmpdir, 'test0.db')
srv._db_path = lambda: DB
_counter = [0]


def reset(*, provider='apple', status='active', period_end=NOW + MONTH, product='Screens_3',
          with_purchase=True, original_txn='OT-1'):
    # app.py's get_db() never closes its connection (house pattern), and Windows
    # will not let us delete a file sqlite still holds - so use a fresh file.
    global DB
    _counter[0] += 1
    DB = os.path.join(tmpdir, f'test{_counter[0]}.db')
    db = sqlite3.connect(DB)
    db.execute('CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT, '
               'subscription_status TEXT, subscription_plan TEXT)')
    db.execute('CREATE TABLE subscriptions (user_id INTEGER PRIMARY KEY, '
               'stripe_subscription_id TEXT, status TEXT, current_period_end INTEGER, '
               'trial_end INTEGER, cancel_at_period_end INTEGER, updated_at INTEGER, '
               'billing_provider TEXT, billing_product_id TEXT)')
    db.execute('CREATE TABLE mobile_store_purchases (id INTEGER PRIMARY KEY AUTOINCREMENT, '
               'user_id INTEGER, provider TEXT, product_id TEXT, original_transaction_id TEXT, '
               'status TEXT, expires_at INTEGER, updated_at INTEGER)')
    db.execute('INSERT INTO users VALUES (7, "a@b.com", ?, ?)', (status, f'apple:{product}'))
    db.execute('INSERT INTO subscriptions VALUES (7, ?, ?, ?, NULL, 0, ?, ?, ?)',
               ('sub_live' if provider == 'stripe' else None, status, period_end, NOW,
                provider, product))
    if with_purchase:
        db.execute('INSERT INTO mobile_store_purchases '
                   '(user_id, provider, product_id, original_transaction_id, status, '
                   'expires_at, updated_at) VALUES (7, "apple", ?, ?, ?, ?, ?)',
                   (product, original_txn, status, period_end, NOW))
    db.commit()
    db.close()


def row():
    db = sqlite3.connect(DB)
    db.row_factory = sqlite3.Row
    r = db.execute('SELECT * FROM subscriptions WHERE user_id = 7').fetchone()
    p = db.execute('SELECT * FROM mobile_store_purchases WHERE user_id = 7').fetchone()
    u = db.execute('SELECT * FROM users WHERE id = 7').fetchone()
    db.close()
    return r, p, u


def txn(expires, product='Screens_3', original='OT-1', **extra):
    return {'originalTransactionId': original, 'productId': product,
            'expiresDate': expires * 1000, **extra}


print('--- renewal extends the period ---')
reset(period_end=NOW + 100)
res = srv._apply_apple_notification('DID_RENEW', '', txn(NOW + MONTH), {'autoRenewStatus': 1})
r, p, u = row()
check('status active', r['status'] == 'active', str(dict(r)))
check('period extended', r['current_period_end'] == NOW + MONTH, str(r['current_period_end']))
check('purchase row updated', p['expires_at'] == NOW + MONTH)
check('users row updated', u['subscription_status'] == 'active')
check('reports the user', 'user 7' in res, res)

print('\n--- trial conversion ---')
reset(status='trialing', period_end=NOW + 100)
srv._apply_apple_notification('DID_RENEW', '', txn(NOW + MONTH), {'autoRenewStatus': 1})
r, _, _ = row()
check('trialing -> active on first renewal', r['status'] == 'active', str(r['status']))
check('trial_end cleared', r['trial_end'] is None, str(r['trial_end']))

print('\n--- auto-renew switched off ---')
reset()
srv._apply_apple_notification('DID_CHANGE_RENEWAL_STATUS', 'AUTO_RENEW_DISABLED',
                              txn(NOW + MONTH), {'autoRenewStatus': 0})
r, _, _ = row()
check('still active until period end', r['status'] == 'active')
check('cancel_at_period_end set', r['cancel_at_period_end'] == 1)

print('\n--- expiry releases the Stripe block ---')
reset()
srv._apply_apple_notification('EXPIRED', 'VOLUNTARY', txn(NOW - 10), {})
r, _, _ = row()
check('status expired', r['status'] == 'expired', str(r['status']))
check('no longer counts as an active store sub',
      r['status'] not in ('active', 'trialing', 'past_due'))

print('\n--- refund revokes immediately ---')
reset()
srv._apply_apple_notification('REFUND', '', txn(NOW - 10), {})
r, _, _ = row()
check('status refunded', r['status'] == 'refunded', str(r['status']))

print('\n--- upgrade records the new product ---')
reset(product='Screens_3')
srv._apply_apple_notification('DID_CHANGE_RENEWAL_PREF', 'UPGRADE',
                              txn(NOW + MONTH, product='Screens_10'), {'autoRenewStatus': 1})
r, p, u = row()
check('subscription product updated', r['billing_product_id'] == 'Screens_10', str(r['billing_product_id']))
check('purchase product updated', p['product_id'] == 'Screens_10')
check('users plan updated', u['subscription_plan'] == 'apple:Screens_10', str(u['subscription_plan']))

print('\n--- out-of-order delivery ---')
reset(period_end=NOW + MONTH)
res = srv._apply_apple_notification('DID_RENEW', '', txn(NOW + 100), {'autoRenewStatus': 1})
r, _, _ = row()
check('stale renewal does not shorten the period', r['current_period_end'] == NOW + MONTH,
      str(r['current_period_end']))
check('and says why', 'out-of-order' in res, res)

reset(period_end=NOW + MONTH)
res = srv._apply_apple_notification('EXPIRED', '', txn(NOW + 100), {})
r, _, _ = row()
check('but an ending event always applies', r['status'] == 'expired', res)

print('\n--- a Stripe subscription is never clobbered ---')
reset(provider='stripe')
res = srv._apply_apple_notification('EXPIRED', '', txn(NOW - 10), {})
r, _, _ = row()
check('stripe row untouched', r['status'] == 'active' and r['billing_provider'] == 'stripe',
      str(dict(r)))
check('and says why', 'stripe' in res.lower(), res)

print('\n--- unknown transaction ---')
reset(with_purchase=False)
res = srv._apply_apple_notification('DID_RENEW', '', txn(NOW + MONTH), {'autoRenewStatus': 1})
check('unmatched transaction is reported, not applied', 'no local purchase' in res, res)
check('points at the recovery path', 'restore' in res.lower(), res)

reset(original_txn='OT-OTHER')
res = srv._apply_apple_notification('DID_RENEW', '', txn(NOW + MONTH, original='OT-1'),
                                    {'autoRenewStatus': 1})
r, _, _ = row()
check('another subscriber is not touched', r['current_period_end'] != NOW + MONTH or
      'no local purchase' in res, res)

print('\n--- malformed input ---')
reset()
res = srv._apply_apple_notification('DID_RENEW', '', {'productId': 'x'}, {})
check('missing originalTransactionId is ignored', 'ignored' in res, res)
res = srv._apply_apple_notification('CONSUMPTION_REQUEST', '', txn(NOW + MONTH), {})
check('non-entitlement event is ignored', 'ignored' in res, res)
reset()
res = srv._apply_apple_notification('DID_RENEW', '', txn(NOW + MONTH, expiresDate=None),
                                    {'autoRenewStatus': 1})
check('missing expiresDate does not crash', 'user 7' in res, res)

print('\n' + '=' * 60)
print(f'{len(PASS)} passed, {len(FAIL)} failed')
for f in FAIL:
    print('  FAILED:', f)
print('=' * 60)
sys.exit(1 if FAIL else 0)
