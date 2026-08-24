from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.config import AppConfig
from app.main import create_app
from app.repository import (
    append_study_progress_event,
    connect,
    create_knowledge_module,
    create_learning_goal,
    create_module_source_link,
    create_plan_item_source_link,
    create_study_plan,
    create_study_plan_item,
    index_material_revision,
    refresh_study_source_links,
    transition_study_plan,
)


def _client(root: Path) -> TestClient:
    return TestClient(create_app(AppConfig(data_root=root)))


def _material(client: TestClient) -> tuple[str, str, str]:
    result = client.post('/api/materials', files={'file': ('source.txt', b'Lifecycle source text.', 'text/plain')}).json()
    return str(result['material_id']), str(result['extraction_id']), str(result['status'])


def _plan(connection, project_id: str, material_id: str, extraction_id: str):
    goal = create_learning_goal(connection, project_id=project_id, title='Lifecycle goal')
    module = create_knowledge_module(connection, project_id=project_id, title='Lifecycle module')
    plan = create_study_plan(connection, project_id=project_id, goal_id=goal['id'], title='Lifecycle plan')
    item = create_study_plan_item(connection, project_id=project_id, plan_id=plan['id'], title='Read source', module_id=module['id'])
    revision = index_material_revision(connection, material_id, extraction_id)
    chunk = connection.execute('SELECT id FROM chunks WHERE revision_id=? LIMIT 1', (revision['id'],)).fetchone()[0]
    link_payload = {'material_id': material_id, 'revision_id': revision['id'], 'extraction_id': extraction_id, 'chunk_id': chunk}
    module_link = create_module_source_link(connection, project_id=project_id, module_id=module['id'], payload=link_payload)
    item_link = create_plan_item_source_link(connection, project_id=project_id, plan_id=plan['id'], item_id=item['id'], payload=link_payload)
    transition_study_plan(connection, project_id=project_id, plan_id=plan['id'], target='confirmed')
    transition_study_plan(connection, project_id=project_id, plan_id=plan['id'], target='active')
    append_study_progress_event(connection, project_id=project_id, plan_id=plan['id'], item_id=item['id'], event_type='completed')
    return goal, module, plan, item, revision, module_link, item_link


def test_material_lifecycle_preserves_plan_progress_and_requires_explicit_refresh(tmp_path: Path):
    with _client(tmp_path) as client:
        material_id, extraction_id, _ = _material(client)
        with connect(tmp_path / 'studybuddy.sqlite3') as connection:
            goal, module, plan, item, revision, module_link, item_link = _plan(connection, 'default', material_id, extraction_id)
            assert module_link['status'] == 'valid'
            assert item_link['status'] == 'valid'
            assert connection.execute('SELECT COUNT(*) FROM study_progress_events').fetchone()[0] == 1

        with connect(tmp_path / 'studybuddy.sqlite3') as connection:
            before_restore = connection.execute('SELECT COUNT(*) FROM extractions').fetchone()[0]
        assert client.delete(f'/api/materials/{material_id}').status_code == 204
        deleted_links = client.get('/api/study/sources?plan_id=' + plan['id']).json()
        assert {link['status'] for link in deleted_links} == {'source_deleted'}
        assert client.post(f'/api/materials/{material_id}/restore').status_code == 200
        with connect(tmp_path / 'studybuddy.sqlite3') as connection:
            assert connection.execute('SELECT COUNT(*) FROM extractions').fetchone()[0] == before_restore
        # Restore does not auto-repair/promote source links.
        restored_links = client.get('/api/study/sources?plan_id=' + plan['id']).json()
        assert {link['status'] for link in restored_links} == {'source_deleted'}
        assert client.post('/api/study/sources/refresh').status_code == 200
        valid_links = client.get('/api/study/sources?plan_id=' + plan['id']).json()
        assert {link['status'] for link in valid_links} == {'valid'}
        with connect(tmp_path / 'studybuddy.sqlite3') as connection:
            assert connection.execute('SELECT status FROM study_plans WHERE id=?', (plan['id'],)).fetchone()[0] == 'active'
            assert connection.execute('SELECT status FROM study_plan_items WHERE id=?', (item['id'],)).fetchone()[0] == 'completed'
            assert connection.execute('SELECT COUNT(*) FROM study_progress_events').fetchone()[0] == 1


