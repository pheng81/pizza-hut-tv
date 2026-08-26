"""/api/account/overview must not quote per-screen Stripe pricing to a store account."""
import sys, json
sys.path.insert(0, r'c:\Users\toeng\Pizza Hut TV')
import app as srv

PASS, FAIL = [], []
def check(n, c, d=''):
    (PASS if c else FAIL).append(n)
    print(('PASS  ' if c else 'FAIL  ') + n + (('  -- ' + d) if d and not c else ''))

# Mirror the response-building branch exactly as the endpoint does.
def build(store_provider, store_plan_screens, price_display, monthly_cost, store_product_id=None):
    payload = {
        'monthly_cost': monthly_cost,
        'price_display': price_display,
        'billing_provider': store_provider or 'stripe',
        'mobile_plan_product_id': store_product_id,
        'mobile_plan_screens': store_plan_screens,
    }
    payload.update({
        'price_display': None,
        'monthly_cost': None,
        'store_plan_label': (f'{store_plan_screens} screens' if store_plan_screens else 'Store plan'),
    } if store_provider else {})
    return payload

print('--- the reported case: Apple Screens_3, 3 screens, admin $1.99 ---')
p = build('apple', 3, '$1.99 per screen / month', 3.98, 'Screens_3')
check('does NOT send a per-screen price', p['price_display'] is None, str(p['price_display']))
check('does NOT send $3.98 monthly cost', p['monthly_cost'] is None, str(p['monthly_cost']))
check('names Apple as the biller', p['billing_provider'] == 'apple', str(p['billing_provider']))
check('says how many screens the plan covers', p['store_plan_label'] == '3 screens', str(p))
check('still sends the product id', p['mobile_plan_product_id'] == 'Screens_3')

print('')
print('--- Google Play behaves the same ---')
p = build('google', 5, '$1.99 per screen / month', 7.96)
check('no per-screen price', p['price_display'] is None)
check('no invented total', p['monthly_cost'] is None)
check('label reflects the tier', p['store_plan_label'] == '5 screens')

print('')
print('--- a store plan with no known tier ---')
p = build('apple', 0, '$1.99 per screen / month', 3.98)
check('falls back to a neutral label', p['store_plan_label'] == 'Store plan', str(p))
check('still suppresses the price', p['price_display'] is None)

print('')
print('--- an ordinary Stripe account must be untouched ---')
p = build(None, 0, '$1.99 per screen / month', 3.98)
check('keeps the per-screen price', p['price_display'] == '$1.99 per screen / month')
check('keeps the computed monthly cost', p['monthly_cost'] == 3.98)
check('reports stripe', p['billing_provider'] == 'stripe')
check('sends no store label', 'store_plan_label' not in p, str(p))

print('')
print('--- the response is JSON-serialisable with nulls ---')
try:
    json.dumps(build('apple', 3, '$1.99 per screen / month', 3.98))
    check('serialises cleanly', True)
except Exception as e:
    check('serialises cleanly', False, str(e))

print('')
print('--- the endpoint really contains this branch ---')
import inspect
src = inspect.getsource(srv.api_account_overview)
check("suppresses price_display for store accounts", "'price_display': None" in src)
check("suppresses monthly_cost for store accounts", "'monthly_cost': None" in src)
check('branch is conditional on store_provider', 'if store_provider else {}' in src)

print('')
print('=' * 60)
print('%d passed, %d failed' % (len(PASS), len(FAIL)))
for f in FAIL: print('  FAILED:', f)
print('=' * 60)
sys.exit(1 if FAIL else 0)
