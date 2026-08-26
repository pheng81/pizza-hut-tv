"""A store plan that has ended must stop blocking and stop capping screens.

Regression test for the deadlock. One subscriptions row was read three ways:
_user_has_active_subscription honoured current_period_end, while
_active_store_subscription and _mobile_plan_allowance looked only at status.
A late store notification leaves 'trialing' on a row whose period ended days
ago, and the user is then told the subscription has ended, refused when they
try to subscribe on the website because it still looks live, and sent back to
the store to upgrade a plan that is no longer charging them.
"""
import sys, sqlite3, time
sys.path.insert(0, r'c:\Users\toeng\Pizza Hut TV')
import app as srv

PASS, FAIL = [], []
def check(n, c, d=''):
    (PASS if c else FAIL).append(n)
    print(('PASS  ' if c else 'FAIL  ') + n + (('  -- ' + d) if d and not c else ''))

NOW = int(time.time())
PAST = NOW - 6 * 86400      # the shape of the live row: ended six days ago
FUTURE = NOW + 6 * 86400
DAY = 86400


def db_with(provider, product_id, status, period_end):
    """A stand-in subscriptions row, so the test needs no real database."""
    con = sqlite3.connect(':memory:')
    con.row_factory = sqlite3.Row
    con.execute(
        'CREATE TABLE subscriptions (user_id INTEGER, billing_provider TEXT, '
        'billing_product_id TEXT, status TEXT, current_period_end INTEGER)'
    )
    con.execute('INSERT INTO subscriptions VALUES (?, ?, ?, ?, ?)',
                (1, provider, product_id, status, period_end))
    return con


def with_row(fn, provider, product_id, status, period_end):
    real = srv.get_db
    srv.get_db = lambda: db_with(provider, product_id, status, period_end)
    try:
        return fn()
    finally:
        srv.get_db = real


def allowance(provider, product_id, status, period_end=FUTURE, wanted=4):
    return with_row(lambda: srv._mobile_plan_allowance(1, wanted),
                    provider, product_id, status, period_end)


def blocks_checkout(provider, product_id, status, period_end=FUTURE):
    return with_row(lambda: srv._active_store_subscription(1),
                    provider, product_id, status, period_end) is not None


print('--- a live plan still caps and still blocks, exactly as before ---')
for status in ('active', 'trialing', 'past_due'):
    screens, needs_upgrade, product = allowance('apple', 'Screens_3', status)
    check('%-9s caps at the tier' % status, screens == 3, str(screens))
    check('%-9s flags the upgrade' % status, needs_upgrade is True)
    check('%-9s reports the product' % status, product == 'Screens_3', str(product))
    check('%-9s blocks web checkout' % status, blocks_checkout('apple', 'Screens_3', status))

print('')
print('--- an ended status caps nothing and blocks nothing ---')
for status in ('expired', 'refunded', 'canceled', 'revoked', ''):
    label = status or '(empty)'
    screens, needs_upgrade, product = allowance('apple', 'Screens_3', status)
    check('%-9s no screen cap' % label, screens == 0, str(screens))
    check('%-9s no upgrade prompt' % label, needs_upgrade is False, str(needs_upgrade))
    check('%-9s no product id' % label, product is None, str(product))
    check('%-9s does not block checkout' % label,
          not blocks_checkout('apple', 'Screens_3', status))

print('')
print('--- THE DEADLOCK: status says live, the paid period ended ---')
for status in ('trialing', 'active', 'past_due'):
    check('%-9s past period does not cap screens' % status,
          allowance('apple', 'Screens_3', status, PAST)[0] == 0,
          str(allowance('apple', 'Screens_3', status, PAST)[0]))
    check('%-9s past period does not block checkout' % status,
          not blocks_checkout('apple', 'Screens_3', status, PAST))
check('the three readers now agree the plan is over',
      srv._user_has_active_subscription is not None
      and allowance('apple', 'Screens_3', 'trialing', PAST) == (0, False, None))
check('one second past the end is already over',
      allowance('apple', 'Screens_3', 'active', NOW - 1)[0] == 0)
check('one day short of the end is still live',
      allowance('apple', 'Screens_3', 'active', NOW + DAY)[0] == 3)

print('')
print('--- an unknown period must NOT be read as ended ---')
for missing in (0, None):
    check('period_end=%-4s still caps' % str(missing),
          allowance('apple', 'Screens_3', 'active', missing)[0] == 3)
    check('period_end=%-4s still blocks checkout' % str(missing),
          blocks_checkout('apple', 'Screens_3', 'active', missing))
check('a non-numeric period is treated as unknown, not ended',
      allowance('apple', 'Screens_3', 'active', 'not-a-date')[0] == 3)

print('')
print('--- Google Play behaves the same ---')
check('live Play plan caps', allowance('google', 'Screens_5', 'active')[0] == 5)
check('ended Play status does not', allowance('google', 'Screens_5', 'expired')[0] == 0)
check('lapsed Play period does not', allowance('google', 'Screens_5', 'active', PAST)[0] == 0)

print('')
print('--- status matching is case insensitive ---')
check('ACTIVE still counts as live', allowance('apple', 'Screens_3', 'ACTIVE')[0] == 3)
check('Expired still counts as ended', allowance('apple', 'Screens_3', 'Expired')[0] == 0)

print('')
print('--- unrelated paths are untouched ---')
check('stripe is not tier capped', allowance('stripe', 'price_x', 'active')[0] == 0)
check('stripe does not block store checkout', not blocks_checkout('stripe', 'price_x', 'active'))
check('no user id returns nothing', srv._mobile_plan_allowance(None, 4) == (0, False, None))

print('')
print('--- both readers share one definition of "ended" ---')
src = open(r'c:\Users\toeng\Pizza Hut TV\app.py', encoding='utf-8').read()
check('the helper exists', 'def _store_period_has_ended(' in src)
check('both store readers call it', src.count('_store_period_has_ended(row)') >= 2,
      str(src.count('_store_period_has_ended(row)')))

print('')
print('=' * 60)
print('%d passed, %d failed' % (len(PASS), len(FAIL)))
for f in FAIL: print('  FAILED:', f)
print('=' * 60)
sys.exit(1 if FAIL else 0)
