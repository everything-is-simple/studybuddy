from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.providers import FakeLLMProvider, ProviderError, ProviderResult
from app.repository import (
    confirm_note,
    connect,
    create_note_generation_operation,
    create_user_note,
    fail_note_generation_operation,
    generate_note_draft,
    get_note,
    create_knowledge_module,
    archive_knowledge_module,
    link_note_module,
    index_material_revision,
    persist_generated_note_draft,
)


def _seed_project(connection: sqlite3.Connection, project_id: str = "project_9b_notes") -> None:
    connection.execute(
        "INSERT INTO projects (id,name,created_at) VALUES (?,?,?)",
        (project_id, "Phase 9B notes", "2026-01-01T00:00:00+00:00"),
    )


def _seed_indexed_source(connection: sqlite3.Connection, *, project_id: str = "project_9b_notes",
                         text: str = "A controlled source supports safe generated notes.") -> tuple[str, str]:
    material_id = "material_abcdef0123456789abcdef0123456789"
    extraction_id = "extraction_9b_notes"
    connection.execute(
        "INSERT INTO materials (id,project_id,original_name,source_sha256,stored_path,media_type,created_at,updated_at,deleted_at) "
        "VALUES (?,?,?,?,?,?,?,?,NULL)",
        (material_id, project_id, "notes.txt", "b" * 64, "originals/b", "text/plain", "now", "now"),
    )
    connection.execute(
        "INSERT INTO extractions (id,material_id,parser_id,parser_version,status,text,warnings_json,created_at,error_code) "
        "VALUES (?,?,?,?,?,?,?,?,NULL)",
        (extraction_id, material_id, "txt", "1", "success", text, "[]", "now"),
    )
    connection.execute(
        "INSERT INTO text_spans (id,extraction_id,ordinal,span_kind,label,text) VALUES (?,?,?,?,?,?)",
        ("span_9b_notes", extraction_id, 0, "document", "notes.txt", text),
    )
    revision = index_material_revision(connection, material_id, extraction_id)
    return material_id, str(revision["id"])


def test_note_module_archive_preserves_link_as_warning(tmp_path: Path):
    with connect(tmp_path / "studybuddy.sqlite3") as connection:
        _seed_project(connection)
        module = create_knowledge_module(connection, project_id="project_9b_notes", title="Organize")
        note = create_user_note(connection, project_id="project_9b_notes", title="User note", blocks=[{"content": "Body"}])
        link_note_module(connection, project_id="project_9b_notes", note_id=note["id"], module_id=module["id"])
        archive_knowledge_module(connection, project_id="project_9b_notes", module_id=module["id"])
        detail = get_note(connection, project_id="project_9b_notes", note_id=note["id"])
        assert detail["modules"][0]["id"] == module["id"]
        assert detail["archived_module_warning_count"] == 1


def test_fake_note_generation_creates_cited_ai_draft_and_replays(tmp_path: Path):
    with connect(tmp_path / "studybuddy.sqlite3") as connection:
        _seed_project(connection)
        material_id, revision_id = _seed_indexed_source(connection)
        first = generate_note_draft(
            connection, project_id="project_9b_notes", topic="controlled source", material_id=material_id,
            provider=FakeLLMProvider(), idempotency_key="note-generation-1",
        )
        assert first["status"] == "succeeded" and first["replay"] is False
        note = first["note"]
        assert note["provenance"] == "ai_generated" and note["status"] == "draft"
        assert note["generation_operation_id"] == first["operation_id"]
        assert note["blocks"] and all(block["provenance"] == "ai_generated" for block in note["blocks"])
        assert all(block["sources"] and all(link["status"] == "valid" for link in block["sources"])
                   for block in note["blocks"])
        replay = generate_note_draft(
            connection, project_id="project_9b_notes", topic="controlled source", material_id=material_id,
            provider=FakeLLMProvider(), idempotency_key="note-generation-1",
        )
        assert replay["replay"] is True and replay["note"]["id"] == note["id"]
        operation = connection.execute(
            "SELECT operation_type,status,source_revision,retrieval_run_id,provider_id,model_id,output_artifact_id "
            "FROM ai_operations WHERE id=?", (first["operation_id"],)
        ).fetchone()
        assert tuple(operation) == ("generate_note", "succeeded", revision_id, first["retrieval_run_id"], "fake", "fake-studybuddy-v1", note["id"])
        confirmed = confirm_note(connection, project_id="project_9b_notes", note_id=note["id"])
        assert confirmed["status"] == "confirmed"