def test_active_plan_allows_unavailable_source_for_pending_started_and_completed_items(tmp_path: Path):
    with _client(tmp_path) as client:
        material_id, extraction_id, _ = _material(client)
        with connect(tmp_path / 'studybuddy.sqlite3') as connection:
            goal = create_learning_goal(connection, project_id='default', title='Warning goal')
            module = create_knowledge_module(connection, project_id='default', title='Warning module')
            plan = create_study_plan(connection, project_id='default', goal_id=goal['id'], title='Warning plan')
            pending = create_study_plan_item(connection, project_id='default', plan_id=plan['id'], title='Not started', module_id=module['id'])
            editing = create_study_plan_item(connection, project_id='default', plan_id=plan['id'], title='Edited before activation', module_id=module['id'])
            completed = create_study_plan_item(connection, project_id='default', plan_id=plan['id'], title='Completed', module_id=module['id'])
            revision = index_material_revision(connection, material_id, extraction_id)
            chunk = connection.execute('SELECT id FROM chunks WHERE revision_id=? LIMIT 1', (revision['id'],)).fetchone()[0]
            payload = {'material_id': material_id, 'revision_id': revision['id'], 'extraction_id': extraction_id, 'chunk_id': chunk}
            create_module_source_link(connection, project_id='default', module_id=module['id'], payload=payload)
            from app.repository import update_study_plan_item
            update_study_plan_item(connection, project_id='default', plan_id=plan['id'], item_id=editing['id'], title='Edited item')
            transition_study_plan(connection, project_id='default', plan_id=plan['id'], target='confirmed')
            transition_study_plan(connection, project_id='default', plan_id=plan['id'], target='active')
            append_study_progress_event(connection, project_id='default', plan_id=plan['id'], item_id=editing['id'], event_type='started')
            append_study_progress_event(connection, project_id='default', plan_id=plan['id'], item_id=completed['id'], event_type='completed')
            assert connection.execute("SELECT COUNT(*) FROM ai_operations").fetchone()[0] == 0
        assert client.delete(f'/api/materials/{material_id}').status_code == 204
        detail = client.get(f'/api/study/plans/{plan["id"]}').json()
        assert detail['status'] == 'active'
        assert {item['status'] for item in detail['items']} == {'pending', 'in_progress', 'completed'}
        assert detail['progress']['source_warning_count'] == 1
        assert {link['status'] for link in client.get(f'/api/study/sources?plan_id={plan["id"]}').json()} == {'source_deleted'}
        with connect(tmp_path / 'studybuddy.sqlite3') as connection:
            assert connection.execute('SELECT COUNT(*) FROM study_progress_events').fetchone()[0] == 2
            assert connection.execute("SELECT COUNT(*) FROM ai_operations").fetchone()[0] == 0


def test_purge_keeps_historical_plan_and_marks_source_unavailable(tmp_path: Path):
    with _client(tmp_path) as client:
        material_id, extraction_id, _ = _material(client)
        with connect(tmp_path / 'studybuddy.sqlite3') as connection:
            _, _, plan, item, _, _, _ = _plan(connection, 'default', material_id, extraction_id)
        assert client.delete(f'/api/materials/{material_id}').status_code == 204
        assert client.post(f'/api/materials/{material_id}/purge').status_code == 200
        links = client.get('/api/study/sources?plan_id=' + plan['id']).json()
        assert links and {link['status'] for link in links} == {'source_unavailable'}
        detail = client.get(f'/api/study/plans/{plan["id"]}')
        assert detail.status_code == 200
        assert detail.json()['progress']['completed_count'] == 1
        assert detail.json()['progress']['source_warning_count'] == len(links)
        assert 'text' not in links[0]
        assert 'original_name' not in links[0]
        assert 'stored_path' not in detail.text
        assert client.post('/api/study/sources/refresh').status_code == 200
        assert {link['status'] for link in client.get('/api/study/sources?plan_id=' + plan['id']).json()} == {'source_unavailable'}
        with connect(tmp_path / 'studybuddy.sqlite3') as connection:
            assert connection.execute('SELECT COUNT(*) FROM study_progress_events').fetchone()[0] == 1
            assert connection.execute('SELECT status FROM study_plan_items WHERE id=?', (item['id'],)).fetchone()[0] == 'completed'


def test_reindex_marks_old_link_stale_and_rejects_editing_active_item(tmp_path: Path):
    with _client(tmp_path) as client:
        material_id, extraction_id, _ = _material(client)
        with connect(tmp_path / 'studybuddy.sqlite3') as connection:
            _, _, plan, item, revision, _, _ = _plan(connection, 'default', material_id, extraction_id)
            old_chunk = connection.execute('SELECT id FROM chunks WHERE revision_id=? LIMIT 1', (revision['id'],)).fetchone()[0]
            connection.execute(
                "INSERT INTO extractions (id,material_id,parser_id,parser_version,status,text,warnings_json,created_at,error_code) "
                "SELECT 'extraction_reindexed',material_id,parser_id,parser_version,status, text || ' Revised',warnings_json,created_at,error_code "
                "FROM extractions WHERE id=?",
                (extraction_id,),
            )
            connection.execute(
                "INSERT INTO text_spans (id,extraction_id,ordinal,span_kind,label,text) "
                "SELECT 'span_reindexed', 'extraction_reindexed', ordinal, span_kind, label, text || ' Revised' "
                "FROM text_spans WHERE extraction_id=?",
                (extraction_id,),
            )
            index_material_revision(connection, material_id, 'extraction_reindexed')
            old_link = connection.execute(
                'SELECT status FROM plan_item_source_links WHERE plan_item_id=?', (item['id'],)
            ).fetchone()[0]
            assert old_link == 'stale'
            assert connection.execute('SELECT COUNT(*) FROM study_progress_events').fetchone()[0] == 1
            assert connection.execute('SELECT status FROM study_plan_items WHERE id=?', (item['id'],)).fetchone()[0] == 'completed'
            assert connection.execute('SELECT COUNT(*) FROM chunks WHERE id=?', (old_chunk,)).fetchone()[0] == 1
        assert client.delete(f'/api/materials/{material_id}').status_code == 204
        bad = client.post(
            f'/api/study/plans/{plan["id"]}/items/{item["id"]}/sources',
            json={'material_id': material_id, 'revision_id': revision['id'], 'chunk_id': 'missing'},
        )
        assert bad.status_code == 409
        assert bad.json()['detail'] == 'study_plan_edit_not_allowed'
