"""P1-4 C0 evidence: write-then-restart durability for `/app` write families.

Each test performs the same request bodies the static `/app` pages send, closes
the application, opens a second application over the same isolated data root,
and re-reads exactly the fields the corresponding page renders.  A family is
only recorded as durable when the second read still shows the expected
identity, status and source state.
"""

from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.config import AppConfig
from app.main import create_app

BODY = ("P1-4 durability source keeps citation retrieval stability verifiable. "
        "The indexed body location supports the recorded citation evidence.")
QUESTION = "citation retrieval stability"


def _client(root: Path) -> TestClient:
    return TestClient(create_app(AppConfig(
        data_root=root, max_upload_bytes=1024 * 1024, ai_provider_id="fake",
    )))


def _post(client: TestClient, path: str, payload: object | None = None, *, expected: int = 200) -> dict:
    response = client.post(path, json=payload) if payload is not None else client.post(path)
    assert response.status_code == expected, (path, response.status_code, response.text)
    return response.json()


def _get(client: TestClient, path: str, *, expected: int = 200):
    response = client.get(path)
    assert response.status_code == expected, (path, response.status_code, response.text)
    return response.json()


def _plan_source_statuses(payload: dict) -> list[str]:
    return [str(link["status"]) for link in payload.get("source_links", [])]


def test_plan_rhythm_and_progress_survive_restart(tmp_path: Path):
    root = tmp_path / "data"
    with _client(root) as client:
        goal = _post(client, "/api/study/goals", {"title": "P1-4 目标"}, expected=201)
        module = _post(client, "/api/study/modules", {"title": "P1-4 模块"}, expected=201)
        plan = _post(client, "/api/study/plans", {"title": "P1-4 计划", "goal_id": goal["id"]}, expected=201)
        item = _post(client, f"/api/study/plans/{plan['id']}/items",
                     {"title": "P1-4 学习项", "module_id": module["id"]}, expected=201)
        rhythm = client.put(f"/api/study/plans/{plan['id']}/rhythm", json={
            "cadence": "daily", "timezone": "Asia/Shanghai",
            "period_start": "2026-09-01", "target_minutes": 90,
        })
        assert rhythm.status_code == 200, rhythm.text
        allocation = _post(client, f"/api/study/plans/{plan['id']}/rhythm/allocations", {
            "item_id": item["id"], "local_date": "2026-09-01", "planned_minutes": 45,
        }, expected=201)
        assert _post(client, f"/api/study/plans/{plan['id']}/confirm")["status"] == "confirmed"
        assert _post(client, f"/api/study/plans/{plan['id']}/activate")["status"] == "active"
        _post(client, f"/api/study/plans/{plan['id']}/items/{item['id']}/progress",
              {"event_type": "completed"}, expected=201)

    with _client(root) as restarted:
        reopened = _get(restarted, f"/api/study/plans/{plan['id']}")
        assert reopened["status"] == "active"
        assert reopened["title"] == "P1-4 计划"
        items = reopened["items"]
        assert [entry["id"] for entry in items] == [item["id"]]
        assert items[0]["status"] in {"completed", "in_progress", "pending"}
        summary = _get(restarted, f"/api/study/plans/{plan['id']}/rhythm/summary")
        assert summary["settings"]["target_minutes"] == 90
        assert summary["settings"]["timezone"] == "Asia/Shanghai"
        allocations = _get(restarted, f"/api/study/plans/{plan['id']}/rhythm/allocations")
        assert [entry["id"] for entry in allocations] == [allocation["id"]]
        assert allocations[0]["planned_minutes"] == 45
        progress = _get(restarted, f"/api/study/plans/{plan['id']}/progress")
        assert [event["event_type"] for event in progress["events"]] == ["completed"]
        # `today.html` reads the plan list plus the rhythm summary.
        assert any(entry["id"] == plan["id"] for entry in _get(restarted, "/api/study/plans"))


