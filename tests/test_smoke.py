import os
import sys
from pathlib import Path
import pytest

# Ensure the project root (parent of this tests/ directory) is on sys.path so "import app" works
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from app import app as flask_app


@pytest.fixture()
def client():
    flask_app.config.update(TESTING=True)
    with flask_app.test_client() as client:
        yield client


def test_healthz(client):
    resp = client.get("/healthz")
    assert resp.status_code == 200
    # Accept either plain text 'OK' or JSON with success flag
    body = resp.get_data(as_text=True)
    assert body.strip() == "OK" or resp.is_json


def test_dashboard_renders(client):
    resp = client.get("/")
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert "Pizza Hut TV - Store Management Dashboard" in html
