(function () {
  const request = sbApi.setPageScope('student');
  const loading = document.querySelector('#student-loading');
  const task = document.querySelector('#student-task');
  const empty = document.querySelector('#student-empty');
  const week = document.querySelector('#student-week');
  const error = document.querySelector('#student-error');
  const retry = document.querySelector('#student-retry');
  const start = document.querySelector('#student-start');
  const taskTitle = document.querySelector('#student-task-title');
  const taskTime = document.querySelector('#student-task-time');
  const taskState = document.querySelector('#student-task-state');
  const weekCopy = document.querySelector('#student-week-copy');
  const weekProgress = document.querySelector('#student-week-progress');
  const streakValue = document.querySelector('#student-streak');
  const weekDaysValue = document.querySelector('#student-week-days');
  const weekRateValue = document.querySelector('#student-week-rate');
  let generation = 0;
  let currentHref = '';

  function text(value) { return typeof value === 'string' ? value : ''; }
  function localDate(timezone) {
    return new Intl.DateTimeFormat('en-CA', { timeZone: timezone || 'UTC', year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date());
  }
  function showError(reason) {
    loading.hidden = true;
    task.hidden = true;
    empty.hidden = true;
    week.hidden = true;
    retry.hidden = false;
    sbUi.errorAction(error, reason, { retry: load });
  }
  function reset() {
    loading.hidden = false;
    task.hidden = true;
    empty.hidden = true;
    week.hidden = true;
    error.hidden = true;
    retry.hidden = true;
    currentHref = '';
  }
  function renderWeek(days) {
    const rows = Array.isArray(days) ? days : [];
    const learned = rows.filter(day => Number(day.completed_count || 0) > 0).length;
    const ordered = rows.slice().sort((a, b) => String(a.local_date || '').localeCompare(String(b.local_date || '')));
    const streakRows = ordered.slice();
    if (streakRows.length && Number(streakRows[streakRows.length - 1].completed_count || 0) <= 0) streakRows.pop();
    let streak = 0;
    for (let index = streakRows.length - 1; index >= 0 && Number(streakRows[index].completed_count || 0) > 0; index -= 1) streak += 1;
    const rate = Math.round(Math.min(learned / 7 * 100, 100));
    streakValue.textContent = String(streak);
    weekDaysValue.textContent = `${learned}/7`;
    weekRateValue.textContent = `${rate}%`;
    weekCopy.textContent = `本周已学 ${learned}/7 天 · 完成率 ${rate}%`;
    weekProgress.style.width = `${Math.min(learned / 7 * 100, 100)}%`;
    weekProgress.parentElement.setAttribute('aria-label', `本周已学 ${learned}/7 天，完成率 ${rate}%`);
    week.hidden = false;
  }
  async function load() {
    const run = ++generation;
    reset();
    try {
      const plans = await sbApi.json('/api/study/plans', { signal: request.signal });
      if (run !== generation) return;
      const active = (Array.isArray(plans) ? plans : []).find(item => item.status === 'active');
      if (!active) {
        loading.hidden = true;
        empty.hidden = false;
        return;
      }
      const detail = await sbApi.json(`/api/study/plans/${encodeURIComponent(active.id)}`, { signal: request.signal });
      const rhythm = await sbApi.json(`/api/study/plans/${encodeURIComponent(active.id)}/rhythm`, { signal: request.signal });
      const timezone = rhythm.settings && rhythm.settings.timezone;
      const today = localDate(timezone);
      const [allocations, trend] = await Promise.all([
        sbApi.json(`/api/study/plans/${encodeURIComponent(active.id)}/rhythm/allocations`, { signal: request.signal }),
        sbApi.json(`/api/study/plans/${encodeURIComponent(active.id)}/rhythm/weekly-trend`, { signal: request.signal })
      ]);
      if (run !== generation) return;
      const byItem = new Map((Array.isArray(allocations) ? allocations : []).filter(item => item.local_date === today).map(item => [item.item_id, item]));
      const items = (Array.isArray(detail.items) ? detail.items : []).filter(item => item.status !== 'archived' && byItem.has(item.id));
      renderWeek(trend && trend.days);
      loading.hidden = true;
      if (!items.length) { empty.hidden = false; return; }
      const item = items.find(entry => entry.status !== 'completed') || items[0];
      const allocation = byItem.get(item.id);
      taskTitle.textContent = text(item.title || item.item_title) || '今天的学习';
      taskTime.textContent = `预计 ${Number(allocation.planned_minutes) || 0} 分钟`;
      const done = item.status === 'completed';
      taskState.textContent = done ? '今天的任务完成啦！' : item.status === 'in_progress' ? '已经开始，接着完成吧' : '';
      currentHref = `/app/plan-detail.html?plan_id=${encodeURIComponent(active.id)}&item_id=${encodeURIComponent(item.id)}&local_date=${encodeURIComponent(today)}&return_to=student`;
      start.textContent = done ? '查看进度' : '开始';
      start.onclick = () => { if (currentHref) window.location.href = currentHref; };
      task.hidden = false;
    } catch (reason) {
      if (run === generation) showError(reason);
    }
  }
  const now = new Date();
  const hour = now.getHours();
  document.querySelector('#student-greeting').textContent = hour >= 5 && hour < 12 ? '早上好！' : hour >= 12 && hour < 18 ? '下午好！' : '晚上好！';
  document.querySelector('#student-date').textContent = new Intl.DateTimeFormat('zh-CN', { month: 'long', day: 'numeric' }).format(now);
  retry.addEventListener('click', () => sbSubmit.once('student-reload', load));
  load();
}());
