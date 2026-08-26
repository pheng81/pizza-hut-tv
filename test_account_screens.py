"""The account page's screens section must reflect who is actually billing."""
import re, sys
from jinja2 import Environment, FileSystemLoader

env = Environment(loader=FileSystemLoader('templates'))
env.globals['url_for'] = lambda n, **k: '/' + n
env.globals['get_flashed_messages'] = lambda **k: []
tpl = env.get_template('account.html')

PASS, FAIL = [], []
def check(name, cond, detail=''):
    (PASS if cond else FAIL).append(name)
    print(('PASS  ' if cond else 'FAIL  ') + name + (('  -- ' + detail) if detail and not cond else ''))

SUBS = [dict(id=i, screen_name='1000_screen%d' % i, store_id='1000', status='trialing',
             cancel_at_period_end=0, billing_start='Aug 15, 2026', next_billing='Aug 29, 2026')
        for i in range(1, 4)]

def render(**over):
    ctx = dict(user_info={'username': 'a@b.com', 'email': 'a@b.com'}, account_created='', phone_number='',
               phone_verified=True, avatar_url='', link_code='X', subscription_info={},
               has_active=True, is_canceled=False, next_billing_date='', screen_count=3,
               screens_list=[], screen_subscriptions=SUBS, billing_history=[], monthly_cost=0,
               price_display='$1 per screen / month', trial_days=14, free_screens=1,
               build_stamp='x', embedded=False,
               store_billed=False, store_provider_label='', store_manage_url='',
               store_plan_screens=0)
    ctx.update(over)
    return re.sub(r'\s+', ' ', tpl.render(**ctx))

print('--- Apple-billed account (the reported case) ---')
h = render(store_billed=True, store_provider_label='the App Store',
           store_manage_url='https://apps.apple.com/account/subscriptions',
           store_plan_screens=10)
check('says it is billed through the App Store', 'billed through <strong>the App Store' in h or 'billed through the App Store' in h)
check('states the plan covers 10 screens', '10 screens' in h)
check('says there is no per-screen charge', 'no separate charge per screen' in h)
check('NO "$1 per screen / month" anywhere', '$1 per screen / month' not in h,
      'still quoting the Stripe per-screen rate to an Apple subscriber')
check('NO per-screen Cancel buttons', 'onclick="cancelScreenSubscription' not in h,
      'Cancel buttons act on Stripe records that should not exist')
check('NO "Cancel All ... remove all screens" block', 'onclick="removeAllScreens' not in h,
      'offers to delete all screens without stopping Apple billing')
check('screens are still listed', '1000_screen1' in h and '1000_screen3' in h)
check('marks screens as included in the plan', 'Included in your the App Store plan' in h)
check('links out to Apple to manage', 'apps.apple.com/account/subscriptions' in h)

print('\n--- Google Play account ---')
h = render(store_billed=True, store_provider_label='Google Play',
           store_manage_url='https://play.google.com/store/account/subscriptions',
           store_plan_screens=5)
check('names Google Play, never the App Store', 'Google Play' in h and 'App Store' not in h)
check('links to Play', 'play.google.com' in h)
check('no per-screen price', '$1 per screen / month' not in h)

print('\n--- ordinary Stripe web account (must be unchanged) ---')
h = render(store_billed=False)
check('still shows the per-screen rate', '$1 per screen / month' in h)
check('still offers per-screen Cancel', 'onclick="cancelScreenSubscription' in h)
check('still offers Cancel All', 'onclick="removeAllScreens' in h)
check('no store wording leaks in', 'App Store' not in h and 'Google Play' not in h)

print('\n--- store account with no screens yet ---')
h = render(store_billed=True, store_provider_label='the App Store', screen_subscriptions=[])
check('section hidden entirely, no crash', 'Manage Screen Subscriptions' not in h)

print('\n' + '=' * 60)
print('%d passed, %d failed' % (len(PASS), len(FAIL)))
for f in FAIL: print('  FAILED:', f)
print('=' * 60)
sys.exit(1 if FAIL else 0)
