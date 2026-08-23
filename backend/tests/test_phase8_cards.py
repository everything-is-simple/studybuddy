from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.config import AppConfig
from app.main import create_app


def client(tmp_path: Path) -> TestClient:
    return TestClient(create_app(AppConfig(data_root=tmp_path)))


def test_card_draft_edit_confirm_review_and_privacy(tmp_path: Path):
    with client(tmp_path) as api:
        deck = api.post("/api/study/decks", json={"title": "Basics"})
        assert deck.status_code == 201
        deck_id = deck.json()["id"]
        created = api.post(f"/api/study/decks/{deck_id}/cards", json={
            "front": "Question", "back": "Answer", "tags": ["intro"]
        })
        assert created.status_code == 201
        card = created.json()
        assert card["status"] == "draft"
        assert "answer_key" not in card
        updated = api.patch(f"/api/study/cards/{card['id']}", json={
            "front": "Edited", "back": "Answer", "tags": []
        })
        assert updated.status_code == 200
        confirmed = api.post(f"/api/study/cards/{card['id']}/confirm")
        assert confirmed.status_code == 200
        assert confirmed.json()["status"] == "ready"
        assert api.patch(f"/api/study/cards/{card['id']}", json={"front": "No", "back": "No"}).status_code == 409
        review = api.post(f"/api/study/cards/{card['id']}/reviews", json={"result": "good"})
        assert review.status_code == 201
        assert api.get(f"/api/study/decks/{deck_id}").json()["cards"][0]["status"] == "ready"


def test_ai_card_requires_valid_current_chunk_citation(tmp_path: Path):
    with client(tmp_path) as api:
        material = api.post("/api/materials", files={"file": ("source.txt", b"citation source", "text/plain")}).json()
        mid = material["material_id"]
        assert api.post(f"/api/materials/{mid}/ai-index").status_code == 200
        deck_id = api.post("/api/study/decks", json={"title": "AI"}).json()["id"]
        response = api.post(f"/api/study/decks/{deck_id}/cards", json={
            "front": "Q", "back": "A", "card_type": "ai_generated",
            "citations": [{"citation_key": "fake", "chunk_id": "missing", "quote": "citation source"}],
        })
        assert response.status_code == 400
        assert response.json()["detail"] == "citation_invalid"


def test_card_invalid_payload_and_review_state_are_safe(tmp_path: Path):
    with client(tmp_path) as api:
        deck_id = api.post("/api/study/decks", json={"title": "Safe"}).json()["id"]
        assert api.post(f"/api/study/decks/{deck_id}/cards", json={"front": "", "back": "x"}).json()["detail"] == "invalid_card_payload"
        card = api.post(f"/api/study/decks/{deck_id}/cards", json={"front": "x", "back": "y"}).json()
        assert api.post(f"/api/study/cards/{card['id']}/reviews", json={"result": "good"}).status_code == 404
        assert api.post(f"/api/study/cards/{card['id']}/confirm").status_code == 200
        assert api.post(f"/api/study/cards/{card['id']}/reviews", json={"result": "bad"}).status_code == 400
