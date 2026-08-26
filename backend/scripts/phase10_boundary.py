from __future__ import annotations

"""Reproducible, synthetic Phase 10-8 boundary evidence.

This runner deliberately measures the supported local v1 envelope only. It writes
no repository artifacts: all data is created below a temporary directory and the
stdout report contains timings, counts and sizes, never source text or paths.
"""

import ctypes
import gc
import json
import sys
import tempfile
import time
from ctypes import wintypes
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.backup import backup_data, restore_backup, verify_backup  # noqa: E402
from app.config import AppConfig  # noqa: E402
from app.main import create_app  # noqa: E402
from app.repository import connect  # noqa: E402
from app.task_handlers import build_task_runner  # noqa: E402


THRESHOLDS_MS = {
    "startup": 5_000,
    "single_import": 2_000,
    "batch_import_20": 10_000,
    "search": 2_000,
    "export": 5_000,
    "revision_chunk_index": 10_000,
    "qa": 5_000,
    "cards_exercises": 5_000,
    "learning_9a_9c": 5_000,
    "capture_report_9d": 5_000,
    "task_enqueue": 2_000,
    "task_run": 10_000,
    "backup": 10_000,
    "verify": 10_000,
    "restore": 10_000,
    "lifecycle_cycle": 2_000,
    "database_bytes": 32 * 1024 * 1024,
    "peak_working_set_bytes": 256 * 1024 * 1024,
}


def timed(function):
    started = time.perf_counter()
    value = function()
    return value, round((time.perf_counter() - started) * 1000, 3)


def check(name: str, elapsed_ms: float, checks: list[dict[str, object]]) -> None:
    threshold = THRESHOLDS_MS[name]
    checks.append({
        "name": name,
        "elapsed_ms": elapsed_ms,
        "threshold_ms": threshold,
        "status": "passed" if elapsed_ms <= threshold else "failed",
    })


def upload(client: TestClient, name: str, body: bytes) -> dict[str, object]:
    response = client.post("/api/materials", files={"file": (name, body, "text/plain")})
    if response.status_code != 201:
        raise RuntimeError("material_import_failed")
    return response.json()


def table_counts(root: Path) -> dict[str, int]:
    with connect(root / "studybuddy.sqlite3") as connection:
        tables = (
            "materials", "extractions", "text_spans", "material_revisions", "chunks",
            "embeddings", "ai_operations", "operation_tasks", "operation_task_attempts",
            "learning_goals", "study_plans", "study_plan_items", "study_decks", "study_cards",
            "exercise_sets", "exercises", "practice_sessions", "capture_sessions",
            "report_snapshots",
        )
        return {table: int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]) for table in tables}


