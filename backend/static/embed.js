(function() {
  // Prevent duplicate instantiation
  if (window.KautilyaWidgetInitialized) return;
  window.KautilyaWidgetInitialized = true;

  // 1. Identify script parameters and backend origin
  var script = document.currentScript || (function() {
    var scripts = document.getElementsByTagName('script');
    for (var i = 0; i < scripts.length; i++) {
      if (scripts[i].src && (scripts[i].src.indexOf('/embed.js') !== -1 || scripts[i].src.indexOf('/widget.js') !== -1)) {
        return scripts[i];
      }
    }
    return null;
  })();

  if (!script) {
    console.error('[Kautilya Widget] Script tag not found.');
    return;
  }

  var agentId = script.getAttribute('data-agent') || script.getAttribute('data-agent-id');
  var token = script.getAttribute('data-token');
  
  if (!agentId) {
    console.error('[Kautilya Widget] data-agent attribute is missing.');
    return;
  }

  // Derive baseUrl dynamically from the script src location
  var parsedUrl = new URL(script.src);
  var baseUrl = parsedUrl.origin;

  // Configuration defaults
  var position = script.getAttribute('data-position') || 'bottom-right';
  var initialTheme = script.getAttribute('data-theme') || 'dark';
  var greeting = script.getAttribute('data-greeting') || 'Hello! How can I help you today?';
  var autoOpen = script.getAttribute('data-auto-open') === 'true';

  // Global variables
  var widgetConfig = null;
  var isLeadSubmitted = false;
  var chatHistory = [];
  var isStreaming = false;

  // 2. Load agent config from backend
  var configUrl = baseUrl + '/api/embed/' + agentId + '/config?token=' + encodeURIComponent(token || '');
  
  fetch(configUrl)
    .then(function(res) {
      if (!res.ok) throw new Error('Failed to load widget config: ' + res.status);
      return res.json();
    })
    .then(function(config) {
      widgetConfig = config;
      initWidget();
    })
    .catch(function(err) {
      console.warn('[Kautilya Widget] falling back to client config:', err.message);
      widgetConfig = {
        name: 'Kautilya AI',
        welcome_message: greeting,
        brand_color: '#FF6D3F',
        lead_capture: { enabled: true, fields: ['name', 'email', 'phone'] }
      };
      initWidget();
    });

  // 3. Main Widget Initialization
  function initWidget() {
    var brandColor = widgetConfig.brand_color || '#FF6D3F';
    var isDark = initialTheme === 'dark';
    
    // Inject Custom CSS Styles
    var css = `
      #k-widget-container {
        font-family: 'Inter', system-ui, -apple-system, sans-serif;
        z-index: 999999;
        position: fixed;
        bottom: 24px;
        box-sizing: border-box;
      }
      #k-widget-container * {
        box-sizing: border-box;
      }
      .k-pos-bottom-right { right: 24px; }
      .k-pos-bottom-left { left: 24px; }
      
      /* Floating Action Button (FAB) */
      #k-widget-fab {
        width: 56px;
        height: 56px;
        border-radius: 50%;
        background: ${brandColor};
        box-shadow: 0 8px 24px rgba(0, 0, 0, 0.25);
        cursor: pointer;
        display: flex;
        align-items: center;
        justify-content: center;
        transition: transform 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275), box-shadow 0.3s;
        border: none;
        outline: none;
      }
      #k-widget-fab:hover {
        transform: scale(1.08) translateY(-2px);
        box-shadow: 0 12px 28px rgba(0, 0, 0, 0.35);
      }
      #k-widget-fab svg {
        width: 26px;
        height: 26px;
        fill: white;
        transition: transform 0.3s;
      }
      #k-widget-fab.active svg {
        transform: rotate(90deg) scale(0.9);
      }

      /* Chat Window Box */
      #k-widget-box {
        width: 360px;
        height: 560px;
        max-height: calc(100vh - 120px);
        border-radius: 16px;
        box-shadow: 0 12px 40px rgba(0, 0, 0, 0.25);
        display: none;
        flex-direction: column;
        overflow: hidden;
        margin-bottom: 16px;
        transition: opacity 0.3s, transform 0.3s;
        transform: translateY(20px);
        opacity: 0;
        border: 1px solid ${isDark ? 'rgba(255, 255, 255, 0.08)' : 'rgba(0, 0, 0, 0.08)'};
        background: ${isDark ? 'rgba(15, 15, 20, 0.92)' : 'rgba(255, 255, 255, 0.95)'};
        backdrop-filter: blur(20px);
        -webkit-backdrop-filter: blur(20px);
        color: ${isDark ? '#F5F5F7' : '#1D1D1F'};
      }
      #k-widget-box.open {
        display: flex;
        transform: translateY(0);
        opacity: 1;
      }

      /* Header */
      .k-widget-header {
        padding: 16px;
        background: linear-gradient(135deg, ${brandColor}, ${brandColor}dd);
        color: white;
        display: flex;
        align-items: center;
        justify-content: space-between;
        flex-shrink: 0;
      }
      .k-header-info {
        display: flex;
        align-items: center;
        gap: 10px;
      }
      .k-header-avatar {
        width: 36px;
        height: 36px;
        border-radius: 10px;
        background: rgba(255,255,255,0.2);
        display: flex;
        align-items: center;
        justify-content: center;
        font-weight: bold;
        font-size: 16px;
      }
      .k-header-title {
        font-size: 14px;
        font-weight: 600;
        line-height: 1.2;
      }
      .k-header-status {
        font-size: 10px;
        opacity: 0.85;
        display: flex;
        align-items: center;
        gap: 4px;
        margin-top: 2px;
      }
      .k-status-dot {
        width: 6px;
        height: 6px;
        background: #10B981;
        border-radius: 50%;
        display: inline-block;
        animation: k-pulse 2s infinite;
      }
      .k-close-btn {
        background: transparent;
        border: none;
        color: white;
        opacity: 0.7;
        cursor: pointer;
        font-size: 20px;
        padding: 4px;
        transition: opacity 0.2s;
        display: flex;
        align-items: center;
      }
      .k-close-btn:hover {
        opacity: 1;
      }

      /* Messages area */
      #k-widget-messages {
        flex: 1;
        overflow-y: auto;
        padding: 16px;
        display: flex;
        flex-direction: column;
        gap: 12px;
        min-height: 0;
      }
      .k-message {
        max-width: 82%;
        padding: 10px 14px;
        border-radius: 14px;
        font-size: 13px;
        line-height: 1.45;
        word-wrap: break-word;
        white-space: pre-wrap;
      }
      .k-msg-agent {
        background: ${isDark ? 'rgba(255, 255, 255, 0.06)' : 'rgba(0, 0, 0, 0.05)'};
        color: inherit;
        align-self: flex-start;
        border-bottom-left-radius: 4px;
      }
      .k-msg-user {
        background: ${brandColor};
        color: white;
        align-self: flex-end;
        border-bottom-right-radius: 4px;
      }
      .k-message a {
        color: ${brandColor};
        text-decoration: underline;
        font-weight: 600;
        transition: opacity 0.2s;
      }
      .k-message a:hover {
        opacity: 0.85;
      }

      /* Lead Form Overlay */
      #k-lead-overlay {
        position: absolute;
        inset: 0;
        background: ${isDark ? '#0f0f14' : '#ffffff'};
        z-index: 10;
        display: flex;
        flex-direction: column;
        padding: 24px;
        justify-content: center;
      }
      .k-lead-title {
        font-size: 18px;
        font-weight: 600;
        margin-bottom: 6px;
        text-align: center;
      }
      .k-lead-desc {
        font-size: 12px;
        color: ${isDark ? '#8A8A93' : '#6E6E73'};
        margin-bottom: 20px;
        text-align: center;
        line-height: 1.4;
      }
      .k-lead-form {
        display: flex;
        flex-direction: column;
        gap: 12px;
      }
      .k-lead-field {
        display: flex;
        flex-direction: column;
        gap: 4px;
      }
      .k-lead-field label {
        font-size: 10px;
        font-weight: 600;
        text-transform: uppercase;
        color: ${isDark ? '#8A8A93' : '#6E6E73'};
        letter-spacing: 0.05em;
      }
      .k-lead-input {
        width: 100%;
        background: ${isDark ? 'rgba(255, 255, 255, 0.05)' : 'rgba(0, 0, 0, 0.03)'};
        border: 1px solid ${isDark ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.1)'};
        border-radius: 8px;
        padding: 9px 12px;
        font-size: 13px;
        color: inherit;
        outline: none;
        transition: border-color 0.2s;
      }
      .k-lead-input:focus {
        border-color: ${brandColor};
      }
      .k-lead-submit {
        background: ${brandColor};
        color: white;
        border: none;
        border-radius: 8px;
        padding: 11px;
        font-weight: 600;
        font-size: 13px;
        cursor: pointer;
        transition: opacity 0.2s;
        margin-top: 8px;
      }
      .k-lead-submit:hover {
        opacity: 0.9;
      }

      /* Input bar */
      .k-widget-input-bar {
        padding: 12px;
        border-t: 1px solid ${isDark ? 'rgba(255, 255, 255, 0.08)' : 'rgba(0, 0, 0, 0.08)'};
        display: flex;
        gap: 8px;
        align-items: center;
        background: ${isDark ? 'rgba(15, 15, 20, 0.98)' : '#ffffff'};
        flex-shrink: 0;
      }
      #k-widget-textarea {
        flex: 1;
        background: ${isDark ? 'rgba(255, 255, 255, 0.05)' : 'rgba(0, 0, 0, 0.03)'};
        border: 1px solid ${isDark ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.1)'};
        border-radius: 20px;
        padding: 8px 14px;
        font-size: 13px;
        color: inherit;
        outline: none;
        resize: none;
        height: 36px;
        line-height: 1.4;
        transition: border-color 0.2s;
        overflow-y: hidden;
      }
      #k-widget-textarea:focus {
        border-color: ${brandColor};
      }
      #k-widget-send-btn {
        width: 36px;
        height: 36px;
        border-radius: 50%;
        background: ${brandColor};
        border: none;
        outline: none;
        cursor: pointer;
        display: flex;
        align-items: center;
        justify-content: center;
        flex-shrink: 0;
        transition: opacity 0.2s, transform 0.2s;
      }
      #k-widget-send-btn:hover {
        transform: scale(1.05);
      }
      #k-widget-send-btn:disabled {
        opacity: 0.4;
        cursor: not-allowed;
      }
      #k-widget-send-btn svg {
        width: 16px;
        height: 16px;
        fill: white;
      }

      /* Branding footer */
      .k-widget-branding {
        text-align: center;
        padding: 6px;
        font-size: 9px;
        color: ${isDark ? '#8A8A93' : '#6E6E73'};
        border-top: 1px solid ${isDark ? 'rgba(255, 255, 255, 0.05)' : 'rgba(0, 0, 0, 0.04)'};
        flex-shrink: 0;
      }

      /* Loader / Bouncing dots */
      .k-loader {
        display: flex;
        gap: 4px;
        align-items: center;
        padding: 10px 14px;
      }
      .k-dot {
        width: 6px;
        height: 6px;
        background: ${isDark ? '#8A8A93' : '#6E6E73'};
        border-radius: 50%;
        animation: k-bounce 1.4s infinite ease-in-out both;
      }
      .k-dot:nth-child(1) { animation-delay: -0.32s; }
      .k-dot:nth-child(2) { animation-delay: -0.16s; }

      @keyframes k-bounce {
        0%, 80%, 100% { transform: scale(0); }
        40% { transform: scale(1.0); }
      }
      @keyframes k-pulse {
        0% { box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.4); }
        70% { box-shadow: 0 0 0 6px rgba(16, 185, 129, 0); }
        100% { box-shadow: 0 0 0 0 rgba(16, 185, 129, 0); }
      }

      /* Mobile responsivess */
      @media (max-width: 480px) {
        #k-widget-container {
          bottom: 0 !important;
          right: 0 !important;
          left: 0 !important;
          width: 100% !important;
          height: 100% !important;
          pointer-events: none;
        }
        #k-widget-fab {
          pointer-events: auto;
          position: fixed;
          bottom: 16px;
          right: 16px;
        }
        #k-widget-box {
          pointer-events: auto;
          width: 100% !important;
          height: 100% !important;
          max-height: 100% !important;
          border-radius: 0 !important;
          bottom: 0 !important;
          left: 0 !important;
          margin-bottom: 0 !important;
          border: none !important;
        }
      }
    `;

    var styleTag = document.createElement('style');
    styleTag.innerHTML = css;
    document.head.appendChild(styleTag);

    // Create Widget DOM Container
    var container = document.createElement('div');
    container.id = 'k-widget-container';
    container.className = position === 'bottom-left' ? 'k-pos-bottom-left' : 'k-pos-bottom-right';

    // HTML Skeleton
    var html = `
      <div id="k-widget-box">
        <div class="k-widget-header">
          <div class="k-header-info">
            <div class="k-header-avatar">K</div>
            <div>
              <div class="k-header-title">${widgetConfig.name || 'Assistant'}</div>
              <div class="k-header-status"><span class="k-status-dot"></span> Online</div>
            </div>
          </div>
          <button class="k-close-btn" id="k-widget-close-x">✕</button>
        </div>

        <div id="k-widget-messages"></div>

        <div class="k-widget-input-bar">
          <textarea id="k-widget-textarea" placeholder="Type a message..." disabled></textarea>
          <button id="k-widget-send-btn" disabled>
            <svg viewBox="0 0 24 24"><path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/></svg>
          </button>
        </div>
        <div class="k-widget-branding">Powered by Kautilya AI</div>
      </div>

      <button id="k-widget-fab">
        <svg viewBox="0 0 24 24" id="k-fab-chat-icon"><path d="M20 2H4c-1.1 0-1.99.9-1.99 2L2 22l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zM6 9h12v2H6V9zm8 5H6v-2h8v2zm4-6H6V6h12v2z"/></svg>
      </button>
    `;

    container.innerHTML = html;
    document.body.appendChild(container);

    // Bind DOM events
    var fab = document.getElementById('k-widget-fab');
    var box = document.getElementById('k-widget-box');
    var closeX = document.getElementById('k-widget-close-x');
    var textarea = document.getElementById('k-widget-textarea');
    var sendBtn = document.getElementById('k-widget-send-btn');
    var messagesDiv = document.getElementById('k-widget-messages');

    fab.addEventListener('click', toggleWidget);
    closeX.addEventListener('click', toggleWidget);

    function toggleWidget() {
      var isOpen = box.classList.contains('open');
      if (isOpen) {
        box.classList.remove('open');
        fab.classList.remove('active');
        fab.style.display = 'flex';
      } else {
        box.classList.add('open');
        fab.classList.add('active');
        // Hide FAB on mobile viewport when open
        if (window.innerWidth <= 480) {
          fab.style.display = 'none';
        }
        
        // Show Lead Form or Welcome message
        if (!isLeadSubmitted && widgetConfig.lead_capture && widgetConfig.lead_capture.enabled) {
          showLeadForm();
        } else if (messagesDiv.children.length === 0) {
          appendMessage('agent', widgetConfig.welcome_message || greeting);
          enableInput();
        }
        textarea.focus();
      }
    }

    if (autoOpen) {
      setTimeout(function() {
        if (!box.classList.contains('open')) {
          toggleWidget();
        }
      }, 5000);
    }

    // Input handlers
    textarea.addEventListener('keydown', function(e) {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
      }
    });

    sendBtn.addEventListener('click', sendMessage);

    function enableInput() {
      textarea.disabled = false;
      sendBtn.disabled = false;
      textarea.placeholder = "Type a message...";
    }

    // 4. Lead Capture UI Overlay
    function showLeadForm() {
      var overlay = document.createElement('div');
      overlay.id = 'k-lead-overlay';
      
      var fields = widgetConfig.lead_capture.fields || ['name', 'email', 'phone'];
      var hasName = fields.indexOf('name') !== -1;
      var hasEmail = fields.indexOf('email') !== -1;
      var hasPhone = fields.indexOf('phone') !== -1;

      var fieldsHtml = '';
      if (hasName) {
        fieldsHtml += `
          <div class="k-lead-field">
            <label>Name</label>
            <input type="text" class="k-lead-input" id="k-lead-name" placeholder="Your name" required />
          </div>
        `;
      }
      if (hasEmail) {
        fieldsHtml += `
          <div class="k-lead-field">
            <label>Email</label>
            <input type="email" class="k-lead-input" id="k-lead-email" placeholder="Your email address" required />
          </div>
        `;
      }
      if (hasPhone) {
        fieldsHtml += `
          <div class="k-lead-field">
            <label>Phone</label>
            <input type="tel" class="k-lead-input" id="k-lead-phone" placeholder="Mobile number" required />
          </div>
        `;
      }

      overlay.innerHTML = `
        <div class="k-lead-title">Get Started</div>
        <div class="k-lead-desc">Please share your details to initiate the chat session with our team.</div>
        <form class="k-lead-form" id="k-lead-form-element">
          ${fieldsHtml}
          <button type="submit" class="k-lead-submit">Start Conversation</button>
        </form>
      `;

      box.appendChild(overlay);

      var form = document.getElementById('k-lead-form-element');
      form.addEventListener('submit', function(e) {
        e.preventDefault();
        
        var nameVal = hasName ? document.getElementById('k-lead-name').value : '';
        var emailVal = hasEmail ? document.getElementById('k-lead-email').value : '';
        var phoneVal = hasPhone ? document.getElementById('k-lead-phone').value : '';

        // Save Lead to backend
        var leadUrl = baseUrl + '/api/embed/' + agentId + '/lead';
        
        fetch(leadUrl, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-Kautilya-Embed-Token': token || ''
          },
          body: JSON.stringify({
            token: token,
            name: nameVal,
            email: emailVal,
            phone: phoneVal,
            message: 'Initiated conversation via website chat widget.'
          })
        }).catch(function(err) {
          console.warn('[Kautilya Widget] Lead sync warning:', err.message);
        });

        // Close Overlay and Start Chat
        isLeadSubmitted = true;
        box.removeChild(overlay);
        
        // Greet user
        appendMessage('agent', widgetConfig.welcome_message || greeting);
        enableInput();
        textarea.focus();
      });
    }

    // Helper to format simple markdown (bold, links) safely
    function parseMarkdown(text) {
      if (!text) return '';
      // Escape HTML to prevent XSS
      var temp = document.createElement('div');
      temp.textContent = text;
      var escaped = temp.innerHTML;

      // Format bold: **text** -> <strong>text</strong>
      escaped = escaped.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');

      // Format links: [text](url) -> <a href="$2" target="_blank" rel="noopener noreferrer">$1</a>
      escaped = escaped.replace(/\[([^\]]+)\]\(((?:https?:\/\/|mailto:|tel:)[^\s\)"]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>');

      return escaped;
    }

    // 5. Message List Rendering Helper
    function appendMessage(role, text) {
      var msgDiv = document.createElement('div');
      msgDiv.className = 'k-message ' + (role === 'user' ? 'k-msg-user' : 'k-msg-agent');
      if (role === 'agent') {
        msgDiv.innerHTML = parseMarkdown(text);
      } else {
        msgDiv.textContent = text;
      }
      messagesDiv.appendChild(msgDiv);
      messagesDiv.scrollTop = messagesDiv.scrollHeight;
      return msgDiv;
    }

    function showTypingIndicator() {
      var loader = document.createElement('div');
      loader.id = 'k-widget-typing';
      loader.className = 'k-message k-msg-agent k-loader';
      loader.innerHTML = '<span class="k-dot"></span><span class="k-dot"></span><span class="k-dot"></span>';
      messagesDiv.appendChild(loader);
      messagesDiv.scrollTop = messagesDiv.scrollHeight;
    }

    function removeTypingIndicator() {
      var loader = document.getElementById('k-widget-typing');
      if (loader) messagesDiv.removeChild(loader);
    }

    // 6. Streaming SSE Message Delivery
    async function sendMessage() {
      var text = textarea.value.trim();
      if (!text || isStreaming) return;

      textarea.value = '';
      appendMessage('user', text);
      chatHistory.push({ role: 'user', content: text });

      isStreaming = true;
      textarea.disabled = true;
      sendBtn.disabled = true;

      showTypingIndicator();

      var chatUrl = baseUrl + '/api/embed/' + agentId + '/chat';
      var payload = {
        token: token,
        history: chatHistory.slice(-10),
        message: text
      };

      try {
        var response = await fetch(chatUrl, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-Kautilya-Embed-Token': token || ''
          },
          body: JSON.stringify(payload)
        });

        removeTypingIndicator();

        if (!response.ok) {
          throw new Error('Server responded with ' + response.status);
        }

        var reader = response.body.getReader();
        var decoder = new TextDecoder();
        var buffer = '';
        var accumulated = '';
        var messageBubble = null;

        while (true) {
          var chunkRes = await reader.read();
          if (chunkRes.done) break;

          buffer += decoder.decode(chunkRes.value, { stream: true });
          var lines = buffer.split('\n');
          buffer = lines.pop(); // Keep partial line in buffer

          for (var i = 0; i < lines.length; i++) {
            var line = lines[i].trim();
            if (!line) continue;

            if (line.indexOf('data: ') === 0) {
              var dataStr = line.slice(6).trim();
              if (dataStr === '[DONE]') {
                break;
              }
              try {
                var parsed = JSON.parse(dataStr);
                var chunk = parsed.chunk || '';
                if (chunk) {
                  accumulated += chunk;
                  if (!messageBubble) {
                    messageBubble = appendMessage('agent', '');
                  }
                  messageBubble.innerHTML = parseMarkdown(accumulated);
                  messagesDiv.scrollTop = messagesDiv.scrollHeight;
                }
              } catch (e) {
                // non-JSON fallback
              }
            }
          }
        }

        if (accumulated) {
          chatHistory.push({ role: 'assistant', content: accumulated });
        } else {
          appendMessage('agent', 'Sorry, I encountered an issue generating a response.');
        }

      } catch (err) {
        removeTypingIndicator();
        console.error('[Kautilya Widget] error:', err);
        appendMessage('agent', 'Connection error. Please try again.');
      } finally {
        isStreaming = false;
        enableInput();
        textarea.focus();
      }
    }
  }
})();
