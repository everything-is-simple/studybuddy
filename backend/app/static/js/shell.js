(() => {
  const page = location.pathname.split('/').pop() || 'index.html';
  const capabilityLabels = Object.freeze({
    available: '可用',
    configured: '已配置·未验证',
    demo: '演示模式',
    degraded: '降级可用',
    not_configured: '未配置',
    invalid_config: '配置无效',
    not_installed: '未安装',
    disabled: '已关闭',
  });
  window.sbCapability = Object.freeze({
    label(status) { return capabilityLabels[status] || '状态未知'; },
    describe(subject, state) {
      const item = state && typeof state === 'object' ? state : {};
      const provider = typeof item.provider_id === 'string' && item.provider_id ? item.provider_id : '';
      const model = typeof item.model_id === 'string' && item.model_id ? item.model_id : '';
      const identity = provider ? `（${provider}${model ? `/${model}` : ''}）` : '';
      return `${subject}：${this.label(item.status)}${identity}`;
    },
  });
  const links = [
    ['today.html', '今天'], ['plans.html', '计划'], ['materials.html', '资料'],
    ['qa.html', '问答'], ['notes.html', '笔记'], ['practice.html', '练习'],
    ['cards.html', '卡片'], ['exercises.html', '题目'], ['capture.html', '课堂采集'],
    ['classroom.html', '课堂工作区'], ['reports.html', '报告'], ['tasks.html', '任务'],
    ['settings-provider.html', '设置'], ['settings.html', '系统设置'], ['review.html', '复盘'],
  ];

  window.addEventListener('pagehide', () => sbApi.cancelAll());
  document.addEventListener('DOMContentLoaded', () => {
    const nav = document.querySelector('[data-nav]');
    if (nav) {
      const toggle = document.createElement('button');
      toggle.className = 'nav-toggle btn';
      toggle.type = 'button';
      toggle.id = 'nav-toggle';
      toggle.dataset.control = 'primary-navigation-toggle';
      toggle.title = '[导航] 展开全部页面链接';
      toggle.setAttribute('aria-expanded', 'false');
      toggle.setAttribute('aria-controls', 'primary-navigation');
      toggle.textContent = '更多';
      nav.id = 'primary-navigation';
      nav.replaceChildren();
      links.forEach(([href, label]) => {
        const link = document.createElement('a');
        link.href = '/app/' + href;
        link.textContent = label;
        link.dataset.control = 'primary-navigation-link';
        link.dataset.page = href;
        link.setAttribute('aria-label', label);
        if (href === page) link.setAttribute('aria-current', 'page');
        nav.append(link);
      });
      nav.parentElement.insertBefore(toggle, nav);
      toggle.addEventListener('click', () => {
        const open = nav.classList.toggle('is-open');
        toggle.setAttribute('aria-expanded', String(open));
        toggle.textContent = open ? '收起' : '更多';
      });
      nav.addEventListener('click', () => {
        if (window.matchMedia('(max-width: 920px)').matches) {
          nav.classList.remove('is-open');
          toggle.setAttribute('aria-expanded', 'false');
          toggle.textContent = '更多';
        }
      });
    }
    const status = document.querySelector('[data-system-status]');
    if (status) {
      sbApi.json('/api/readiness').then(data => {
        status.textContent = data.status === 'ready' ? '系统就绪' : '系统状态：' + (data.status || '未知');
      }).catch(() => { status.textContent = '系统状态暂不可用'; });
    }
  });
})();
