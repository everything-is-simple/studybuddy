from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.config import AppConfig
from app.main import create_app


def client(root: Path) -> TestClient:
    return TestClient(create_app(AppConfig(data_root=root)))


def setup_source(api: TestClient) -> tuple[dict, dict]:
    material = api.post('/api/materials', files={'file': ('source.txt', b'C4-2 source body', 'text/plain')}).json()
    indexed = api.post(f"/api/materials/{material['material_id']}/ai-index").json()
    with sqlite3.connect(api.app.state.config.database_path) as db:
        chunk = db.execute('SELECT id,text FROM chunks WHERE material_id=?', (material['material_id'],)).fetchone()
    with sqlite3.connect(api.app.state.config.database_path) as db:
        extraction_id = db.execute('SELECT extraction_id FROM chunks WHERE id=?', (chunk[0],)).fetchone()[0]
    return material, {'revision_id': indexed['revision_id'], 'extraction_id': extraction_id, 'chunk_id': chunk[0], 'quote': chunk[1]}


def test_source_candidates_are_identity_only_and_links_delete_with_owner_scope(tmp_path: Path):
    with client(tmp_path) as api:
        material, source = setup_source(api)
        candidates = api.get('/api/study/source-candidates')
        assert candidates.status_code == 200
        assert candidates.json()[0]['material_name'] == 'source.txt'
        assert 'text' not in candidates.text and 'stored_path' not in candidates.text
        module = api.post('/api/study/modules', json={'title': 'C4-2 module'}).json()
        goal = api.post('/api/study/goals', json={'title': 'C4-2 goal'}).json()
        plan = api.post('/api/study/plans', json={'goal_id': goal['id'], 'title': 'C4-2 plan'}).json()
        item = api.post(f"/api/study/plans/{plan['id']}/items", json={'title': 'C4-2 item'}).json()
        payload = {key: source[key] for key in ('revision_id', 'extraction_id', 'chunk_id')}
        payload['material_id'] = material['material_id']
        module_link = api.post(f"/api/study/modules/{module['id']}/sources", json=payload)
        item_link = api.post(f"/api/study/plans/{plan['id']}/items/{item['id']}/sources", json=payload)
        assert module_link.status_code == 201 and item_link.status_code == 201
        assert api.delete(f"/api/study/modules/{module['id']}/sources/{item_link.json()['id']}").status_code == 404
        assert api.delete(f"/api/study/modules/{module['id']}/sources/{module_link.json()['id']}").status_code == 204
        assert api.get(f"/api/study/sources?item_id={item['id']}").json()
        assert api.delete(f"/api/study/plans/{plan['id']}/items/{item['id']}/sources/{item_link.json()['id']}").status_code == 204
        assert api.get('/api/study/sources').json() == []
        assert api.get(f"/api/materials/{material['material_id']}").status_code == 200


def test_source_delete_respects_archived_plan_edit_boundary(tmp_path: Path):
    with client(tmp_path) as api:
        material, source = setup_source(api)
        goal = api.post('/api/study/goals', json={'title': 'Goal'}).json()
        plan = api.post('/api/study/plans', json={'goal_id': goal['id'], 'title': 'Plan'}).json()
        item = api.post(f"/api/study/plans/{plan['id']}/items", json={'title': 'Item'}).json()
        payload = {'material_id': material['material_id'], **{key: source[key] for key in ('revision_id', 'extraction_id', 'chunk_id')}}
        link = api.post(f"/api/study/plans/{plan['id']}/items/{item['id']}/sources", json=payload).json()
        assert api.post(f"/api/study/plans/{plan['id']}/archive").status_code == 200
        response = api.delete(f"/api/study/plans/{plan['id']}/items/{item['id']}/sources/{link['id']}")
        assert response.status_code == 409
        assert response.json()['detail'] == 'study_plan_edit_not_allowed'
