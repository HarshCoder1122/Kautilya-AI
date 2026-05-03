/* =======================================================================
 * KAUTILYA AI — Premium UI v3
 *
 * Features:
 *   - Streaming SSE chat (/api/jarvis/stream) with thinking + tool-call events
 *   - Claude-style collapsible thinking bubble that animates live
 *   - Max Thinking toggle (pro/coder)
 *   - Background task mode (create, poll, notify on completion)
 *   - Welcome "floating feature cards" for first-time users
 *   - Artifacts side panel (html/svg/mermaid preview)
 *   - File attachments, markdown + syntax highlighting + LaTeX
 *   - Firebase auth, recent chat history (Firestore), settings, API keys
 *   - Fully responsive — sidebar auto-collapses on mobile
 * ======================================================================= */

(() => {
'use strict';

// ------------------------------------------------------------------------
// Markdown helpers
// ------------------------------------------------------------------------
if (typeof marked !== 'undefined') {
  marked.setOptions({
    breaks: true,
    gfm: true,
    highlight: (code, lang) => {
      try {
        if (lang && hljs.getLanguage(lang)) return hljs.highlight(code, { language: lang }).value;
        return hljs.highlightAuto(code).value;
      } catch (_) { return code; }
    },
  });
}

function mdRender(text) {
  if (typeof marked === 'undefined') return escapeHtml(text);
  const html = marked.parse(text || '');
  return DOMPurify.sanitize(html, { ADD_ATTR: ['target'] });
}

function escapeHtml(s = '') {
  return s.replace(/[&<>"']/g, c => ({ '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;' }[c]));
}

function renderMath(el) {
  if (typeof renderMathInElement !== 'function') return;
  try {
    renderMathInElement(el, {
      delimiters: [
        { left: '$$', right: '$$', display: true },
        { left: '$',  right: '$',  display: false },
        { left: '\\[', right: '\\]', display: true },
        { left: '\\(', right: '\\)', display: false },
      ],
      throwOnError: false,
    });
  } catch (_) {}
}

function decorateCodeBlocks(el) {
  el.querySelectorAll('pre > code').forEach(code => {
    const pre = code.parentElement;
    if (pre.dataset.decorated) return;
    pre.dataset.decorated = '1';
    const lang = (code.className.match(/language-(\S+)/) || [, ''])[1] || 'text';
    const header = document.createElement('div');
    header.className = 'code-header';
    const runnable = ['python', 'py'].includes(lang.toLowerCase());
    header.innerHTML = `
      <span>${lang}</span>
      <span style="display:inline-flex;gap:6px;">
        ${runnable ? `<button type="button" data-act="run"><span class="material-icons-round" style="font-size:14px;">play_arrow</span>Run</button>` : ''}
        <button type="button" data-act="copy"><span class="material-icons-round" style="font-size:14px;">content_copy</span>Copy</button>
      </span>`;
    pre.insertBefore(header, code);
    header.querySelector('[data-act="copy"]').addEventListener('click', async () => {
      try { await navigator.clipboard.writeText(code.textContent); toast('Copied', 'success'); }
      catch { toast('Copy failed', 'error'); }
    });
    if (runnable) {
      header.querySelector('[data-act="run"]').addEventListener('click', () => {
        if (window.app) window.app.runPython(code.textContent, pre);
      });
    }
  });
}

// ------------------------------------------------------------------------
// Toasts
// ------------------------------------------------------------------------
function toast(msg, kind = '') {
  const host = document.getElementById('toastHost');
  if (!host) return;
  const el = document.createElement('div');
  el.className = `toast ${kind}`;
  el.textContent = msg;
  host.appendChild(el);
  setTimeout(() => { el.style.opacity = '0'; el.style.transition = 'opacity 200ms'; }, 2600);
  setTimeout(() => el.remove(), 2900);
}

// ========================================================================
// APP
// ========================================================================
class KautilyaApp {
  constructor() {
    this.sessionId   = this._sess();
    this.messages    = [];
    this.isStreaming = false;
    this.abortCtrl   = null;
    this.user        = null;
    this.isPro       = false;
    this.theme       = localStorage.getItem('kautilya_theme') || 'dark';
    this.maxThinking = localStorage.getItem('kautilya_maxthink') === '1';
    this.bgMode      = false;
    this.researchMode = false;
    this.files       = [];
    this.bgTasks     = new Map();
    this.bgPolling   = null;

    this.$ = id => document.getElementById(id);
    this.bindAll();
    this.applyTheme();
    this.restoreMaxThinkingUI();
    this.hideSplash();
    this.setupAuth();
  }

  _sess() {
    let s = localStorage.getItem('kautilya_session');
    if (!s) {
      s = 'sess_' + Math.random().toString(36).slice(2, 11);
      localStorage.setItem('kautilya_session', s);
    }
    return s;
  }
  newSession() {
    const s = 'sess_' + Math.random().toString(36).slice(2, 11);
    localStorage.setItem('kautilya_session', s);
    this.sessionId = s;
    return s;
  }

  // ----------------------------------------------------------------------
  // Event binding
  // ----------------------------------------------------------------------
  bindAll() {
    const $ = this.$;

    // Core
    $('sendBtn').addEventListener('click', () => this.isStreaming ? this.stopStream() : this.sendMessage());
    $('messageInput').addEventListener('keydown', e => {
      if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); this.sendMessage(); }
    });
    $('messageInput').addEventListener('input', e => this.autoGrow(e.target));

    $('attachBtn').addEventListener('click', () => $('fileInput').click());
    $('fileInput').addEventListener('change', e => this.onFiles(e.target.files));

    $('newChatBtn').addEventListener('click', () => this.newChat());
    $('toggleSidebar').addEventListener('click', () => this.toggleSidebar());
    $('sidebarScrim').addEventListener('click', () => this.closeSidebar());
    $('themeToggle').addEventListener('click', () => this.cycleTheme());

    // Toolbar toggles
    $('maxThinkingBtn').addEventListener('click', () => this.toggleMaxThinking());
    $('backgroundBtn').addEventListener('click', () => this.toggleBgMode());
    $('researchBtn').addEventListener('click', () => this.toggleResearchMode());
    $('voiceBtn').addEventListener('click', () => toast('Voice input coming soon'));

    // Model
    $('modelSelector').addEventListener('change', e => {
      localStorage.setItem('kautilya_model', e.target.value);
      this.updateToolbarCompat();
    });
    const savedModel = localStorage.getItem('kautilya_model');
    if (savedModel) $('modelSelector').value = savedModel;

    // Feature cards / chips
    document.querySelectorAll('[data-prompt]').forEach(el => {
      el.addEventListener('click', () => {
        $('messageInput').value = el.dataset.prompt;
        $('messageInput').focus();
        this.autoGrow($('messageInput'));
      });
    });

    // Login modal
    $('loginBtn').addEventListener('click', () => this.openModal('loginModal'));
    $('closeLoginModal').addEventListener('click', () => this.closeModal('loginModal'));
    $('googleSignIn').addEventListener('click', () => this.googleSignIn());
    $('loginSubmitBtn').addEventListener('click', () => this.emailSignIn());

    // Sidebar user menu
    $('sidebarProfile').addEventListener('click', () => this.toggleUserMenu());
    $('settingsBtn').addEventListener('click', () => { this.closeUserMenu(); this.openSettings(); });
    $('logoutBtn').addEventListener('click', () => { this.closeUserMenu(); this.logout(); });
    $('closeSettingsModal').addEventListener('click', () => this.closeModal('settingsModal'));
    document.querySelectorAll('.settings-tab').forEach(t => {
      t.addEventListener('click', () => this.showSettingsSection(t.dataset.target));
    });
    $('themeSelect').addEventListener('change', e => { this.theme = e.target.value; this.applyTheme(); localStorage.setItem('kautilya_theme', this.theme); });
    $('clearMemoryBtn').addEventListener('click', () => this.clearMemory());
    $('saveProfileBtn').addEventListener('click', () => this.saveProfile());
    $('createApiKeyBtn').addEventListener('click', () => this.createApiKey());

    // Background panel
    $('bgLauncher').addEventListener('click', () => this.openBgPanel());
    $('bgPanelClose').addEventListener('click', () => this.closeBgPanel());
    $('bgTaskModalClose').addEventListener('click', () => this.closeModal('bgTaskModal'));

    // Artifact panel
    $('artifactCloseBtn').addEventListener('click', () => $('artifactPanel').classList.remove('open'));
    document.querySelectorAll('.artifact-tab').forEach(t => {
      t.addEventListener('click', () => this.switchArtifactTab(t.dataset.tab));
    });

    // Click-outside modals
    document.querySelectorAll('.modal-overlay').forEach(ov => {
      ov.addEventListener('click', e => { if (e.target === ov) ov.classList.remove('open'); });
    });

    // Auto-collapse sidebar on mobile at load
    if (window.innerWidth <= 720) {
      document.getElementById('appContainer').classList.remove('sidebar-open');
    }
  }

  autoGrow(el) {
    el.style.height = 'auto';
    el.style.height = Math.min(el.scrollHeight, 200) + 'px';
    this.$('sendBtn').disabled = !el.value.trim() && this.files.length === 0;
  }

  // ----------------------------------------------------------------------
  // THEME / SIDEBAR / SPLASH
  // ----------------------------------------------------------------------
  applyTheme() {
    let t = this.theme;
    if (t === 'system') t = window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', t);
    const icon = this.$('themeIcon');
    if (icon) icon.textContent = t === 'dark' ? 'light_mode' : 'dark_mode';
    const sel = this.$('themeSelect');
    if (sel) sel.value = this.theme;
  }
  cycleTheme() {
    this.theme = this.theme === 'dark' ? 'light' : 'dark';
    localStorage.setItem('kautilya_theme', this.theme);
    this.applyTheme();
  }
  toggleSidebar() {
    const c = document.getElementById('appContainer');
    if (window.innerWidth <= 720) c.classList.toggle('sidebar-open');
    else c.classList.toggle('sidebar-collapsed');
  }
  closeSidebar() { document.getElementById('appContainer').classList.remove('sidebar-open'); }
  toggleUserMenu() { this.$('userMenu').classList.toggle('open'); }
  closeUserMenu() { this.$('userMenu').classList.remove('open'); }

  hideSplash() {
    setTimeout(() => { const s = this.$('splashScreen'); if (s) s.classList.add('hidden'); }, 700);
  }

  // ----------------------------------------------------------------------
  // MAX THINKING  /  BACKGROUND MODE
  // ----------------------------------------------------------------------
  restoreMaxThinkingUI() {
    this.$('maxThinkingBtn').classList.toggle('active', this.maxThinking);
    this.updateToolbarCompat();
  }
  toggleMaxThinking() {
    this.maxThinking = !this.maxThinking;
    localStorage.setItem('kautilya_maxthink', this.maxThinking ? '1' : '0');
    this.$('maxThinkingBtn').classList.toggle('active', this.maxThinking);
    toast(this.maxThinking ? 'Max Thinking: ON — reasoning traces enabled' : 'Max Thinking: OFF');
  }
  toggleBgMode() {
    this.bgMode = !this.bgMode;
    this.$('backgroundBtn').classList.toggle('active', this.bgMode);
    if (this.bgMode) toast('Background mode — next message runs async');
  }
  toggleResearchMode() {
    this.researchMode = !this.researchMode;
    this.$('researchBtn').classList.toggle('active', this.researchMode);
    if (this.researchMode) toast('Deep Research mode — next message runs multi-source research');
  }
  updateToolbarCompat() {
    const model = this.$('modelSelector').value;
    const mt = this.$('maxThinkingBtn');
    if (model === 'daily') {
      mt.style.opacity = '.45';
      mt.title = 'Max Thinking only available on Pro / Coder';
    } else {
      mt.style.opacity = '1';
      mt.title = 'Toggle extended reasoning';
    }
  }

  // ----------------------------------------------------------------------
  // FILE ATTACHMENTS
  // ----------------------------------------------------------------------
  onFiles(fl) {
    [...fl].forEach(f => {
      if (f.size > 20 * 1024 * 1024) { toast(`${f.name} > 20MB, skipped`, 'error'); return; }
      this.files.push(f);
    });
    this.renderFileChips();
    this.$('sendBtn').disabled = !this.$('messageInput').value.trim() && this.files.length === 0;
    this.$('fileInput').value = '';
  }
  renderFileChips() {
    const host = this.$('attachedFiles');
    host.innerHTML = '';
    this.files.forEach((f, i) => {
      const chip = document.createElement('div');
      chip.className = 'file-chip';
      chip.innerHTML = `<span class="material-icons-round">description</span><span>${escapeHtml(f.name)}</span><button class="remove"><span class="material-icons-round">close</span></button>`;
      chip.querySelector('.remove').addEventListener('click', () => {
        this.files.splice(i, 1);
        this.renderFileChips();
        this.$('sendBtn').disabled = !this.$('messageInput').value.trim() && this.files.length === 0;
      });
      host.appendChild(chip);
    });
    this.$('inputWrapper').classList.toggle('has-files', this.files.length > 0);
  }

  // ----------------------------------------------------------------------
  // MESSAGE SEND / STREAM
  // ----------------------------------------------------------------------
  async sendMessage() {
    if (this.isStreaming) return;
    const input = this.$('messageInput');
    const text = input.value.trim();
    if (!text && this.files.length === 0) return;

    // First user message — hide welcome
    const welcome = this.$('welcomeScreen');
    if (welcome) welcome.remove();

    this.appendUserMessage(text, [...this.files]);
    input.value = '';
    this.autoGrow(input);

    if (this.bgMode) {
      await this.submitBackground(text);
      this.bgMode = false;
      this.$('backgroundBtn').classList.remove('active');
      return;
    }

    if (this.researchMode) {
      await this.streamResearch(text);
      this.researchMode = false;
      this.$('researchBtn').classList.remove('active');
      this.files = [];
      this.renderFileChips();
      return;
    }

    await this.streamMessage(text, this.files);
    this.files = [];
    this.renderFileChips();
  }

  async streamMessage(text, files) {
    this.isStreaming = true;
    this.setSendMode('stop');

    const assistant = this.appendAssistantScaffold();
    const model = this.$('modelSelector').value;

    const form = new FormData();
    form.append('message', text);
    form.append('session_id', this.sessionId);
    form.append('model', model);
    form.append('max_thinking', this.maxThinking ? '1' : '0');
    (files || []).forEach(f => form.append('files', f));

    const headers = {};
    try {
      if (this.user) headers['Authorization'] = 'Bearer ' + await this.user.getIdToken();
    } catch (_) {}

    this.abortCtrl = new AbortController();
    let full = '';

    try {
      const resp = await fetch('/api/jarvis/stream', {
        method: 'POST', body: form, headers, signal: this.abortCtrl.signal,
      });
      if (!resp.ok || !resp.body) throw new Error(`HTTP ${resp.status}`);

      const reader = resp.body.getReader();
      const dec = new TextDecoder();
      let buf = '';
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buf += dec.decode(value, { stream: true });
        const lines = buf.split('\n');
        buf = lines.pop();
        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          const payload = line.slice(6).trim();
          if (payload === '[DONE]') continue;
          let obj; try { obj = JSON.parse(payload); } catch { obj = { chunk: payload }; }
          full = this.handleSSE(obj, assistant, full);
        }
      }
    } catch (err) {
      if (err.name !== 'AbortError') this.appendToContent(assistant, `\n\n⚠️ ${err.message}`);
    }

    this.finalizeAssistant(assistant, full);
    this.isStreaming = false;
    this.setSendMode('send');
    this.abortCtrl = null;
    this.refreshHistory();
  }

  stopStream() {
    if (this.abortCtrl) { try { this.abortCtrl.abort(); } catch {} }
  }

  setSendMode(mode) {
    const btn = this.$('sendBtn');
    const icon = this.$('sendIcon');
    if (mode === 'stop') {
      btn.classList.add('stop-mode'); icon.textContent = 'stop'; btn.disabled = false;
      btn.title = 'Stop generation';
    } else {
      btn.classList.remove('stop-mode'); icon.textContent = 'arrow_upward';
      btn.disabled = !this.$('messageInput').value.trim() && this.files.length === 0;
      btn.title = 'Send';
    }
  }

  // ----------------------------------------------------------------------
  // SSE event dispatch
  // ----------------------------------------------------------------------
  handleSSE(obj, scaffold, full) {
    if (obj.event === 'agent') {
      this.renderAgentPill(scaffold, obj);
    } else if (obj.thinking) {
      this.appendThinking(scaffold, obj.thinking);
    } else if (obj.thinking_done) {
      this.closeThinking(scaffold);
    } else if (obj.tool_calls) {
      this.renderToolCalls(scaffold, obj.tool_calls);
    } else if (obj.type === 'status') {
      this.showStatus(scaffold, obj.message);
    } else if (obj.chunk !== undefined) {
      full += obj.chunk;
      this.updateContent(scaffold, full);
    }
    this.scrollToEnd();
    return full;
  }

  renderAgentPill(row, meta) {
    const host = row.querySelector('.tool-call-host');
    if (!host) return;
    const pill = document.createElement('div');
    pill.className = 'agent-pill';
    pill.innerHTML = `<span class="agent-emoji">${meta.emoji || '🤖'}</span>
                      Routing to <strong>${escapeHtml(meta.label || meta.agent)}</strong>
                      <span style="color:var(--text-tertiary);">· ${escapeHtml(meta.description || '')}</span>`;
    host.appendChild(pill);
  }

  // ----------------------------------------------------------------------
  // MESSAGE DOM
  // ----------------------------------------------------------------------
  appendUserMessage(text, files) {
    const row = document.createElement('div');
    row.className = 'msg-row user';
    const filesHtml = (files || []).length
      ? `<div style="margin-top:6px; font-size:12px; color:var(--text-tertiary);">📎 ${files.map(f => escapeHtml(f.name)).join(', ')}</div>` : '';
    row.innerHTML = `
      <div class="msg-avatar" style="background: var(--user-bubble); color: var(--text-primary);">
        ${this.userInitial()}
      </div>
      <div class="msg-body">
        <div class="msg-bubble-user">${escapeHtml(text || '(attachments)')}${filesHtml}</div>
      </div>`;
    this.$('chatContent').appendChild(row);
    this.scrollToEnd();
  }

  appendAssistantScaffold() {
    const row = document.createElement('div');
    row.className = 'msg-row assistant';
    row.innerHTML = `
      <div class="msg-avatar"><img src="/static/kautilya_logo.png" alt=""/></div>
      <div class="msg-body">
        <div class="thinking-block hidden" data-role="thinking">
          <div class="thinking-head">
            <span class="dot-wave"><span></span><span></span><span></span></span>
            <span class="thinking-label">Thinking…</span>
            <span class="material-icons-round chevron">expand_more</span>
          </div>
          <div class="thinking-body"><div class="thinking-body-inner"></div></div>
        </div>
        <div class="tool-call-host"></div>
        <div class="status-line" style="color: var(--text-tertiary); font-size: 12.5px; margin: 4px 0;"></div>
        <div class="msg-content" data-role="content"></div>
        <div class="msg-actions hidden">
          <button data-act="copy"><span class="material-icons-round">content_copy</span>Copy</button>
          <button data-act="regen"><span class="material-icons-round">refresh</span>Regenerate</button>
        </div>
      </div>`;
    // Expand/collapse thinking
    row.querySelector('.thinking-head').addEventListener('click', () => {
      row.querySelector('.thinking-block').classList.toggle('open');
    });
    this.$('chatContent').appendChild(row);
    return row;
  }

  appendThinking(row, delta) {
    const block = row.querySelector('[data-role="thinking"]');
    const inner = row.querySelector('.thinking-body-inner');
    block.classList.remove('hidden');
    block.classList.add('active');
    inner.textContent = (inner.textContent || '') + delta;
    // Claude-like: follow the latest words
    const body = row.querySelector('.thinking-body');
    body.scrollTop = body.scrollHeight;
  }

  closeThinking(row) {
    const block = row.querySelector('[data-role="thinking"]');
    if (!block) return;
    block.classList.remove('active');
    // Change the label; briefly stay expanded if user opened it
    const label = block.querySelector('.thinking-label');
    const wave = block.querySelector('.dot-wave');
    if (label) label.textContent = 'Thought for a moment';
    if (wave) wave.style.display = 'none';
    block.classList.remove('open');
  }

  renderToolCalls(row, toolCalls) {
    const host = row.querySelector('.tool-call-host');
    toolCalls.forEach(tc => {
      const name = tc.function?.name || tc.name || 'tool';
      const args = tc.function?.arguments || '';
      const pill = document.createElement('div');
      pill.className = 'tool-call';
      pill.innerHTML = `<span class="spinner"></span>Calling <strong>${escapeHtml(name)}</strong>${args ? `<span style="color:var(--text-tertiary); font-family: 'JetBrains Mono', monospace; font-size:11.5px; margin-left:6px;">${escapeHtml(String(args).slice(0,80))}</span>` : ''}`;
      host.appendChild(pill);
    });
  }

  showStatus(row, msg) {
    const line = row.querySelector('.status-line');
    if (!line) return;
    if (!msg) { line.textContent = ''; return; }
    line.innerHTML = `<span class="dot-wave" style="margin-right:6px;"><span></span><span></span><span></span></span>${escapeHtml(msg)}`;
  }

  updateContent(row, full) {
    const el = row.querySelector('[data-role="content"]');
    if (!el) return;
    el.innerHTML = mdRender(full);
    decorateCodeBlocks(el);
    this.detectArtifact(el, full);
  }
  appendToContent(row, text) {
    const el = row.querySelector('[data-role="content"]');
    if (el) { el.innerHTML += `<p>${escapeHtml(text)}</p>`; }
  }

  finalizeAssistant(row, full) {
    const content = row.querySelector('[data-role="content"]');
    if (!content) return;
    content.innerHTML = mdRender(full);
    decorateCodeBlocks(content);
    renderMath(content);
    this.detectArtifact(content, full);

    const actions = row.querySelector('.msg-actions');
    if (actions) {
      actions.classList.remove('hidden');
      actions.querySelector('[data-act="copy"]').addEventListener('click', async () => {
        try { await navigator.clipboard.writeText(full); toast('Copied', 'success'); } catch { toast('Copy failed', 'error'); }
      });
      actions.querySelector('[data-act="regen"]').addEventListener('click', () => toast('Regenerate — send the same message again'));
    }
    const statusLine = row.querySelector('.status-line');
    if (statusLine) statusLine.textContent = '';
  }

  // ----------------------------------------------------------------------
  // ARTIFACT DETECTION (html / svg / mermaid)
  // ----------------------------------------------------------------------
  detectArtifact(container, full) {
    // Pick first <pre><code class="language-html|svg|mermaid">
    const code = container.querySelector('pre code.language-html, pre code.language-svg, pre code.language-mermaid');
    if (!code) return;
    const raw = code.textContent;
    this._openArtifact(raw, code.className.includes('html') ? 'html' : code.className.includes('svg') ? 'svg' : 'mermaid');
  }
  _openArtifact(source, kind) {
    const panel = this.$('artifactPanel');
    const frame = this.$('artifactPreviewFrame');
    const code  = this.$('artifactCodeContent');
    panel.classList.add('open');
    code.textContent = source;
    code.className = '';
    try { hljs.highlightElement(code); } catch {}
    if (kind === 'html') {
      frame.srcdoc = source;
    } else if (kind === 'svg') {
      frame.srcdoc = `<!doctype html><style>html,body{margin:0;background:#fff;display:grid;place-items:center;height:100%;}</style>${source}`;
    } else if (kind === 'mermaid') {
      frame.srcdoc = `<!doctype html><script src="https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js"><\/script><style>body{margin:16px;font-family:Inter,sans-serif;}</style><div class="mermaid">${source}</div><script>mermaid.initialize({startOnLoad:true,theme:'dark'});<\/script>`;
    }
  }
  switchArtifactTab(tab) {
    document.querySelectorAll('.artifact-tab').forEach(t => t.classList.toggle('active', t.dataset.tab === tab));
    this.$('artifactPreviewFrame').classList.toggle('hidden', tab !== 'preview');
    this.$('artifactCodeView').classList.toggle('hidden', tab !== 'code');
  }

  scrollToEnd() {
    const c = this.$('chatContainer');
    // Don't hijack scroll if user is reading earlier messages
    if (c.scrollTop + c.clientHeight > c.scrollHeight - 200) {
      c.scrollTop = c.scrollHeight;
    }
  }

  userInitial() {
    if (this.user?.displayName) return escapeHtml(this.user.displayName[0].toUpperCase());
    if (this.user?.email) return escapeHtml(this.user.email[0].toUpperCase());
    return 'U';
  }

  // ----------------------------------------------------------------------
  // BACKGROUND TASKS
  // ----------------------------------------------------------------------
  async submitBackground(text) {
    if (!this.user) { toast('Sign in to run background tasks', 'error'); this.openModal('loginModal'); return; }
    const headers = { 'Content-Type': 'application/json' };
    try { headers['Authorization'] = 'Bearer ' + await this.user.getIdToken(); } catch {}
    const model = this.$('modelSelector').value;
    try {
      const r = await fetch('/api/jarvis/background', {
        method: 'POST', headers,
        body: JSON.stringify({ prompt: text, model, max_thinking: true, title: text.slice(0, 80) }),
      });
      const data = await r.json();
      if (data.task_id) {
        toast('Background task submitted — we will notify you', 'success');
        this.appendBgSubmittedCard(data.task_id, data.title);
        this.startBgPolling();
      } else {
        toast(data.error || 'Failed to submit', 'error');
      }
    } catch (e) { toast(String(e), 'error'); }
  }

  appendBgSubmittedCard(id, title) {
    const row = document.createElement('div');
    row.className = 'msg-row assistant';
    row.innerHTML = `
      <div class="msg-avatar"><img src="/static/kautilya_logo.png" alt=""/></div>
      <div class="msg-body">
        <div class="msg-content">
          <div class="tool-call">
            <span class="spinner"></span>
            <span>Running in background: <strong>${escapeHtml(title)}</strong></span>
          </div>
          <p style="font-size:13px; color:var(--text-secondary); margin-top:6px;">
            You can close this tab. Result will appear in the <strong>Background</strong> panel when ready.
          </p>
        </div>
      </div>`;
    this.$('chatContent').appendChild(row);
    this.scrollToEnd();
  }

  async startBgPolling() {
    if (this.bgPolling) return;
    const poll = async () => {
      if (!this.user) return;
      try {
        const headers = { 'Authorization': 'Bearer ' + await this.user.getIdToken() };
        const r = await fetch('/api/jarvis/background', { headers });
        if (!r.ok) return;
        const data = await r.json();
        this.renderBgTasks(data.tasks || []);
        const anyRunning = (data.tasks || []).some(t => t.status === 'queued' || t.status === 'running');
        if (!anyRunning) {
          clearInterval(this.bgPolling);
          this.bgPolling = null;
        }
      } catch {}
    };
    poll();
    this.bgPolling = setInterval(poll, 3500);
  }

  renderBgTasks(tasks) {
    const body = this.$('bgPanelBody');
    const launcher = this.$('bgLauncher');
    if (!tasks.length) {
      body.innerHTML = `<div style="padding:20px;text-align:center;color:var(--text-tertiary);font-size:12.5px;">No background tasks yet.</div>`;
      launcher.classList.add('hidden');
      return;
    }
    launcher.classList.remove('hidden');
    this.$('bgLauncherCount').textContent = tasks.length;
    this.$('bgPanelCount').textContent = tasks.length;
    body.innerHTML = tasks.map(t => {
      const time = new Date((t.created || Date.now()/1000) * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
      return `<div class="bg-task" data-id="${t.id}">
        <div class="title">${escapeHtml(t.title || 'Untitled')}</div>
        <div class="meta"><span class="status-dot ${t.status}"></span>${escapeHtml(t.status)} · ${time}</div>
      </div>`;
    }).join('');
    body.querySelectorAll('.bg-task').forEach(el => {
      el.addEventListener('click', () => this.openBgTaskDetail(el.dataset.id));
    });
  }

  async openBgTaskDetail(taskId) {
    if (!this.user) return;
    const headers = { 'Authorization': 'Bearer ' + await this.user.getIdToken() };
    try {
      const r = await fetch(`/api/jarvis/background/${taskId}`, { headers });
      const t = await r.json();
      this.$('bgTaskModalTitle').textContent = t.title || 'Background Task';
      const body = this.$('bgTaskModalBody');
      if (t.status === 'done') {
        body.innerHTML = mdRender(t.result || '(empty result)');
        decorateCodeBlocks(body); renderMath(body);
      } else if (t.status === 'error') {
        body.innerHTML = `<p style="color:#FF6B6B;">Error: ${escapeHtml(t.error || 'unknown')}</p>`;
      } else {
        body.innerHTML = `<p>Status: <strong>${escapeHtml(t.status)}</strong></p><p style="color:var(--text-secondary);">This task is still running. Come back in a minute.</p>`;
      }
      this.openModal('bgTaskModal');
    } catch (e) { toast(String(e), 'error'); }
  }

  openBgPanel() { this.$('bgPanel').classList.add('open'); }
  closeBgPanel() { this.$('bgPanel').classList.remove('open'); }

  // ----------------------------------------------------------------------
  // AUTH
  // ----------------------------------------------------------------------
  setupAuth() {
    const auth = firebase.auth();
    auth.onAuthStateChanged(async user => {
      this.user = user;
      if (user) {
        this.$('loginBtn').style.display = 'none';
        this.$('userMenu').style.display = 'block';
        this.$('sidebarUsername').textContent = user.displayName || user.email?.split('@')[0] || 'User';
        if (user.photoURL) this.$('sidebarAvatarImg').src = user.photoURL;
        this.closeModal('loginModal');
        await this.loadStatus();
        this.refreshHistory();
        this.startBgPolling();
      } else {
        this.$('loginBtn').style.display = 'flex';
        this.$('userMenu').style.display = 'none';
        this.$('sidebarPlan').textContent = 'Guest';
      }
    });
  }
  async logout() {
    try {
      await firebase.auth().signOut();
      toast('Signed out successfully', 'success');
    } catch (e) { toast(e.message, 'error'); }
  }
  async googleSignIn() {
    try {
      const prov = new firebase.auth.GoogleAuthProvider();
      await firebase.auth().signInWithPopup(prov);
    } catch (e) { toast(e.message, 'error'); }
  }
  async emailSignIn() {
    const email = this.$('loginEmail').value.trim();
    const pw = this.$('loginPassword').value;
    if (!email || !pw) return toast('Enter email & password', 'error');
    try {
      await firebase.auth().signInWithEmailAndPassword(email, pw);
    } catch (e) {
      if (e.code === 'auth/user-not-found') {
        try {
          await firebase.auth().createUserWithEmailAndPassword(email, pw);
        } catch (e2) { toast(e2.message, 'error'); }
      } else { toast(e.message, 'error'); }
    }
  }
  async loadStatus() {
    if (!this.user) return;
    try {
      const r = await fetch('/api/jarvis/status', {
        headers: { 'Authorization': 'Bearer ' + await this.user.getIdToken() },
      });
      if (r.ok) {
        const d = await r.json();
        this.isPro = !!d.is_pro;
        this.$('sidebarPlan').textContent = d.role || 'Free Plan';
      }
    } catch {}
  }

  // ----------------------------------------------------------------------
  // HISTORY
  // ----------------------------------------------------------------------
  async refreshHistory() {
    if (!this.user) { this.$('recentList').innerHTML = ''; return; }
    try {
      const r = await fetch('/api/jarvis/history', {
        headers: { 'Authorization': 'Bearer ' + await this.user.getIdToken() },
      });
      if (!r.ok) return;
      const d = await r.json();
      const list = (d.chats || []).slice(0, 40);
      const host = this.$('recentList');
      host.innerHTML = list.map(c => `
        <div class="recent-item" data-id="${escapeHtml(c.session_id)}" title="${escapeHtml(c.preview || '')}">
          <span class="material-icons-round">chat_bubble_outline</span>
          <span class="recent-preview">${escapeHtml(c.preview || 'New chat')}</span>
          <button class="recent-del" title="Delete"><span class="material-icons-round" style="font-size:16px;">close</span></button>
        </div>`).join('');
      host.querySelectorAll('.recent-item').forEach(el => {
        el.addEventListener('click', e => {
          if (e.target.closest('.recent-del')) return;
          this.loadChat(el.dataset.id);
          host.querySelectorAll('.recent-item').forEach(i => i.classList.remove('active'));
          el.classList.add('active');
        });
        el.querySelector('.recent-del').addEventListener('click', async e => {
          e.stopPropagation();
          await this.deleteChat(el.dataset.id);
          el.remove();
        });
      });
    } catch {}
  }

  async loadChat(id) {
    if (!this.user) return;
    this.sessionId = id;
    localStorage.setItem('kautilya_session', id);
    try {
      const r = await fetch(`/api/jarvis/history/${id}`, {
        headers: { 'Authorization': 'Bearer ' + await this.user.getIdToken() },
      });
      const d = await r.json();
      this.$('chatContent').innerHTML = '';
      (d.messages || []).forEach(m => {
        if (m.role === 'user') {
          const text = typeof m.content === 'string' ? m.content
                      : (m.content || []).filter(p => p.type === 'text').map(p => p.text).join('\n');
          this.appendUserMessage(text, []);
        } else if (m.role === 'assistant') {
          const row = this.appendAssistantScaffold();
          this.finalizeAssistant(row, typeof m.content === 'string' ? m.content : '');
        }
      });
      this.scrollToEnd();
    } catch {}
    this.closeSidebar();
  }

  async deleteChat(id) {
    if (!this.user) return;
    try {
      await fetch(`/api/jarvis/history/${id}`, {
        method: 'DELETE',
        headers: { 'Authorization': 'Bearer ' + await this.user.getIdToken() },
      });
    } catch {}
    if (id === this.sessionId) this.newChat();
  }

  newChat() {
    this.newSession();
    this.$('chatContent').innerHTML = `
      <div class="welcome-screen" id="welcomeScreen"></div>`;
    // Rebuild welcome dynamically cheap way — reload only grid
    const w = this.$('welcomeScreen');
    w.innerHTML = `
      <img src="/static/kautilya_logo.png" alt="" class="welcome-logo" />
      <h1 class="welcome-title">New conversation</h1>
      <p class="welcome-subtitle">What shall we tackle, Sir?</p>`;
    this.closeSidebar();
  }

  // ----------------------------------------------------------------------
  // SETTINGS
  // ----------------------------------------------------------------------
  async openSettings() {
    this.openModal('settingsModal');
    // Try load profile
    if (this.user) {
      // nothing required; API keys load on tab switch
      this.loadApiKeys();
    }
  }
  showSettingsSection(id) {
    document.querySelectorAll('.settings-tab').forEach(t => t.classList.toggle('active', t.dataset.target === id));
    document.querySelectorAll('.settings-section').forEach(s => s.classList.toggle('active', s.id === 'settings-' + id));
    if (id === 'keys') this.loadApiKeys();
  }
  async clearMemory() {
    if (!confirm('Clear all memory?')) return;
    try {
      await fetch('/api/memory/clear', {
        method: 'POST',
        headers: { 'Authorization': 'Bearer ' + (this.user ? await this.user.getIdToken() : '') },
      });
      toast('Memory cleared', 'success');
    } catch { toast('Failed', 'error'); }
  }
  async saveProfile() {
    if (!this.user) return toast('Sign in first', 'error');
    try {
      await fetch('/api/user/profile', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + await this.user.getIdToken() },
        body: JSON.stringify({ displayName: this.$('displayNameInput').value, preferences: this.$('preferencesInput').value }),
      });
      toast('Profile saved', 'success');
    } catch { toast('Failed', 'error'); }
  }
  async loadApiKeys() {
    if (!this.user) { this.$('apiKeysContainer').innerHTML = '<p style="color:var(--text-tertiary);font-size:12.5px;">Sign in to manage API keys.</p>'; return; }
    try {
      const r = await fetch('/api/keys/list', {
        headers: { 'Authorization': 'Bearer ' + await this.user.getIdToken() },
      });
      const d = await r.json();
      const host = this.$('apiKeysContainer');
      if (!d.keys || !d.keys.length) { host.innerHTML = '<p style="color:var(--text-tertiary);font-size:12.5px;">No keys yet. Generate your first one below.</p>'; return; }
      host.innerHTML = d.keys.map(k => `
        <div style="display:flex;align-items:center;gap:10px;padding:10px 12px;border:1px solid var(--border-subtle);border-radius:10px;margin-bottom:6px;">
          <span class="material-icons-round" style="color:var(--brand-primary);">key</span>
          <div style="flex:1;">
            <div style="font-weight:500;">${escapeHtml(k.name)}</div>
            <div style="font-size:11.5px;color:var(--text-tertiary);font-family:monospace;">${escapeHtml(k.preview)}</div>
          </div>
          <button class="btn btn-secondary" data-revoke="${escapeHtml(k.key_hash)}" style="padding:6px 10px;font-size:12px;">Revoke</button>
        </div>`).join('');
      host.querySelectorAll('[data-revoke]').forEach(btn => {
        btn.addEventListener('click', async () => {
          if (!confirm('Revoke this API key?')) return;
          try {
            await fetch('/api/keys/revoke', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + await this.user.getIdToken() },
              body: JSON.stringify({ key_hash: btn.dataset.revoke }),
            });
            this.loadApiKeys();
            toast('Revoked', 'success');
          } catch { toast('Failed', 'error'); }
        });
      });
    } catch { this.$('apiKeysContainer').innerHTML = '<p style="color:#FF6B6B;">Failed to load keys.</p>'; }
  }
  async createApiKey() {
    if (!this.user) return toast('Sign in first', 'error');
    const name = prompt('Name this API key (e.g., "My Laptop Cline")', 'Kautilya Coder');
    if (!name) return;
    try {
      const r = await fetch('/api/keys/create', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + await this.user.getIdToken() },
        body: JSON.stringify({ name }),
      });
      const d = await r.json();
      if (d.key) {
        prompt('Copy this key NOW (shown only once):', d.key);
        this.loadApiKeys();
      } else { toast(d.error || 'Failed', 'error'); }
    } catch { toast('Failed', 'error'); }
  }

  // ----------------------------------------------------------------------
  // Misc helpers
  // ----------------------------------------------------------------------
  openModal(id) { this.$(id).classList.add('open'); }
  closeModal(id) { this.$(id).classList.remove('open'); }

  // ----------------------------------------------------------------------
  // DEEP RESEARCH
  // ----------------------------------------------------------------------
  async streamResearch(question) {
    if (!this.user) { toast('Sign in to use Research mode', 'error'); this.openModal('loginModal'); return; }
    this.isStreaming = true;
    this.setSendMode('stop');

    const row = document.createElement('div');
    row.className = 'msg-row assistant';
    row.innerHTML = `
      <div class="msg-avatar"><img src="/static/kautilya_logo.png" alt=""/></div>
      <div class="msg-body">
        <div class="research-head">
          <span class="material-icons-round" style="color:var(--brand-primary);">travel_explore</span>
          <strong>Deep Research</strong>
          <span class="research-status"><span class="spinner"></span>Planning queries…</span>
        </div>
        <div class="research-queries"></div>
        <div class="research-sources"></div>
        <div class="msg-content" data-role="content"></div>
      </div>`;
    this.$('chatContent').appendChild(row);
    this.scrollToEnd();

    const statusEl = row.querySelector('.research-status');
    const qEl      = row.querySelector('.research-queries');
    const srcEl    = row.querySelector('.research-sources');
    const content  = row.querySelector('[data-role="content"]');
    let full = '';

    this.abortCtrl = new AbortController();
    try {
      const headers = { 'Content-Type': 'application/json' };
      try { headers['Authorization'] = 'Bearer ' + await this.user.getIdToken(); } catch {}
      const resp = await fetch('/api/research/stream', {
        method: 'POST', headers, signal: this.abortCtrl.signal,
        body: JSON.stringify({ question }),
      });
      if (!resp.ok || !resp.body) throw new Error(`HTTP ${resp.status}`);

      const reader = resp.body.getReader();
      const dec = new TextDecoder();
      let buf = '';
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buf += dec.decode(value, { stream: true });
        const lines = buf.split('\n'); buf = lines.pop();
        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          const payload = line.slice(6).trim();
          if (payload === '[DONE]') continue;
          let obj; try { obj = JSON.parse(payload); } catch { continue; }
          if (obj.event === 'query') {
            statusEl.innerHTML = `<span class="spinner"></span>Searching ${obj.queries.length} queries…`;
            qEl.innerHTML = obj.queries.map(q => `<span class="research-chip">🔎 ${escapeHtml(q)}</span>`).join('');
          } else if (obj.event === 'sources') {
            statusEl.innerHTML = `<span class="spinner"></span>Reading ${obj.sources.length} sources…`;
            srcEl.innerHTML = `
              <div class="research-source-label">Sources</div>
              <div class="research-source-grid">
                ${obj.sources.map((s, i) => `
                  <a class="research-source" href="${escapeHtml(s.url)}" target="_blank" rel="noopener">
                    <div class="research-source-num">[${i+1}]</div>
                    <div class="research-source-body">
                      <div class="research-source-title">${escapeHtml(s.title)}</div>
                      <div class="research-source-site">${escapeHtml(s.site || '')}</div>
                    </div>
                  </a>`).join('')}
              </div>`;
          } else if (obj.event === 'chunk') {
            if (statusEl.parentElement) statusEl.innerHTML = '<span style="color:var(--brand-primary);">● writing…</span>';
            full += obj.chunk;
            content.innerHTML = mdRender(full);
            this.scrollToEnd();
          } else if (obj.event === 'done') {
            statusEl.textContent = '✓ Done';
          }
        }
      }
    } catch (e) {
      content.innerHTML += `<p style="color:#FF6B6B;">${escapeHtml(String(e))}</p>`;
    }

    content.innerHTML = mdRender(full);
    decorateCodeBlocks(content); renderMath(content);
    this.isStreaming = false;
    this.setSendMode('send');
    this.abortCtrl = null;
  }

  // ----------------------------------------------------------------------
  // CODE INTERPRETER
  // ----------------------------------------------------------------------
  async runPython(code, preEl) {
    if (!this.user) { toast('Sign in to run code', 'error'); this.openModal('loginModal'); return; }
    // Output panel (insert once, reuse)
    let out = preEl.nextElementSibling;
    if (!out || !out.classList.contains('ci-output')) {
      out = document.createElement('div');
      out.className = 'ci-output';
      preEl.parentElement.insertBefore(out, preEl.nextSibling);
    }
    out.innerHTML = `<div class="ci-status"><span class="spinner"></span>Running…</div>`;
    try {
      const headers = { 'Content-Type': 'application/json' };
      try { headers['Authorization'] = 'Bearer ' + await this.user.getIdToken(); } catch {}
      const r = await fetch('/api/code/run', { method: 'POST', headers, body: JSON.stringify({ code }) });
      const d = await r.json();
      if (!r.ok) { out.innerHTML = `<div class="ci-err">${escapeHtml(d.error || 'failed')}</div>`; return; }
      const stdoutHtml = d.stdout ? `<pre class="ci-stdout">${escapeHtml(d.stdout)}</pre>` : '';
      const stderrHtml = d.stderr ? `<pre class="ci-stderr">${escapeHtml(d.stderr)}</pre>` : '';
      const figsHtml = (d.figures || []).map(b64 => `<img class="ci-fig" src="data:image/png;base64,${b64}"/>`).join('');
      const metaHtml = `<div class="ci-meta">${d.timed_out ? '⏱️ timed out · ' : ''}exit ${d.exit_code} · ${d.duration_ms}ms</div>`;
      out.innerHTML = stdoutHtml + stderrHtml + figsHtml + metaHtml;
    } catch (e) {
      out.innerHTML = `<div class="ci-err">${escapeHtml(String(e))}</div>`;
    }
  }
}

// Boot once DOM is parsed
document.addEventListener('DOMContentLoaded', () => {
  window.app = new KautilyaApp();
});

})();
