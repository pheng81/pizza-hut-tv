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
    # Using store_id '1765' and screen_id 'screen1' (normalizes to '1765_screen1')
    payload = {'store_id': '1765', 'screen_id': 'screen1', 'filename': fname}
    r2 = client.post('/assign_to_screen', json=payload)
    assert r2.status_code == 200
    aj = r2.get_json()
    assert aj and aj.get('success')
