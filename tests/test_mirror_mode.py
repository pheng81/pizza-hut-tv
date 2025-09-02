import json
import sys
from pathlib import Path
import uuid
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


def _load_cfg():
    cfg_path = ROOT / 'store_config.json'
    if not cfg_path.exists():
        # importing app will create default on first access via endpoints
        pass
    with cfg_path.open('r', encoding='utf-8') as f:
        return json.load(f)


def _save_cfg(cfg):
    cfg_path = ROOT / 'store_config.json'
    tmp = cfg_path.with_suffix(cfg_path.suffix + '.tmp')
    with tmp.open('w', encoding='utf-8') as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)
    tmp.replace(cfg_path)


def test_mirror_replaces_exactly(client):
    # Prepare config: master 1881 with screen1 playlist of two items; target store 2001 with extra items
    cfg = _load_cfg()
    master = cfg.get('master_store_id') or (cfg['stores'][0]['id'] if cfg.get('stores') else '1881')
    if master not in [s['id'] for s in cfg.get('stores', [])]:
        cfg.setdefault('stores', []).append({'id': master, 'name': 'Master'})
    cfg.setdefault('screens', {}).setdefault(master, {})

    # Ensure target store exists
    target = '2001'
    if target not in [s['id'] for s in cfg.get('stores', [])]:
        cfg['stores'].append({'id': target, 'name': 'Target Store'})
    cfg['screens'].setdefault(target, {})

    # Build screen ids
    m_sid = f'{master}_screen1'
    t_sid = f'{target}_screen1'

    # Seed master playlist with two items
    cfg['screens'][master].setdefault(m_sid, {'file': None, 'vertical': False, 'horizontal': True, 'rotation': 0})
    master_items = [
        {
            'id': str(uuid.uuid4()),
            'file': 'users/testuser/2025-09/a.jpg',
            'enabled': True,
            'start': None,
            'end': None,
            'schedule': [],
            'duration': 7,
            'repeat': True,
            'link_next': False,
            'media_type': 'image'
        },
        {
            'id': str(uuid.uuid4()),
            'file': 'users/testuser/2025-09/b.mp4',
            'enabled': True,
            'start': None,
            'end': None,
            'schedule': [],
            'duration': 12,
            'repeat': True,
            'link_next': False,
            'media_type': 'video'
        },
    ]
    cfg['screens'][master][m_sid]['playlist'] = master_items.copy()
    cfg['screens'][master][m_sid]['file'] = master_items[0]['file']

    # Seed target with a different playlist (including an extra that must be deleted)
    cfg['screens'][target][t_sid] = {
        'file': 'users/testuser/2025-08/old.png',
        'vertical': False,
        'horizontal': True,
        'rotation': 0,
        'playlist': [
            {'id': str(uuid.uuid4()), 'file': 'users/testuser/2025-08/old.png', 'enabled': True, 'start': None, 'end': None, 'schedule': [], 'duration': 5, 'repeat': True, 'link_next': False, 'media_type': 'image'},
            {'id': str(uuid.uuid4()), 'file': 'users/testuser/2025-08/extra.jpg', 'enabled': True, 'start': None, 'end': None, 'schedule': [], 'duration': 8, 'repeat': True, 'link_next': False, 'media_type': 'image'},
        ]
    }

    _save_cfg(cfg)

    # Call mirror replicate selecting all master item ids, and target only the 2001 store
    payload = {
        'store_id': master,
        'screen_id': m_sid,  # full id is accepted
        'mode': 'mirror',
        'selected_item_ids': [master_items[0]['id'], master_items[1]['id']],
        'target_store_ids': [target],
    }
    r = client.post('/replicate_screen', json=payload)
    assert r.status_code == 200, r.get_data(as_text=True)
    j = r.get_json()
    assert j and j.get('success')

    # Reload and verify target playlist equals master's (order and files)
    updated = _load_cfg()
    tgt = updated['screens'][target][t_sid]
    mpl = updated['screens'][master][m_sid]['playlist']
    tpl = tgt['playlist']
    assert len(tpl) == len(mpl)
    # Compare file sequence only; ids are regenerated on targets
    assert [i['file'] for i in tpl] == [i['file'] for i in mpl]
    # Target primary file should be first master file
    assert tgt['file'] == mpl[0]['file']
