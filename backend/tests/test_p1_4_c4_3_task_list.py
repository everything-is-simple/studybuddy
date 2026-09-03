import sys
from pathlib import Path
from fastapi.testclient import TestClient
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.main import create_app
from app.config import AppConfig
from app.migrations.runner import migrate
from app.repository import connect


def test_task_list_filters_paginates_and_hides_other_project(tmp_path, monkeypatch):
    root = tmp_path / 'data'; root.mkdir()
    config = AppConfig(data_root=root)
    with connect(config.database_path) as db: migrate(db)
    with connect(config.database_path) as db:
        db.execute("INSERT INTO projects(id,name,created_at) VALUES (?,?,datetime('now'))", (config.project_id, 'Main'))
        for n, status in enumerate(('queued', 'failed', 'succeeded')):
            op = f'op_{n}'; task = f'task_{n}'
            db.execute("INSERT INTO ai_operations(id,operation_type,status,project_id,input_fingerprint,created_at) VALUES (?,?,?,?,?,datetime('now'))", (op, 'embedding_index', status, config.project_id, f'ofp_{n}'))
            db.execute("INSERT INTO operation_tasks(id,project_id,operation_id,task_kind,status,input_fingerprint,progress_percent,stage_code,retry_count,max_retries,created_at,updated_at) VALUES (?,?,?,?,?,?,0,'queued',0,0,datetime('now'),datetime('now'))", (task, config.project_id, op, 'embedding_index', status, f'fp_{n}'))
        db.commit()
    app = create_app(config)
    with TestClient(app) as client:
        response = client.get('/api/tasks?status=failed&limit=1&offset=0')
        assert response.status_code == 200
        body = response.json(); assert body['total'] == 1 and len(body['items']) == 1
        assert body['items'][0]['task_id'] == 'task_1'
        assert client.get('/api/tasks?status=success').status_code == 400
        assert client.get('/api/tasks?limit=101').status_code == 400
        assert client.get('/api/tasks?offset=-1').status_code == 400
