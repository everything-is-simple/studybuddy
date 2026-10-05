"""S2 repository uses real source identities, atomic writes and maintained FTS."""
import sqlite3
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.config import AppConfig
from app.main import create_app
from app.repository import connect
from app.repositories import knowledge_modules as km


@pytest.fixture
def source(tmp_path):
    config = AppConfig(data_root=tmp_path, ai_provider_id="fake")
    with TestClient(create_app(config)) as api:
        mid = api.post("/api/materials", files={"file": ("physics.txt", b"Newton force mass acceleration is a stable controlled result.", "text/plain")}).json()["material_id"]
        assert api.post(f"/api/materials/{mid}/ai-index").status_code == 200
        cid = api.get("/api/knowledge-modules/sources", params={"material_id": mid}).json()[0]["chunk_id"]
    return config, mid, cid


def test_crud_search_and_shared_identity(source):
    config, mid, cid = source
    with connect(config.database_path) as c:
        module = km.create_modules(c, project_id=config.project_id, material_id=mid, payloads=[{"title":"Newton force","chunk_ids":[cid],"tags":["physics"]}])[0]
        key = module["id"]
        assert module["source_status"] == "valid" and module["source_evidence"]["span_ids"]
        assert c.execute("SELECT title FROM knowledge_modules WHERE id=?", (key,)).fetchone()[0] == "Newton force"
        assert km.list_modules(c, project_id=config.project_id, query="Newton")["total"] == 1
        km.update_module(c, project_id=config.project_id, module_id=key, payload={"title":"Momentum conservation"})
        assert km.list_modules(c, project_id=config.project_id, query="Newton")["total"] == 0
        assert km.list_modules(c, project_id=config.project_id, query="Momentum")["total"] == 1
        # Edits through the existing plan module API must update the same FTS identity.
        c.execute("UPDATE knowledge_modules SET title='Energy' WHERE id=?", (key,)); c.commit()
        assert km.list_modules(c, project_id=config.project_id, query="Energy")["total"] == 1
        km.transition_module(c, project_id=config.project_id, module_id=key, action="delete")
        assert km.get_module(c, project_id=config.project_id, module_id=key) is None
        assert c.execute("SELECT COUNT(*) FROM s2_knowledge_modules_fts WHERE module_id=?", (key,)).fetchone()[0] == 0
        assert c.execute("SELECT status FROM knowledge_modules WHERE id=?", (key,)).fetchone()[0] == "archived"


def test_batch_failure_rolls_back_modules_sources_and_fts(source):
    config, mid, cid = source
    with connect(config.database_path) as c:
        c.execute("CREATE TEMP TRIGGER fail_second BEFORE INSERT ON knowledge_modules WHEN new.title='Bad' BEGIN SELECT RAISE(ABORT,'synthetic'); END")
        with pytest.raises(sqlite3.IntegrityError):
            km.create_modules(c, project_id=config.project_id, material_id=mid, payloads=[
                {"title":"Good","chunk_ids":[cid]},{"title":"Bad","chunk_ids":[cid]}])
        for table in ("knowledge_modules","s2_knowledge_modules","module_source_links","s2_knowledge_modules_fts"):
            assert c.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0


@pytest.mark.parametrize("payload", [
    {"title":"", "chunk_ids":[]}, {"title":"Bad","chunk_ids":["unknown"]},
    {"title":"Bad","importance":True}, {"title":"Bad","difficulty":6},
    {"title":"Bad","estimated_minutes":-1}, {"title":"Bad","tags":["x"*51]},
])
def test_rejects_invalid_payload_without_partial_write(source, payload):
    config, mid, cid = source
    with connect(config.database_path) as c:
        with pytest.raises(ValueError):
            km.create_modules(c, project_id=config.project_id, material_id=mid, payloads=[{"chunk_ids":[cid],**payload}])
        assert c.execute("SELECT COUNT(*) FROM s2_knowledge_modules").fetchone()[0] == 0


def test_project_isolation_and_safe_search(source):
    config, mid, cid = source
    with connect(config.database_path) as c:
        module = km.create_modules(c, project_id=config.project_id, material_id=mid, payloads=[{"title":"Newton force","chunk_ids":[cid]}])[0]
        assert km.get_module(c, project_id="other", module_id=module["id"]) is None
        assert km.list_modules(c, project_id="other")["total"] == 0
        assert km.list_modules(c, project_id=config.project_id, query='Newton" OR missing')["total"] == 0
        with pytest.raises(ValueError, match="material_not_found"):
            km.create_modules(c, project_id="other", material_id=mid, payloads=[{"title":"X","chunk_ids":[cid]}])
