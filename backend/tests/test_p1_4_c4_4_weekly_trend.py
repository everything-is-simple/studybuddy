from __future__ import annotations
import sys
from datetime import datetime, timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from app.repository import connect, create_learning_goal, create_study_plan, create_study_plan_item, append_study_progress_event, study_weekly_trend


def test_weekly_trend_uses_local_timezone_and_fixed_seven_day_window(tmp_path):
    with connect(tmp_path/'studybuddy.sqlite3') as db:
        db.execute("INSERT INTO projects(id,name,created_at) VALUES (?,?,?)",('project_main','Trend','2026-03-01T00:00:00+00:00'))
        goal=create_learning_goal(db,project_id='project_main',title='Goal');plan=create_study_plan(db,project_id='project_main',goal_id=goal['id'],title='Plan');item=create_study_plan_item(db,project_id='project_main',plan_id=plan['id'],title='Item')
        db.execute("INSERT INTO rhythm_settings(id,project_id,plan_id,cadence,timezone,period_start,target_minutes,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?)",('rhythm_1','project_main',plan['id'],'daily','Asia/Shanghai','2026-03-01',30,'2026-03-01','2026-03-01'))
        db.execute("INSERT INTO study_progress_events(id,plan_id,item_id,project_id,event_type,metadata_json,created_at) VALUES (?,?,?,?,?,?,?)",('event_1',plan['id'],item['id'],'project_main','completed','{}','2026-03-01T16:30:00+00:00'))
        result=study_weekly_trend(db,project_id='project_main',plan_id=plan['id'],local_date='2026-03-08')
        assert result['timezone']=='Asia/Shanghai';assert result['local_date_start']=='2026-03-02';assert result['local_date_end']=='2026-03-08';assert len(result['days'])==7;assert result['days'][0]['completed_count']==1;assert result['totals']['completed_count']==1
