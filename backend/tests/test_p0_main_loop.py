"""P0 主闭环：每一跳产生的事实都必须让 Today 给出新的、可点击的下一步。

目标/计划 → Today → 资料与知识模块 → 练习 → 错题 → 重做闭合 → 冲刺倒计时 → Today。
对应 docs/07-TEST-PLAN.md §1。全部使用 fake Provider 与 tmp_path 隔离 data_root。
"""
import sys
from pathlib import Path
from urllib.parse import urlsplit

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.config import AppConfig
from app.main import create_app

DAY = "2026-10-05"


def today(api):
    response = api.get("/api/today/pending-items", params={"date": DAY})
    assert response.status_code == 200, response.text
    return response.json()["pending_items"]


def kinds(items):
    return {i["category"] for i in items}


def assert_links_open(api, items):
    for item in items:
        assert api.get(urlsplit(item["action_url"]).path).status_code == 200, item["action_url"]


def test_main_loop_always_shows_a_next_step(tmp_path):
    with TestClient(create_app(AppConfig(data_root=tmp_path, ai_provider_id="fake"))) as api:
        # 0. 空库：诚实地没有事项
        assert today(api) == []

        # 1. 建计划并激活，但还没排日程 → Today 提示"待安排日程"
        goal = api.post("/api/study/goals", json={"title": "期末"}).json()["id"]
        plan = api.post("/api/study/plans", json={"title": "力学复习", "goal_id": goal}).json()["id"]
        item = api.post(f"/api/study/plans/{plan}/items", json={"title": "牛顿定律"}).json()["id"]
        assert api.post(f"/api/study/plans/{plan}/confirm").status_code == 200
        assert api.post(f"/api/study/plans/{plan}/activate").status_code == 200
        items = today(api)
        assert kinds(items) == {"plan_schedule"}
        assert items[0]["evidence"]["plan_id"] == plan
        assert_links_open(api, items)

        # 排到今天 → 变成 due_task，"待安排"消失
        assert api.put(f"/api/study/plans/{plan}/rhythm", json={"cadence": "weekly", "timezone": "Asia/Shanghai",
                       "period_start": "2026-10-01", "target_minutes": 300}).status_code == 200
        assert api.post(f"/api/study/plans/{plan}/rhythm/allocations",
                        json={"item_id": item, "local_date": DAY, "planned_minutes": 20}).status_code == 201
        assert kinds(today(api)) == {"due_task"}

        # 2. 导入资料并抽取 AI 草稿 → Today 出现"知识草稿待确认"
        mid = api.post("/api/materials", files={"file": ("newton.txt", b"Newton force mass acceleration law.", "text/plain")}).json()["material_id"]
        assert api.post(f"/api/materials/{mid}/ai-index").status_code == 200
        drafts = api.post("/api/knowledge-modules/extract", json={"material_id": mid, "max_modules": 1}).json()["draft_modules"]
        items = today(api)
        assert "quality_check" in kinds(items)
        assert_links_open(api, items)

        # 3. 确认模块 → 草稿提示消失；模块成为可练习的下一步
        module = drafts[0]["id"]
        assert api.post(f"/api/knowledge-modules/{module}/confirm").status_code == 200
        items = today(api)
        assert "quality_check" not in kinds(items)
        nxt = [i for i in items if i["category"] == "next_step"]
        assert nxt and nxt[0]["evidence"]["module_id"] == module

        # 4. 按模块生成题目、确认、作答答错 → 错题进入 Today
        key = api.post("/api/study/exercise-sets", json={"title": "力学"}).json()["id"]
        generated = api.post(f"/api/study/exercise-sets/{key}/generate", headers={"Idempotency-Key": "p0-loop"},
                             json={"topic": "Newton", "knowledge_module_ids": [module], "count": 1, "exercise_type": "multiple_choice"})
        assert generated.status_code == 200, generated.text
        exercise = generated.json()["artifacts"][0]["id"]
        assert api.post(f"/api/study/exercises/{exercise}/confirm").status_code == 200
        session = api.post("/api/study/practice-sessions", json={"title": "主路径错题练习", "exercise_ids": [exercise]})
        assert session.status_code == 201, session.text
        session_id = session.json()["id"]
        assert api.post(f"/api/study/practice-sessions/{session_id}/start").status_code == 200
        session_item = api.get(f"/api/study/practice-sessions/{session_id}").json()["items"][0]["id"]
        wrong = api.post(f"/api/study/practice-sessions/{session_id}/items/{session_item}/submit", json={"answer": 1})
        assert wrong.status_code in (200, 201) and wrong.json()["is_correct"] is False
        items = today(api)
        assert "mistake_review" in kinds(items)
        assert_links_open(api, items)

        # 5. 重做错题（练习会话）并答对 → 错题闭合，Today 不再提示
        mistake = api.get("/api/study/mistakes").json()
        mistake = (mistake.get("items") if isinstance(mistake, dict) else mistake)[0]["id"]
        redo = api.post(f"/api/study/mistakes/{mistake}/redo", json={}).json()
        assert api.post(f"/api/study/practice-sessions/{redo['id']}/start").status_code == 200
        detail = api.get(f"/api/study/practice-sessions/{redo['id']}").json()
        redo_item = detail["items"][0]["id"]
        right = api.post(f"/api/study/practice-sessions/{redo['id']}/items/{redo_item}/submit", json={"answer": 0})
        assert right.status_code in (200, 201) and right.json()["is_correct"] is True
        assert api.get(f"/api/study/mistakes/{mistake}").json()["status"] == "fixed"
        assert "mistake_review" not in kinds(today(api))

        # 6. 建 5 天后的冲刺目标 → Today 显示倒计时
        cram = api.post("/api/study/cram-goals", json={"title": "期末冲刺", "target_date": "2026-10-10",
                        "timezone": "Asia/Shanghai", "target_exercise_count": 5})
        assert cram.status_code == 201, cram.text
        assert today(api) and "cram_countdown" not in kinds(today(api)), "草稿冲刺目标不进 Today"
        assert api.post(f"/api/study/cram-goals/{cram.json()['id']}/active").status_code == 200
        countdown = [i for i in today(api) if i["category"] == "cram_countdown"]
        assert countdown and countdown[0]["evidence"]["days_left"] == 5
        assert_links_open(api, countdown)

        # 7. 完成今天的计划项 → due_task 消失，Today 仍有下一步（冲刺）
        for event in ("started", "completed"):
            assert api.post(f"/api/study/plans/{plan}/items/{item}/progress",
                            json={"event_type": event, "metadata": {"local_date": DAY}}).status_code == 201
        items = today(api)
        assert "due_task" not in kinds(items) and items, "闭环走完后 Today 不应断档"


