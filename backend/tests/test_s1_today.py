"""S1 reads real domain facts without inventing work or mutating progress."""
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.config import AppConfig
from app.main import create_app
from app.repositories.connection import connect
from app.repositories.today import get_daily_pending_items


DAY = '2026-10-05'


def plan(api, dates=(DAY,), tz='Asia/Shanghai', name='S1 plan'):
    goal = api.post('/api/study/goals', json={'title':name}).json()['id']
    key = api.post('/api/study/plans', json={'title':name,'goal_id':goal}).json()['id']
    items = []
    for i, day in enumerate(dates):
        item = api.post(f'/api/study/plans/{key}/items', json={'title':f'{name} item {i}'}).json()['id']
        items.append(item)
    assert api.put(f'/api/study/plans/{key}/rhythm', json={'cadence':'weekly','timezone':tz,'period_start':'2026-10-01','target_minutes':1000}).status_code == 200
    for item, day in zip(items, dates):
        assert api.post(f'/api/study/plans/{key}/rhythm/allocations',json={'item_id':item,'local_date':day,'planned_minutes':15}).status_code == 201
    assert api.post(f'/api/study/plans/{key}/confirm').status_code == 200
    assert api.post(f'/api/study/plans/{key}/activate').status_code == 200
    return key, items


def pending(api, **params):
    response=api.get('/api/today/pending-items', params={'date':DAY,**params})
    assert response.status_code == 200, response.text
    return response.json()


def test_empty_is_honest_and_schema_unchanged(tmp_path):
    config=AppConfig(data_root=tmp_path)
    with TestClient(create_app(config)) as api:
        result=pending(api)
        assert result['pending_items']==[] and result['total']==0 and result['candidate_total']==0
        assert result['unavailable_sources']==['course_timetable','confirmed_exam_dates']
        with connect(config.database_path) as c:
            assert c.execute('PRAGMA user_version').fetchone()[0]==16


def test_due_overdue_tomorrow_cap_and_stable_refresh(tmp_path):
    with TestClient(create_app(AppConfig(data_root=tmp_path))) as api:
        plan(api,('2026-10-04',DAY,DAY,DAY,DAY,DAY,'2026-10-06','2026-10-08'))
        first=pending(api)
        second=pending(api)
        assert first['total']==5 and first['candidate_total']==7 and first['remaining_count']==2
        assert first['remaining_p0_count']==2
        assert all(i['priority']==0 for i in first['pending_items'])
        assert first['pending_items'][0]['title'].startswith('逾期未闭合')
        assert [i['id'] for i in first['pending_items']]==[i['id'] for i in second['pending_items']]
        for i in first['pending_items']:
            assert i['evidence']['allocation_id']
            assert api.get(urlsplit(i['action_url']).path).status_code==200


def test_completion_uses_existing_events_and_read_does_not_write(tmp_path):
    config=AppConfig(data_root=tmp_path)
    with TestClient(create_app(config)) as api:
        key,[item]=plan(api)
        for _ in range(3): assert pending(api)['total']==1
        with connect(config.database_path) as c:
            assert c.execute('SELECT COUNT(*) FROM study_progress_events').fetchone()[0]==0
        for action in ['started','completed']:
            assert api.post(f'/api/study/plans/{key}/items/{item}/progress',json={'event_type':action,'metadata':{'local_date':DAY}}).status_code==201
        assert pending(api)['total']==0
    with TestClient(create_app(config)) as api:
        assert pending(api)['total']==0


def test_paused_skipped_completed_and_foreign_project_excluded(tmp_path):
    config=AppConfig(data_root=tmp_path)
    with TestClient(create_app(config)) as api:
        key,_=plan(api)
        assert api.post(f'/api/study/plans/{key}/pause').status_code==200
        assert pending(api)['total']==0
        with connect(config.database_path) as c:
            c.execute("INSERT INTO projects VALUES ('foreign','foreign','now')")
            c.execute("UPDATE study_plans SET project_id='foreign',status='active' WHERE id=?",(key,))
            c.execute("UPDATE rhythm_allocations SET project_id='foreign' WHERE plan_id=?",(key,))
            c.execute("UPDATE study_plan_items SET project_id='foreign' WHERE plan_id=?",(key,))
            c.commit()
        assert pending(api)['total']==0


