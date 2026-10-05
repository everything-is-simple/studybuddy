"""S2 material -> modules -> cited draft exercises -> scored practice -> restore."""
import json
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.config import AppConfig
from app.main import create_app
from app.repository import connect
from app.providers import ProviderResult
from app.backup import backup_data, verify_backup, restore_backup
from app.restore_acceptance import verify_restored_data


def source(api, name="source.txt"):
    mid = api.post("/api/materials", files={"file":(name,b"A controlled study establishes Newton force mass acceleration.", "text/plain")}).json()["material_id"]
    assert api.post(f"/api/materials/{mid}/ai-index").status_code == 200
    cid = api.get("/api/knowledge-modules/sources", params={"material_id":mid}).json()[0]["chunk_id"]
    return mid, cid


def manual(api, mid, cid):
    response = api.post("/api/knowledge-modules", json={"material_id":mid,"chunk_ids":[cid],"title":"Newton"})
    assert response.status_code == 201
    return response.json()


def generate(api, key, module_ids):
    return api.post(f"/api/study/exercise-sets/{key}/generate", json={
        "topic":"Newton force", "knowledge_module_ids":module_ids, "count":1,"exercise_type":"multiple_choice"},
        headers={"Idempotency-Key":"s2-generate"})


def test_manual_ai_confirmation_edit_reject_and_filters(tmp_path):
    with TestClient(create_app(AppConfig(data_root=tmp_path, ai_provider_id="fake"))) as api:
        mid,cid=source(api)
        user=manual(api,mid,cid)
        response=api.post("/api/knowledge-modules/extract",json={"material_id":mid,"max_modules":2})
        assert response.status_code == 200
        drafts=response.json()["draft_modules"]
        assert all(m["lifecycle"]=="draft" and m["provenance"]=="ai_generated" for m in drafts)
        assert [m['id'] for m in api.get('/api/study/modules').json()] == [user['id']]
        key=drafts[0]["id"]
        assert api.patch(f"/api/knowledge-modules/{key}",json={"title":"Edited Newton","description":"My edit"}).status_code==200
        assert api.post(f"/api/knowledge-modules/{key}/confirm").json()["title"]=="Edited Newton"
        assert key in [m['id'] for m in api.get('/api/study/modules').json()]
        assert api.patch(f"/api/knowledge-modules/{key}",json={"source_evidence":{}}).status_code==422
        assert api.post(f"/api/knowledge-modules/{drafts[1]['id']}/reject").json()["lifecycle"]=="rejected"
        assert api.get("/api/knowledge-modules",params={"material_id":mid,"lifecycle":"confirmed","q":"Newton"}).json()["total"]==2
        assert api.get("/api/knowledge-modules",params={"limit":1,"offset":10}).json()["total"]==3
        assert api.delete(f"/api/knowledge-modules/{user['id']}").status_code==204
        assert api.get(f"/api/knowledge-modules/{user['id']}").status_code==404


def test_source_selected_generation_practice_replay_and_mastery(tmp_path):
    config=AppConfig(data_root=tmp_path, ai_provider_id="fake")
    with TestClient(create_app(config)) as api:
        mid,cid=source(api)
        module=manual(api,mid,cid)
        key=api.post("/api/study/exercise-sets",json={"title":"S2"}).json()["id"]
        generated=generate(api,key,[module["id"]])
        assert generated.status_code==200, generated.text
        item=generated.json()["artifacts"][0]
        assert item["status"]=="draft" and item["citations"][0]["status"]=="valid"
        assert "answer_key" not in generated.text
        assert generate(api,key,[module["id"]]).json()["replay"] is True
        assert api.post(f"/api/study/exercises/{item['id']}/confirm").status_code==200
        attempt=api.post(f"/api/study/exercises/{item['id']}/attempts",json={"answer":0})
        assert attempt.status_code==201, attempt.text
        assert attempt.json()["is_correct"] is True
        view=api.get(f"/api/knowledge-modules/{module['id']}").json()
        assert view["mastery_level"]==.1 and view["learn_status"]=="in_progress"
        assert api.get(f"/api/knowledge-modules/{module['id']}").json()["mastery_level"]==.1
        assert len(api.get(f"/api/knowledge-modules/{module['id']}/practice-history").json()["attempts"])==1
        api.post(f"/api/study/exercises/{item['id']}/attempts",json={"answer":1})
        assert api.get(f"/api/knowledge-modules/{module['id']}").json()["mastery_level"]==.08
        assert api.get(f"/api/knowledge-modules/{module['id']}").json()["learn_status"]=="needs_review"
        assert api.delete(f"/api/knowledge-modules/{module['id']}").status_code==204
        assert api.get(f"/api/study/exercises/{item['id']}").status_code==200


