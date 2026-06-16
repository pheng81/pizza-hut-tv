#!/usr/bin/env python3
"""
Backfill lat/lng for screens in store_config__*.json files using OpenStreetMap Nominatim.

Usage:
  python scripts/geocode_store_configs_osm.py --dry-run

This script is polite to Nominatim: it sets a User-Agent and sleeps between requests.
It writes a timestamped .bak before modifying each file.
"""
import os
import sys
import json
import glob
import time
import argparse
import requests

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
USER_AGENT = 'EverydayAdvertiseGeocoder/1.0 (admin@everydayadvertise.com)'


def nominatim_geocode(address):
    url = 'https://nominatim.openstreetmap.org/search'
    params = {'q': address, 'format': 'json', 'limit': 1, 'addressdetails': 0}
    try:
        resp = requests.get(url, params=params, headers={'User-Agent': USER_AGENT}, timeout=10)
        if resp.status_code != 200:
            return None
        data = resp.json() if resp.content else []
        if not data:
            return None
        item = data[0]
        lat = item.get('lat')
        lon = item.get('lon')
        if lat is None or lon is None:
            return None
        return {'latitude': float(lat), 'longitude': float(lon), 'display_name': item.get('display_name')}
    except Exception as e:
        print('  Nominatim error for', address, '->', e)
        return None


def process_file(path, dry_run=True, sleep_between=1.0):
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
            screen_addr = str(screen.get('address') or '').strip()
            effective_address = screen_addr or store_addr
            if not effective_address:
                print('  Skipping', screen_id, '(no address)')
                continue
            print('  Geocoding', screen_id, '->', effective_address)
            result = nominatim_geocode(effective_address)
            if not result:
                print('    No result')
                continue
            screen['latitude'] = result['latitude']
            screen['longitude'] = result['longitude']
            screen['address'] = screen.get('address') or effective_address
            changed = True
            print('    ->', result['latitude'], result['longitude'])
            time.sleep(sleep_between)

    if changed and not dry_run:
        bak = f"{path}.bak.{int(time.time())}"
        try:
            os.rename(path, bak)
        except Exception as e:
            print('  Failed to make backup', e)
            return False
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print('  Wrote updates to', path, 'backup at', bak)

    return changed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--pattern', default=os.path.join(BASE_DIR, 'store_config__*.json'))
    ap.add_argument('--sleep', type=float, default=1.0, help='Seconds between requests')
    args = ap.parse_args()

    files = sorted(glob.glob(args.pattern))
    if not files:
        print('No files matched', args.pattern)
        return

    any_changed = False
    for p in files:
        changed = process_file(p, dry_run=args.dry_run, sleep_between=args.sleep)
        any_changed = any_changed or bool(changed)

    if any_changed:
        print('\nDone — some files would be/were updated.')
    else:
        print('\nDone — no changes.')


if __name__ == '__main__':
    main()