def test_tomorrow_and_dedup_same_plan_item(tmp_path):
    with TestClient(create_app(AppConfig(data_root=tmp_path))) as api:
        key,items=plan(api,(DAY,'2026-10-06'))
        assert api.post(f'/api/study/plans/{key}/rhythm/allocations',json={'item_id':items[0],'local_date':'2026-10-06','planned_minutes':10}).status_code==201
        result=pending(api)
        assert [i['category'] for i in result['pending_items']]==['due_task','tomorrow_prep']
        assert len({i['evidence']['item_id'] for i in result['pending_items']})==2


def test_quality_status_and_ai_confirmation_disappear_after_resolution(tmp_path):
    config=AppConfig(data_root=tmp_path,ai_provider_id='fake')
    with TestClient(create_app(config)) as api:
        empty=api.post('/api/materials', files={'file':('empty.txt',b'','text/plain')}).json()['material_id']
        source=api.post('/api/materials', files={'file':('facts.txt',b'Controlled source establishes a supported learning fact.','text/plain')}).json()['material_id']
        assert api.post(f'/api/materials/{source}/ai-index').status_code==200
        drafts=api.post('/api/knowledge-modules/extract',json={'material_id':source,'max_modules':2}).json()['draft_modules']
        result=pending(api)
        assert result['total']==2 and all(i['category']=='quality_check' for i in result['pending_items'])
        assert any(i['evidence'].get('draft_count')==2 for i in result['pending_items'])
        for module in drafts: assert api.post(f"/api/knowledge-modules/{module['id']}/reject").status_code==200
        assert api.delete(f'/api/materials/{empty}').status_code==204
        assert pending(api)['total']==0


def test_s2_confirmed_module_fills_only_when_priority_work_less_than_three(tmp_path):
    with TestClient(create_app(AppConfig(data_root=tmp_path,ai_provider_id='fake'))) as api:
        source=api.post('/api/materials',files={'file':('module.txt',b'Synthetic material supports this module.','text/plain')}).json()['material_id']
        api.post(f'/api/materials/{source}/ai-index')
        chunk=api.get('/api/knowledge-modules/sources',params={'material_id':source}).json()[0]['chunk_id']
        module=api.post('/api/knowledge-modules',json={'material_id':source,'chunk_ids':[chunk],'title':'Useful module'}).json()
        assert pending(api)['pending_items'][0]['evidence']['module_id']==module['id']
        plan(api,(DAY,DAY,DAY))
        assert all(i['priority']==0 for i in pending(api)['pending_items'])


@pytest.mark.parametrize('params',[{'date':''},{'date':'2026-02-30'},{'date':'20261005'},{'timezone':'invalid-zone'}])
def test_invalid_dates_and_timezone_are_safe(tmp_path,params):
    with TestClient(create_app(AppConfig(data_root=tmp_path))) as api:
        result=api.get('/api/today/pending-items',params=params)
        assert result.status_code==400 and result.json()['detail']=='today_invalid_date_or_timezone'


def test_timezone_midnight_is_not_machine_timezone(tmp_path):
    config=AppConfig(data_root=tmp_path)
    with TestClient(create_app(config)) as api:
        plan(api,('2026-10-05','2026-10-06'))
        with connect(config.database_path) as c:
            result=get_daily_pending_items(c,project_id=config.project_id,timezone_name='Asia/Shanghai',now=datetime(2026,10,5,18,tzinfo=timezone.utc))
            assert result['date']=='2026-10-06'