def test_provider_not_configured_does_not_block_manual(tmp_path):
    with TestClient(create_app(AppConfig(data_root=tmp_path))) as api:
        mid,cid=source(api)
        assert api.post("/api/knowledge-modules/extract",json={"material_id":mid}).status_code==503
        assert manual(api,mid,cid)["lifecycle"]=="confirmed"


def test_invalid_provider_response_and_citations_are_atomic(tmp_path, monkeypatch):
    from app.api import knowledge_modules as routes
    class Bad:
        def configured_provider(self): return self
        def generate_answer(self, request):
            return ProviderResult(answer_text=json.dumps({"items":[{"title":"Invented","description":"bad","importance":1,"difficulty":3,"tags":[],"citations":["invented"]}]}),citation_keys=[],provider_id="fake",model_id="fake",prompt_tokens=None,completion_tokens=None)
    with TestClient(create_app(AppConfig(data_root=tmp_path,ai_provider_id="fake"))) as api:
        mid,cid=source(api)
        monkeypatch.setattr(routes,"ProviderRegistry",lambda *a,**k:Bad())
        response=api.post("/api/knowledge-modules/extract",json={"material_id":mid,"max_modules":1})
        assert response.status_code==502 and response.json()["detail"]=="knowledge_generation_invalid"
        assert api.get("/api/knowledge-modules").json()["total"]==0


def test_generation_rejects_draft_cross_material_and_deleted_sources(tmp_path):
    with TestClient(create_app(AppConfig(data_root=tmp_path,ai_provider_id="fake"))) as api:
        mid,cid=source(api); other,other_cid=source(api,"other.txt")
        invalid=api.post("/api/knowledge-modules",json={"material_id":mid,"chunk_ids":[other_cid],"title":"Wrong"})
        assert invalid.status_code==409
        draft=api.post("/api/knowledge-modules/extract",json={"material_id":mid,"max_modules":1}).json()["draft_modules"][0]
        key=api.post("/api/study/exercise-sets",json={"title":"S2"}).json()["id"]
        assert generate(api,key,[draft["id"]]).status_code==409
        module=manual(api,mid,cid)
        assert api.delete(f"/api/materials/{mid}").status_code==204
        view=api.get(f"/api/knowledge-modules/{module['id']}").json()
        assert view["source_status"]=="source_deleted" and "context" not in view["source_evidence"]
        assert generate(api,key,[module["id"]]).status_code==409


def test_s2_backup_restore_preserves_modules_fts_links_and_mastery(tmp_path):
    root,backup,restored=tmp_path/"source",tmp_path/"backup",tmp_path/"restored"
    config=AppConfig(data_root=root,ai_provider_id="fake")
    with TestClient(create_app(config)) as api:
        mid,cid=source(api); module=manual(api,mid,cid)
        key=api.post("/api/study/exercise-sets",json={"title":"S2"}).json()["id"]
        item=generate(api,key,[module["id"]]).json()["artifacts"][0]
        api.post(f"/api/study/exercises/{item['id']}/confirm")
        api.post(f"/api/study/exercises/{item['id']}/attempts",json={"answer":0})
    assert backup_data(root,backup)["status"]=="complete"
    assert verify_backup(backup)["status"]=="valid"
    assert restore_backup(restored,backup,confirm=True)["status"]=="restored"
    assert verify_restored_data(restored)["status"]=="passed"
    with TestClient(create_app(AppConfig(data_root=restored,ai_provider_id="fake"))) as api:
        view=api.get(f"/api/knowledge-modules/{module['id']}").json()
        assert view["mastery_level"]==.1 and view["source_status"]=="valid"
        assert api.get("/api/knowledge-modules",params={"q":"Newton"}).json()["total"]==1
        assert len(api.get(f"/api/knowledge-modules/{module['id']}/practice-history").json()["attempts"])==1


