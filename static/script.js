/**
 * KAUTILYA AI - Premium UI Script
 * Features: Claude-style thinking, tool execution, dark/light mode, TTS, copy
 */

class KautilyaApp {
    constructor() {
        this.sessionId = localStorage.getItem('kautilya_session') || this.generateSessionId();
        this.currentChatId = null;
        this.messages = [];
        this.isProcessing = false;
        this.ttsEnabled = localStorage.getItem('kautilya_tts') !== 'false';
        this.currentTheme = localStorage.getItem('kautilya_theme') || 'dark';
        this.auth = firebase.auth();
        this.user = null;
        
        // DOM Elements
        this.elements = {
            splash: document.getElementById('splashScreen'),
            sidebar: document.getElementById('appSidebar'),
            chatContainer: document.getElementById('chatContainer'),
            chatContent: document.getElementById('chatContent'),
            welcomeScreen: document.getElementById('welcomeScreen'),
            messageInput: document.getElementById('messageInput'),
            sendBtn: document.getElementById('sendBtn'),
            attachBtn: document.getElementById('attachBtn'),
            fileInput: document.getElementById('fileInput'),
            recentList: document.getElementById('recentList'),
            newChatBtn: document.getElementById('newChatBtn'),
            toggleSidebar: document.getElementById('toggleSidebar'),
            themeToggle: document.getElementById('themeToggle'),
            themeIcon: document.getElementById('themeIcon'),
            modelSelector: document.getElementById('modelSelector'),
            loginBtn: document.getElementById('loginBtn'),
            loginModal: document.getElementById('loginModal'),
            closeLoginModal: document.getElementById('closeLoginModal'),
            googleSignIn: document.getElementById('googleSignIn'),
            loginEmail: document.getElementById('loginEmail'),
            loginPassword: document.getElementById('loginPassword'),
            loginSubmitBtn: document.getElementById('loginSubmitBtn'),
            sidebarProfile: document.getElementById('sidebarProfile'),
            sidebarUsername: document.getElementById('sidebarUsername'),
            sidebarAvatarImg: document.getElementById('sidebarAvatarImg'),
            userBadge: document.getElementById('userBadge'),
            settingsModal: document.getElementById('settingsModal'),
            closeSettingsModal: document.getElementById('closeSettingsModal'),
            settingsTabs: document.querySelectorAll('.settings-tab'),
            settingsSections: document.querySelectorAll('.settings-section'),
            themeSelect: document.getElementById('themeSelect'),
            artifactPanel: document.getElementById('artifactPanel'),
            artifactCloseBtn: document.getElementById('artifactCloseBtn'),
            artifactTabs: document.querySelectorAll('.artifact-tab'),
            artifactPreviewFrame: document.getElementById('artifactPreviewFrame'),
            artifactCodeView: document.getElementById('artifactCodeView'),
            artifactCodeContent: document.getElementById('artifactCodeContent'),
            audioPlayer: document.getElementById('audioPlayer')
        };
        
        this.init();
    }
    
    generateSessionId() {
        const id = 'sess_' + Math.random().toString(36).substr(2, 9);
        localStorage.setItem('kautilya_session', id);
        return id;
    }
    
    init() {
        this.applyTheme();
        this.bindEvents();
        this.setupFirebaseAuth();
        this.hideSplash();
        this.loadChats();
        this.startHeartbeat();
    }
    
    /* =========================================
       THEME MANAGEMENT
       ========================================= */
    applyTheme() {
        document.documentElement.setAttribute('data-theme', this.currentTheme);
        this.updateThemeIcon();
        if (this.elements.themeSelect) {
            this.elements.themeSelect.value = this.currentTheme;
        }
    }
    
    toggleTheme() {
        this.currentTheme = this.currentTheme === 'dark' ? 'light' : 'dark';
        localStorage.setItem('kautilya_theme', this.currentTheme);
        this.applyTheme();
    }
    