def test_database_failure_has_stable_safe_error(tmp_path,monkeypatch):
    from app.api import today
    with TestClient(create_app(AppConfig(data_root=tmp_path))) as api:
        def fail(*args,**kwargs): raise sqlite3.OperationalError('private database path')
        monkeypatch.setattr(today,'get_daily_pending_items',fail)
        response=api.get('/api/today/pending-items')
        assert response.status_code==500 and response.json()=={'detail':'today_pending_items_failed'}


def test_multiple_plan_timezones_each_use_their_local_day(tmp_path):
    config=AppConfig(data_root=tmp_path)
    with TestClient(create_app(config)) as api:
        plan(api,('2026-10-06',),name='Shanghai',tz='Asia/Shanghai')
        plan(api,('2026-10-05',),name='Los Angeles',tz='America/Los_Angeles')
        with connect(config.database_path) as c:
            result=get_daily_pending_items(c,project_id=config.project_id,now=datetime(2026,10,5,18,tzinfo=timezone.utc))
            assert result['total']==2
            assert all(i['title'].startswith('今天安排') for i in result['pending_items'])


def test_mistakes_aggregate_real_statuses_and_fixed_no_longer_pending(tmp_path):
    config=AppConfig(data_root=tmp_path)
    with TestClient(create_app(config)) as api:
        exercise_set=api.post('/api/study/exercise-sets',json={'title':'Review'}).json()['id']
        exercise=api.post(f'/api/study/exercise-sets/{exercise_set}/exercises',json={'prompt':'Synthetic question','exercise_type':'multiple_choice','options':['A','B'],'answer_key':0,'explanation':''}).json()['id']
        assert api.post(f'/api/study/exercises/{exercise}/confirm').status_code==200
        attempt=api.post(f'/api/study/exercises/{exercise}/attempts',json={'answer':1})
        assert attempt.status_code==201
        with connect(config.database_path) as c:
            from app.repository import mark_mistake_from_attempt
            mark_mistake_from_attempt(c,project_id=config.project_id,attempt_id=attempt.json()['id'])
        result=pending(api)
        assert result['total']==1 and result['pending_items'][0]['evidence']['mistake_count']==1
        with connect(config.database_path) as c:
            c.execute("UPDATE mistake_cases SET status='fixed' WHERE project_id=?",(config.project_id,))
            c.commit()
        assert pending(api)['total']==0


def test_predecessor_blocks_inline_action_and_p0_precedes_quality(tmp_path):
    config=AppConfig(data_root=tmp_path)
    with TestClient(create_app(config)) as api:
        key,items=plan(api,(DAY,DAY))
        with connect(config.database_path) as c:
            c.execute("INSERT INTO study_plan_dependencies VALUES ('s1-dependency',?,?,?,?,?)",(key,config.project_id,items[0],items[1],'now'))
            c.commit()
        api.post('/api/materials',files={'file':('empty.txt',b'','text/plain')})
        result=pending(api)
        assert [i['priority'] for i in result['pending_items']]==[0,0,1]
        blocked=next(i for i in result['pending_items'] if i['evidence'].get('item_id')==items[1])
        assert blocked['evidence']['blocked_count']==1 and blocked['action_label']=='查看计划详情'


def test_tomorrow_cram_goal_is_not_mislabeled_exam(tmp_path):
    config=AppConfig(data_root=tmp_path)
    with TestClient(create_app(config)) as api:
        api.post('/api/study/goals',json={'title':'Synthetic project initialization'})
        with connect(config.database_path) as c:
            c.execute("INSERT INTO cram_goals VALUES ('s1-cram',?,?,?,'Asia/Shanghai',5,'active',NULL,NULL,'now','now',NULL,NULL)",(config.project_id,'Revision goal','2026-10-06'))
            c.commit()
        result=pending(api)
        assert result['total']==1 and result['pending_items'][0]['category']=='tomorrow_prep'
        assert '备考目标' in result['pending_items'][0]['title'] and '考试日期' in result['pending_items'][0]['description']
        assert api.get(urlsplit(result['pending_items'][0]['action_url']).path).status_code==200
