#!/usr/bin/env python3
"""Simple diagnostic tool to inspect playlist + commands endpoints for a store/screen.

Usage examples:
  python3 playlist_probe.py --store 1000 --screen 2 --code 4682
  python3 playlist_probe.py --play-url "https://everydayadvertise.com/webplayer/play?store_id=1000&screen_id=1000_screen2&code=4682"

Prints:
- Final resolved screen_id
- Playlist HTTP status + JSON snippet (truncated)
- Commands HTTP status + JSON snippet (truncated)
- Basic interpretation (empty playlist / items found)

Exits non-zero if network errors occur.
"""
import argparse, sys, json, requests, re
from urllib.parse import urlparse, parse_qs

BASE_PLAYLIST_ORIGIN = "https://everydayadvertise.com"  # root origin; playlist path is /playlist/{store}/{screen}
COMMANDS_ENDPOINT = BASE_PLAYLIST_ORIGIN + "/api/commands"
TIMEOUT = 12


def derive_screen_id(store: str, screen: str) -> str:
    s = str(screen).strip()
    if s.startswith(f"{store}_"):
        return s
    if '_' in s:
        return s
    if s.isdigit():
        return f"{store}_screen{s}"
    return s


def parse_play_url(play_url: str):
    parts = urlparse(play_url)
    qs = parse_qs(parts.query)
    return {
        'store': qs.get('store_id', [None])[0],
        'screen_id': qs.get('screen_id', [None])[0],
        'code': qs.get('code', [None])[0],
    }


def truncate(obj, length=400):
    js = json.dumps(obj, ensure_ascii=False)
    if len(js) > length:
        return js[:length] + '…(truncated)'
    return js


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--store')
    ap.add_argument('--screen')
    ap.add_argument('--screen-id')
    ap.add_argument('--code')
    ap.add_argument('--play-url')
    ap.add_argument('--user-code', help='Optional user_code param if backend uses it', default=None)
    args = ap.parse_args()

    if args.play_url:
        parsed = parse_play_url(args.play_url)
        if parsed['store'] and not args.store:
            args.store = parsed['store']
        if parsed['screen_id'] and not args.screen_id:
            args.screen_id = parsed['screen_id']
        if parsed['code'] and not args.code:
            args.code = parsed['code']

    if not args.store:
        print('ERROR: Need --store (or --play-url).', file=sys.stderr); sys.exit(2)
    if not (args.screen or args.screen_id):
        print('ERROR: Need --screen or --screen-id (or --play-url).', file=sys.stderr); sys.exit(2)

    final_screen_id = args.screen_id or derive_screen_id(args.store, args.screen)

    playlist_url = f"{BASE_PLAYLIST_ORIGIN}/playlist/{args.store}/{final_screen_id}"
    if args.user_code:
        connector = '&' if '?' in playlist_url else '?'
        playlist_url += f"{connector}user_code={args.user_code}"

    cmd_params = {
        'store_id': args.store,
        'screen_id': final_screen_id,
        'limit': 5,
        'pop': 1,
    }
    if args.user_code:
        cmd_params['user_code'] = args.user_code

    print(f"Store: {args.store}")
    print(f"Screen input: {args.screen or '(explicit)'}")
    print(f"Resolved screen_id: {final_screen_id}")
    print(f"Derived playlist URL: {playlist_url}")

    # Playlist fetch
    try:
        r = requests.get(playlist_url, timeout=TIMEOUT)
        status = r.status_code
        data = None
        try:
            data = r.json()
        except Exception:
            data = {'raw': r.text[:400]}
        print(f"Playlist status: {status}")
        print(f"Playlist body: {truncate(data)}")
        empty = False
        if isinstance(data, dict):
            if 'playlist' in data and isinstance(data['playlist'], list) and len(data['playlist']) == 0:
                empty = True
        elif isinstance(data, list) and len(data) == 0:
            empty = True
        if empty:
            print("Interpretation: EMPTY playlist (webplayer would show 'Waiting for schedule…')")
        else:
            print("Interpretation: Playlist has content or non-empty structure")
    except Exception as e:
        print(f"ERROR fetching playlist: {e}", file=sys.stderr)

    # Commands fetch
    try:
        r2 = requests.get(COMMANDS_ENDPOINT, params=cmd_params, timeout=TIMEOUT)
        status2 = r2.status_code
        cdata = None
        try:
            cdata = r2.json()
        except Exception:
            cdata = {'raw': r2.text[:400]}
        print(f"Commands status: {status2}")
        print(f"Commands body: {truncate(cdata)}")
    except Exception as e:
        print(f"ERROR fetching commands: {e}", file=sys.stderr)

if __name__ == '__main__':
    main()