def test_note_generation_rejects_invalid_scope_empty_and_idempotency_mismatch(tmp_path: Path):
    with connect(tmp_path / "studybuddy.sqlite3") as connection:
        _seed_project(connection)
        material_id, revision_id = _seed_indexed_source(connection)
        with pytest.raises(ValueError, match="study_note_generation_empty"):
            generate_note_draft(connection, project_id="project_9b_notes", topic="absent token", material_id=material_id, provider=FakeLLMProvider())
        with pytest.raises(ValueError, match="study_note_generation_stale_source"):
            generate_note_draft(connection, project_id="project_9b_notes", topic="controlled", material_id=material_id,
                                source_revision=revision_id + "stale", provider=FakeLLMProvider())
        unindexed = "material_0123456789abcdef0123456789abcdef"
        connection.execute(
            "INSERT INTO materials (id,project_id,original_name,source_sha256,stored_path,media_type,created_at,updated_at,deleted_at) "
            "VALUES (?,?,?,?,?,?,?,?,NULL)", (unindexed, "project_9b_notes", "new.txt", "c" * 64, "originals/c", "text/plain", "now", "now"),
        )
        with pytest.raises(ValueError, match="study_note_generation_not_ready"):
            generate_note_draft(connection, project_id="project_9b_notes", topic="controlled", material_id=unindexed, provider=FakeLLMProvider())
        generate_note_draft(connection, project_id="project_9b_notes", topic="controlled", material_id=material_id,
                            provider=FakeLLMProvider(), idempotency_key="note-generation-mismatch")
        with pytest.raises(ValueError, match="study_note_generation_idempotency_mismatch"):
            generate_note_draft(connection, project_id="project_9b_notes", topic="different", material_id=material_id,
                                provider=FakeLLMProvider(), idempotency_key="note-generation-mismatch")


def test_note_generation_failure_keeps_only_safe_failed_operation_and_retry_is_new_draft(tmp_path: Path):
    class TimeoutProvider:
        provider_id = "fake"
        model_id = "fake-studybuddy-v1"

        def generate_answer(self, _request):
            raise ProviderError("provider_timeout")

    class ForgingProvider:
        provider_id = "fake"
        model_id = "fake-studybuddy-v1"

        def generate_answer(self, _request):
            return ProviderResult(
                '{"title":"forged","blocks":[{"block_kind":"text","content":"bad","citation_keys":["ctx-deadbeef-deadbeef"]}]}',
                [], self.provider_id, self.model_id, 1, 1,
            )

    with connect(tmp_path / "studybuddy.sqlite3") as connection:
        _seed_project(connection)
        material_id, _ = _seed_indexed_source(connection)
        with pytest.raises(ValueError, match="study_note_provider_timeout"):
            generate_note_draft(connection, project_id="project_9b_notes", topic="controlled", material_id=material_id,
                                provider=TimeoutProvider(), idempotency_key="retry-note")
        failed = connection.execute(
            "SELECT id,status,error_code FROM ai_operations WHERE idempotency_key='retry-note'"
        ).fetchone()
        assert tuple(failed[1:]) == ("failed", "study_note_provider_timeout")
        assert connection.execute("SELECT COUNT(*) FROM notes").fetchone()[0] == 0
        retry = generate_note_draft(connection, project_id="project_9b_notes", topic="controlled", material_id=material_id,
                                    provider=FakeLLMProvider(), idempotency_key="retry-note")
        assert retry["status"] == "succeeded" and retry["replay"] is False
        with pytest.raises(ValueError, match="study_note_generation_citation_invalid"):
            generate_note_draft(connection, project_id="project_9b_notes", topic="controlled", material_id=material_id,
                                provider=ForgingProvider())
        failed_count = connection.execute(
            "SELECT COUNT(*) FROM ai_operations WHERE operation_type='generate_note' AND status='failed'"
        ).fetchone()[0]
        assert failed_count == 2
        assert connection.execute("SELECT COUNT(*) FROM notes").fetchone()[0] == 1


