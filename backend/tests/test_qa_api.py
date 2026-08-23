from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.config import AppConfig
from app.embedding import FakeEmbeddingProvider
from app.main import create_app
from app.providers import ProviderResult
from app.repository import connect, create_qa_request, index_embeddings_for_material, index_material_revision


def make_client(root: Path, *, fake: bool = True, embedding: bool = False) -> TestClient:
    return TestClient(create_app(AppConfig(
        data_root=root, max_upload_bytes=4096, ai_provider_id="fake" if fake else None,
        embedding_provider_id="fake" if embedding else None,
        embedding_model_id="fake-embedding-v1" if embedding else None,
    )))


def upload(client: TestClient, name: str, text: str) -> dict:
    response = client.post("/api/materials", files={"file": (name, text.encode(), "text/plain")})
    assert response.status_code == 201
    return response.json()


def index(client: TestClient, material_id: str) -> None:
    assert client.post(f"/api/materials/{material_id}/ai-index").status_code == 200


def ask(client: TestClient, question: str, material_id: str, **extra) -> object:
    return client.post("/api/qa/ask", json={
        "question": question, "material_ids": [material_id], **extra,
    })


def test_qa_ask_success_persists_traceable_answer(tmp_path: Path):
    with make_client(tmp_path) as client:
        material = upload(client, "notes.txt", "Alpha establishes the central study conclusion.")
        index(client, material["material_id"])
        response = ask(client, "Alpha establishes", material["material_id"])
        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "succeeded"
        assert payload["provider_id"] == "fake"
        assert payload["model_id"] == "fake-studybuddy-v1"
        assert payload["citations"]
        assert all(citation["status"] == "valid" for citation in payload["citations"])
        assert all("stored_path" not in citation for citation in payload["citations"])
        for forbidden in ("stored_path", "sqlite", "traceback", "select ", "h:/", "g:/"):
            assert forbidden not in response.text.lower()
        with connect(tmp_path / "studybuddy.sqlite3") as db:
            operation = db.execute(
                "SELECT status, provider_id, model_id, total_tokens, finish_reason, latency_ms "
                "FROM ai_operations WHERE id = ?", (payload["operation_id"],)
            ).fetchone()
            assert tuple(operation[:3]) == ("succeeded", "fake", "fake-studybuddy-v1")
            assert operation[3] is not None and operation[4] == "stop" and operation[5] is not None
            assert db.execute("SELECT role FROM qa_messages WHERE id = ?", (payload["user_message_id"],)).fetchone()[0] == "user"
            assert db.execute("SELECT role FROM qa_messages WHERE id = ?", (payload["assistant_message_id"],)).fetchone()[0] == "assistant"
            answer = db.execute("SELECT status, source_coverage FROM qa_answers WHERE id = ?", (payload["answer_id"],)).fetchone()
            assert tuple(answer) == ("ready", "cited")
            rows = db.execute(
                "SELECT citation_key, material_id, revision_id, chunk_id, status FROM qa_citations WHERE answer_id = ?",
                (payload["answer_id"],),
            ).fetchall()
            assert len(rows) == len(payload["citations"])
            assert all(row[1] == material["material_id"] and row[4] == "valid" for row in rows)
            assert db.execute("SELECT COUNT(*) FROM retrieval_hits WHERE run_id = ?", (payload["retrieval_run_id"],)).fetchone()[0] > 0


def test_qa_hybrid_uses_rrf_and_verified_citations(tmp_path: Path):
    with make_client(tmp_path, embedding=True) as client:
        material = upload(client, "hybrid-qa.txt", "Hybrid retrieval grounds this answer in a stable source.")
        index(client, material["material_id"])
        with connect(tmp_path / "studybuddy.sqlite3") as db:
            extraction = db.execute(
                "SELECT id FROM extractions WHERE material_id = ? ORDER BY created_at DESC LIMIT 1",
                (material["material_id"],),
            ).fetchone()
            index_material_revision(db, material["material_id"], str(extraction["id"]))
            index_embeddings_for_material(db, material_id=material["material_id"], provider=FakeEmbeddingProvider())
        response = ask(client, "stable source", material["material_id"], retrieval_mode="hybrid",
                       allow_retrieval_fallback=False)
        assert response.status_code == 200
        payload = response.json()
        assert payload["retrieval"]["mode"] == "hybrid"
        assert payload["retrieval"]["policy_version"] == "hybrid_rrf_v1"
        assert payload["retrieval"]["fallback"] is False
        assert payload["citations"]
        with connect(tmp_path / "studybuddy.sqlite3") as db:
            operation = db.execute(
                "SELECT retrieval_policy_version, retrieval_run_id FROM ai_operations WHERE id = ?",
                (payload["operation_id"],),
            ).fetchone()
            assert tuple(operation) == ("hybrid_rrf_v1", payload["retrieval_run_id"])
            assert db.execute(
                "SELECT policy_version, embedding_provider_id, embedding_model_id FROM retrieval_runs WHERE id = ?",
                (payload["retrieval_run_id"],),
            ).fetchone()[:3] == ("hybrid_rrf_v1", "fake", "fake-embedding-v1")