    updateThemeIcon() {
        if (this.elements.themeIcon) {
            this.elements.themeIcon.textContent = this.currentTheme === 'dark' ? 'light_mode' : 'dark_mode';
        }
    }
    
    /* =========================================
       SPLASH SCREEN
       ========================================= */
    hideSplash() {
        setTimeout(() => {
            if (this.elements.splash) {
                this.elements.splash.classList.add('shrink-out');
                setTimeout(() => {
                    this.elements.splash.classList.add('hidden');
                }, 600);
            }
        }, 2000);
    }
    
    /* =========================================
       EVENT BINDING
       ========================================= */
    bindEvents() {
        // Sidebar toggle
        this.elements.toggleSidebar?.addEventListener('click', () => {
            this.elements.sidebar.classList.toggle('open');
        });
        
        // New chat
        this.elements.newChatBtn?.addEventListener('click', () => this.startNewChat());
        
        // Theme toggle
        this.elements.themeToggle?.addEventListener('click', () => this.toggleTheme());
        
        // Message input
        this.elements.messageInput?.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
        });
        
        this.elements.messageInput?.addEventListener('input', () => {
            this.autoResizeTextarea();
        });
        
        // Send button
        this.elements.sendBtn?.addEventListener('click', () => this.sendMessage());
        
        // File attachment
        this.elements.attachBtn?.addEventListener('click', () => {
            this.elements.fileInput?.click();
        });
        
        this.elements.fileInput?.addEventListener('change', (e) => {
            this.handleFileSelect(e.target.files);
        });
        
        // Suggestion chips
        document.querySelectorAll('.chip').forEach(chip => {
            chip.addEventListener('click', () => {
                const prompt = chip.dataset.prompt;
                this.elements.messageInput.value = prompt;
                this.sendMessage();
            });
        });
        
        // Login modal
        this.elements.loginBtn?.addEventListener('click', () => this.openModal('loginModal'));
        this.elements.closeLoginModal?.addEventListener('click', () => this.closeModal('loginModal'));
        this.elements.googleSignIn?.addEventListener('click', () => this.signInWithGoogle());
        this.elements.loginSubmitBtn?.addEventListener('click', () => this.signInWithEmail());
        
        // Settings
        this.elements.sidebarProfile?.addEventListener('click', () => this.openModal('settingsModal'));
        this.elements.closeSettingsModal?.addEventListener('click', () => this.closeModal('settingsModal'));
        
        // Settings tabs
        this.elements.settingsTabs.forEach(tab => {
            tab.addEventListener('click', () => {
                const target = tab.dataset.target;
                this.switchSettingsTab(target);
            });
        });
        
        // Theme select
        this.elements.themeSelect?.addEventListener('change', (e) => {
            this.currentTheme = e.target.value;
            localStorage.setItem('kautilya_theme', this.currentTheme);
            this.applyTheme();
        });
        
        // Artifact panel
        this.elements.artifactCloseBtn?.addEventListener('click', () => this.closeArtifactPanel());
        this.elements.artifactTabs.forEach(tab => {
            tab.addEventListener('click', () => this.switchArtifactTab(tab.dataset.tab));
        });
        
        // Close modals on outside click
        document.querySelectorAll('.modal-overlay').forEach(modal => {
            modal.addEventListener('click', (e) => {
                if (e.target === modal) {
                    modal.classList.remove('show');
                }
            });
        });
    }
    
    autoResizeTextarea() {
        const textarea = this.elements.messageInput;
        textarea.style.height = 'auto';
        textarea.style.height = Math.min(textarea.scrollHeight, 200) + 'px';
    }
    
    openModal(modalId) {
        const modal = document.getElementById(modalId);
        if (modal) {
            modal.classList.add('show');
        }
    }
    
    closeModal(modalId) {
        const modal = document.getElementById(modalId);
        if (modal) {
            modal.classList.remove('show');
        }
    }
    
    switchSettingsTab(target) {
        this.elements.settingsTabs.forEach(tab => {
            tab.classList.toggle('active', tab.dataset.target === target);
        });
        this.elements.settingsSections.forEach(section => {
            section.classList.toggle('active', section.id === `settings-${target}`);
        });
    }
    
    /* =========================================
       AUTHENTICATION
       ========================================= */
    setupFirebaseAuth() {
        this.auth.onAuthStateChanged((user) => {
            this.user = user;
            this.updateAuthUI();
        });
    }
    
    updateAuthUI() {
        if (this.user) {
            this.elements.loginBtn.style.display = 'none';
            this.elements.sidebarProfile.style.display = 'flex';
            this.elements.sidebarUsername.textContent = this.user.displayName || this.user.email;
            this.elements.sidebarAvatarImg.src = this.user.photoURL || 'https://lh3.googleusercontent.com/a/default-user';
            this.elements.userBadge.style.display = 'flex';
        } else {
            this.elements.loginBtn.style.display = 'flex';
            this.elements.sidebarProfile.style.display = 'none';
            this.elements.userBadge.style.display = 'none';
        }
    }
    
    async signInWithGoogle() {
        const provider = new firebase.auth.GoogleAuthProvider();
        try {
            await this.auth.signInWithPopup(provider);
            this.closeModal('loginModal');
        } catch (error) {
            console.error('Google sign-in error:', error);
            alert('Sign-in failed: ' + error.message);
        }
    }
    
    async signInWithEmail() {
        const email = this.elements.loginEmail.value;
        const password = this.elements.loginPassword.value;
        if (!email || !password) {
            alert('Please enter email and password');
            return;
        }
        try {
            await this.auth.signInWithEmailAndPassword(email, password);
            this.closeModal('loginModal');
        } catch (error) {
            console.error('Email sign-in error:', error);
            alert('Sign-in failed: ' + error.message);
        }
    }
    
    /* =========================================
       CHAT MANAGEMENT
       ========================================= */
    startNewChat() {
        this.currentChatId = null;
        this.messages = [];
        this.elements.chatContent.innerHTML = '';
        this.elements.welcomeScreen.style.display = 'flex';
        this.elements.sidebar.classList.remove('open');
    }
    
    loadChats() {
        // Load recent chats from localStorage
        const chats = JSON.parse(localStorage.getItem('kautilya_chats') || '[]');
        this.renderRecentChats(chats);
    }
    
    renderRecentChats(chats) {
        if (!this.elements.recentList) return;
        
        this.elements.recentList.innerHTML = chats.slice(0, 10).map(chat => `
            <div class="recent-item ${chat.id === this.currentChatId ? 'active' : ''}" data-chat-id="${chat.id}">
                <span class="material-icons-round">chat</span>
                <span>${chat.title || 'New Chat'}</span>
            </div>
        `).join('');
        
        this.elements.recentList.querySelectorAll('.recent-item').forEach(item => {
            item.addEventListener('click', () => this.loadChat(item.dataset.chatId));
        });
    }
    
    loadChat(chatId) {
        // Load chat from localStorage or server
        const chats = JSON.parse(localStorage.getItem('kautilya_chats') || '[]');
        const chat = chats.find(c => c.id === chatId);
        if (chat) {
            this.currentChatId = chatId;
            this.messages = chat.messages || [];
            this.renderMessages();
            this.elements.welcomeScreen.style.display = 'none';
        }
    }
    
    saveChat() {
        if (!this.messages.length) return;
        
        const chats = JSON.parse(localStorage.getItem('kautilya_chats') || '[]');
        const title = this.messages[1]?.content?.slice(0, 30) + '...' || 'New Chat';
        
        if (this.currentChatId) {
            const index = chats.findIndex(c => c.id === this.currentChatId);
            if (index !== -1) {
                chats[index] = { id: this.currentChatId, title, messages: this.messages, updatedAt: Date.now() };
            }
        } else {
            this.currentChatId = 'chat_' + Date.now();
            chats.unshift({ id: this.currentChatId, title, messages: this.messages, updatedAt: Date.now() });
        }
        
        localStorage.setItem('kautilya_chats', JSON.stringify(chats.slice(0, 20)));
        this.renderRecentChats(chats);
    }
    
    /* =========================================
       MESSAGE HANDLING
       ========================================= */
    async sendMessage() {
        const content = this.elements.messageInput.value.trim();
        if (!content || this.isProcessing) return;
        
        // Hide welcome screen
        this.elements.welcomeScreen.style.display = 'none';
        
        // Add user message
        this.addMessage('user', content);
        this.elements.messageInput.value = '';
        this.autoResizeTextarea();
        
        // Show typing indicator
        this.showTypingIndicator();
        this.isProcessing = true;
        this.elements.sendBtn.disabled = true;
        
        try {
            // Get auth token
            const token = this.user ? await this.user.getIdToken() : null;
            
            // Send to API
            const response = await fetch('/api/chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': token ? `Bearer ${token}` : ''
                },
                body: JSON.stringify({
                    message: content,
                    session_id: this.sessionId,
                    chat_id: this.currentChatId,
                    model: this.elements.modelSelector.value
                })
            });
            
            const data = await response.json();
            
            // Remove typing indicator
            this.hideTypingIndicator();
            
            // Process response with thinking/tools
            await this.processAssistantResponse(data);
            
        } catch (error) {
            console.error('Chat error:', error);
            this.hideTypingIndicator();
            this.addMessage('assistant', 'Sorry, I encountered an error. Please try again.');
        } finally {
            this.isProcessing = false;
            this.elements.sendBtn.disabled = false;
            this.saveChat();
        }
    }
    
    async processAssistantResponse(data) {
        // Handle thinking/reasoning
        if (data.thinking) {
            this.addThinkingBlock(data.thinking);
        }
        
        // Handle tool executions
        if (data.tools && data.tools.length > 0) {
            for (const tool of data.tools) {
                await this.addToolCard(tool);
            }
        }
        
        // Add main response
        this.addMessage('assistant', data.response);
        
        // Handle TTS
        if (this.ttsEnabled && data.audio_url) {
            this.playTTS(data.audio_url);
        }
        
        // Handle artifacts
        if (data.artifact) {
            this.showArtifact(data.artifact);
        }
    }
    
    addMessage(role, content) {
        const message = { role, content, timestamp: Date.now() };
        this.messages.push(message);
        
        const messageEl = document.createElement('div');
        messageEl.className = `message ${role}-msg`;
        
        const avatarHtml = role === 'user' 
            ? `<div class="message-avatar"><span class="material-icons-round">person</span></div>`
            : `<div class="message-avatar"><img src="/static/kautilya_logo.png" alt="Kautilya"></div>`;
        
        const processedContent = this.processContent(content);
        
        messageEl.innerHTML = `
            ${avatarHtml}
            <div class="message-content">
                <div class="message-bubble">
                    ${processedContent}
                </div>
                ${role === 'assistant' ? this.getMessageActions() : ''}
            </div>
        `;
        
        this.elements.chatContent.appendChild(messageEl);
        this.scrollToBottom();
        
        // Bind action buttons
        if (role === 'assistant') {
            this.bindMessageActions(messageEl, content);
        }
        
        // Highlight code blocks
        messageEl.querySelectorAll('pre code').forEach((block) => {
            hljs.highlightBlock(block);
        });
        
        return messageEl;
    }
    
    processContent(content) {
        // Process markdown
        let processed = DOMPurify.sanitize(marked.parse(content));
        
        // Add copy buttons to code blocks
        processed = processed.replace(
            /<pre><code class="language-(\w+)">/g,
            `<div class="code-block"><div class="code-header"><span class="code-lang">$1</span><button class="code-copy-btn" onclick="copyCode(this)"><span class="material-icons-round" style="font-size: 14px;">content_copy</span> Copy</button></div><pre><code class="language-$1">`
        );
        processed = processed.replace(/<\/pre>/g, '</code></pre></div>');
        
        return processed;
    }
    
    getMessageActions() {
        return `
            <div class="message-actions">
                <button class="msg-action-btn" data-action="copy" title="Copy message">
                    <span class="material-icons-round">content_copy</span>
                </button>
                <button class="msg-action-btn" data-action="tts" title="Read aloud">
                    <span class="material-icons-round">volume_up</span>
                </button>
                <button class="msg-action-btn" data-action="regenerate" title="Regenerate">
                    <span class="material-icons-round">refresh</span>
                </button>
            </div>
        `;
    }
    
    bindMessageActions(messageEl, content) {
        const actions = messageEl.querySelectorAll('.msg-action-btn');
        actions.forEach(btn => {
            btn.addEventListener('click', () => {
                const action = btn.dataset.action;
                switch (action) {
                    case 'copy':
                        this.copyToClipboard(content, btn);
                        break;
                    case 'tts':
                        this.speakText(content);
                        break;
                    case 'regenerate':
                        this.regenerateMessage();
                        break;
                }
            });
        });
    }
    
    async copyToClipboard(text, btn) {
        try {
            await navigator.clipboard.writeText(text);
            btn.classList.add('copied');
            btn.innerHTML = '<span class="material-icons-round">check</span>';
            setTimeout(() => {
                btn.classList.remove('copied');
                btn.innerHTML = '<span class="material-icons-round">content_copy</span>';
            }, 2000);
        } catch (err) {
            console.error('Copy failed:', err);
        }
    }
    
    speakText(text) {
        // Strip HTML tags
        const plainText = text.replace(/<[^>]+>/g, '');
        const utterance = new SpeechSynthesisUtterance(plainText);
        utterance.rate = 1;
        utterance.pitch = 1;
        speechSynthesis.speak(utterance);
    }
    
    regenerateMessage() {
        // Remove last assistant message and resend
        this.messages = this.messages.filter(m => m.timestamp !== this.messages[this.messages.length - 1]?.timestamp);
        this.renderMessages();
        this.sendMessage();
    }
    
    /* =========================================
       THINKING / REASONING DISPLAY
       ========================================= */
    addThinkingBlock(thinking) {
        const thinkingEl = document.createElement('div');
        thinkingEl.className = 'thinking-container';
        thinkingEl.innerHTML = `
            <div class="thinking-header" onclick="this.parentElement.classList.toggle('open')">
                <span class="material-icons-round thinking-icon">psychology</span>
                <span class="thinking-label">Thinking...</span>
                <span class="material-icons-round thinking-toggle">expand_more</span>
            </div>
            <div class="thinking-content">${thinking}</div>
        `;
        
        this.elements.chatContent.appendChild(thinkingEl);
        this.scrollToBottom();
    }
    
    /* =========================================
       TOOL EXECUTION CARDS
       ========================================= */
    async addToolCard(tool) {
        const toolEl = document.createElement('div');
        toolEl.className = 'tool-card';
        toolEl.id = `tool-${tool.id}`;
        
        const iconMap = {
            'search': 'search',
            'code': 'code',
            'file': 'description',
            'browser': 'public',
            'calculator': 'calculate',
            'api': 'api'
        };
        
        const icon = iconMap[tool.type] || 'build';
        
        toolEl.innerHTML = `
            <div class="tool-header">
                <div class="tool-icon ${tool.status}">
                    <span class="material-icons-round">${icon}</span>
                </div>
                <span class="tool-name">${tool.name}</span>
                <span class="tool-status">${tool.status}</span>
            </div>
            <div class="tool-content ${tool.collapsed ? 'collapsed' : ''}">
                ${tool.output || 'Running...'}
            </div>
        `;
        
        this.elements.chatContent.appendChild(toolEl);
        this.scrollToBottom();
        
        // Animate status changes
        if (tool.status === 'running') {
            await this.animateToolExecution(tool.id);
        }
    }
    
    async animateToolExecution(toolId) {
        // Simulate tool execution animation
        await new Promise(resolve => setTimeout(resolve, 1000));
        const toolEl = document.getElementById(`tool-${toolId}`);
        if (toolEl) {
            const icon = toolEl.querySelector('.tool-icon');
            const status = toolEl.querySelector('.tool-status');
            icon.classList.remove('running');
            icon.classList.add('success');
            status.textContent = 'completed';
        }
    }
    
    /* =========================================
       ARTIFACT PANEL
       ========================================= */
    showArtifact(artifact) {
        this.elements.artifactTitle.textContent = artifact.title || 'Preview';
        this.elements.artifactCodeContent.textContent = artifact.code || '';
        
        if (artifact.preview) {
            this.elements.artifactPreviewFrame.srcdoc = artifact.preview;
        }
        
        this.elements.artifactPanel.classList.add('open');
        document.body.classList.add('artifact-open');
    }
    
    closeArtifactPanel() {
        this.elements.artifactPanel.classList.remove('open');
        document.body.classList.remove('artifact-open');
    }
    
    switchArtifactTab(tab) {
        this.elements.artifactTabs.forEach(t => {
            t.classList.toggle('active', t.dataset.tab === tab);
        });
        
        if (tab === 'preview') {
            this.elements.artifactPreviewFrame.classList.remove('hidden');
            this.elements.artifactCodeView.classList.add('hidden');
        } else {
            this.elements.artifactPreviewFrame.classList.add('hidden');
            this.elements.artifactCodeView.classList.remove('hidden');
        }
    }
    
    /* =========================================
       TTS
       ========================================= */
    playTTS(url) {
        this.elements.audioPlayer.src = url;
        this.elements.audioPlayer.play();
    }
    
    /* =========================================
       TYPING INDICATOR
       ========================================= */
    showTypingIndicator() {
        const indicator = document.createElement('div');
        indicator.className = 'message jarvis-msg typing-message';
        indicator.innerHTML = `
            <div class="message-avatar"><img src="/static/kautilya_logo.png" alt="Kautilya"></div>
            <div class="message-content">
                <div class="typing-indicator">
                    <span></span>
                    <span></span>
                    <span></span>
                </div>
            </div>
        `;
        indicator.id = 'typingIndicator';
        this.elements.chatContent.appendChild(indicator);
        this.scrollToBottom();
    }
    
    hideTypingIndicator() {
        const indicator = document.getElementById('typingIndicator');
        if (indicator) {
            indicator.remove();
        }
    }
    
    /* =========================================
       UTILITIES
       ========================================= */
    scrollToBottom() {
        this.elements.chatContainer.scrollTop = this.elements.chatContainer.scrollHeight;
    }
    
    handleFileSelect(files) {
        // Handle file upload
        console.log('Files selected:', files);
        // Implementation for file upload
    }
    
    renderMessages() {
        this.elements.chatContent.innerHTML = '';
        if (this.messages.length === 0) {
            this.elements.welcomeScreen.style.display = 'flex';
            return;
        }
        this.elements.welcomeScreen.style.display = 'none';
        this.messages.forEach(msg => this.addMessage(msg.role, msg.content));
    }
    
    startHeartbeat() {
        setInterval(async () => {
            try {
                await fetch('/api/health');
            } catch (e) {
                // Silent fail
            }
        }, 60000);
    }
}

// Global function for copying code blocks
window.copyCode = function(btn) {
    const code = btn.closest('.code-block').querySelector('code').textContent;
    navigator.clipboard.writeText(code).then(() => {
        const original = btn.innerHTML;
        btn.innerHTML = '<span class="material-icons-round" style="font-size: 14px;">check</span> Copied!';
        setTimeout(() => btn.innerHTML = original, 2000);
    });
};

// Initialize app
document.addEventListener('DOMContentLoaded', () => {
    window.app = new KautilyaApp();
});
