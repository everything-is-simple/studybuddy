"""Capture archive lifecycle/API contracts; synthetic fake-provider fixtures only."""
from __future__ import annotations

import sqlite3

import pytest

from test_phase9d_api import PROJECT_ID, _capture_ready, _client
from app.repository import (
    archive_capture_session, connect, create_transcription_operation,
    fail_transcription_operation,
)
from app.repositories import capture as capture_repository


def reviewed(client, action):
    capture_id, _ = _capture_ready(client)
    result = client.post(f'/api/study/capture-sessions/{capture_id}/transcribe')
    assert result.status_code == 200
    draft_id = result.json()['draft']['id']
    result = client.post(f'/api/study/capture-sessions/{capture_id}/{action}',
                         json={'draft_id': draft_id})
    assert result.status_code == 200
    return capture_id, result.json()['capture']


@pytest.mark.parametrize('action', ['confirm', 'reject'])
def test_archive_preserves_reviewed_content_and_is_idempotent(tmp_path, action):
    with _client(tmp_path) as client:
        capture_id, before = reviewed(client, action)
        url = f'/api/study/capture-sessions/{capture_id}'
        material_url = f"/api/materials/{before['material_id']}"
        material_before = client.get(material_url).json()
        original_before = client.get(material_url + '/original').content
        response = client.post(url + '/archive')
        assert response.status_code == 200
        archived = response.json()
        assert archived['status'] == 'archived'
        assert archived['archived_at']
        for key in ('transcript_drafts', 'transcription_operations', 'material_id',
                    'source_status', 'created_at', 'confirmed_at', 'rejected_at'):
            assert archived[key] == before[key]
        assert client.post(url + '/archive').json() == archived
        assert client.get(url).json() == archived
        assert client.get('/api/study/capture-sessions').json()['items'] == []
        assert client.get('/api/study/capture-sessions?include_archived=true').json()['items'] == [archived]
        assert client.get(material_url).json() == material_before
        assert client.get(material_url + '/original').content == original_before
        assert client.post(url + '/transcribe').status_code == 409
    with _client_reopen(tmp_path) as client:
        assert client.get(url).json() == archived


def _client_reopen(tmp_path):
    from fastapi.testclient import TestClient
    from app.config import AppConfig
    from app.main import create_app
    return TestClient(create_app(AppConfig(data_root=tmp_path / 'data', project_id=PROJECT_ID,
                                          asr_provider_id='fake', asr_model_id='fake-capture-v1')))


@pytest.mark.parametrize('state', ['draft', 'uploaded', 'transcribing', 'review_required', 'failed'])
def test_archive_rejects_unreviewed_or_running_sessions(tmp_path, state):
    with _client(tmp_path) as client:
        if state == 'draft':
            capture_id = client.post('/api/study/capture-sessions', json={
                'asset_kind': 'audio', 'original_name': 'synthetic.wav', 'media_type': 'audio/wav',
            }).json()['id']
        else:
            capture_id, _ = _capture_ready(client)
        url = f'/api/study/capture-sessions/{capture_id}'
        if state == 'review_required':
            assert client.post(url + '/transcribe').status_code == 200
        elif state in ('transcribing', 'failed'):
            with connect(tmp_path / 'data' / 'studybuddy.sqlite3') as connection:
                operation = create_transcription_operation(
                    connection, project_id=PROJECT_ID, capture_session_id=capture_id, input_fingerprint='a' * 64,
                )
                if state == 'failed':
                    fail_transcription_operation(connection, project_id=PROJECT_ID, operation_id=operation['id'])
        before = client.get(url).json()
        assert before['status'] == state
        response = client.post(url + '/archive')
        assert response.status_code == 409
        assert response.json()['detail'] == 'capture_invalid_state'
        assert client.get(url).json() == before


def test_archive_missing_and_cross_project_are_not_found(tmp_path):
    with _client(tmp_path) as client:
        capture_id, before = reviewed(client, 'confirm')
        assert client.post('/api/study/capture-sessions/missing/archive').status_code == 404
        with connect(tmp_path / 'data' / 'studybuddy.sqlite3') as connection:
            with pytest.raises(ValueError, match='^capture_not_found$'):
                archive_capture_session(connection, project_id='other_project', capture_session_id=capture_id)
        assert client.get(f'/api/study/capture-sessions/{capture_id}').json() == before


def test_archive_rolls_back_and_returns_safe_error(tmp_path, monkeypatch):
    with _client(tmp_path) as client:
        capture_id, before = reviewed(client, 'confirm')
        def fail_projection(*args, **kwargs):
            raise sqlite3.OperationalError('synthetic-private-diagnostic')
        with monkeypatch.context() as scoped:
            scoped.setattr(capture_repository._part_06, 'get_capture_session', fail_projection)
            response = client.post(f'/api/study/capture-sessions/{capture_id}/archive')
        assert response.status_code == 500
        assert response.json() == {'detail': 'capture_archive_failed'}
        assert client.get(f'/api/study/capture-sessions/{capture_id}').json() == before
