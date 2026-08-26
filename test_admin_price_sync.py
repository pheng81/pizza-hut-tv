"""The admin's per-screen number must decide what Stripe actually charges.

Runs entirely against a fake Stripe - never touches the live account.
"""
import sys, types
sys.path.insert(0, r'c:\Users\toeng\Pizza Hut TV')
import app as srv

PASS, FAIL = [], []
def check(n, c, d=''):
    (PASS if c else FAIL).append(n)
    print(('PASS  ' if c else 'FAIL  ') + n + (('  -- ' + d) if d and not c else ''))


class FakeStripe:
    """Minimal stand-in recording what would have been sent to Stripe."""
    def __init__(self, prices=None, fail_create=False):
        self.prices = prices or {}
        self.created = []
        self.fail_create = fail_create
        outer = self
        class Price:
            @staticmethod
            def retrieve(pid):
                if pid not in outer.prices:
                    raise Exception('No such price: ' + pid)
                return outer.prices[pid]
            @staticmethod
            def list(product=None, active=None, type=None, limit=None):
                return {'data': [p for p in outer.prices.values()
                                 if p.get('product') == product and p.get('active')]}
            @staticmethod
            def create(**kw):
                if outer.fail_create:
                    raise Exception('card_declined: simulated Stripe failure')
                pid = 'price_NEW%d' % (len(outer.created) + 1)
                obj = {'id': pid, 'unit_amount': kw['unit_amount'], 'currency': kw['currency'],
                       'recurring': kw['recurring'], 'active': True,
                       'product': kw.get('product') or 'prod_AUTO'}
                outer.prices[pid] = obj
                outer.created.append(kw)
                return obj
        self.Price = Price


def price(pid, amount_cents, currency='aud', product='prod_X', active=True, interval='month'):
    return {'id': pid, 'unit_amount': amount_cents, 'currency': currency, 'product': product,
            'active': active, 'recurring': {'interval': interval, 'interval_count': 1}}


def run(amount, existing, prices=None, fail_create=False, currency_env=''):
    fake = FakeStripe(prices, fail_create)
    real_stripe, real_key, real_cur = srv.stripe, srv.STRIPE_SECRET_KEY, srv.STRIPE_CURRENCY
    srv.stripe, srv.STRIPE_SECRET_KEY, srv.STRIPE_CURRENCY = fake, 'sk_test_x', currency_env
    try:
        return srv._sync_stripe_price_to_amount(amount, existing), fake
    finally:
        srv.stripe, srv.STRIPE_SECRET_KEY, srv.STRIPE_CURRENCY = real_stripe, real_key, real_cur


print('--- the reported situation: admin says $1, Stripe price is A$5 ---')
existing = {'price_1STZq': price('price_1STZq', 500)}
(pid, note), fake = run(1.0, 'price_1STZq', existing)
check('does NOT keep the A$5 price', pid != 'price_1STZq', pid)
check('creates a price for 100 cents', fake.created and fake.created[0]['unit_amount'] == 100,
      str(fake.created))
check('keeps the existing AUD currency', fake.created[0]['currency'] == 'aud', str(fake.created))
check('stays on the same Stripe product', fake.created[0].get('product') == 'prod_X', str(fake.created))
check('bills monthly', fake.created[0]['recurring'] == {'interval': 'month'}, str(fake.created))
check('tells the admin what happened', 'Created a new Stripe price' in note, note)

print('')
print('--- already correct: nothing should change ---')
existing = {'price_ok': price('price_ok', 100)}
(pid, note), fake = run(1.0, 'price_ok', existing)
check('keeps the matching price', pid == 'price_ok', pid)
check('creates nothing', fake.created == [], str(fake.created))
check('says nothing (no noise)', note == '', note)

print('')
print('--- a matching price already exists on the product: reuse it ---')
existing = {'price_old': price('price_old', 500), 'price_1dollar': price('price_1dollar', 100)}
(pid, note), fake = run(1.0, 'price_old', existing)
check('reuses the existing $1 price', pid == 'price_1dollar', pid)
check('does NOT create a duplicate', fake.created == [], str(fake.created))
check('explains the reuse', 'existing Stripe price' in note, note)

print('')
print('--- never reuse a price that only looks right ---')
for label, bad in [
    ('wrong currency', price('p_usd', 100, currency='usd')),
    ('yearly not monthly', price('p_year', 100, interval='year')),
    ('archived/inactive', price('p_off', 100, active=False)),
]:
    existing = {'price_old': price('price_old', 500), bad['id']: bad}
    (pid, note), fake = run(1.0, 'price_old', existing)
    check('ignores a %s price' % label, pid != bad['id'] and len(fake.created) == 1, pid)

print('')
print('--- decimal and zero amounts ---')
existing = {'p': price('p', 500)}
(pid, note), fake = run(3.5, 'p', existing)
check('$3.50 -> 350 cents', fake.created[0]['unit_amount'] == 350, str(fake.created))
existing = {'p': price('p', 500)}
(pid, note), fake = run(0.0, 'p', existing)
check('$0 -> 0 cents (free plan)', fake.created[0]['unit_amount'] == 0, str(fake.created))

print('')
print('--- failure must not silently mislead ---')
existing = {'price_1STZq': price('price_1STZq', 500)}
(pid, note), fake = run(1.0, 'price_1STZq', existing, fail_create=True)
check('keeps the old price id on failure', pid == 'price_1STZq', pid)
check('warns customers are NOT on the new amount', 'NOT being charged the new amount' in note, note)

print('')
print('--- Stripe not configured ---')
real = srv.stripe
srv.stripe = None
try:
    pid, note = srv._sync_stripe_price_to_amount(1.0, 'price_keep')
finally:
    srv.stripe = real
check('leaves the id untouched', pid == 'price_keep', pid)
check('says why', 'not configured' in note, note)

print('')
print('--- no existing price at all (fresh setup) ---')
(pid, note), fake = run(2.0, '', {})
check('creates one with product_data', fake.created and 'product_data' in fake.created[0],
      str(fake.created))
check('amount is 200 cents', fake.created[0]['unit_amount'] == 200, str(fake.created))

print('')
print('=' * 62)
print('%d passed, %d failed' % (len(PASS), len(FAIL)))
for f in FAIL: print('  FAILED:', f)
print('=' * 62)
sys.exit(1 if FAIL else 0)
