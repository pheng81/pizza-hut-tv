import io
import os
import sys
from pathlib import Path

import pytest

# Ensure project root on sys.path for importing app
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import app as flask_app
import json


@pytest.fixture()
def client():
    flask_app.config.update(TESTING=True)
    with flask_app.test_client() as c:
        yield c


def test_upload_media_small_png(client):
    png_sig = b"\x89PNG\r\n\x1a\n" + b"0" * 1024  # tiny fake PNG
    data = {
        'file': (io.BytesIO(png_sig), 'tiny.png')
    }
    resp = client.post('/upload_media', data=data, content_type='multipart/form-data')
    assert resp.status_code == 200, resp.get_data(as_text=True)
    j = resp.get_json()
    assert j and j.get('success') is True
    assert j.get('filename') and j.get('url')


def test_assign_uploaded_file_to_screen(client):
    # First upload
    body = b"GIF89a" + b"0" * 512
    data = {'file': (io.BytesIO(body), 'tiny.gif')}
    r1 = client.post('/upload_media', data=data, content_type='multipart/form-data')
    assert r1.status_code == 200
    up = r1.get_json()
    assert up and up.get('success')
    fname = up['filename']

    # Assign to an existing store/screen from current store_config.json
    # Pick a store that exists in the current config and normalize 'screen1' -> '{store}_screen1'
    cfg_path = ROOT / 'store_config.json'
    with cfg_path.open('r', encoding='utf-8') as f:
        cfg = json.load(f)
    # Prefer a non-master store if available; fall back to master
    master = cfg.get('master_store_id')
    candidates = [s['id'] for s in cfg.get('stores', []) if s.get('id')]
    if master in candidates and len(candidates) > 1:
        # move master to end
        candidates = [c for c in candidates if c != master] + [master]
    chosen = None
    for sid in candidates:
        screens = cfg.get('screens', {}).get(sid, {})
        # Look for a screen1 variant for that store
        if f"{sid}_screen1" in screens or 'screen1' in screens:
            chosen = sid
            break
    if not chosen:
        # As a last resort, pick any store present in config
        chosen = candidates[0]
    payload = {'store_id': chosen, 'screen_id': 'screen1', 'filename': fname}
    r2 = client.post('/assign_to_screen', json=payload)
    assert r2.status_code == 200
    aj = r2.get_json()
    assert aj and aj.get('success')
