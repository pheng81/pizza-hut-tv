#!/usr/bin/env python3
"""
Backfill lat/lng for screens in store_config__*.json files using Google Geocoding API.

Usage:
  python scripts/geocode_store_configs.py --dry-run
  GOOGLE_MAPS_API_KEY must be set in the environment to perform real writes.

This script is conservative: it only fills missing latitude/longitude when an
address is available (screen address or store address). It writes a .bak
copy before modifying each file.
"""
import os
import sys
import json
import glob
import time
import argparse
from urllib.parse import urlencode

try:
    import requests
except Exception:
    print('requests is required. Install with: pip install requests')
    sys.exit(1)


GOOGLE_KEY_ENV = 'GOOGLE_MAPS_API_KEY'
BASE_DIR = os.path.dirname(os.path.dirname(__file__))


def geocode_address(address, api_key, country='AU'):
    if not address or not api_key:
        return None
    params = {
        'address': address,
        'components': f'country:{country}',
        'region': country.lower(),
        'key': api_key,
    }
    url = 'https://maps.googleapis.com/maps/api/geocode/json?' + urlencode(params)
    try:
        resp = requests.get(url, timeout=8)
        data = resp.json() if resp.content else {}
        if str(data.get('status') or '').upper() != 'OK':
            return None
        res = (data.get('results') or [None])[0] or {}
        loc = (res.get('geometry') or {}).get('location') or {}
        lat = loc.get('lat')
        lng = loc.get('lng')
        if lat is None or lng is None:
            return None
        return {'latitude': float(lat), 'longitude': float(lng), 'formatted_address': res.get('formatted_address')}
    except Exception as e:
        print('Geocode request failed for', address, '->', e)
        return None


def process_file(path, api_key=None, dry_run=True, sleep_between=0.15):
    print('\nProcessing', path)
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    stores = data.get('stores') or []
    stores_by_id = {str(s.get('id')): s for s in stores}
    screens = data.get('screens') or {}
    changed = False

    for store_id, store_screens in screens.items():
        if not isinstance(store_screens, dict):
            continue
        store_addr = (stores_by_id.get(str(store_id)) or {}).get('address') or ''
        for screen_id, screen in store_screens.items():
            if not isinstance(screen, dict):
                continue
            lat = screen.get('latitude')
            lng = screen.get('longitude')
            if lat is not None and lng is not None:
                continue

            # derive effective address
            screen_addr = str(screen.get('address') or '').strip()
            effective_address = screen_addr or store_addr
            if not effective_address:
                print(f'  Skipping {screen_id} (no address)')
                continue

            print(f'  Geocoding {screen_id} -> "{effective_address}"')
            if not api_key:
                print('    (no API key provided; would geocode here)')
                changed = True
                continue

            result = geocode_address(effective_address, api_key)
            if not result:
                print('    Geocode failed or returned no coords')
                continue

            screen['latitude'] = result['latitude']
            screen['longitude'] = result['longitude']
            # Keep the address field so server can show it as before
            screen['address'] = screen.get('address') or effective_address
            changed = True
            print('    ->', result['latitude'], result['longitude'])
            time.sleep(sleep_between)

    if changed and not dry_run:
        bak = path + '.bak'
        try:
            if not os.path.exists(bak):
                os.rename(path, bak)
            else:
                # keep timestamped backup
                ts = int(time.time())
                os.rename(path, f"{path}.bak.{ts}")
        except Exception as e:
            print('Failed to create backup for', path, e)
            return False

        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print('Wrote updates to', path)

    return changed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true', help='Do not write changes')
    ap.add_argument('--sleep', type=float, default=0.15, help='Delay between geocode requests')
    ap.add_argument('--key', type=str, default=None, help='Google Maps API key (overrides env)')
    ap.add_argument('--pattern', type=str, default=os.path.join(BASE_DIR, 'store_config__*.json'))
    args = ap.parse_args()

    api_key = args.key or os.environ.get(GOOGLE_KEY_ENV)
    if not api_key:
        print('No Google API key found in env ({}). Running in dry-run mode unless --key provided.'.format(GOOGLE_KEY_ENV))

    files = glob.glob(args.pattern)
    if not files:
        print('No config files matched pattern', args.pattern)
        return

    any_changed = False
    for p in sorted(files):
        changed = process_file(p, api_key=api_key, dry_run=args.dry_run or not api_key, sleep_between=args.sleep)
        any_changed = any_changed or bool(changed)

    if any_changed:
        print('\nFinished. Some files would be/were updated.')
    else:
        print('\nFinished. No changes made.')


if __name__ == '__main__':
    main()
