from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.config import AppConfig
from app.main import create_app
from app.repository import connect, create_generation_operation, fail_generation_operation


def client(root: Path, provider: str | None = "fake") -> TestClient:
    return TestClient(create_app(AppConfig(data_root=root, ai_provider_id=provider)))


def indexed_material(api: TestClient, name: str = "source.txt", text: str = "A controlled source establishes a stable result.") -> tuple[str, str]:
    uploaded = api.post("/api/materials", files={"file": (name, text.encode(), "text/plain")})
    assert uploaded.status_code == 201
    material_id = uploaded.json()["material_id"]
    indexed = api.post(f"/api/materials/{material_id}/ai-index")
    assert indexed.status_code == 200
    return material_id, indexed.json()["revision_id"]


def test_fake_generation_creates_cited_drafts_and_audits_operation(tmp_path: Path):
    with client(tmp_path) as api:
        material_id, revision_id = indexed_material(api)
        deck_id = api.post("/api/study/decks", json={"title": "Generated cards"}).json()["id"]
        card = api.post(f"/api/study/decks/{deck_id}/generate", json={
            "topic": "controlled source", "material_ids": [material_id], "count": 1,
        }, headers={"Idempotency-Key": "generated-card-1"})
        assert card.status_code == 200
        card_payload = card.json()
        assert card_payload["status"] == "succeeded" and card_payload["replay"] is False
        artifact = card_payload["artifacts"][0]
        assert artifact["status"] == "draft" and artifact["card_type"] == "ai_generated"
        assert artifact["source_revision"] == revision_id
        assert artifact["citations"][0]["status"] == "valid"
        assert "answer_key" not in card.text

        set_id = api.post("/api/study/exercise-sets", json={"title": "Generated exercises"}).json()["id"]
        exercise = api.post(f"/api/study/exercise-sets/{set_id}/generate", json={
            "topic": "stable result", "material_ids": [material_id], "count": 1,
            "exercise_type": "multiple_choice",
        })
        assert exercise.status_code == 200
        generated = exercise.json()["artifacts"][0]
        assert generated["status"] == "draft" and generated["exercise_kind"] == "ai_generated"
        assert generated["exercise_type"] == "multiple_choice"
        assert generated["source_revision"] == revision_id
        assert "answer_key" not in exercise.text
        with connect(tmp_path / "studybuddy.sqlite3") as db:
            operations = db.execute(
                "SELECT operation_type,status,source_revision,retrieval_run_id,provider_id,model_id,output_artifact_id "
                "FROM ai_operations WHERE operation_type LIKE 'generate_%' ORDER BY created_at"
            ).fetchall()
            assert len(operations) == 2
            assert all(row[1] == "succeeded" and row[2] == revision_id and row[3] and row[4] == "fake" and row[5] for row in operations)
            assert db.execute("SELECT COUNT(*) FROM study_cards WHERE status='ready'").fetchone()[0] == 0
            assert db.execute("SELECT COUNT(*) FROM exercises WHERE status='ready'").fetchone()[0] == 0


def test_generation_idempotency_and_request_boundaries(tmp_path: Path):
    with client(tmp_path) as api:
        material_id, _revision_id = indexed_material(api)
        deck_id = api.post("/api/study/decks", json={"title": "Idempotent"}).json()["id"]
        body = {"topic": "controlled source", "material_ids": [material_id], "count": 1}
        first = api.post(f"/api/study/decks/{deck_id}/generate", json=body, headers={"Idempotency-Key": "generate-key"})
        replay = api.post(f"/api/study/decks/{deck_id}/generate", json=body, headers={"Idempotency-Key": "generate-key"})
        assert first.status_code == replay.status_code == 200
        assert replay.json()["replay"] is True
        assert replay.json()["artifacts"][0]["id"] == first.json()["artifacts"][0]["id"]
        mismatch = api.post(f"/api/study/decks/{deck_id}/generate", json={**body, "topic": "different"}, headers={"Idempotency-Key": "generate-key"})
        assert mismatch.status_code == 409 and mismatch.json()["detail"] == "generation_idempotency_key_mismatch"
        multiple = api.post(f"/api/study/decks/{deck_id}/generate", json={**body, "count": 2})
        assert multiple.status_code == 200 and len(multiple.json()["artifacts"]) == 2
        assert all(item["status"] == "draft" for item in multiple.json()["artifacts"])
        assert api.post(f"/api/study/decks/{deck_id}/generate", json={"topic": "source", "material_ids": [], "count": 1}).status_code == 400
        unindexed = api.post("/api/materials", files={"file": ("unindexed.txt", b"source text", "text/plain")}).json()
        not_ready = api.post(f"/api/study/decks/{deck_id}/generate", json={"topic": "source", "material_ids": [unindexed["material_id"]], "count": 1})
        assert not_ready.status_code == 409 and not_ready.json()["detail"] == "retrieval_not_ready"
        empty = api.post(f"/api/study/decks/{deck_id}/generate", json={**body, "topic": "absent-token"})
        assert empty.status_code == 409 and empty.json()["detail"] == "retrieval_empty"

        with connect(tmp_path / "studybuddy.sqlite3") as db:
            pending = create_generation_operation(
                db, project_id="default", artifact_kind="card", container_id=deck_id,
                topic="controlled source", material_ids=[material_id], retrieval_mode="lexical",
                allow_fallback=True, count=1, exercise_type=None, source_revision=None, request_id=None,
                idempotency_key="running-generation-key",
            )
        running = api.post(f"/api/study/decks/{deck_id}/generate", json=body, headers={"Idempotency-Key": "running-generation-key"})
        assert running.status_code == 409 and running.json()["detail"] == "generation_in_progress"
        with connect(tmp_path / "studybuddy.sqlite3") as db:
            fail_generation_operation(db, pending["operation_id"], "provider_timeout")
        retry = api.post(f"/api/study/decks/{deck_id}/generate", json=body, headers={"Idempotency-Key": "running-generation-key"})
        assert retry.status_code == 200 and retry.json()["replay"] is False