def test_qa_hybrid_fallback_is_recorded_and_vector_does_not_fallback(tmp_path: Path):
    with make_client(tmp_path) as client:
        material = upload(client, "hybrid-fallback.txt", "Fallback retrieval still uses this lexical source.")
        index(client, material["material_id"])
        fallback = ask(client, "lexical source", material["material_id"], retrieval_mode="hybrid")
        assert fallback.status_code == 200
        payload = fallback.json()
        assert payload["retrieval"]["policy_version"] == "fallback_lexical_v1"
        assert payload["retrieval"]["fallback"] is True
        assert payload["retrieval"]["fallback_reason"] == "embedding_provider_not_configured"
        vector = ask(client, "lexical source", material["material_id"], retrieval_mode="vector")
        assert vector.status_code == 503
        assert vector.json()["detail"] == "embedding_provider_not_configured"
        with connect(tmp_path / "studybuddy.sqlite3") as db:
            assert db.execute(
                "SELECT error_code FROM ai_operations WHERE id = ?", (vector.json().get("operation_id", ""),)
            ).fetchone() is None


def test_qa_rejects_unknown_retrieval_mode(tmp_path: Path):
    with make_client(tmp_path) as client:
        material = upload(client, "invalid-mode.txt", "Mode boundary source.")
        response = ask(client, "mode", material["material_id"], retrieval_mode="custom")
        assert response.status_code == 400
        assert response.json()["detail"] == "retrieval_invalid_mode"


def test_qa_ask_reuses_thread_and_fake_answer_is_deterministic(tmp_path: Path):
    with make_client(tmp_path) as client:
        material = upload(client, "thread.txt", "The repeatable answer is grounded in this sentence.")
        index(client, material["material_id"])
        first = ask(client, "repeatable grounded", material["material_id"]).json()
        second_response = ask(client, "repeatable grounded", material["material_id"], thread_id=first["thread_id"])
        assert second_response.status_code == 200
        second = second_response.json()
        assert second["thread_id"] == first["thread_id"]
        assert second["answer_text"] == first["answer_text"]
        with connect(tmp_path / "studybuddy.sqlite3") as db:
            assert db.execute("SELECT COUNT(*) FROM qa_messages WHERE thread_id = ?", (first["thread_id"],)).fetchone()[0] == 4


def test_qa_idempotency_key_replays_succeeded_answer_without_new_artifacts(tmp_path: Path):
    with make_client(tmp_path) as client:
        material = upload(client, "idempotent.txt", "A stable source supports idempotent responses.")
        index(client, material["material_id"])
        headers = {"Idempotency-Key": "qa-replay-001"}
        first_response = client.post("/api/qa/ask", json={
            "question": "stable source", "material_ids": [material["material_id"]],
        }, headers=headers)
        assert first_response.status_code == 200
        first = first_response.json()
        with connect(tmp_path / "studybuddy.sqlite3") as db:
            before = tuple(db.execute(
                "SELECT (SELECT COUNT(*) FROM ai_operations), (SELECT COUNT(*) FROM qa_messages), "
                "(SELECT COUNT(*) FROM qa_answers), (SELECT COUNT(*) FROM retrieval_runs)"
            ).fetchone())
        replay_response = client.post("/api/qa/ask", json={
            "question": "stable source", "material_ids": [material["material_id"]],
        }, headers=headers)
        assert replay_response.status_code == 200
        replay = replay_response.json()
        assert replay == first
        with connect(tmp_path / "studybuddy.sqlite3") as db:
            after = tuple(db.execute(
                "SELECT (SELECT COUNT(*) FROM ai_operations), (SELECT COUNT(*) FROM qa_messages), "
                "(SELECT COUNT(*) FROM qa_answers), (SELECT COUNT(*) FROM retrieval_runs)"
            ).fetchone())
            assert after == before
            operation = db.execute(
                "SELECT idempotency_key, retrieval_run_id FROM ai_operations WHERE id = ?",
                (first["operation_id"],),
            ).fetchone()
            assert tuple(operation) == ("qa-replay-001", first["retrieval_run_id"])


