(function () {
  const request = sbApi.setPageScope('parent');
  const home = document.querySelector('#parent-home');
  const wizard = document.querySelector('#parent-wizard');
  const success = document.querySelector('#parent-success');
  const status = document.querySelector('#parent-status');
  const materialSelect = document.querySelector('#parent-material');
  const minutes = document.querySelector('#parent-minutes');
  const reviewMaterial = document.querySelector('#parent-review-material');
  const reviewMinutes = document.querySelector('#parent-review-minutes');
  const createButton = document.querySelector('#parent-create');
  const steps = [document.querySelector('#parent-step-material'), document.querySelector('#parent-step-time'), document.querySelector('#parent-step-review')];
  const progress = [document.querySelector('#wizard-progress-1'), document.querySelector('#wizard-progress-2'), document.querySelector('#wizard-progress-3')];
  const state = { materials: [], selected: null, minutes: 20, step: 1, busy: false };

  function text(value) { return typeof value === 'string' ? value : ''; }
  function today(timezone) { return new Intl.DateTimeFormat('en-CA', { timeZone: timezone || 'UTC', year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date()); }
  function setStatus(message, kind) { status.hidden = !message; status.className = `parent-status${kind ? ` ${kind}` : ''}`; status.textContent = message || ''; }
  function showStep(number) {
    state.step = number;
    steps.forEach((step, index) => { step.hidden = index !== number - 1; });
    progress.forEach((item, index) => item.classList.toggle('current', index === number - 1));
    setStatus('');
  }
  function showWizard() { home.hidden = true; success.hidden = true; wizard.hidden = false; showStep(1); loadMaterials(); }
  function showHome() { wizard.hidden = true; success.hidden = true; home.hidden = false; setStatus(''); }
  function showError(reason) {
    sbUi.errorAction(status, reason, { retry: loadMaterials });
    status.className = 'parent-status';
    status.hidden = false;
  }
  async function loadMaterials() {
    materialSelect.replaceChildren(new Option('正在加载教材...', ''));
    materialSelect.disabled = true;
    try {
      const data = await sbApi.json('/api/materials?limit=100', { signal: request.signal });
      state.materials = (Array.isArray(data) ? data : data && Array.isArray(data.items) ? data.items : []).filter(item => !item.deleted_at);
      materialSelect.replaceChildren();
      state.materials.forEach(item => {
        const id = text(item.id || item.material_id);
        const name = text(item.original_name || item.display_name || item.name) || '未命名教材';
        if (id) materialSelect.append(new Option(name, id));
      });
      if (!state.materials.length) {
        materialSelect.append(new Option('还没有教材，请先导入', ''));
        setStatus('还没有可选教材。请先导入一份教材，再回来安排学习。');
      } else {
        materialSelect.insertBefore(new Option('请选择教材', ''), materialSelect.firstChild);
        materialSelect.value = '';
        materialSelect.disabled = false;
        setStatus('');
      }
    } catch (reason) {
      materialSelect.replaceChildren(new Option('教材加载失败', ''));
      showError(reason);
    }
  }
  function selectedMaterial() { return state.materials.find(item => String(item.id || item.material_id) === materialSelect.value) || null; }
  function syncMinuteOptions() {
    document.querySelectorAll('.minute-option').forEach(button => {
      const selected = minutes.value !== '' && Number(button.dataset.minutes) === Number(minutes.value);
      button.classList.toggle('selected', selected);
      button.setAttribute('aria-pressed', String(selected));
    });
  }
  function chooseMinutes(value) { minutes.value = String(value); syncMinuteOptions(); }
  function validateMinutes() { const value = Number(minutes.value); return Number.isInteger(value) && value >= 5 && value <= 240; }
  async function createPlan() {
    if (state.busy || !state.selected || !validateMinutes()) return;
    state.busy = true;
    createButton.disabled = true;
    createButton.textContent = '正在安排...';
    setStatus('正在为孩子安排学习，请稍等...');
    try {
      const materialName = text(state.selected.original_name || state.selected.display_name || state.selected.name) || '今天的教材';
      const duration = Number(minutes.value);
      const goal = await sbApi.json('/api/study/goals', { method: 'POST', body: JSON.stringify({ title: `${materialName}学习`, description: `根据${materialName}安排学习` }), signal: request.signal });
      const plan = await sbApi.json('/api/study/plans', { method: 'POST', body: JSON.stringify({ goal_id: goal.id, title: `${materialName}学习安排`, description: `每天学习 ${duration} 分钟` }), signal: request.signal });
      const item = await sbApi.json(`/api/study/plans/${encodeURIComponent(plan.id)}/items`, { method: 'POST', body: JSON.stringify({ title: materialName }), signal: request.signal });
      await sbApi.json(`/api/study/plans/${encodeURIComponent(plan.id)}/confirm`, { method: 'POST', signal: request.signal });
      await sbApi.json(`/api/study/plans/${encodeURIComponent(plan.id)}/activate`, { method: 'POST', signal: request.signal });
      const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC';
      const localDate = today(timezone);
      await sbApi.json(`/api/study/plans/${encodeURIComponent(plan.id)}/rhythm`, { method: 'PUT', body: JSON.stringify({ cadence: 'daily', timezone, period_start: localDate, target_minutes: duration }), signal: request.signal });
      await sbApi.json(`/api/study/plans/${encodeURIComponent(plan.id)}/rhythm/allocations`, { method: 'POST', body: JSON.stringify({ item_id: item.id, local_date: localDate, planned_minutes: duration }), signal: request.signal });
      wizard.hidden = true;
      success.hidden = false;
      document.querySelector('#parent-success-copy').textContent = `今天安排了「${materialName}」，每天 ${duration} 分钟。`;
    } catch (reason) {
      showError(reason);
    } finally {
      state.busy = false;
      createButton.disabled = false;
      createButton.textContent = '安排完成';
    }
  }

  document.querySelector('#parent-start-planning').addEventListener('click', showWizard);
  document.querySelector('#parent-cancel').addEventListener('click', showHome);
  document.querySelector('#parent-material-next').addEventListener('click', () => { state.selected = selectedMaterial(); if (!state.selected) { setStatus('请先选择一份教材。'); materialSelect.focus(); return; } showStep(2); });
  document.querySelector('#parent-time-back').addEventListener('click', () => showStep(1));
  document.querySelector('#parent-time-next').addEventListener('click', () => { if (!validateMinutes()) { setStatus('请输入 5 到 240 之间的学习分钟数。'); minutes.focus(); return; } state.minutes = Number(minutes.value); const name = text(state.selected.original_name || state.selected.display_name || state.selected.name) || '今天的教材'; reviewMaterial.textContent = name; reviewMinutes.textContent = `${state.minutes} 分钟`; showStep(3); });
  document.querySelector('#parent-review-back').addEventListener('click', () => showStep(2));
  createButton.addEventListener('click', createPlan);
  document.querySelectorAll('.minute-option').forEach(button => button.addEventListener('click', () => chooseMinutes(button.dataset.minutes)));
  minutes.addEventListener('input', syncMinuteOptions);
  minutes.addEventListener('change', syncMinuteOptions);
  syncMinuteOptions();
  document.querySelector('#parent-new-plan').addEventListener('click', showWizard);
}());
