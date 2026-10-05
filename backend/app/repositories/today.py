"""Read-only S1 closure suggestions from existing local study facts."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from urllib.parse import urlencode
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .knowledge_modules import get_module


def _url(page, **params):
    return '/app/' + page + (('?' + urlencode(params)) if params else '')


def _item(key, category, priority, title, description, action, url, evidence, order=''):
    return dict(id=key, category=category, priority=priority, title=title,
                description=description, action_label=action, action_url=url,
                evidence=evidence, _order=order)


def _allocations(conn, project_id):
    return [dict(r) for r in conn.execute(
        "SELECT a.id AS allocation_id,a.local_date,a.planned_minutes,i.id AS item_id,"
        "i.title,i.status,p.id AS plan_id,p.title AS plan_title,s.timezone,"
        "(SELECT COUNT(*) FROM study_plan_dependencies d JOIN study_plan_items prior ON prior.id=d.predecessor_item_id "
        "WHERE d.successor_item_id=i.id AND d.project_id=? AND prior.status NOT IN ('completed','skipped')) AS blocked_count "
        "FROM rhythm_allocations a JOIN study_plan_items i ON i.id=a.item_id AND i.project_id=a.project_id "
        "JOIN study_plans p ON p.id=a.plan_id AND p.project_id=a.project_id "
        "JOIN rhythm_settings s ON s.plan_id=p.id AND s.project_id=p.project_id "
        "WHERE a.project_id=? AND p.status='active' AND i.status IN ('pending','in_progress') "
        "ORDER BY a.local_date,a.id", (project_id, project_id))]


def get_tomorrow_prep_items(conn, project_id, today, allocations, now=None, explicit_date=False):
    tomorrow = (today + timedelta(days=1)).isoformat()
    due_ids = {r['item_id'] for r in allocations if r['local_date'] <= r['_today']}
    rows = []
    for r in allocations:
        tomorrow = (date.fromisoformat(r['_today']) + timedelta(days=1)).isoformat()
        if r['local_date'] != tomorrow or r['item_id'] in due_ids:
            continue
        rows.append(_item('prep-' + r['item_id'], 'tomorrow_prep', 0,
                          '明日准备：' + r['title'], '已安排明天学习，提前查看所需资料。',
                          '查看学习安排', _url('plan-detail.html', plan_id=r['plan_id'], item_id=r['item_id'], local_date=tomorrow, return_to='today'),
                          dict(plan_id=r['plan_id'], item_id=r['item_id'], allocation_id=r['allocation_id'],
                               local_date=tomorrow, planned_minutes=r['planned_minutes'], timezone=r['timezone']), tomorrow + '-1'))
    for r in conn.execute("SELECT id,title,target_date,timezone FROM cram_goals WHERE project_id=? AND status='active' ORDER BY id", (project_id,)):
        cram_today = today if explicit_date or now is None else now.astimezone(ZoneInfo(r['timezone'])).date()
        if r['target_date'] != (cram_today + timedelta(days=1)).isoformat():
            continue
        rows.append(_item('prep-cram-' + r['id'], 'tomorrow_prep', 0, '明日备考目标：' + r['title'],
                          '备考目标日期在明天；这是已设置的目标，不代表考试日期。', '查看备考目标',
                          _url('practice.html') + '#cram-goals',
                          dict(cram_goal_id=r['id'], target_date=r['target_date'], timezone=r['timezone']), r['target_date'] + '-0'))
    return rows


def get_due_task_items(conn, project_id, today, allocations):
    latest = {}
    for r in allocations:
        if r['local_date'] <= r['_today']:
            latest[r['item_id']] = r
    rows = []
    for r in latest.values():
        overdue = r['local_date'] < r['_today']
        evidence = dict(plan_id=r['plan_id'], item_id=r['item_id'], allocation_id=r['allocation_id'],
                        local_date=r['local_date'], planned_minutes=r['planned_minutes'], timezone=r['timezone'],
                        status=r['status'], blocked_count=r['blocked_count'])
        rows.append(_item('due-' + r['item_id'], 'due_task', 0,
                          ('逾期未闭合：' if overdue else '今天安排：') + r['title'],
                          ('需先完成前置学习项。' if r['blocked_count'] else '计划 ' + str(r['planned_minutes']) + ' 分钟') + ' · ' + r['local_date'],
                          '查看计划详情' if r['blocked_count'] else '记录完成' if r['status'] == 'in_progress' else '开始学习',
                          _url('plan-detail.html', plan_id=r['plan_id'], item_id=r['item_id'], local_date=r['local_date'], return_to='today'),
                          evidence, r['local_date'] + '-0'))
    return rows


def get_quality_check_items(conn, project_id):
    rows = []
    for r in conn.execute(
        "SELECT m.id,m.original_name,m.created_at,e.status FROM materials m "
        "JOIN extractions e ON e.id=(SELECT x.id FROM extractions x WHERE x.material_id=m.id ORDER BY x.created_at DESC,x.id DESC LIMIT 1) "
        "WHERE m.project_id=? AND m.deleted_at IS NULL AND e.status IN ('failed','rejected','empty') ORDER BY m.created_at,m.id", (project_id,)):
        label = {'failed': '解析待处理', 'rejected': '格式待处理', 'empty': '正文待核对'}[r['status']]
        rows.append(_item('quality-' + r['id'], 'quality_check', 1, label + '：' + r['original_name'],
                          '查看解析提示，修复或转换文件后重新导入。', '查看材料', _url('material-detail.html', material=r['id']),
                          dict(material_id=r['id'], status=r['status']), r['created_at']))
    for r in conn.execute(
        "SELECT s.material_id,COUNT(*) AS draft_count,MIN(k.created_at) AS created_at,m.original_name "
        "FROM s2_knowledge_modules s JOIN knowledge_modules k ON k.id=s.id JOIN materials m ON m.id=s.material_id "
        "WHERE k.project_id=? AND m.project_id=? AND m.deleted_at IS NULL AND k.status='active' "
        "AND s.deleted_at IS NULL AND s.lifecycle='draft' GROUP BY s.material_id ORDER BY created_at,s.material_id", (project_id, project_id)):
        rows.append(_item('quality-modules-' + r['material_id'], 'quality_check', 1,
                          '知识草稿待确认：' + r['original_name'], str(r['draft_count']) + ' 个 AI 草稿需要你核对来源并确认或拒绝。',
                          '核对知识草稿', _url('material-detail.html', material=r['material_id'], tab='knowledge'),
                          dict(material_id=r['material_id'], draft_count=r['draft_count']), r['created_at']))
    return rows


def get_mistake_review_items(conn, project_id):
    row = conn.execute("SELECT COUNT(*) AS count,MIN(created_at) AS created_at FROM mistake_cases WHERE project_id=? AND status IN ('open','in_review','reopened')", (project_id,)).fetchone()
    if not row['count']:
        return []
    return [_item('mistake-review', 'mistake_review', 1, '错题复习', str(row['count']) + ' 道错题尚未闭合。先复盘，再决定再次练习或记录改正。',
                  '开始复盘', _url('review.html'), dict(mistake_count=row['count'], statuses=['open','in_review','reopened']), row['created_at'])]


def get_next_step_items(conn, project_id, today, now=None):
    for r in conn.execute("SELECT k.id FROM knowledge_modules k JOIN s2_knowledge_modules s ON s.id=k.id WHERE k.project_id=? AND k.status='active' AND s.lifecycle='confirmed' AND s.deleted_at IS NULL ORDER BY s.importance,k.created_at,k.id", (project_id,)):
        module = get_module(conn, project_id=project_id, module_id=r['id'])
        if module['source_status'] != 'valid' or module['learn_status'] == 'mastered' or module['mastery_level'] >= .5:
            continue
        return [_item('next-module-' + module['id'], 'next_step', 2,
                      ('建议学习：' if module['learn_status'] == 'not_started' else '继续练习：') + module['title'],
                      '来自已确认的知识模块 · 当前掌握度 ' + str(round(module['mastery_level'] * 100)) + '%',
                      '按模块练习', _url('exercises.html', knowledge_module=module['id']),
                      dict(module_id=module['id'], importance=module['importance'], mastery_level=module['mastery_level']))]
    session = conn.execute("SELECT id,title,status FROM practice_sessions WHERE project_id=? AND status IN ('draft','active') AND (deadline_at IS NULL OR julianday(deadline_at)>julianday(?)) ORDER BY updated_at DESC,id LIMIT 1", (project_id, (now or datetime.now(timezone.utc)).isoformat())).fetchone()
    if session:
        return [_item('next-session-' + session['id'], 'next_step', 2, '继续练习：' + session['title'], '已有练习会话尚未完成。',
                      '进入练习', _url('practice-session.html', session_id=session['id']), dict(session_id=session['id'], status=session['status']))]
    return []


def get_daily_pending_items(conn, *, project_id, target_date=None, timezone_name=None, now=None):
    now = now or datetime.now(timezone.utc)
    allocations = _allocations(conn, project_id)
    if timezone_name is None:
        setting = conn.execute("SELECT s.timezone FROM rhythm_settings s JOIN study_plans p ON p.id=s.plan_id AND p.project_id=s.project_id WHERE p.project_id=? AND p.status='active' ORDER BY p.updated_at DESC,p.id LIMIT 1", (project_id,)).fetchone()
        timezone_name = setting['timezone'] if setting else 'Asia/Shanghai'
    try:
        zone = ZoneInfo(timezone_name)
        today = date.fromisoformat(target_date) if target_date is not None else now.astimezone(zone).date()
        if target_date is not None and today.isoformat() != target_date:
            raise ValueError('invalid date')
        for row in allocations:
            row['_today'] = today.isoformat() if target_date is not None else now.astimezone(ZoneInfo(row['timezone'])).date().isoformat()
    except (ValueError, ZoneInfoNotFoundError, TypeError):
        raise ValueError('today_invalid_date_or_timezone') from None
    candidates = get_due_task_items(conn, project_id, today, allocations) + get_tomorrow_prep_items(conn, project_id, today, allocations, now, target_date is not None)
    candidates += get_quality_check_items(conn, project_id) + get_mistake_review_items(conn, project_id)
    candidates.sort(key=lambda r: (r['priority'], r['_order'], r['id']))
    if len(candidates) < 3:
        candidates += get_next_step_items(conn, project_id, today, now)
    shown = candidates[:5]
    generated_at = now.isoformat()
    for item in shown:
        item.pop('_order')
        item['created_at'] = generated_at
    return dict(date=today.isoformat(), timezone=timezone_name, pending_items=shown, total=len(shown),
                candidate_total=len(candidates), remaining_count=max(0, len(candidates) - 5),
                remaining_p0_count=sum(r['priority'] == 0 for r in candidates[5:]), generated_at=generated_at,
                unavailable_sources=['course_timetable', 'confirmed_exam_dates'])
