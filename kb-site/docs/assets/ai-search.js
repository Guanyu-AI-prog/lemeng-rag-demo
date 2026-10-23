/**
 * 乐萌知识库 — AI 助手悬浮入口
 * 吉祥物按钮（右下角）→ 点击弹出 AI 问答面板
 * 接口地址由本脚本所在路径推导（支持根路径与 /kb/ 子路径部署）：<站点根>/ask
 */
(function () {
  'use strict';

  var ASSETS_BASE = (function () {
    // 兼容 MkDocs 子路径部署：从当前页面 URL 推导 site_url
    var el = document.querySelector('script[src*="ai-search"]');
    if (el && el.src) return el.src.replace(/ai-search\.js.*$/, '');
    return '/assets/';
  })();
  // assets/ 在站点根下，../ask 即 <站点根>/ask
  var API = ASSETS_BASE + '../ask';

  var fab = null;
  var panel = null;
  var isOpen = false;
  var busy = false;
  var HISTORY_KEY = 'lemeng-ai-history';
  var HISTORY_TTL = 2 * 60 * 60 * 1000; // 2 小时未活动自动过期
  var MAX_HISTORY = 20;                 // 本地最多保留 20 条(约 10 轮)

  // 回答模式:auto=自动分流,faq=知识问答,talk=销售话术,script=新媒体脚本
  var MODE_KEY = 'lemeng-ai-mode';
  var MODES = [
    { key: 'auto', label: '智能' },
    { key: 'faq', label: '知识问答' },
    { key: 'talk', label: '销售话术' },
    { key: 'script', label: '新媒体脚本' }
  ];
  function loadMode() {
    try {
      var m = localStorage.getItem(MODE_KEY);
      return MODES.some(function (x) { return x.key === m; }) ? m : 'auto';
    } catch (e) { return 'auto'; }
  }
  var currentMode = loadMode();

  function generateSessionId() {
    var id = 'sess-' + Date.now() + '-' + Math.random().toString(36).slice(2, 10);
    try { localStorage.setItem('lemeng-ai-session', id); } catch (e) {}
    return id;
  }

  function saveHistory() {
    try {
      localStorage.setItem(HISTORY_KEY, JSON.stringify({
        savedAt: Date.now(),
        sessionId: sessionId,
        history: history.slice(-MAX_HISTORY)
      }));
    } catch (e) { /* 存储不可用/超限,忽略 */ }
  }

  function loadHistory() {
    try {
      var raw = localStorage.getItem(HISTORY_KEY);
      if (!raw) return [];
      var data = JSON.parse(raw);
      if (!data || !Array.isArray(data.history)) return [];
      if (Date.now() - (data.savedAt || 0) > HISTORY_TTL) {
        localStorage.removeItem(HISTORY_KEY);
        return [];
      }
      return data.history.slice(-MAX_HISTORY);
    } catch (e) { return []; }
  }

  var sessionId = (function () {
    try { return localStorage.getItem('lemeng-ai-session') || generateSessionId(); }
    catch (e) { return 'sess-' + Date.now(); }
  })();
  var history = loadHistory(); // {role, content, sources?} 跨页面持久化

  function clearConversation() {
    history = [];
    sessionId = generateSessionId();
    try { localStorage.removeItem(HISTORY_KEY); } catch (e) {}
    renderBody(false);
    var q = document.getElementById('lemeng-panel-q');
    if (q) q.focus();
  }

  function escapeHtml(text) {
    var div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }

  function renderMd(text) {
    return text
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
      .replace(/\*(.+?)\*/g, '<em>$1</em>')
      .replace(/^### (.+)$/gm, '<h4>$1</h4>')
      .replace(/^## (.+)$/gm, '<h3>$1</h3>')
      .replace(/^- (.+)$/gm, '<li>$1</li>')
      .replace(/\n\n/g, '<br><br>')
      .replace(/\n/g, '<br>')
      .replace(/\[来源: (.+?)\]/g,
        '<em class="lemeng-src">[来源: $1]</em>');
  }

  /* ---------- 构建悬浮按钮 ---------- */
  function buildFab() {
    fab = document.createElement('button');
    fab.id = 'lemeng-ai-fab';
    fab.className = 'lemeng-enter';
    fab.type = 'button';
    fab.setAttribute('aria-label', '打开 AI 知识库问答');
    fab.setAttribute('aria-expanded', 'false');

    var img = document.createElement('img');
    img.src = ASSETS_BASE + 'mascot-head.png';
    img.alt = '';
    img.setAttribute('aria-hidden', 'true');
    fab.appendChild(img);

    var tip = document.createElement('span');
    tip.className = 'lemeng-fab-tip';
    tip.textContent = '问小乐萌 · AI 知识库问答';
    fab.appendChild(tip);

    fab.addEventListener('click', togglePanel);
    document.body.appendChild(fab);

    // 入场动画类清理
    setTimeout(function () { fab.classList.remove('lemeng-enter'); }, 700);
  }

  /* ---------- 构建问答面板 ---------- */
  function buildPanel() {
    panel = document.createElement('div');
    panel.id = 'lemeng-ai-panel';
    panel.setAttribute('role', 'dialog');
    panel.setAttribute('aria-label', 'AI 知识库问答');
    panel.innerHTML =
      '<div class="lemeng-panel-head">' +
      '  <img src="' + ASSETS_BASE + 'mascot-head.png" alt="" aria-hidden="true">' +
      '  <div class="lemeng-panel-title">' +
      '    <strong>小乐萌 · AI 问答</strong>' +
      '    <span>基于全站知识库检索</span>' +
      '  </div>' +
      '  <button type="button" class="lemeng-panel-clear" aria-label="清空对话">🗑</button>' +
      '  <button type="button" class="lemeng-panel-close" aria-label="关闭">✕</button>' +
      '</div>' +
      '<div class="lemeng-panel-body" id="lemeng-panel-body">' +
      '  <div class="lemeng-welcome">' +
      '    <p>你好！我是小乐萌 🤖</p>' +
      '    <p>问我任何知识库相关问题，例如：</p>' +
      '    <ul>' +
      '      <li>乐萌的教育理念是什么？</li>' +
      '      <li>新老师怎么培训？</li>' +
      '      <li>C++ 课程有哪些？</li>' +
      '    </ul>' +
      '  </div>' +
      '</div>' +
      '<div class="lemeng-mode-bar" id="lemeng-mode-bar" role="group" aria-label="回答模式">' +
        MODES.map(function (m) {
          return '<button type="button" data-mode="' + m.key + '"' +
            (m.key === currentMode ? ' class="active"' : '') + '>' + m.label + '</button>';
        }).join('') +
      '</div>' +
      '<form class="lemeng-panel-input" id="lemeng-panel-form">' +
      '  <input type="text" id="lemeng-panel-q" placeholder="输入问题，回车提问…" ' +
      '         autocomplete="off" aria-label="问题输入框">' +
      '  <button type="submit" aria-label="发送">发送</button>' +
      '</form>';
    document.body.appendChild(panel);

    panel.querySelector('.lemeng-panel-close').addEventListener('click', closePanel);
    var clearBtn = panel.querySelector('.lemeng-panel-clear');
    if (clearBtn) clearBtn.addEventListener('click', clearConversation);
    var modeBar = panel.querySelector('#lemeng-mode-bar');
    if (modeBar) modeBar.addEventListener('click', function (e) {
      var btn = e.target.closest('button[data-mode]');
      if (!btn) return;
      currentMode = btn.getAttribute('data-mode');
      try { localStorage.setItem(MODE_KEY, currentMode); } catch (er) {}
      modeBar.querySelectorAll('button').forEach(function (b) {
        b.classList.toggle('active', b.getAttribute('data-mode') === currentMode);
      });
    });
    document.getElementById('lemeng-panel-form').addEventListener('submit', onAsk);
    renderBody(false); // 恢复本地持久化的历史对话
  }

  /* ---------- 面板开关 ---------- */
  function togglePanel() {
    if (isOpen) { closePanel(); } else { openPanel(); }
  }

  function openPanel() {
    if (!panel) buildPanel();
    panel.classList.add('open');
    isOpen = true;
    fab.classList.add('ai-active');
    fab.setAttribute('aria-expanded', 'true');
    setTimeout(function () {
      var q = document.getElementById('lemeng-panel-q');
      if (q) q.focus();
    }, 150);
  }

  function closePanel() {
    if (!panel) return;
    panel.classList.remove('open');
    isOpen = false;
    fab.classList.remove('ai-active');
    fab.setAttribute('aria-expanded', 'false');
  }

  /* ---------- 提问 ---------- */
  function onAsk(e) {
    e.preventDefault();
    if (busy) return;
    var input = document.getElementById('lemeng-panel-q');
    var question = (input.value || '').trim();
    if (!question) return;
    input.value = '';
    ask(question);
  }

  function renderMessage(msg) {
    if (msg.role === 'user') {
      return '<div class="lemeng-msg lemeng-msg-user"><strong>Q:</strong> ' +
        escapeHtml(msg.content) + '</div>';
    }
    var html = '<div class="lemeng-msg lemeng-msg-ai">' +
      '<img src="' + ASSETS_BASE + 'mascot-head.png" alt="" aria-hidden="true">' +
      '<div class="lemeng-msg-content">' + renderMd(msg.content || '未找到相关答案');
    if (msg.sources && msg.sources.length) {
      html += '<div class="lemeng-sources">参考来源：' +
        msg.sources.map(function (s) {
          return '<a href="' + s.url + '">' + escapeHtml(s.title) + '</a>';
        }).join('、') + '</div>';
    }
    html += '</div></div>';
    return html;
  }

  function renderBody(loading) {
    var body = document.getElementById('lemeng-panel-body');
    if (!body) return;
    var html = '';
    if (history.length === 0) {
      html =
        '<div class="lemeng-welcome">' +
        '  <p>你好！我是小乐萌 🤖</p>' +
        '  <p>问我任何知识库相关问题，例如：</p>' +
        '  <ul>' +
        '    <li>乐萌的教育理念是什么？</li>' +
        '    <li>新老师怎么培训？</li>' +
        '    <li>C++ 课程有哪些？</li>' +
        '  </ul>' +
        '</div>';
    } else {
      html = history.map(renderMessage).join('');
    }
    if (loading) {
      html +=
        '<div class="lemeng-msg lemeng-msg-ai lemeng-loading">' +
        '<img src="' + ASSETS_BASE + 'mascot-head.png" alt="" aria-hidden="true">' +
        '<span>正在搜索知识库…</span></div>';
    }
    body.innerHTML = html;
    body.scrollTop = body.scrollHeight;
  }

  function ask(question) {
    busy = true;
    fab.classList.add('lemeng-thinking');
    history.push({ role: 'user', content: question });
    saveHistory();
    renderBody(true);

    fetch(API, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        question: question,
        mode: currentMode,
        session_id: sessionId,
        // 只发 role/content(过滤 sources 等展示字段),不含当前问题,最多 12 条
        history: history.slice(0, -1).slice(-12).map(function (m) {
          return { role: m.role, content: m.content };
        })
      })
    })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        busy = false;
        fab.classList.remove('lemeng-thinking');
        var answer = data && data.answer;
        var sources = (data && data.sources) || [];
        history.push({ role: 'assistant', content: answer || '未找到相关答案', sources: sources });
        saveHistory();
        renderBody(false);
      })
      .catch(function () {
        busy = false;
        fab.classList.remove('lemeng-thinking');
        history.push({ role: 'assistant', content: '服务未启动：请先运行 `python3 server.py`' });
        saveHistory();
        renderBody(false);
      });
  }

  /* ---------- 启动 ---------- */
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', buildFab);
  } else {
    buildFab();
  }

  /* Esc 关闭面板 */
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && isOpen) closePanel();
  });
})();
