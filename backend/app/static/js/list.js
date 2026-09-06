/**
 * StudyBuddy 列表渲染共享模块
 * 提供通用的列表渲染、空态、分页功能
 */

const sbList = {
  /**
   * 渲染列表
   * @param {HTMLElement} container - 列表容器（通常是 ul）
   * @param {Array} items - 数据项数组
   * @param {Function} renderItemFn - 渲染单个项的函数，返回 HTMLElement
   * @param {string|Object} emptyConfig - 空态配置（字符串或 {message, className}）
   * @returns {void}
   */
  render(container, items, renderItemFn, emptyConfig) {
    if (!container) return;
    
    container.replaceChildren();
    
    if (!items || items.length === 0) {
      const emptyMsg = typeof emptyConfig === 'string' ? emptyConfig : (emptyConfig?.message || '暂无数据');
      const emptyClass = typeof emptyConfig === 'object' ? emptyConfig.className : 'empty';
      const li = document.createElement('li');
      li.className = emptyClass;
      li.textContent = emptyMsg;
      container.append(li);
      return;
    }
    
    items.forEach(item => {
      const el = renderItemFn(item);
      if (el) container.append(el);
    });
  },

  /**
   * 渲染空态（用于非列表容器的空态）
   * @param {HTMLElement} container - 容器元素
   * @param {string} message - 空态消息
   * @param {Object} exitButton - 可选的出口按钮配置 {text, href, onclick}
   * @returns {void}
   */
  renderEmpty(container, message, exitButton) {
    if (!container) return;
    
    container.replaceChildren();
    
    const emptyDiv = document.createElement('div');
    emptyDiv.className = 'empty-state';
    
    const text = document.createElement('p');
    text.textContent = message || '暂无数据';
    emptyDiv.append(text);
    
    if (exitButton) {
      if (exitButton.href) {
        const link = document.createElement('a');
        link.href = exitButton.href;
        link.className = 'btn';
        link.textContent = exitButton.text || '前往';
        emptyDiv.append(link);
      } else if (exitButton.onclick) {
        const btn = document.createElement('button');
        btn.className = 'btn';
        btn.textContent = exitButton.text || '操作';
        btn.onclick = exitButton.onclick;
        emptyDiv.append(btn);
      }
    }
    
    container.append(emptyDiv);
  },

  /**
   * 渲染分页控件
   * @param {HTMLElement} container - 分页容器
   * @param {Object} config - 分页配置
   * @param {number} config.offset - 当前偏移量
   * @param {number} config.limit - 每页数量
   * @param {boolean} config.hasMore - 是否有下一页
   * @param {number} [config.total] - 总数（可选）
   * @param {Function} config.onPrev - 上一页回调
   * @param {Function} config.onNext - 下一页回调
   * @returns {void}
   */
  renderPagination(container, config) {
    if (!container) return;
    
    container.replaceChildren();
    
    const currentPage = Math.floor(config.offset / config.limit);
    const hasPrev = config.offset > 0;
    const hasNext = config.hasMore;
    
    if (!hasPrev && !hasNext) {
      container.hidden = true;
      return;
    }
    
    container.hidden = false;
    
    const prev = document.createElement('button');
    prev.className = 'btn';
    prev.textContent = '上一页';
    prev.disabled = !hasPrev;
    if (config.onPrev) prev.onclick = config.onPrev;
    container.append(prev);
    
    const info = document.createElement('span');
    info.className = 'muted';
    info.textContent = `第 ${currentPage + 1} 页`;
    container.append(info);
    
    const next = document.createElement('button');
    next.className = 'btn';
    next.textContent = '下一页';
    next.disabled = !hasNext;
    if (config.onNext) next.onclick = config.onNext;
    container.append(next);
  },

  /**
   * 创建列表项容器
   * @param {string} tag - HTML 标签名（默认 'li'）
   * @param {Array<string>} classes - CSS 类名数组
   * @returns {HTMLElement}
   */
  createItem(tag = 'li', classes = []) {
    const el = document.createElement(tag);
    if (classes.length > 0) {
      el.className = classes.join(' ');
    }
    return el;
  },

  /**
   * 安全的文本内容提取（防止 undefined/null）
   * @param {*} value - 任意值
   * @returns {string}
   */
  text(value) {
    if (value === null || value === undefined) return '';
    return String(value);
  }
};
