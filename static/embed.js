/* ============================================================================
 * Kautilya AI — Embed Widget (drop-in)
 *
 * Usage:
 *   <script src="https://your-host/embed.js"
 *           data-agent="AGENT_ID"
 *           data-token="kte_..."
 *           data-primary="#FF6D3F"
 *           data-position="bottom-right">
 *   </script>
 *
 * Renders a floating chat bubble. Opens a panel with the agent's welcome,
 * streams responses via /embed/<id>/chat, and captures leads via
 * /embed/<id>/lead.
 * ============================================================================ */
(function () {
  'use strict';

  if (window.__KautilyaEmbedLoaded) return;
  window.__KautilyaEmbedLoaded = true;

  // ---- Resolve host + config from the <script> tag ----
  const script = document.currentScript || (function () {
    const s = document.getElementsByTagName('script');
    return s[s.length - 1];
  })();
  const src = script.src;
  const host = src.replace(/\/embed\.js.*$/, '');
  const agentId = script.getAttribute('data-agent');
  const token   = script.getAttribute('data-token') || '';
  const primary = script.getAttribute('data-primary') || '#FF6D3F';
  const position = script.getAttribute('data-position') || 'bottom-right';

  if (!agentId) {
    console.warn('[Kautilya embed] data-agent missing; refusing to mount.');
    return;
  }

  // ---- Shadow DOM host ----
  const root = document.createElement('div');
  root.id = 'kautilya-embed-root';
  document.body.appendChild(root);
  const shadow = root.attachShadow({ mode: 'open' });

  // ---- Styles (scoped to shadow root) ----
  const style = document.createElement('style');
  style.textContent = `
    :host, *, *::before, *::after { box-sizing: border-box; }
    .kt-wrap {
      position: fixed;
      ${position.includes('left')   ? 'left: 20px;'   : 'right: 20px;'}
      ${position.includes('top')    ? 'top: 20px;'    : 'bottom: 20px;'}
      z-index: 2147483640;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Inter, sans-serif;
      color: #111;
    }
    .kt-bubble {
      width: 58px; height: 58px; border-radius: 50%;
      background: var(--p); color: white;
      box-shadow: 0 12px 32px rgba(0,0,0,.22);
      display: grid; place-items: center; cursor: pointer;
      transition: transform 160ms cubic-bezier(.2,.8,.25,1);
      border: 0;
    }
    .kt-bubble:hover { transform: scale(1.06); }
    .kt-bubble svg { width: 26px; height: 26px; fill: white; }

    .kt-panel {
      position: absolute;
      ${position.includes('left')   ? 'left: 0;'  : 'right: 0;'}
      ${position.includes('top')    ? 'top: 72px;' : 'bottom: 72px;'}
      width: 360px; max-width: calc(100vw - 24px);
      height: 520px; max-height: calc(100vh - 120px);
      background: #fff; color: #111;
      border-radius: 16px;
      box-shadow: 0 24px 60px rgba(0,0,0,.28);
      display: none; flex-direction: column; overflow: hidden;
      animation: kt-in 220ms cubic-bezier(.2,.8,.25,1);
    }
    .kt-panel.open { display: flex; }
    @keyframes kt-in { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: none; } }

    .kt-head {
      padding: 14px 16px; color: white; background: var(--p);
      display: flex; align-items: center; gap: 10px;
    }
    .kt-head .kt-title { flex: 1; font-weight: 600; font-size: 15px; }
    .kt-head .kt-close {
      background: rgba(255,255,255,.18); border: 0; color: white;
      width: 28px; height: 28px; border-radius: 50%;
      cursor: pointer; display: grid; place-items: center;
    }
    .kt-head .kt-close:hover { background: rgba(255,255,255,.3); }

    .kt-body {
      flex: 1; overflow-y: auto; padding: 14px; background: #F7F7F9;
    }
    .kt-msg { margin: 8px 0; display: flex; gap: 8px; }
    .kt-msg.user { justify-content: flex-end; }
    .kt-msg .kt-bubble-text {
      max-width: 80%; padding: 9px 13px; border-radius: 14px;
      font-size: 14px; line-height: 1.45; white-space: pre-wrap; word-wrap: break-word;
    }
    .kt-msg.assistant .kt-bubble-text { background: white; border: 1px solid #E5E5EA; border-bottom-left-radius: 4px; }
    .kt-msg.user .kt-bubble-text      { background: var(--p); color: white; border-bottom-right-radius: 4px; }
    .kt-typing { display: inline-flex; gap: 3px; padding: 10px 13px; background: white; border: 1px solid #E5E5EA; border-radius: 14px; border-bottom-left-radius: 4px; }
    .kt-typing span { width: 6px; height: 6px; border-radius: 50%; background: #999; animation: kt-dot 1.1s infinite ease-in-out; }
    .kt-typing span:nth-child(2) { animation-delay: .15s; }
    .kt-typing span:nth-child(3) { animation-delay: .3s; }
    @keyframes kt-dot { 0%,100% { transform: translateY(0); opacity: .4; } 50% { transform: translateY(-3px); opacity: 1; } }

    .kt-input {
      display: flex; align-items: flex-end; gap: 8px;
      padding: 10px; border-top: 1px solid #E5E5EA; background: white;
    }
    .kt-input textarea {
      flex: 1; border: 1px solid #E5E5EA; border-radius: 10px;
      padding: 9px 11px; font: inherit; font-size: 14px;
      resize: none; outline: none; max-height: 120px; color: #111;
    }
    .kt-input textarea:focus { border-color: var(--p); box-shadow: 0 0 0 2px color-mix(in srgb, var(--p) 20%, transparent); }
    .kt-send {
      background: var(--p); color: white; border: 0;
      width: 36px; height: 36px; border-radius: 50%;
      display: grid; place-items: center; cursor: pointer;
    }
    .kt-send:disabled { opacity: .4; cursor: not-allowed; }

    .kt-lead {
      padding: 14px; border-top: 1px solid #E5E5EA; background: #fafafa;
    }
    .kt-lead h4 { margin: 0 0 8px; font-size: 13px; color: #444; font-weight: 600; }
    .kt-lead input {
      width: 100%; padding: 8px 10px; border: 1px solid #E5E5EA;
      border-radius: 8px; font-size: 13px; margin-bottom: 6px; outline: none;
    }
    .kt-lead input:focus { border-color: var(--p); }
    .kt-lead button {
      width: 100%; padding: 8px; background: var(--p); color: white;
      border: 0; border-radius: 8px; font-size: 13px; font-weight: 500; cursor: pointer;
    }
    .kt-lead button:disabled { opacity: .5; }
    .kt-lead .kt-ok { color: #0a7d4a; font-size: 13px; text-align: center; padding: 10px 0; }

    .kt-footer {
      padding: 6px 10px; text-align: center; background: white;
      border-top: 1px solid #F0F0F2; font-size: 10.5px; color: #888;
    }
    .kt-footer a { color: #888; text-decoration: none; }

    @media (max-width: 480px) {
      .kt-panel { width: 100vw; max-width: 100vw; height: 100vh; max-height: 100vh;
                  border-radius: 0; bottom: 0 !important; right: 0 !important; left: 0 !important; top: 0 !important; }
    }
  `;
  shadow.appendChild(style);

  // ---- DOM scaffold ----
  const wrap = document.createElement('div');
  wrap.className = 'kt-wrap';
  wrap.style.setProperty('--p', primary);
  wrap.innerHTML = `
    <div class="kt-panel" id="kt-panel">
      <div class="kt-head">
        <div class="kt-title" id="kt-title">Assistant</div>
        <button class="kt-close" aria-label="Close">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2.5" stroke-linecap="round">
            <path d="M18 6L6 18M6 6l12 12"/>
          </svg>
        </button>
      </div>
      <div class="kt-body" id="kt-body"></div>
      <div class="kt-lead" id="kt-lead" style="display:none;">
        <h4>Leave your contact — we'll follow up</h4>
        <input id="kt-lead-name" type="text" placeholder="Name" />
        <input id="kt-lead-email" type="email" placeholder="Email" />
        <input id="kt-lead-phone" type="tel" placeholder="Phone (optional)" />
        <button id="kt-lead-submit">Submit</button>
      </div>
      <div class="kt-input">
        <textarea id="kt-textarea" rows="1" placeholder="Type a message…"></textarea>
        <button class="kt-send" id="kt-send" aria-label="Send">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="white">
            <path d="M3 20v-6l10-2-10-2V4l18 8z"/>
          </svg>
        </button>
      </div>
      <div class="kt-footer">Powered by <a href="https://ai.revealiq.in" target="_blank">Kautilya AI</a></div>
    </div>
    <button class="kt-bubble" id="kt-bubble" aria-label="Open chat">
      <svg viewBox="0 0 24 24"><path d="M4 4h16v12H5.17L4 17.17V4m0-2a2 2 0 0 0-2 2v18l4-4h14a2 2 0 0 0 2-2V4a2 2 0 0 0-2-2H4z"/></svg>
    </button>
  `;
  shadow.appendChild(wrap);

  // ---- Refs ----
  const $ = s => shadow.querySelector(s);
  const panel = $('#kt-panel');
  const bubble = $('#kt-bubble');
  const closeBtn = shadow.querySelector('.kt-close');
  const body = $('#kt-body');
  const title = $('#kt-title');
  const textarea = $('#kt-textarea');
  const sendBtn = $('#kt-send');
  const leadBox = $('#kt-lead');
  const leadSubmit = $('#kt-lead-submit');

  let history = [];
  let config = null;
  let leadSent = false;

  // ---- Fetch config ----
  async function loadConfig() {
    try {
      const r = await fetch(`${host}/embed/${agentId}/config?token=${encodeURIComponent(token)}`, {
        headers: { 'X-Kautilya-Embed-Token': token },
      });
      config = await r.json();
      if (config.error) { console.warn('[Kautilya embed]', config.error); return; }
      title.textContent = config.name || 'Assistant';
      if (config.welcome_message) {
        appendMsg('assistant', config.welcome_message);
      }
      if (!config.lead_capture?.enabled) leadBox.style.display = 'none';
    } catch (e) {
      console.warn('[Kautilya embed] config failed:', e);
    }
  }
  loadConfig();

  // ---- UI wiring ----
  bubble.addEventListener('click', () => {
    panel.classList.toggle('open');
    if (panel.classList.contains('open')) setTimeout(() => textarea.focus(), 120);
  });
  closeBtn.addEventListener('click', () => panel.classList.remove('open'));
  textarea.addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); }
  });
  textarea.addEventListener('input', () => {
    textarea.style.height = 'auto';
    textarea.style.height = Math.min(textarea.scrollHeight, 120) + 'px';
  });
  sendBtn.addEventListener('click', send);
  leadSubmit.addEventListener('click', submitLead);

  function appendMsg(role, text) {
    const row = document.createElement('div');
    row.className = `kt-msg ${role}`;
    row.innerHTML = `<div class="kt-bubble-text"></div>`;
    row.querySelector('.kt-bubble-text').textContent = text;
    body.appendChild(row);
    body.scrollTop = body.scrollHeight;
    return row.querySelector('.kt-bubble-text');
  }

  function appendTyping() {
    const row = document.createElement('div');
    row.className = 'kt-msg assistant kt-typing-row';
    row.innerHTML = `<div class="kt-typing"><span></span><span></span><span></span></div>`;
    body.appendChild(row);
    body.scrollTop = body.scrollHeight;
    return row;
  }

  async function send() {
    const text = textarea.value.trim();
    if (!text) return;
    appendMsg('user', text);
    history.push({ role: 'user', content: text });
    textarea.value = ''; textarea.style.height = 'auto';
    sendBtn.disabled = true;

    const typing = appendTyping();
    let bubbleEl = null;
    let acc = '';

    try {
      const resp = await fetch(`${host}/embed/${agentId}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text, history, token }),
      });
      if (!resp.body) throw new Error('stream unavailable');
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
          try {
            const obj = JSON.parse(payload);
            if (obj.chunk) {
              if (!bubbleEl) { typing.remove(); bubbleEl = appendMsg('assistant', ''); }
              acc += obj.chunk;
              bubbleEl.textContent = acc;
              body.scrollTop = body.scrollHeight;
            }
          } catch {}
        }
      }
      if (!bubbleEl) { typing.remove(); appendMsg('assistant', '(no response)'); }
      else history.push({ role: 'assistant', content: acc });
    } catch (e) {
      typing.remove();
      appendMsg('assistant', '⚠️ ' + e.message);
    } finally {
      sendBtn.disabled = false;

      // After 2 assistant turns, prompt for lead if not yet captured
      if (!leadSent && history.filter(m => m.role === 'assistant').length >= 2
          && config?.lead_capture?.enabled) {
        leadBox.style.display = 'block';
      }
    }
  }

  async function submitLead() {
    const name  = $('#kt-lead-name').value.trim();
    const email = $('#kt-lead-email').value.trim();
    const phone = $('#kt-lead-phone').value.trim();
    if (!name && !email && !phone) return;
    leadSubmit.disabled = true;
    try {
      await fetch(`${host}/embed/${agentId}/lead`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          token, name, email, phone,
          message: history.map(m => `${m.role}: ${m.content}`).join('\n').slice(-4000),
          source: location.href,
        }),
      });
      leadSent = true;
      leadBox.innerHTML = `<div class="kt-ok">✓ Thanks! We'll reach out shortly.</div>`;
    } catch (e) {
      leadSubmit.disabled = false;
      alert('Failed: ' + e.message);
    }
  }
})();