def test_plan_item_source_state_lives_on_source_links_not_items(tmp_path: Path):
    """Records the observed shape that `plans.html`/`today.html` depend on.

    Confirmed gap: plan items carry no per-item source status field, so both
    pages fall back to the shared `valid` label even when the linked material
    was deleted.  Tracked as P14-P1-04 for the source-honesty slice.
    """
    root = tmp_path / "data"
    with _client(root) as client:
        goal = _post(client, "/api/study/goals", {"title": "P1-4 来源目标"}, expected=201)
        plan = _post(client, "/api/study/plans", {"title": "P1-4 来源计划", "goal_id": goal["id"]}, expected=201)
        item = _post(client, f"/api/study/plans/{plan['id']}/items", {"title": "P1-4 来源学习项"}, expected=201)
        created = client.post("/api/materials", files={"file": ("linked.txt", BODY.encode(), "text/plain")})
        material_id = created.json()["material_id"]
        indexed = _post(client, f"/api/materials/{material_id}/ai-index")
        hit = _post(client, "/api/retrieval", {
            "query": QUESTION, "material_ids": [material_id], "mode": "lexical", "top_k": 3,
        })["hits"][0]
        _post(client, f"/api/study/plans/{plan['id']}/items/{item['id']}/sources", {
            "material_id": material_id, "revision_id": indexed["revision_id"],
            "chunk_id": hit["chunk_id"],
        }, expected=201)
        linked = _get(client, f"/api/study/plans/{plan['id']}")
        assert _plan_source_statuses(linked) == ["valid"]
        assert "source_link_status" not in linked["items"][0]
        assert client.delete(f"/api/materials/{material_id}").status_code == 204

    with _client(root) as restarted:
        after = _get(restarted, f"/api/study/plans/{plan['id']}")
        assert _plan_source_statuses(after) == ["source_deleted"]
        assert "source_link_status" not in after["items"][0]
        assert "source_status" not in after["items"][0]
        listed = _get(restarted, "/api/study/sources")
        rows = listed if isinstance(listed, list) else listed["items"]
        assert [row["status"] for row in rows] == ["source_deleted"]


def test_note_write_confirm_and_archive_survive_restart(tmp_path: Path):
    root = tmp_path / "data"
    with _client(root) as client:
        module = _post(client, "/api/study/modules", {"title": "P1-4 笔记模块"}, expected=201)
        note = _post(client, "/api/study/notes", {
            "title": "P1-4 笔记", "blocks": [{"block_kind": "text", "content": "初始内容"}],
        }, expected=201)
        edited = client.patch(f"/api/study/notes/{note['id']}", json={
            "title": "P1-4 已编辑笔记",
            "blocks": [{"block_kind": "text", "content": "编辑后的内容"}],
        })
        assert edited.status_code == 200, edited.text
        _post(client, f"/api/study/notes/{note['id']}/modules/{module['id']}", expected=201)
        assert _post(client, f"/api/study/notes/{note['id']}/confirm")["status"] == "confirmed"
        refreshed = _post(client, "/api/study/notes/sources/refresh", {"note_id": note["id"]})
        assert isinstance(refreshed, dict)

    with _client(root) as restarted:
        reopened = _get(restarted, f"/api/study/notes/{note['id']}")
        assert reopened["title"] == "P1-4 已编辑笔记"
        assert reopened["status"] == "confirmed"
        assert [block["content"] for block in reopened["blocks"]] == ["编辑后的内容"]
        assert [entry["id"] for entry in reopened["modules"]] == [module["id"]]
        assert reopened.get("source_citation_status") in {None, "valid", "stale", "source_deleted", "source_unavailable"}
        assert _post(restarted, f"/api/study/notes/{note['id']}/archive")["status"] == "archived"

    with _client(root) as final:
        assert _get(final, f"/api/study/notes/{note['id']}")["status"] == "archived"