def test_wrong_answer_after_fix_reopens_mistake(tmp_path):
    with TestClient(create_app(AppConfig(data_root=tmp_path, ai_provider_id="fake"))) as api:
        mid = api.post("/api/materials", files={"file": ("a.txt", b"Newton force mass acceleration law.", "text/plain")}).json()["material_id"]
        api.post(f"/api/materials/{mid}/ai-index")
        cid = api.get("/api/knowledge-modules/sources", params={"material_id": mid}).json()[0]["chunk_id"]
        module = api.post("/api/knowledge-modules", json={"material_id": mid, "chunk_ids": [cid], "title": "Newton"}).json()["id"]
        key = api.post("/api/study/exercise-sets", json={"title": "s"}).json()["id"]
        exercise = api.post(f"/api/study/exercise-sets/{key}/generate", headers={"Idempotency-Key": "p0-reopen"},
                            json={"topic": "Newton", "knowledge_module_ids": [module], "count": 1,
                                  "exercise_type": "multiple_choice"}).json()["artifacts"][0]["id"]
        api.post(f"/api/study/exercises/{exercise}/confirm")

        def status():
            data = api.get("/api/study/mistakes").json()
            rows = data.get("items") if isinstance(data, dict) else data
            return rows[0]["status"] if rows else None

        api.post(f"/api/study/exercises/{exercise}/attempts", json={"answer": 1})
        assert status() == "open"
        api.post(f"/api/study/exercises/{exercise}/attempts", json={"answer": 0})
        assert status() == "fixed"
        api.post(f"/api/study/exercises/{exercise}/attempts", json={"answer": 1})
        assert status() == "reopened"