def test_multiple_modules_keep_attribution_and_reject_mixed_revisions(tmp_path):
    config=AppConfig(data_root=tmp_path,ai_provider_id='fake')
    with TestClient(create_app(config)) as api:
        mid,cid=source(api)
        first,second=manual(api,mid,cid),manual(api,mid,cid)
        other,other_cid=source(api,'another.txt')
        third=manual(api,other,other_cid)
        key=api.post('/api/study/exercise-sets',json={'title':'Multiple'}).json()['id']
        assert generate(api,key,[first['id'],third['id']]).status_code==400
        assert generate(api,key,[first['id'],first['id']]).status_code==400
        result=generate(api,key,[first['id'],second['id']])
        assert result.status_code==200
        exercise=result.json()['artifacts'][0]
        with connect(config.database_path) as conn:
            assert conn.execute('SELECT COUNT(*) FROM s2_module_exercises WHERE exercise_id=?',(exercise['id'],)).fetchone()[0]==2
        # Reusing the same operation key for another module selection must fail.
        assert generate(api,key,[first['id']]).status_code==409


def test_pending_review_does_not_invent_mastery(tmp_path):
    with TestClient(create_app(AppConfig(data_root=tmp_path,ai_provider_id='fake'))) as api:
        mid,cid=source(api); module=manual(api,mid,cid)
        key=api.post('/api/study/exercise-sets',json={'title':'Review'}).json()['id']
        response=api.post(f'/api/study/exercise-sets/{key}/generate',json={
            'topic':'Newton','knowledge_module_ids':[module['id']],'exercise_type':'short_answer','count':1})
        exercise=response.json()['artifacts'][0]
        assert api.post(f"/api/study/exercises/{exercise['id']}/confirm").status_code==200
        attempt=api.post(f"/api/study/exercises/{exercise['id']}/attempts",json={'answer':'My explanation'})
        assert attempt.json()['grading_status']=='pending_review'
        view=api.get(f"/api/knowledge-modules/{module['id']}").json()
        assert view['mastery_level']==0 and view['learn_status']=='not_started'


def test_purged_source_preserves_module_identity_and_degrades_without_excerpt(tmp_path):
    with TestClient(create_app(AppConfig(data_root=tmp_path,ai_provider_id='fake'))) as api:
        mid,cid=source(api); module=manual(api,mid,cid)
        assert api.delete(f'/api/materials/{mid}').status_code==204
        assert api.post(f'/api/materials/{mid}/purge').status_code==200
        view=api.get(f"/api/knowledge-modules/{module['id']}").json()
        assert view['id']==module['id'] and view['source_status']=='source_unavailable'
        assert 'context' not in view['source_evidence']


def test_module_removed_during_provider_io_prevents_partial_exercises(tmp_path,monkeypatch):
    from app import main
    from app.providers import ProviderRegistry
    config=AppConfig(data_root=tmp_path,ai_provider_id='fake')
    with TestClient(create_app(config)) as api:
        mid,cid=source(api); module=manual(api,mid,cid)
        key=api.post('/api/study/exercise-sets',json={'title':'Concurrent'}).json()['id']
        class Race:
            def configured_provider(self): return self
            def generate_answer(self,request):
                result=ProviderRegistry('fake').configured_provider().generate_answer(request)
                from app.repositories import knowledge_modules as km
                with connect(config.database_path) as conn:
                    km.transition_module(conn,project_id=config.project_id,module_id=module['id'],action='delete')
                return result
        monkeypatch.setattr(main,'provider_registry',lambda *a,**k:Race())
        response=generate(api,key,[module['id']])
        assert response.status_code==404
        with connect(config.database_path) as conn:
            assert conn.execute('SELECT COUNT(*) FROM exercises').fetchone()[0]==0
            assert conn.execute('SELECT COUNT(*) FROM s2_module_exercises').fetchone()[0]==0