def test_note_generation_not_configured_malformed_and_running_idempotency_are_safe(tmp_path: Path):
    class MalformedProvider:
        provider_id = "fake"
        model_id = "fake-studybuddy-v1"

        def generate_answer(self, _request):
            return ProviderResult("{bad", [], self.provider_id, self.model_id, 1, 1)

    with connect(tmp_path / "studybuddy.sqlite3") as connection:
        _seed_project(connection)
        material_id, _ = _seed_indexed_source(connection)
        with pytest.raises(ValueError, match="study_note_provider_not_configured"):
            generate_note_draft(connection, project_id="project_9b_notes", topic="controlled", material_id=material_id,
                                provider=None, idempotency_key="unconfigured-note")
        assert connection.execute(
            "SELECT status,error_code FROM ai_operations WHERE idempotency_key='unconfigured-note'"
        ).fetchone()[:] == ("failed", "study_note_provider_not_configured")
        with pytest.raises(ValueError, match="study_note_generation_schema_invalid"):
            generate_note_draft(connection, project_id="project_9b_notes", topic="controlled", material_id=material_id,
                                provider=MalformedProvider())
        assert connection.execute("SELECT COUNT(*) FROM notes").fetchone()[0] == 0
        running = create_note_generation_operation(
            connection, project_id="project_9b_notes", topic="controlled", material_id=material_id,
            idempotency_key="running-note",
        )
        with pytest.raises(ValueError, match="study_note_generation_in_progress"):
            generate_note_draft(connection, project_id="project_9b_notes", topic="controlled", material_id=material_id,
                                provider=FakeLLMProvider(), idempotency_key="running-note")
        fail_note_generation_operation(connection, operation_id=running["operation_id"], error_code="study_note_operation_stale")


def test_note_generation_persistence_rollback_and_user_note_protection(tmp_path: Path):
    with connect(tmp_path / "studybuddy.sqlite3") as connection:
        _seed_project(connection)
        material_id, revision_id = _seed_indexed_source(connection)
        user_note = create_user_note(connection, project_id="project_9b_notes", title="User note", blocks=[{"content": "Keep me"}])
        confirm_note(connection, project_id="project_9b_notes", note_id=user_note["id"])
        connection.execute(
            "CREATE TRIGGER fail_generated_note_link BEFORE INSERT ON note_block_source_links "
            "BEGIN SELECT RAISE(ABORT, 'private'); END"
        )
        with pytest.raises(ValueError, match="study_note_generation_failed"):
            generate_note_draft(connection, project_id="project_9b_notes", topic="controlled", material_id=material_id,
                                provider=FakeLLMProvider())
        connection.execute("DROP TRIGGER fail_generated_note_link")
        assert get_note(connection, project_id="project_9b_notes", note_id=user_note["id"])["blocks"][0]["content"] == "Keep me"
        assert connection.execute("SELECT COUNT(*) FROM notes WHERE provenance='ai_generated'").fetchone()[0] == 0
        operation = connection.execute(
            "SELECT status,error_code FROM ai_operations WHERE operation_type='generate_note' ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
        assert tuple(operation) == ("failed", "study_note_generation_failed")
        # Persist must reject an operation whose source revision is no longer current.
        pending = create_note_generation_operation(
            connection, project_id="project_9b_notes", topic="controlled", material_id=material_id,
        )
        with pytest.raises(ValueError, match="study_note_generation_stale_source"):
            persist_generated_note_draft(
                connection, project_id="project_9b_notes", operation_id=pending["operation_id"],
                source_revision="revision_changed", raw_output='{"title":"x","blocks":[]}', context_blocks=[],
                provider_id="fake", model_id="fake-studybuddy-v1", prompt_tokens=1, completion_tokens=1,
                latency_ms=0, provider_request_id=None, total_tokens=2, finish_reason="stop",
            )
        fail_note_generation_operation(connection, operation_id=pending["operation_id"], error_code="study_note_generation_stale_source")
        assert connection.execute("SELECT source_revision FROM ai_operations WHERE id=?", (pending["operation_id"],)).fetchone()[0] == revision_id