def test_qa_idempotency_key_rejects_different_request_fingerprint(tmp_path: Path):
    with make_client(tmp_path) as client:
        material = upload(client, "idempotent-mismatch.txt", "A stable source supports idempotent responses.")
        index(client, material["material_id"])
        headers = {"Idempotency-Key": "qa-mismatch-001"}
        first = client.post("/api/qa/ask", json={
            "question": "stable source", "material_ids": [material["material_id"]],
        }, headers=headers)
        assert first.status_code == 200
        mismatch = client.post("/api/qa/ask", json={
            "question": "different question", "material_ids": [material["material_id"]],
        }, headers=headers)
        assert mismatch.status_code == 409
        assert mismatch.json()["detail"] == "qa_idempotency_key_mismatch"


def test_qa_idempotency_key_rejects_running_operation_and_failure_allows_retry(tmp_path: Path):
    with make_client(tmp_path, fake=False) as client:
        material = upload(client, "idempotency-retry.txt", "A source supports retry after failure.")
        index(client, material["material_id"])
        key = "qa-retry-001"
        with connect(tmp_path / "studybuddy.sqlite3") as db:
            create_qa_request(
                db, project_id="default", question="source supports", material_ids=[material["material_id"]],
                thread_id=None, request_id=None, idempotency_key=key,
            )
        in_progress = client.post("/api/qa/ask", json={
            "question": "source supports", "material_ids": [material["material_id"]],
        }, headers={"Idempotency-Key": key})
        assert in_progress.status_code == 409
        assert in_progress.json()["detail"] == "qa_operation_in_progress"
        failed = client.post("/api/qa/ask", json={
            "question": "source supports", "material_ids": [material["material_id"]],
        }, headers={"Idempotency-Key": "qa-failed-retry-001"})
        assert failed.status_code == 503
    with make_client(tmp_path) as client:
        retry = client.post("/api/qa/ask", json={
            "question": "source supports", "material_ids": [material["material_id"]],
        }, headers={"Idempotency-Key": "qa-failed-retry-001"})
        assert retry.status_code == 200
        with connect(tmp_path / "studybuddy.sqlite3") as db:
            assert db.execute(
                "SELECT COUNT(*) FROM ai_operations WHERE idempotency_key = 'qa-failed-retry-001' AND status = 'succeeded'"
            ).fetchone()[0] == 1


def test_qa_stale_operation_is_reclaimed_and_idempotency_key_can_retry(tmp_path: Path):
    with make_client(tmp_path) as client:
        material = upload(client, "stale-operation.txt", "A stable source supports recovery after an expired lease.")
        index(client, material["material_id"])
        key = "qa-stale-retry-001"
        with connect(tmp_path / "studybuddy.sqlite3") as db:
            stale = create_qa_request(
                db, project_id="default", question="stable source", material_ids=[material["material_id"]],
                thread_id=None, request_id=None, idempotency_key=key,
            )
            db.execute(
                "UPDATE ai_operations SET started_at = ? WHERE id = ?",
                ("2000-01-01T00:00:00+00:00", stale["operation_id"]),
            )
            db.commit()
        response = client.post("/api/qa/ask", json={
            "question": "stable source", "material_ids": [material["material_id"]],
        }, headers={"Idempotency-Key": key})
        assert response.status_code == 200
        payload = response.json()
        assert payload["operation_id"] != stale["operation_id"]
        with connect(tmp_path / "studybuddy.sqlite3") as db:
            stale_operation = db.execute(
                "SELECT status, error_code, output_artifact_id FROM ai_operations WHERE id = ?",
                (stale["operation_id"],),
            ).fetchone()
            assert tuple(stale_operation) == ("stale", "qa_operation_stale", None)
            assert db.execute(
                "SELECT COUNT(*) FROM qa_messages WHERE ai_operation_id = ? AND role = 'user'",
                (stale["operation_id"],),
            ).fetchone()[0] == 1
            assert db.execute(
                "SELECT COUNT(*) FROM qa_messages WHERE ai_operation_id = ? AND role = 'assistant'",
                (stale["operation_id"],),
            ).fetchone()[0] == 0
            assert db.execute(
                "SELECT COUNT(*) FROM ai_operations WHERE idempotency_key = ? AND status = 'succeeded'",
                (key,),
            ).fetchone()[0] == 1


