"""
One-time admin migration: move legacy media not under users/ namespace
into a per-user namespace and rewrite config references.

Behavior:
- Detects if R2 is enabled via app.r2_enabled(); if so, scans bucket objects.
- Otherwise scans local UPLOAD_FOLDER.
- Moves any object/key that does not start with 'users/' to
  'users/<target_user>/legacy/<original-name>'
- Updates store_config.json references (screen file and playlist items)
  from legacy names to new namespaced keys.

Dry-run by default. Use --apply to perform changes.

Usage:
  python scripts/migrate_legacy_media.py --target-user master [--apply]

Note:
- Requires the Flask app's environment to be configured for R2 if using R2.
- Safe to re-run; skips already-namespaced keys.
"""
import os
import sys
import argparse
from datetime import datetime, timezone

# Reuse app helpers
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
import app as _app  # type: ignore


def main():
    parser = argparse.ArgumentParser(description='Migrate legacy media into per-user namespace')
    parser.add_argument('--target-user', default='master', help='User key to place legacy items under (default: master)')
    parser.add_argument('--apply', action='store_true', help='Perform changes; default is dry-run')
    args = parser.parse_args()

    t_user = args.target_user.strip() or 'master'
    user_root = f"users/{t_user}"
    legacy_prefix = f"{user_root}/legacy"
    dry_run = not args.apply

    moved = []
    errors = []

    # Collect mapping of old->new for later config rewrite
    rewrite_map = {}

    if _app.r2_enabled():
        print('[migrate] R2 mode enabled')
        prefix = ''
        for obj in _app.r2_list_objects(prefix):
            key = obj.get('Key')
            if not key or key.endswith('/'):
                continue
            if key.startswith('users/'):
                continue
            new_key = f"{legacy_prefix}/{key.split('/')[-1]}"
            rewrite_map[key] = new_key
            print(f"[migrate] plan move: {key} -> {new_key}")
            if not dry_run:
                try:
                    s3 = _app.get_s3_client()
                    bucket = os.environ['R2_BUCKET_NAME']
                    s3.copy_object(Bucket=bucket, CopySource={'Bucket': bucket, 'Key': key}, Key=new_key)
                    _app.r2_delete_object(key)
                    moved.append((key, new_key))
                except Exception as e:
                    print(f"[migrate] ERROR moving {key}: {e}")
                    errors.append((key, str(e)))
    else:
        print('[migrate] Local filesystem mode')
        base = _app.app.config['UPLOAD_FOLDER']
        # Ensure destination directory
        if not dry_run:
            os.makedirs(os.path.join(base, legacy_prefix), exist_ok=True)
        # Scan root of uploads for files not under users/
        for root, dirs, files in os.walk(base):
            rel = os.path.relpath(root, base)
            # Skip namespaced directories
            if rel != '.' and rel.split('/')[0].split('\\')[0] == 'users':
                continue
            # Only look at top-level and non-users subdirs for loose files
            for name in files:
                src_key = (os.path.join(rel, name) if rel != '.' else name).replace('\\', '/')
                if src_key.startswith('users/'):
                    continue
                new_key = f"{legacy_prefix}/{name}"
                rewrite_map[src_key] = new_key
                print(f"[migrate] plan move: {src_key} -> {new_key}")
                if not dry_run:
                    try:
                        src_path = os.path.join(base, src_key)
                        dst_path = os.path.join(base, new_key)
                        os.makedirs(os.path.dirname(dst_path), exist_ok=True)
                        os.replace(src_path, dst_path)
                        moved.append((src_key, new_key))
                    except Exception as e:
                        print(f"[migrate] ERROR moving {src_key}: {e}")
                        errors.append((src_key, str(e)))

    # Update config references
    if rewrite_map:
        try:
            cfg = _app.ensure_playlists_structure(_app.load_store_config())
            rewrote = 0
            for sid, screens in (cfg.get('screens') or {}).items():
                for scr_id, sdata in (screens or {}).items():
                    f = sdata.get('file')
                    if f in rewrite_map:
                        sdata['file'] = rewrite_map[f]
                        rewrote += 1
                    for it in sdata.get('playlist', []) or []:
                        fi = it.get('file')
                        if fi in rewrite_map:
                            it['file'] = rewrite_map[fi]
                            rewrote += 1
            if rewrote:
                if dry_run:
                    print(f"[migrate] would rewrite {rewrote} config references")
                else:
                    _app.save_store_config(cfg)
                    print(f"[migrate] rewrote {rewrote} config references")
        except Exception as e:
            print(f"[migrate] ERROR updating config: {e}")
            errors.append(("config", str(e)))

    print('--- summary ---')
    print(f"planned_or_moved: {len(rewrite_map)}; actually moved: {len(moved)}; errors: {len(errors)}; dry_run={dry_run}")
    if errors:
        for k, msg in errors[:20]:
            print(f"error: {k}: {msg}")


if __name__ == '__main__':
    main()
