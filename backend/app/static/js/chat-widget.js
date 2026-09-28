(function () {
  function mount() {
    if (document.querySelector('.chat-widget')) return;
    const root = document.createElement('aside');
    root.className = 'chat-widget';
    root.setAttribute('aria-label', 'Buddy 学习助手');
    root.innerHTML = '<button class="chat-toggle" type="button" aria-expanded="false" aria-controls="chat-panel" title="打开 Buddy 学习助手">问</button><section id="chat-panel" class="chat-panel" hidden aria-labelledby="chat-title"><header class="chat-head"><strong id="chat-title">Buddy 学习助手</strong><button class="chat-close" type="button" aria-label="关闭 Buddy 学习助手">×</button></header><div class="chat-messages" aria-live="polite"></div><p class="chat-hint">可以问“今天学什么？”或“这道题怎么做？”</p><form class="chat-form"><input class="chat-input" required maxlength="500" placeholder="问我今天怎么学…" aria-label="输入问题"><button class="chat-send" type="submit">发送</button></form></section>';
    document.body.append(root);
    const toggle = root.querySelector('.chat-toggle');
    const panel = root.querySelector('.chat-panel');
    const close = root.querySelector('.chat-close');
    const messages = root.querySelector('.chat-messages');
    const input = root.querySelector('.chat-input');
    const send = root.querySelector('.chat-send');
    const form = root.querySelector('.chat-form');
    const addMessage = (text, role) => { const item = document.createElement('p'); item.className = `chat-message ${role}`; item.textContent = text; messages.append(item); messages.scrollTop = messages.scrollHeight; };
    const setOpen = open => { panel.hidden = !open; toggle.setAttribute('aria-expanded', String(open)); if (open) input.focus(); };
    addMessage('你好！今天想学什么？', 'bot');
    toggle.addEventListener('click', () => setOpen(panel.hidden));
    close.addEventListener('click', () => setOpen(false));
    form.addEventListener('submit', async event => {
      event.preventDefault();
      const question = input.value.trim();
      if (!question || send.disabled) return;
      addMessage(question, 'user'); input.value = ''; send.disabled = true; send.textContent = '…';
      try {
        const materialsResponse = await fetch('/api/materials?limit=20', { headers: { Accept: 'application/json' } });
        if (!materialsResponse.ok) throw new Error('materials_unavailable');
        const payload = await materialsResponse.json();
        const rows = Array.isArray(payload) ? payload : payload.items || [];
        const materialIds = rows.filter(item => ['valid', 'ready', 'confirmed'].includes(item.source_status || item.status)).map(item => item.id || item.material_id).filter(Boolean).slice(0, 5);
        if (!materialIds.length) { addMessage('先导入并准备好一份教材，我就能基于它回答。打开问答页继续。', 'bot'); return; }
        const response = await fetch('/api/qa/ask', { method: 'POST', headers: { 'Content-Type': 'application/json', 'Idempotency-Key': `chat-${Date.now()}-${Math.random().toString(36).slice(2)}` }, body: JSON.stringify({ question, material_ids: materialIds, retrieval_mode: 'hybrid', allow_retrieval_fallback: true, top_k: 5 }) });
        const result = await response.json();
        if (!response.ok) throw new Error(result.detail || 'qa_unavailable');
        addMessage(result.answer_text || result.answer || '我暂时没有生成答案，请稍后重试。', 'bot');
      } catch (_) { addMessage('这次没有完成回答。请稍后重试，或打开问答页继续。', 'bot'); }
      finally { send.disabled = false; send.textContent = '发送'; }
    });
  }
  window.sbChat = Object.freeze({ mount });
}());
