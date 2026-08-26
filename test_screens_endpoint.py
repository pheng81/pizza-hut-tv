"""A store that exists but has no screens must not report "store not found"."""
import sys, json
sys.path.insert(0, r'c:\Users\toeng\Pizza Hut TV')
import app as srv

PASS, FAIL = [], []
def check(n, c, d=''):
    (PASS if c else FAIL).append(n)
    print(('PASS  ' if c else 'FAIL  ') + n + (('  -- ' + d) if d and not c else ''))

CFG = {
    'stores': [{'id': '1000', 'name': 'My First Store'},
               {'id': '1111', 'name': 'test3'},
               {'id': '2222', 'name': 'test'}],
    'screens': {},                       # every screen deleted - the reported state
    'master_store_id': '1000',
}

def call(store_id, cfg):
    srv.app.config['TESTING'] = True
    orig_load = srv.load_store_config_for_user_safe_key
    orig_ensure = srv.ensure_playlists_structure
    orig_key = srv._safe_user_key
    orig_save = srv.save_store_config_for_user_safe_key
    srv.load_store_config_for_user_safe_key = lambda k: json.loads(json.dumps(cfg))
    srv.ensure_playlists_structure = lambda c: c
    srv._safe_user_key = lambda: 'u_at_x.com'
    srv.save_store_config_for_user_safe_key = lambda k, c: None
    try:
        with srv.app.test_request_context('/screens/' + store_id):
            fn = srv.get_screens_for_store
            inner = getattr(fn, '__wrapped__', fn)
            resp = inner(store_id)
        body, status = (resp if isinstance(resp, tuple) else (resp, 200))
        return status, json.loads(body.get_data(as_text=True))
    finally:
        srv.load_store_config_for_user_safe_key = orig_load
        srv.ensure_playlists_structure = orig_ensure
        srv._safe_user_key = orig_key
        srv.save_store_config_for_user_safe_key = orig_save

print('--- the reported case: store exists, all screens deleted ---')
status, body = call('1000', CFG)
check('returns 200, not 404', status == 200, 'status=%s body=%s' % (status, body))
check('reports success', body.get('success') is True, str(body))
check('returns an empty screens map', body.get('screens') == {}, str(body))
check('echoes the store id', body.get('store_id') == '1000', str(body))

print('')
print('--- other stores with no screens behave the same ---')
for sid in ('1111', '2222'):
    status, body = call(sid, CFG)
    check('store %s -> 200 empty' % sid, status == 200 and body.get('screens') == {},
          'status=%s' % status)

print('')
print('--- a store that genuinely does not exist still 404s ---')
status, body = call('9999', CFG)
check('unknown store -> 404', status == 404, 'status=%s body=%s' % (status, body))
check('says store not found', body.get('error') == 'store not found', str(body))

print('')
print('--- a store WITH screens is unaffected ---')
cfg2 = json.loads(json.dumps(CFG))
cfg2['screens'] = {'1000': {'1000_screen1': {'file': None}, '1000_screen2': {'file': None}}}
status, body = call('1000', cfg2)
check('returns its screens', status == 200 and set(body.get('screens', {})) ==
      {'1000_screen1', '1000_screen2'}, str(body))

print('')
print('--- screens present for a store missing from the store list ---')
cfg3 = {'stores': [], 'screens': {'7777': {'7777_screen1': {}}}}
status, body = call('7777', cfg3)
check('still served (legacy data not orphaned)', status == 200, 'status=%s' % status)

print('')
print('=' * 60)
print('%d passed, %d failed' % (len(PASS), len(FAIL)))
for f in FAIL: print('  FAILED:', f)
print('=' * 60)
sys.exit(1 if FAIL else 0)
