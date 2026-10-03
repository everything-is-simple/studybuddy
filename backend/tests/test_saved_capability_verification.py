from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import capability_verify as verify
from app.config import AppConfig
from app.embedding import EmbeddingError
from app.app_factory import create_app
from app.providers import ProviderError


def config(tmp_path):
    return AppConfig(data_root=tmp_path, auto_detect_enabled=False,
                     ai_provider_id='synthetic-cloud', ai_model_id='synthetic-model',
                     ai_base_url='https://example.invalid/v1', ai_api_key='SYNTHETIC_SECRET')


def stub_llm(monkeypatch, result, seen):
    def registry(*args, **kwargs):
        seen['registry'] = kwargs
        def answer(request):
            seen['request'] = request
            return result
        provider = SimpleNamespace(provider_id='synthetic-cloud', model_id='synthetic-model', generate_answer=answer)
        return SimpleNamespace(configured_provider=lambda: provider)
    monkeypatch.setattr(verify, 'provider_registry', registry)


def test_qa_uses_server_held_credentials_and_returns_only_receipt(tmp_path, monkeypatch):
    seen = {}
    stub_llm(monkeypatch, SimpleNamespace(answer_text='Synthetic answer [ctx-synthetic-water]',
             citation_keys=['ctx-synthetic-water']), seen)
    cfg = config(tmp_path)
    with TestClient(create_app(cfg, index_html='<html></html>')) as client:
        before = client.get('/api/system/capabilities').json()
        response = client.post('/api/system/capabilities/verify-saved', json={'capability':'qa'})
        after = client.get('/api/system/capabilities').json()
    assert response.status_code == 200
    assert response.json()['valid_citation'] is True
    assert response.json()['scope'] == 'synthetic_provider_request'
    assert seen['registry']['api_key'] == 'SYNTHETIC_SECRET'
    assert seen['request'].max_output_tokens == cfg.ai_max_output_tokens
    assert seen['request'].context_blocks[0]['citation_key'] == verify.SYNTHETIC_CITATION
    assert 'SYNTHETIC_SECRET' not in response.text
    assert 'Synthetic answer' not in response.text
    assert before == after


@pytest.mark.parametrize('citations', [[], ['ctx-invented'], ['ctx-synthetic-water','ctx-invented']])
def test_qa_cannot_pass_without_exact_valid_citation(tmp_path, monkeypatch, citations):
    stub_llm(monkeypatch, SimpleNamespace(answer_text='answer',citation_keys=citations), {})
    with pytest.raises(ProviderError, match='provider_schema_mismatch'):
        verify.verify_saved_capability(config(tmp_path),'qa')


@pytest.mark.parametrize('bad', [False, True])
def test_generation_checks_json_shape_and_citations(tmp_path, monkeypatch, bad):
    item={'front':'Water cycle?', 'back':'Evaporation.', 'explanation':'Synthetic explanation.',
          'tags':[], 'citations':['ctx-invented' if bad else verify.SYNTHETIC_CITATION]}
    seen={}
    stub_llm(monkeypatch, SimpleNamespace(answer_text=json.dumps({'items':[item]})), seen)
    if bad:
        with pytest.raises(ProviderError, match='provider_schema_mismatch'):
            verify.verify_saved_capability(config(tmp_path),'generation')
    else:
        result=verify.verify_saved_capability(config(tmp_path),'generation')
        assert result['draft_count']==1
        assert seen['request'].generation_kind=='card'
        assert 'Synthetic explanation' not in json.dumps(result)


@pytest.mark.parametrize('vectors,passes', [([[1.0,0.0],[0.0,1.0]],True), ([[float('nan')],[1.0]],False), ([[1.0]],False)])
def test_embedding_receipt_validates_vectors(tmp_path, monkeypatch, vectors, passes):
    provider=SimpleNamespace(provider_id='synthetic',model_id='synthetic-embedding',embed=lambda texts:vectors)
    monkeypatch.setattr(verify,'EmbeddingProviderRegistry',lambda *a,**k:SimpleNamespace(configured_provider=lambda:provider))
    if passes:
        assert verify.verify_saved_capability(config(tmp_path),'index')['dimensions']==2
    else:
        with pytest.raises(EmbeddingError,match='embedding_invalid_vector'):
            verify.verify_saved_capability(config(tmp_path),'index')


def test_invalid_payload_and_raw_failures_do_not_leak_or_call_providers(tmp_path,monkeypatch):
    seen={}
    stub_llm(monkeypatch,SimpleNamespace(),seen)
    with TestClient(create_app(config(tmp_path),index_html='<html></html>')) as client:
        for payload in ({'capability':'email'}, {'capability':'qa','api_key':'PRIVATE_SENTINEL'}):
            response=client.post('/api/system/capabilities/verify-saved',json=payload)
            assert response.status_code==400
            assert response.json()['detail']=='invalid_capability_check'
            assert 'PRIVATE_SENTINEL' not in response.text
        assert not seen
        response=client.post('/api/system/capabilities/verify-saved',json={'capability':'qa'})
        assert response.status_code==500
        assert response.json()['detail']=='capability_verification_failed'
