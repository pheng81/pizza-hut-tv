#!/usr/bin/env python3
"""
Seed playlists for a store from existing uploads.

Usage:
  python scripts/seed_playlists.py [store_id] [count]

Defaults:
  store_id = '1881'
  count = 1  (how many recent uploads to add per screen if empty)

Behavior:
  - Reads store_config.json in repo root.
  - If a screen's playlist is empty, add N newest files from static/uploads.
  - Also sets screen['file'] to the first added item for convenience.
  - Writes a timestamped backup before modifying.
"""
import os
import json
import sys
import time
import uuid
from pathlib import Path

# Mirror allowed extensions from app.py (keep lowercase)
IMAGE_EXTENSIONS = {
    'png', 'jpg', 'jpeg', 'bmp', 'webp', 'svg', 'avif', 'heic', 'heif', 'tif', 'tiff'
}
ANIMATED_EXTENSIONS = {
    'gif', 'webp'
}
VIDEO_EXTENSIONS = {
    'mp4', 'webm', 'ogg', 'mov', 'avi', 'mkv', 'm4v'
}
ALLOWED_EXTENSIONS = IMAGE_EXTENSIONS | ANIMATED_EXTENSIONS | VIDEO_EXTENSIONS

def classify_media(filename: str) -> str:
    ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
    if ext in VIDEO_EXTENSIONS:
        return 'video'
    if ext in ANIMATED_EXTENSIONS:
        return 'animated'
    return 'image'

def main():
    store_id = sys.argv[1] if len(sys.argv) > 1 else '1881'
    try:
        count = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    except Exception:
        count = 1
    count = max(1, min(count, 20))

    repo_root = Path(__file__).resolve().parents[1]
    cfg_path = repo_root / 'store_config.json'
    uploads_dir = repo_root / 'static' / 'uploads'

    if not cfg_path.exists():
        print(f"store_config.json not found at {cfg_path}")
        sys.exit(1)
    if not uploads_dir.exists():
        print(f"uploads folder not found at {uploads_dir}")
        sys.exit(1)

    cfg = json.load(cfg_path.open('r', encoding='utf-8'))
    screens_all = cfg.get('screens', {})
    if store_id not in screens_all:
        print(f"store_id {store_id} not found in config")
        sys.exit(1)

    # Collect usable uploads sorted by mtime desc
    files = []
    for p in uploads_dir.iterdir():
        if not p.is_file():
            continue
        name = p.name
        if '.' not in name:
            continue
        ext = name.rsplit('.', 1)[-1].lower()
        if ext not in ALLOWED_EXTENSIONS:
            continue
        try:
            mtime = p.stat().st_mtime
        except Exception:
            mtime = 0
        files.append((mtime, name))
    files.sort(key=lambda t: t[0], reverse=True)

    if not files:
        print("No eligible uploads found to seed from.")
        sys.exit(1)

    newest = [name for _, name in files[:count]]
    screens = screens_all.get(store_id, {})

    # Backup first
    ts = time.strftime('%Y%m%d-%H%M%S')
    backup_path = repo_root / f'store_config.json.backup.{ts}'
    backup_path.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding='utf-8')
    print(f"Backup written to {backup_path}")

    changed = False
    for sid, sdata in screens.items():
        pl = sdata.setdefault('playlist', [])
        if pl:
            continue  # don't overwrite existing playlists
        # Add newest items
        to_add = newest
        for fname in to_add:
            if any(i.get('file') == fname for i in pl):
                continue
            pl.append({
                'id': str(uuid.uuid4()),
                'file': fname,
                'enabled': True,
                'start': None,
                'end': None,
                'schedule': [],
                'duration': 10,
                'repeat': True,
                'link_next': False,
                'media_type': classify_media(fname),
            })
        if pl:
            # Set primary file to first item for legacy paths
            sdata['file'] = pl[0]['file']
            changed = True
            print(f"Seeded {sid} with {len(pl)} item(s)")

    if changed:
        cfg_path.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding='utf-8')
        print("store_config.json updated")
    else:
        print("No changes (playlists already populated)")

if __name__ == '__main__':
    main()