def test_qa_history_lists_threads_and_returns_citations(tmp_path: Path):
    with make_client(tmp_path) as client:
        first = upload(client, "history-a.txt", "Alpha history source is here.")
        second = upload(client, "history-b.txt", "Beta history source is here.")
        index(client, first["material_id"])
        index(client, second["material_id"])
        answer = ask(client, "history source", first["material_id"]).json()
        follow_up = ask(client, "history source", first["material_id"], thread_id=answer["thread_id"])
        assert follow_up.status_code == 200
        threads = client.get("/api/qa/threads")
        assert threads.status_code == 200
        assert threads.json()["items"][0]["id"] == answer["thread_id"]
        assert threads.json()["items"][0]["status"] == "active"
        assert threads.json()["items"][0]["message_count"] == 4
        history = client.get(f"/api/qa/threads/{answer['thread_id']}")
        assert history.status_code == 200
        messages = history.json()["messages"]
        assert [message["role"] for message in messages] == ["user", "assistant", "user", "assistant"]
        citation = messages[1]["citations"][0]
        assert citation["material_name"] == "history-a.txt"
        assert citation["status"] == "valid"
        assert "stored_path" not in history.text
        assert client.get("/api/qa/threads/thread_missing").status_code == 404


def test_qa_history_refreshes_deleted_citation_status(tmp_path: Path):
    with make_client(tmp_path) as client:
        material = upload(client, "history-delete.txt", "A source that will be deleted.")
        index(client, material["material_id"])
        answer = ask(client, "source deleted", material["material_id"]).json()
        assert client.delete(f"/api/materials/{material['material_id']}").status_code == 204
        history = client.get(f"/api/qa/threads/{answer['thread_id']}").json()
        assert history["messages"][1]["citations"][0]["status"] == "source_deleted"


def test_qa_history_rejects_invalid_limit(tmp_path: Path):
    with make_client(tmp_path) as client:
        assert client.get("/api/qa/threads?limit=0").status_code == 400
        assert client.get("/api/qa/threads?limit=101").status_code == 400


def test_qa_not_configured_persists_failed_operation_without_answer(tmp_path: Path):
    with make_client(tmp_path, fake=False) as client:
        material = upload(client, "not-configured.txt", "Provider configuration should be required.")
        index(client, material["material_id"])
        response = ask(client, "Provider required", material["material_id"])
        assert response.status_code == 503
        assert response.json()["detail"] == "provider_not_configured"
        with connect(tmp_path / "studybuddy.sqlite3") as db:
            assert db.execute("SELECT error_code FROM ai_operations WHERE operation_type = 'qa_answer'").fetchone()[0] == "provider_not_configured"
            assert db.execute("SELECT COUNT(*) FROM qa_answers").fetchone()[0] == 0
            assert db.execute("SELECT COUNT(*) FROM qa_citations").fetchone()[0] == 0
            assert db.execute("SELECT COUNT(*) FROM qa_messages WHERE role = 'assistant'").fetchone()[0] == 0


def test_qa_unindexed_and_empty_retrieval_fail_without_answer(tmp_path: Path):
    with make_client(tmp_path) as client:
        unindexed = upload(client, "unindexed.txt", "No indexing has occurred.")
        response = ask(client, "What occurred?", unindexed["material_id"])
        assert response.status_code == 409
        assert response.json()["detail"] == "retrieval_not_ready"
        index(client, unindexed["material_id"])
        empty = ask(client, "completely absent token", unindexed["material_id"])
        assert empty.status_code == 409
        assert empty.json()["detail"] == "retrieval_empty"
        with connect(tmp_path / "studybuddy.sqlite3") as db:
            assert db.execute("SELECT COUNT(*) FROM qa_answers").fetchone()[0] == 0
            assert db.execute("SELECT COUNT(*) FROM qa_citations").fetchone()[0] == 0
            assert db.execute("SELECT COUNT(*) FROM ai_operations WHERE status = 'failed'").fetchone()[0] == 2


