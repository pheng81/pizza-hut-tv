import sys
sys.path.insert(0, r'c:\Users\toeng\Pizza Hut TV')
import app as srv

PASS, FAIL = [], []
def check(n, c, d=''):
    (PASS if c else FAIL).append(n)
    print(('PASS  ' if c else 'FAIL  ') + n + (('  -- ' + d) if d and not c else ''))

print('--- price text is derived from the admin number ---')
for amount, expect in [(1.0, '$1 per screen / month'), (5.0, '$5 per screen / month'),
                       (3.5, '$3.50 per screen / month'), (0.0, '$0 per screen / month'),
                       (12.99, '$12.99 per screen / month')]:
    got = srv._format_price_display(amount)
    check('%-6s -> %s' % (amount, expect), got == expect, got)

print('')
print('--- admin values win over any built-in ---')
pol = srv._normalize_billing_settings(
    {'price_per_screen': 1.0, 'price_display': '$1 per screen / month',
     'trial_days': 14, 'free_screens': 1})
check('admin text used verbatim', pol['price_display'] == '$1 per screen / month', pol['price_display'])
check('admin number used', pol['price_per_screen'] == 1.0, str(pol['price_per_screen']))

print('')
print('--- blank admin text falls back to the admin NUMBER, not a literal ---')
pol = srv._normalize_billing_settings({'price_per_screen': 2.0, 'price_display': '',
                                       'trial_days': 14, 'free_screens': 1})
check('derives from price_per_screen=2.0', pol['price_display'] == '$2 per screen / month',
      pol['price_display'])
check('does NOT say $5', '$5' not in pol['price_display'], pol['price_display'])

print('')
print('--- no stray price literals remain in the source ---')
src = open(r'c:\Users\toeng\Pizza Hut TV\app.py', encoding='utf-8').read()
check("no '$5 per screen' literal in app.py", '$5 per screen' not in src)
check('the only 5.0 default is _default_price_per_screen',
      src.count('return 5.0') == 1, str(src.count('return 5.0')))

print('')
print('=' * 60)
print('%d passed, %d failed' % (len(PASS), len(FAIL)))
for f in FAIL: print('  FAILED:', f)
print('=' * 60)
sys.exit(1 if FAIL else 0)
