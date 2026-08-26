"""Render subscribe.html in each billing state and assert what the user sees."""
import re, sys
from jinja2 import Environment, FileSystemLoader

env = Environment(loader=FileSystemLoader('templates'))
env.globals['url_for'] = lambda n, **k: f'/{n}'
env.globals['get_flashed_messages'] = lambda **k: []
tpl = env.get_template('subscribe.html')

PASS, FAIL = [], []
def check(name, cond, detail=''):
    (PASS if cond else FAIL).append(name)
    print(f'{"PASS" if cond else "FAIL"}  {name}' + (f'  -- {detail}' if detail and not cond else ''))

def render(**over):
    ctx = dict(stripe_enabled=True, subscription=None, has_active=False, publishable_key='pk',
               price_display='$1 per screen / month', trial_days=14, price_id='price',
               free_screens=1, next_renewal=None, billing_provider='', billing_provider_label='',
               pending_add_screen=False, pending_store_id='', pending_screen_type='screen',
               store_billed=False, store_manage_url='', subscription_ended=False)
    ctx.update(over)
    return re.sub(r'\s+', ' ', tpl.render(**ctx))

print('--- 1. Apple subscription ACTIVE ---')
h = render(has_active=True, billing_provider='apple', billing_provider_label='Apple App Store',
           store_billed=True, store_manage_url='https://apps.apple.com/account/subscriptions',
           next_renewal='Sep 18, 2026', subscription={'status':'active'})
check('shows it is active', 'Active Subscription' in h)
check('names Apple as the biller', 'Apple App Store' in h)
check('says it is managed in the App Store', 'managed in Apple App Store' in h)
check('links to Apple to manage it', 'apps.apple.com/account/subscriptions' in h)
check('NO Stripe subscribe button', 'Start Subscription Securely' not in h,
      'the website is offering to charge an active Apple subscriber')
check('no per-screen price pitch', '$1 per screen' not in h)

print('\n--- 2. Apple subscription EXPIRED (the reported case) ---')
h = render(billing_provider='apple', billing_provider_label='Apple App Store', store_billed=True,
           store_manage_url='https://apps.apple.com/account/subscriptions',
           next_renewal='Aug 18, 2026', subscription={'status':'expired'}, subscription_ended=True)
check('says the Apple subscription ended', 'Apple App Store subscription ended' in h)
check('reassures screens are safe', 'screens and playlists are safe' in h)
check('offers resubscribing in the app', 'Resubscribe in the app' in h)
check('offers subscribing on the website', 'Subscribe on this website' in h)
check('warns against doing both', 'charges you twice' in h)
check('does NOT call the end date a renewal', 'Next renewal Aug 18' not in h,
      'still says "Next renewal" for a dead subscription')
check('calls it Ended instead', 'Ended Aug 18, 2026' in h)
check('web checkout still reachable', 'Start Subscription Securely' in h)

print('\n--- 3. Never used a store (plain web user) ---')
h = render(subscription=None)
check('normal Stripe pitch shown', 'Start Subscription Securely' in h)
check('no Apple wording leaks in', 'App Store' not in h and 'subscription ended' not in h)

print('\n--- 4. Lapsed Stripe user (not a store account) ---')
h = render(subscription={'status':'past_due'}, next_renewal='Sep 1, 2026',
           billing_provider='stripe', billing_provider_label='Stripe')
check('no store-ended banner', 'subscription ended' not in h)
check('still says Next renewal for a live Stripe sub', 'Next renewal Sep 1, 2026' in h)

print('\n--- 5. Google Play expired ---')
h = render(billing_provider='google', billing_provider_label='Google Play', store_billed=True,
           store_manage_url='https://play.google.com/store/account/subscriptions',
           next_renewal='Aug 18, 2026', subscription={'status':'expired'}, subscription_ended=True)
check('names Google Play, not Apple', 'Google Play subscription ended' in h and 'App Store' not in h)
check('links to Play, not Apple', 'play.google.com' in h and 'apps.apple.com' not in h)

print('')
print('--- pricing comes only from admin settings ---')
h = render(price_display='$1 per screen / month')
check('renders the admin price text', '$1 per screen / month' in h)
h = render(price_display='$3.50 per screen / month')
check('follows the admin value when it changes',
      '$3.50 per screen / month' in h and '$1 per screen' not in h)
h = render(price_display='')
check('blank admin text does NOT invent a price',
      '$5 per screen' not in h, 'template still hardcodes a price')

print('\n' + '='*60)
print(f'{len(PASS)} passed, {len(FAIL)} failed')
for f in FAIL: print('  FAILED:', f)
print('='*60)
sys.exit(1 if FAIL else 0)