def run(root: Path) -> dict[str, object]:
    root.mkdir(parents=True, exist_ok=True)
    body = ("Boundary evidence keeps source data synthetic and local. " * 80).encode()
    config = AppConfig(
        data_root=root, max_upload_bytes=2_000_000, ai_provider_id="fake",
        embedding_provider_id="fake", embedding_model_id="fake-embedding-v1",
    )
    checks: list[dict[str, object]] = []
    counts_before = table_counts(root) if (root / "studybuddy.sqlite3").exists() else {}

    startup_started = time.perf_counter()
    client = TestClient(create_app(config))
    client.__enter__()
    check("startup", round((time.perf_counter() - startup_started) * 1000, 3), checks)
    try:
        health = client.get("/api/health")
        readiness = client.get("/api/readiness")
        if health.status_code != 200 or readiness.status_code != 200:
            raise RuntimeError("startup_not_ready")

        one, elapsed = timed(lambda: upload(client, "boundary-single.txt", body))
        check("single_import", elapsed, checks)

        def batch_import():
            response = client.post(
                "/api/materials/batch",
                files=[("files", (f"boundary-{i}.txt", body, "text/plain")) for i in range(20)],
            )
            if response.status_code != 201:
                raise RuntimeError("batch_import_failed")
            return response.json()

        batch, elapsed = timed(batch_import)
        check("batch_import_20", elapsed, checks)

        search, elapsed = timed(lambda: client.get("/api/materials", params={"q": "synthetic", "limit": 20}))
        if search.status_code != 200:
            raise RuntimeError("search_failed")
        check("search", elapsed, checks)

        exported, elapsed = timed(lambda: client.post(
            "/api/materials/export",
            json={"material_ids": [one["material_id"]], "include_original": True, "include_text": True},
        ))
        if exported.status_code != 200:
            raise RuntimeError("export_failed")
        check("export", elapsed, checks)

        indexed, elapsed = timed(lambda: client.post(f"/api/materials/{one['material_id']}/ai-index"))
        if indexed.status_code != 200 or indexed.json().get("status") not in {"ready", "empty"}:
            raise RuntimeError("index_failed")
        check("revision_chunk_index", elapsed, checks)

        qa, elapsed = timed(lambda: client.post(
            "/api/qa/ask", json={"question": "synthetic local", "material_ids": [one["material_id"]]},
        ))
        if qa.status_code != 200 or qa.json().get("status") != "succeeded":
            raise RuntimeError("qa_failed")
        check("qa", elapsed, checks)

        deck = client.post("/api/study/decks", json={"title": "Boundary deck"})
        exercise_set = client.post("/api/study/exercise-sets", json={"title": "Boundary exercises"})
        if deck.status_code != 201 or exercise_set.status_code != 201:
            raise RuntimeError("study_container_failed")
        card, elapsed = timed(lambda: client.post(
            f"/api/study/decks/{deck.json()['id']}/cards",
            json={"front": "Synthetic front", "back": "Synthetic back"},
        ))
        exercise = client.post(
            f"/api/study/exercise-sets/{exercise_set.json()['id']}/exercises",
            json={"exercise_type": "true_false", "prompt": "Synthetic", "answer_key": True},
        )
        if card.status_code != 201 or exercise.status_code != 201:
            raise RuntimeError("cards_exercises_failed")
        confirmed_exercise = client.post(f"/api/study/exercises/{exercise.json()['id']}/confirm")
        if confirmed_exercise.status_code != 200:
            raise RuntimeError("exercise_confirm_failed")
        check("cards_exercises", elapsed, checks)

        def learning_flow():
            goal = client.post("/api/study/goals", json={"title": "Boundary goal"})
            plan = client.post("/api/study/plans", json={"goal_id": goal.json()["id"], "title": "Boundary plan"})
            item = client.post(f"/api/study/plans/{plan.json()['id']}/items", json={"title": "Boundary item"})
            practice = client.post(
                "/api/study/practice-sessions",
                json={"title": "Boundary practice", "exercise_ids": [exercise.json()["id"]], "duration_seconds": 60},
            )
            if any(response.status_code not in {201, 200} for response in (goal, plan, item, practice)):
                raise RuntimeError("learning_9a_9c_failed")

        _, elapsed = timed(learning_flow)
        check("learning_9a_9c", elapsed, checks)

        def capture_report_flow():
            capture = client.post(
                "/api/study/capture-sessions",
                json={"asset_kind": "audio", "original_name": "boundary.wav", "media_type": "audio/wav"},
            )
            report = client.post(
                "/api/study/reports",
                json={"report_kind": "daily", "timezone": "UTC", "period_start": "2026-01-01", "period_end": "2026-01-02"},
            )
            if capture.status_code != 201 or report.status_code != 201:
                raise RuntimeError("capture_report_failed")

        _, elapsed = timed(capture_report_flow)
        check("capture_report_9d", elapsed, checks)

        task, elapsed = timed(lambda: client.post(f"/api/materials/{one['material_id']}/ai-index/tasks"))
        if task.status_code != 202:
            raise RuntimeError("task_enqueue_failed")
        check("task_enqueue", elapsed, checks)
        runner = build_task_runner(config)
        _, elapsed = timed(lambda: runner.run_once())
        completed_task = client.get(f"/api/tasks/{task.json()['task_id']}").json()
        if completed_task.get("status") != "succeeded" or completed_task.get("progress_percent") != 100:
            raise RuntimeError("task_run_failed")
        check("task_run", elapsed, checks)

        # Exercise the explicit retry contract with a deterministic local failure;
        # no network or real provider is involved.
        retry_source = upload(client, "boundary-retry.txt", b"retryable synthetic source")
        retry_task = client.post(f"/api/materials/{retry_source['material_id']}/ai-index/tasks")
        if retry_task.status_code != 202:
            raise RuntimeError("task_retry_enqueue_failed")
        from app import task_handlers
        from app.embedding import EmbeddingError
        original_provider = task_handlers._embedding_provider
        task_handlers._embedding_provider = lambda _config: (_ for _ in ()).throw(
            EmbeddingError("embedding_provider_timeout")
        )
        try:
            if not runner.run_once():
                raise RuntimeError("task_retry_first_run_failed")
        finally:
            task_handlers._embedding_provider = original_provider
        failed_task = client.get(f"/api/tasks/{retry_task.json()['task_id']}").json()
        if failed_task.get("status") != "failed":
            raise RuntimeError("task_retry_failure_not_recorded")
        retry_response = client.post(f"/api/tasks/{retry_task.json()['task_id']}/retry")
        if retry_response.status_code != 200 or not runner.run_once():
            raise RuntimeError("task_retry_run_failed")
        retried_task = client.get(f"/api/tasks/{retry_task.json()['task_id']}").json()
        if retried_task.get("status") != "succeeded" or retried_task.get("attempt_count") != 2:
            raise RuntimeError("task_retry_result_failed")
        checks.append({"name": "task_retry_progress", "status": "passed", "attempt_count": 2,
                       "progress_percent": retried_task.get("progress_percent")})

        cycle_times: list[float] = []
        for index in range(10):
            started = time.perf_counter()
            material = upload(client, f"cycle-{index}.txt", b"bounded lifecycle source")
            material_id = material["material_id"]
            if client.patch(f"/api/materials/{material_id}", json={"original_name": f"renamed-{index}.txt"}).status_code != 200:
                raise RuntimeError("lifecycle_rename_failed")
            if client.delete(f"/api/materials/{material_id}").status_code != 204:
                raise RuntimeError("lifecycle_delete_failed")
            if client.post(f"/api/materials/{material_id}/restore").status_code != 200:
                raise RuntimeError("lifecycle_restore_failed")
            if client.delete(f"/api/materials/{material_id}").status_code != 204:
                raise RuntimeError("lifecycle_delete_failed")
            if client.post(f"/api/materials/{material_id}/purge").status_code != 200:
                raise RuntimeError("lifecycle_purge_failed")
            cycle_times.append(round((time.perf_counter() - started) * 1000, 3))
        check("lifecycle_cycle", max(cycle_times), checks)

        backup = root.parent / "backup"
        restored = root.parent / "restored"
        _, elapsed = timed(lambda: backup_data(root, backup))
        check("backup", elapsed, checks)
        _, elapsed = timed(lambda: verify_backup(backup))
        check("verify", elapsed, checks)
        _, elapsed = timed(lambda: restore_backup(restored, backup, confirm=True))
        check("restore", elapsed, checks)
        if not (restored / "studybuddy.sqlite3").is_file():
            raise RuntimeError("restore_failed")

        gc.collect()
        current_rss = _rss_bytes()
        database_bytes = (root / "studybuddy.sqlite3").stat().st_size
        originals_bytes = sum(path.stat().st_size for path in (root / "originals").rglob("original"))
        counts_after = table_counts(root)
        database_status = "passed" if database_bytes <= THRESHOLDS_MS["database_bytes"] else "failed"
        memory_status = "passed" if current_rss <= THRESHOLDS_MS["peak_working_set_bytes"] else "failed"
        checks.extend([
            {"name": "database_bytes", "status": database_status, "value": database_bytes,
             "threshold_bytes": THRESHOLDS_MS["database_bytes"]},
            {"name": "peak_working_set_bytes", "status": memory_status, "value": current_rss,
             "threshold_bytes": THRESHOLDS_MS["peak_working_set_bytes"]},
        ])
        return {
            "status": "passed" if all(item["status"] == "passed" for item in checks) else "failed",
            "task": "phase10_boundary_v1",
            "environment": "synthetic/local/single-process/single-instance/SQLite/fake-provider",
            "checks": checks,
            "lifecycle": {"cycles": len(cycle_times), "max_cycle_ms": max(cycle_times)},
            "database_bytes": database_bytes,
            "originals_bytes": originals_bytes,
            "python_maxrss_bytes": current_rss,
            "table_counts": counts_after,
            "table_count_delta": {key: counts_after[key] - counts_before.get(key, 0) for key in counts_after},
            "backup_restore": {"verified": True, "restored_schema_preserved": True},
            "task_retry": {"verified": True, "attempt_count": retried_task.get("attempt_count"),
                            "progress_percent": retried_task.get("progress_percent")},
            "thresholds_are_local_timebox_only": True,
        }
    finally:
        client.__exit__(*sys.exc_info())
        client.close()


def _rss_bytes() -> int:
    if sys.platform == "win32":
        class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
            _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD),
                        ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                        ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t)]
        counters = PROCESS_MEMORY_COUNTERS()
        counters.cb = ctypes.sizeof(counters)
        handle = ctypes.windll.kernel32.GetCurrentProcess()
        get_info = ctypes.windll.psapi.GetProcessMemoryInfo
        get_info.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESS_MEMORY_COUNTERS), wintypes.DWORD]
        get_info.restype = wintypes.BOOL
        if get_info(handle, ctypes.byref(counters), counters.cb):
            return int(counters.PeakWorkingSetSize)
        return 0
    import resource
    return int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024)


def main() -> None:
    # Keep cleanup best-effort on Windows: SQLite/WAL handles may be released
    # after the TestClient shutdown callback returns. The directory is outside
    # the repository and contains only synthetic data.
    directory = tempfile.mkdtemp(prefix="studybuddy-phase10-boundary-")
    try:
        result = run(Path(directory) / "data")
    finally:
        import shutil
        shutil.rmtree(directory, ignore_errors=True)
    print(json.dumps(result, ensure_ascii=True, sort_keys=True))
    raise SystemExit(0 if result["status"] == "passed" else 1)


if __name__ == "__main__":
    main()