def test_fake_generation_supports_all_frozen_exercise_types(tmp_path: Path):
    with client(tmp_path) as api:
        material_id, _revision_id = indexed_material(api)
        set_id = api.post("/api/study/exercise-sets", json={"title": "All types"}).json()["id"]
        for exercise_type in ("multiple_choice", "true_false", "short_answer"):
            response = api.post(f"/api/study/exercise-sets/{set_id}/generate", json={
                "topic": "controlled source", "material_ids": [material_id], "count": 1,
                "exercise_type": exercise_type,
            })
            assert response.status_code == 200
            artifact = response.json()["artifacts"][0]
            assert artifact["exercise_type"] == exercise_type
            assert artifact["exercise_kind"] == "ai_generated" and artifact["status"] == "draft"
            assert artifact["citations"][0]["status"] == "valid"
            assert "answer_key" not in response.text


def test_generation_rejects_explicit_stale_source_revision(tmp_path: Path):
    with client(tmp_path) as api:
        material_id, revision_id = indexed_material(api)
        deck_id = api.post("/api/study/decks", json={"title": "Explicit stale"}).json()["id"]
        stale = api.post(f"/api/study/decks/{deck_id}/generate", json={
            "topic": "controlled source", "material_ids": [material_id], "count": 1,
            "source_revision": revision_id + "stale",
        })
        assert stale.status_code == 400 and stale.json()["detail"] == "generation_stale_source"
        current = api.post(f"/api/study/decks/{deck_id}/generate", json={
            "topic": "controlled source", "material_ids": [material_id], "count": 1,
            "source_revision": revision_id,
        })
        assert current.status_code == 200 and current.json()["artifacts"][0]["source_revision"] == revision_id


def test_generation_failure_keeps_only_failed_operation_and_no_draft(monkeypatch, tmp_path: Path):
    from app import main
    from app.providers import ProviderResult

    class ForgingProvider:
        provider_id = "fake"
        model_id = "fake-studybuddy-v1"

        def generate_answer(self, _request):
            return ProviderResult('{"items":[{"front":"q","back":"a","explanation":"","tags":[],"citations":["ctx-forged-key"]}]}', [], self.provider_id, self.model_id, 1, 1)

    class ForgingRegistry:
        def configured_provider(self):
            return ForgingProvider()

    monkeypatch.setattr(main, "provider_registry", lambda *_args, **_kwargs: ForgingRegistry())
    with client(tmp_path) as api:
        material_id, _revision_id = indexed_material(api)
        deck_id = api.post("/api/study/decks", json={"title": "Failure"}).json()["id"]
        failed = api.post(f"/api/study/decks/{deck_id}/generate", json={"topic": "controlled", "material_ids": [material_id], "count": 1})
        assert failed.status_code == 400 and failed.json()["detail"] == "citation_verification_failed"
        with connect(tmp_path / "studybuddy.sqlite3") as db:
            assert db.execute("SELECT COUNT(*) FROM study_cards").fetchone()[0] == 0
            assert db.execute("SELECT status,error_code FROM ai_operations WHERE operation_type='generate_card'").fetchone()[:] == ("failed", "citation_verification_failed")