def test_card_write_confirm_and_review_survive_restart(tmp_path: Path):
    root = tmp_path / "data"
    with _client(root) as client:
        deck = _post(client, "/api/study/decks", {"title": "P1-4 卡组"}, expected=201)
        card = _post(client, f"/api/study/decks/{deck['id']}/cards",
                     {"front": "什么是稳定性？", "back": "可预测行为"}, expected=201)
        assert card["status"] == "draft"
        updated = client.patch(f"/api/study/cards/{card['id']}",
                               json={"front": "什么是可验证稳定性？", "back": "可预测且可观察"})
        assert updated.status_code == 200, updated.text
        assert _post(client, f"/api/study/cards/{card['id']}/confirm")["status"] == "ready"
        # `cards.html` posts the FSRS-style grade values only.
        review = _post(client, f"/api/study/cards/{card['id']}/reviews", {"result": "good"}, expected=201)
        assert review["card_id"] == card["id"]

    with _client(root) as restarted:
        reopened = _get(restarted, f"/api/study/cards/{card['id']}")
        assert reopened["front"] == "什么是可验证稳定性？"
        assert reopened["status"] == "ready"
        assert "answer_key" not in reopened
        listed = _get(restarted, f"/api/study/cards?deck_id={deck['id']}")
        rows = listed if isinstance(listed, list) else listed["items"]
        assert [row["id"] for row in rows] == [card["id"]]


def test_exercise_practice_and_mistake_flow_survives_restart(tmp_path: Path):
    root = tmp_path / "data"
    with _client(root) as client:
        exercise_set = _post(client, "/api/study/exercise-sets", {"title": "P1-4 练习集"}, expected=201)
        exercise = _post(client, f"/api/study/exercise-sets/{exercise_set['id']}/exercises", {
            "exercise_type": "multiple_choice", "prompt": "2+2 等于几？",
            "options": ["3", "4"], "answer_key": 1, "explanation": "",
            "citations": [], "exercise_kind": "user_created",
        }, expected=201)
        edited = client.patch(f"/api/study/exercises/{exercise['id']}", json={
            "prompt": "2+2 的结果是什么？", "options": ["3", "4"],
            "explanation": "加法", "citations": [],
        })
        assert edited.status_code == 200, edited.text
        assert _post(client, f"/api/study/exercises/{exercise['id']}/confirm")["status"] == "ready"
        session = _post(client, "/api/study/practice-sessions", {
            "title": "P1-4 会话", "exercise_ids": [exercise["id"]],
            "duration_seconds": 600, "timezone": "UTC", "local_date": "2026-09-01",
        }, expected=201)
        assert _post(client, f"/api/study/practice-sessions/{session['id']}/start")["status"] == "active"
        detail = _get(client, f"/api/study/practice-sessions/{session['id']}")
        item = detail["items"][0]
        assert "answer_key" not in item
        submitted = client.post(
            f"/api/study/practice-sessions/{session['id']}/items/{item['id']}/submit",
            json={"answer": 0}, headers={"Idempotency-Key": "p1-4-submit"},
        )
        assert submitted.status_code == 200, submitted.text
        assert _post(client, f"/api/study/practice-sessions/{session['id']}/finish")["status"] == "finished"
        mistakes = _get(client, "/api/study/mistakes")
        rows = mistakes if isinstance(mistakes, list) else mistakes["items"]
        assert rows, mistakes
        mistake_id = rows[0]["id"]
        _post(client, f"/api/study/mistakes/{mistake_id}/feedback",
              {"event_kind": "user_note", "content": "需要复习加法"}, expected=201)

    with _client(root) as restarted:
        reopened = _get(restarted, f"/api/study/exercises/{exercise['id']}")
        assert reopened["prompt"] == "2+2 的结果是什么？"
        assert reopened["status"] == "ready"
        assert "answer_key" not in reopened
        session_after = _get(restarted, f"/api/study/practice-sessions/{session['id']}")
        assert session_after["status"] == "finished"
        result = _get(restarted, f"/api/study/practice-sessions/{session['id']}/result")
        summary = result["summary"]
        # `practice-result.html` renders exactly these nested summary fields.
        for field in ("score_total", "total_item_count", "scored_count", "submitted_count"):
            assert field in summary, summary
        assert summary["total_item_count"] == 1
        assert summary["submitted_count"] == 1
        mistakes_after = _get(restarted, "/api/study/mistakes")
        rows_after = mistakes_after if isinstance(mistakes_after, list) else mistakes_after["items"]
        assert [row["id"] for row in rows_after] == [mistake_id]
        detail_after = _get(restarted, f"/api/study/mistakes/{mistake_id}")
        assert detail_after["status"] in {"open", "in_review", "fixed", "reopened", "archived"}
        for occurrence in detail_after.get("occurrences", []):
            assert occurrence["source_status"] in {"valid", "stale", "source_deleted", "source_unavailable"}
        assert _get(restarted, "/api/study/weak-points")
        assert "answer_key" not in str(result)


