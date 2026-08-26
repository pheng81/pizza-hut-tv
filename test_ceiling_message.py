"""At the store plan ceiling, the advice must not send the user into a refusal."""
import sys, re
sys.path.insert(0, r'c:\Users\toeng\Pizza Hut TV')
import app as srv

PASS, FAIL = [], []
def check(n, c, d=''):
    (PASS if c else FAIL).append(n)
    print(('PASS  ' if c else 'FAIL  ') + n + (('  -- ' + d) if d and not c else ''))

print('--- the message must not contradict the checkout block ---')
for provider, store, settings in [
    ('apple', 'App Store', 'iPhone Settings'),
    ('google', 'Google Play', 'Play Store'),
]:
    m = srv._store_plan_ceiling_message(provider, 10)
    check('%-6s names the right store' % provider, store in m, m[:80])
    check('%-6s points at the right settings' % provider, settings in m, m[:80])
    check('%-6s does NOT say just "sign up on the website"' % provider,
          'Sign up on the website for more screens' not in m)
    check('%-6s warns about double charging' % provider, 'twice' in m)
    check('%-6s gives the ordered steps' % provider,
          '1.' in m and '2.' in m and '3.' in m)
    check('%-6s says turn off auto-renew first' % provider, 'auto-renew' in m)
    check('%-6s warns against cancelling immediately' % provider,
          'Do not cancel immediately' in m)
    check('%-6s no double article ("your the ")' % provider, 'your the ' not in m, m)

print('')
print('--- the block message and the ceiling message agree ---')
ceiling = srv._store_plan_ceiling_message('apple', 10)
block = srv._store_subscription_block_message('apple')
check('both tell the user to cancel at the store first',
      'auto-renew' in ceiling and 'Cancel it in' in block)
check('neither implies web checkout works right now',
      'Sign up on the website for more screens' not in ceiling)

print('')
print('--- screen count is reflected ---')
for n in (3, 5, 10):
    check('states %d screens' % n, ('covers %d screens' % n) in
          srv._store_plan_ceiling_message('apple', n))

print('')
print('--- the old wording is gone from the source ---')
src = open(r'c:\Users\toeng\Pizza Hut TV\app.py', encoding='utf-8').read()
check('no "Sign up on the website for more screens" left',
      'Sign up on the website for more screens' not in src)
check('both call sites use the helper',
      src.count('_store_plan_ceiling_message(') >= 3,
      str(src.count('_store_plan_ceiling_message(')))

print('')
print('=' * 60)
print('%d passed, %d failed' % (len(PASS), len(FAIL)))
for f in FAIL: print('  FAILED:', f)
print('=' * 60)
sys.exit(1 if FAIL else 0)