def test_generation_rejects_malformed_response_and_rolls_back_draft_write(monkeypatch, tmp_path: Path):
    from app import main
    from app.providers import ProviderResult

    class MalformedProvider:
        provider_id = "fake"
        model_id = "fake-studybuddy-v1"

        def generate_answer(self, _request):
            return ProviderResult('{"items":[{"front":"missing required fields"}]}', [], self.provider_id, self.model_id, 1, 1)

    class MalformedRegistry:
        def configured_provider(self):
            return MalformedProvider()

    with client(tmp_path) as api:
        material_id, _revision_id = indexed_material(api)
        deck_id = api.post("/api/study/decks", json={"title": "Malformed"}).json()["id"]
        monkeypatch.setattr(main, "provider_registry", lambda *_args, **_kwargs: MalformedRegistry())
        malformed = api.post(f"/api/study/decks/{deck_id}/generate", json={"topic": "controlled", "material_ids": [material_id], "count": 1})
        assert malformed.status_code == 400 and malformed.json()["detail"] == "generation_schema_invalid"
        with connect(tmp_path / "studybuddy.sqlite3") as db:
            assert db.execute("SELECT COUNT(*) FROM study_cards WHERE deck_id=?", (deck_id,)).fetchone()[0] == 0

    # A database failure after the artifact INSERT still rolls back the draft
    # and citations; only the separately persisted failed operation remains.
    monkeypatch.undo()
    with client(tmp_path) as api:
        material_id, _revision_id = indexed_material(api, "rollback.txt", "A distinct source supports transaction rollback.")
        deck_id = api.post("/api/study/decks", json={"title": "Rollback"}).json()["id"]
        with connect(tmp_path / "studybuddy.sqlite3") as db:
            db.execute("CREATE TRIGGER fail_generated_card_citation BEFORE INSERT ON card_citations BEGIN SELECT RAISE(ABORT, 'test'); END")
            db.commit()
        failed = api.post(f"/api/study/decks/{deck_id}/generate", json={"topic": "transaction rollback", "material_ids": [material_id], "count": 1})
        assert failed.status_code == 500 and failed.json()["detail"] == "generation_failed"
        with connect(tmp_path / "studybuddy.sqlite3") as db:
            assert db.execute("SELECT COUNT(*) FROM study_cards WHERE deck_id=?", (deck_id,)).fetchone()[0] == 0
            assert db.execute("SELECT status,error_code FROM ai_operations WHERE operation_type='generate_card' ORDER BY created_at DESC").fetchone()[:] == ("failed", "generation_persist_failed")


def test_generation_not_configured_and_provider_failure_are_safe(monkeypatch, tmp_path: Path):
    with client(tmp_path, provider=None) as api:
        material_id, _revision_id = indexed_material(api)
        deck_id = api.post("/api/study/decks", json={"title": "Unavailable"}).json()["id"]
        response = api.post(f"/api/study/decks/{deck_id}/generate", json={"topic": "controlled", "material_ids": [material_id], "count": 1})
        assert response.status_code == 503 and response.json()["detail"] == "provider_not_configured"
        with connect(tmp_path / "studybuddy.sqlite3") as db:
            assert db.execute("SELECT status,error_code FROM ai_operations WHERE operation_type='generate_card'").fetchone()[:] == ("failed", "provider_not_configured")

    from app import main
    from app.providers import ProviderError

    class TimeoutProvider:
        def generate_answer(self, _request):
            raise ProviderError("provider_timeout")

    class TimeoutRegistry:
        def configured_provider(self):
            return TimeoutProvider()

    with client(tmp_path) as api:
        material_id, _revision_id = indexed_material(api, "timeout.txt", "A distinct source establishes a timeout boundary.")
        deck_id = api.post("/api/study/decks", json={"title": "Timeout"}).json()["id"]
        monkeypatch.setattr(main, "provider_registry", lambda *_args, **_kwargs: TimeoutRegistry())
        response = api.post(f"/api/study/decks/{deck_id}/generate", json={"topic": "timeout boundary", "material_ids": [material_id], "count": 1})
        assert response.status_code == 504 and response.json()["detail"] == "provider_timeout"
        with connect(tmp_path / "studybuddy.sqlite3") as db:
            assert db.execute("SELECT status,error_code FROM ai_operations WHERE operation_type='generate_card' ORDER BY created_at DESC").fetchone()[:] == ("failed", "provider_timeout")
            assert db.execute("SELECT COUNT(*) FROM study_cards WHERE deck_id=?", (deck_id,)).fetchone()[0] == 0


def test_generation_rejects_source_changed_while_provider_runs(monkeypatch, tmp_path: Path):
    from app import main
    from app.providers import ProviderResult

    with client(tmp_path) as api:
        material_id, _revision_id = indexed_material(api)
        deck_id = api.post("/api/study/decks", json={"title": "Stale"}).json()["id"]
        original_persist = main.persist_generated_draft

        def stale_persist(*args, **kwargs):
            kwargs["source_revision"] = "revision_changed"
            return original_persist(*args, **kwargs)

        monkeypatch.setattr(main, "persist_generated_draft", stale_persist)
        response = api.post(f"/api/study/decks/{deck_id}/generate", json={"topic": "controlled", "material_ids": [material_id], "count": 1})
        assert response.status_code == 400 and response.json()["detail"] == "generation_stale_source"
        with connect(tmp_path / "studybuddy.sqlite3") as db:
            assert db.execute("SELECT status,error_code FROM ai_operations WHERE operation_type='generate_card'").fetchone()[:] == ("failed", "generation_stale_source")
            assert db.execute("SELECT COUNT(*) FROM study_cards WHERE deck_id=?", (deck_id,)).fetchone()[0] == 0