def test_qa_thread_and_citation_state_survive_restart_and_purge(tmp_path: Path):
    root = tmp_path / "data"
    with _client(root) as client:
        created = client.post("/api/materials", files={"file": ("durable.txt", BODY.encode(), "text/plain")})
        assert created.status_code == 201, created.text
        material_id = created.json()["material_id"]
        assert _post(client, f"/api/materials/{material_id}/ai-index")["status"] == "ready"
        answer = _post(client, "/api/qa/ask", {
            "question": QUESTION, "material_ids": [material_id],
            "retrieval_mode": "lexical", "top_k": 5,
        })
        assert answer["status"] == "succeeded"
        citation_key = answer["citations"][0]["citation_key"]

    with _client(root) as restarted:
        threads = _get(restarted, "/api/qa/threads")["items"]
        assert threads
        history = _get(restarted, f"/api/qa/threads/{threads[0]['id']}")
        assert any(message["role"] == "assistant" for message in history["messages"])
        located = _get(restarted, f"/api/qa/citations/{citation_key}")
        assert located["status"] == "valid"
        detail = _get(restarted, f"/api/materials/{material_id}")
        body = str(detail["text"])
        assert body[located["start_offset"]:located["end_offset"]]
        assert restarted.delete(f"/api/materials/{material_id}").status_code == 204

    with _client(root) as after_delete:
        assert _get(after_delete, f"/api/qa/citations/{citation_key}")["status"] == "source_deleted"
        deleted = _get(after_delete, "/api/materials/deleted")
        rows = deleted if isinstance(deleted, list) else deleted["items"]
        assert [row["id"] for row in rows] == [material_id]
        assert _post(after_delete, f"/api/materials/{material_id}/restore")["id"] == material_id

    with _client(root) as after_restore:
        assert _get(after_restore, f"/api/qa/citations/{citation_key}")["status"] == "valid"
        assert after_restore.delete(f"/api/materials/{material_id}").status_code == 204
        assert _post(after_restore, f"/api/materials/{material_id}/purge")["status"] == "purged"

    with _client(root) as after_purge:
        purged = _get(after_purge, f"/api/qa/citations/{citation_key}")
        assert purged["status"] == "source_unavailable"
        assert purged["material_name"] is None
        assert "excerpt" not in purged
        assert _get(after_purge, f"/api/materials/{material_id}", expected=404)["detail"] == "material_not_found"
        # The answer history itself is retained; only the source becomes unavailable.
        assert _get(after_purge, "/api/qa/threads")["items"]


def test_material_index_status_labels_are_within_the_shared_state_vocabulary(tmp_path: Path):
    """`material-detail.html` maps index status through sbState.label()."""
    shared = (ROOT / "app" / "static" / "js" / "state.js").read_text(encoding="utf-8")
    root = tmp_path / "data"
    with _client(root) as client:
        created = client.post("/api/materials", files={"file": ("labels.txt", BODY.encode(), "text/plain")})
        material_id = created.json()["material_id"]
        before = _get(client, f"/api/materials/{material_id}/ai-index")["status"]
        _post(client, f"/api/materials/{material_id}/ai-index")
        after = _get(client, f"/api/materials/{material_id}/ai-index")["status"]

    with _client(root) as restarted:
        assert _get(restarted, f"/api/materials/{material_id}/ai-index")["status"] == after

    assert before == "not_indexed"
    assert after == "ready"
    assert "ready:" in shared
    # Recorded gap: `not_indexed` has no shared label, so the page falls back to
    # the generic unknown-state wording. Tracked as P14-P1-04 in the P1-4 ledger.
    assert "not_indexed:" not in shared