def test_qa_rejects_provider_forged_citation(monkeypatch, tmp_path: Path):
    from app import main

    class ForgingProvider:
        provider_id = "fake"
        model_id = "fake-studybuddy-v1"

        def generate_answer(self, request):
            return ProviderResult("forged response", ["ctx-aaaaaaaa-bbbbbbbb"], "fake", "fake-studybuddy-v1", 1, 1)

    class ForgingRegistry:
        def configured_provider(self):
            return ForgingProvider()

    monkeypatch.setattr(main, "provider_registry", lambda *_args: ForgingRegistry())
    with make_client(tmp_path) as client:
        material = upload(client, "forged.txt", "A trusted chunk exists for citation validation.")
        index(client, material["material_id"])
        response = ask(client, "trusted chunk", material["material_id"])
        assert response.status_code == 500
        assert response.json()["detail"] == "qa_generation_failed"
        with connect(tmp_path / "studybuddy.sqlite3") as db:
            assert db.execute("SELECT error_code FROM ai_operations WHERE operation_type = 'qa_answer'").fetchone()[0] == "citation_verification_failed"
            assert db.execute("SELECT COUNT(*) FROM qa_answers").fetchone()[0] == 0
            assert db.execute("SELECT COUNT(*) FROM qa_citations").fetchone()[0] == 0


def test_qa_rejects_provider_without_citation(monkeypatch, tmp_path: Path):
    from app import main

    class NoCitationProvider:
        provider_id = "mock"
        model_id = "mock-v1"

        def generate_answer(self, request):
            return ProviderResult("An uncited answer", [], self.provider_id, self.model_id, 2, 3)

    class NoCitationRegistry:
        def configured_provider(self):
            return NoCitationProvider()

    monkeypatch.setattr(main, "provider_registry", lambda *_args, **_kwargs: NoCitationRegistry())
    with make_client(tmp_path) as client:
        material = upload(client, "uncited.txt", "A source requiring a citation.")
        index(client, material["material_id"])
        response = ask(client, "requiring citation", material["material_id"])
        assert response.status_code == 500
        assert response.json()["detail"] == "qa_generation_failed"
        with connect(tmp_path / "studybuddy.sqlite3") as db:
            assert db.execute("SELECT error_code FROM ai_operations WHERE operation_type = 'qa_answer'").fetchone()[0] == "citation_verification_failed"
            assert db.execute("SELECT COUNT(*) FROM qa_answers").fetchone()[0] == 0
            assert db.execute("SELECT COUNT(*) FROM qa_citations").fetchone()[0] == 0
            assert db.execute("SELECT COUNT(*) FROM qa_messages WHERE role = 'assistant'").fetchone()[0] == 0


def test_qa_answer_persistence_rolls_back_on_citation_failure(tmp_path: Path):
    with make_client(tmp_path) as client:
        material = upload(client, "rollback.txt", "Rollback requires trusted citation evidence.")
        index(client, material["material_id"])
        with connect(tmp_path / "studybuddy.sqlite3") as db:
            db.execute(
                "CREATE TRIGGER fail_qa_citation BEFORE INSERT ON qa_citations "
                "BEGIN SELECT RAISE(ABORT, 'injected'); END"
            )
            db.commit()
        response = ask(client, "trusted citation", material["material_id"])
        assert response.status_code == 500
        assert response.json()["detail"] == "qa_generation_failed"
        with connect(tmp_path / "studybuddy.sqlite3") as db:
            assert db.execute("SELECT COUNT(*) FROM qa_answers").fetchone()[0] == 0
            assert db.execute("SELECT COUNT(*) FROM qa_citations").fetchone()[0] == 0
            assert db.execute("SELECT COUNT(*) FROM qa_messages WHERE role = 'assistant'").fetchone()[0] == 0
            assert db.execute("SELECT error_code FROM ai_operations WHERE operation_type = 'qa_answer'").fetchone()[0] == "qa_persist_failed"


def test_qa_input_and_deleted_source_boundaries(tmp_path: Path):
    with make_client(tmp_path) as client:
        material = upload(client, "boundaries.txt", "Boundary text.")
        index(client, material["material_id"])
        cases = [
            client.post("/api/qa/ask", json={"question": " ", "material_ids": [material["material_id"]]}),
            client.post("/api/qa/ask", json={"question": "x" * 1001, "material_ids": [material["material_id"]]}),
            client.post("/api/qa/ask", json={"question": "x", "material_ids": []}),
            client.post("/api/qa/ask", json={"question": "x", "material_ids": [material["material_id"]], "top_k": 0}),
        ]
        assert [response.status_code for response in cases] == [400, 400, 400, 400]
        assert client.delete(f"/api/materials/{material['material_id']}").status_code == 204
        deleted = ask(client, "Boundary?", material["material_id"])
        assert deleted.status_code == 404
        assert deleted.json()["detail"] == "source_deleted"
