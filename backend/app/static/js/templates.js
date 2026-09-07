/**
 * Shared status templates for the formal /app pages.
 * DOM is built with textContent; callers keep ownership of page-specific content.
 */
(function (root) {
  function baseClass(container) {
    if (!container.dataset.baseClass) container.dataset.baseClass = container.className || 'notice';
    return container.dataset.baseClass;
  }

  function apply(container, kind, message) {
    if (!container) return;
    container.hidden = false;
    container.className = baseClass(container) + (kind ? ' ' + kind : '');
    if (message !== undefined) container.textContent = String(message);
  }

  const api = {
    showStatus(container, message, kind = '') { apply(container, kind, message); },
    hideStatus(container) { if (container) container.hidden = true; },
    showLoading(container, message = '正在加载…') { apply(container, 'status-loading', message); },
    showReady(container, message) { apply(container, 'status-ready', message); },
    showSuccess(container, message) { apply(container, 'status-success', message); },
    showEmpty(container, config = {}) {
      const options = typeof config === 'string' ? { message: config } : config;
      apply(container, '', options.message || '暂无数据');
      if (options.retry) {
        const button = this.createRetryButton(options.retryLabel || '重试', options.retry);
        container.append(button);
      }
    },
    showError(container, error, retryFn) {
      const message = typeof error === 'string'
        ? error
        : (root.sbApi && typeof root.sbApi.safeError === 'function'
          ? root.sbApi.safeError(error)
          : (error && error.message) || '操作失败');
      apply(container, 'warn', message);
      if (retryFn) container.append(this.createRetryButton('重试', retryFn));
    },
    setState(container, state, config = {}) {
      const options = typeof config === 'string' ? { message: config } : config;
      if (state === 'loading') return this.showLoading(container, options.message);
      if (state === 'empty') return this.showEmpty(container, options);
      if (state === 'failed' || state === 'error') return this.showError(container, options.error || options.message, options.retry);
      if (state === 'ready' || state === 'success') return this.showReady(container, options.message || '已就绪');
      return this.showStatus(container, options.message || '', options.kind || '');
    },
    createEmpty(message, buttonText, buttonHandler) {
      const container = document.createElement('div');
      container.className = 'empty-state';
      const p = document.createElement('p');
      p.className = 'muted';
      p.textContent = message;
      container.append(p);
      if (buttonText && buttonHandler) container.append(this.createRetryButton(buttonText, buttonHandler));
      return container;
    },
    createRetryButton(text = '重试', handler) {
      const button = document.createElement('button');
      button.className = 'btn';
      button.type = 'button';
      button.textContent = text;
      if (handler) button.addEventListener('click', handler);
      return button;
    },
    setBusy(elements, busy) {
      (Array.isArray(elements) ? elements : [elements]).forEach(element => { if (element) element.disabled = busy; });
    },
    setFormBusy(container, disabled, excludeId = null) {
      if (!container) return;
      container.querySelectorAll('button, input, select, textarea').forEach(node => {
        if (!excludeId || node.id !== excludeId) node.disabled = disabled;
      });
    },
    createStatusBadge(status, label) {
      const badge = document.createElement('span');
      badge.className = 'status-badge ' + (status || 'draft');
      badge.textContent = label;
      return badge;
    },
  };
  root.sbTemplates = api;
})(window);
