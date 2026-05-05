/**
 * Kautilya AI - Production-Ready Chat Interface
 * Strategic Intelligence with Indian Soul
 */

class KautilyaChat {
    constructor() {
        this.currentModel = 'daily';
        this.messages = [];
        this.isStreaming = false;
        this.sessionId = this.generateSessionId();
        
        this.init();
    }

    init() {
        this.bindEvents();
        this.loadSession();
        this.autoResizeTextarea();
    }

    generateSessionId() {
        return 'session_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
    }

    bindEvents() {
        // Model selection
        document.querySelectorAll('.model-btn').forEach(btn => {
            btn.addEventListener('click', (e) => this.selectModel(e.target.dataset.model));
        });

        // Send message
        document.getElementById('sendBtn').addEventListener('click', () => this.sendMessage());
        document.getElementById('messageInput').addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
        });

        // Shortcuts
        document.querySelectorAll('.shortcut-chip').forEach(chip => {
            chip.addEventListener('click', () => {
                const prompt = chip.dataset.prompt;
                document.getElementById('messageInput').value = prompt;
                document.getElementById('messageInput').focus();
            });
        });

        // File attachment
        document.getElementById('attachBtn').addEventListener('click', () => {
            document.getElementById('fileInput').click();
        });

        document.getElementById('fileInput').addEventListener('change', (e) => {
            this.handleFileUpload(e.target.files);
        });

        // New chat
        document.getElementById('newChatBtn').addEventListener('click', () => this.newChat());

        // Logout
        document.getElementById('logoutBtn').addEventListener('click', () => this.logout());

        // Navigation
        document.getElementById('navPersonas').addEventListener('click', (e) => {
            e.preventDefault();
            this.showToast('Personas coming soon', 'info');
        });

        document.getElementById('navKnowledge').addEventListener('click', (e) => {
            e.preventDefault();
            this.showToast('Knowledge Base coming soon', 'info');
        });

        document.getElementById('navSettings').addEventListener('click', (e) => {
            e.preventDefault();
            this.showToast('Settings coming soon', 'info');
        });
    }

    selectModel(model) {
        this.currentModel = model;
        
        // Update UI
        document.querySelectorAll('.model-btn').forEach(btn => {
            if (btn.dataset.model === model) {
                btn.classList.add('text-indigo-600', 'dark:text-indigo-300', 'border-indigo-600');
                btn.classList.remove('text-slate-500', 'dark:text-slate-400', 'border-transparent');
            } else {
                btn.classList.remove('text-indigo-600', 'dark:text-indigo-300', 'border-indigo-600');
                btn.classList.add('text-slate-500', 'dark:text-slate-400', 'border-transparent');
            }
        });

        this.showToast(`Switched to Kautilya ${model.charAt(0).toUpperCase() + model.slice(1)}`, 'info');
    }

    async sendMessage() {
        if (this.isStreaming) return;

        const input = document.getElementById('messageInput');
        const message = input.value.trim();

        if (!message) return;

        // Clear input
        input.value = '';
        input.style.height = 'auto';

        // Hide empty state
        document.getElementById('emptyState').classList.add('hidden');

        // Add user message
        this.addMessageToUI('user', message);
        this.messages.push({ role: 'user', content: message });

        // Show loading
        this.isStreaming = true;
        const assistantMessageId = this.addMessageToUI('assistant', '');
        const assistantElement = document.getElementById(assistantMessageId);

        try {
            await this.streamResponse(assistantElement);
        } catch (error) {
            console.error('Chat error:', error);
            this.showToast('Failed to get response. Please try again.', 'error');
            assistantElement.querySelector('.message-content').innerHTML = '<p class="text-error">Sorry, something went wrong. Please try again.</p>';
        } finally {
            this.isStreaming = false;
        }
    }

    addMessageToUI(role, content) {
        const container = document.getElementById('messagesContainer');
        const messageId = 'msg_' + Date.now();
        
        const messageHtml = role === 'user' 
            ? this.createUserMessageHtml(messageId, content)
            : this.createAssistantMessageHtml(messageId, content);

        container.insertAdjacentHTML('beforeend', messageHtml);
        
        // Scroll to bottom
        const chatFeed = document.getElementById('chatFeed');
        chatFeed.scrollTop = chatFeed.scrollHeight;

        return messageId;
    }

    createUserMessageHtml(messageId, content) {
        return `
<div id="${messageId}" class="flex flex-col items-end w-full group">
<div class="max-w-[85%] bg-surfaceContainerHigh text-onSurface px-5 py-4 rounded-2xl rounded-tr-sm shadow-sm font-bodyMd text-bodyMd leading-relaxed">
${this.escapeHtml(content)}
</div>
</div>`;
    }

    createAssistantMessageHtml(messageId, content = '') {
        return `
<div id="${messageId}" class="flex flex-col items-start w-full group">
<div class="flex items-center gap-3 mb-3 text-onSurfaceVariant font-medium">
<div class="w-6 h-6 rounded-md bg-primary flex items-center justify-center text-onPrimary">
<span class="material-symbols-outlined text-[14px]">psychology</span>
</div>
<span class="text-sm">Kautilya AI</span>
<span class="text-xs text-outline ml-2">Kautilya ${this.currentModel.charAt(0).toUpperCase() + this.currentModel.slice(1)}</span>
</div>
<div class="w-full text-onBackground font-bodyLg text-bodyLg leading-relaxed space-y-6 message-content">
${content ? this.formatMessage(content) : '<div class="typing-indicator"><span></span><span></span><span></span></div>'}
</div>
<div class="flex items-center gap-2 mt-4 opacity-0 group-hover:opacity-100 transition-opacity">
<button class="action-btn p-1.5 rounded-md text-outline hover:bg-surfaceContainer hover:text-onSurface transition-colors" title="Copy" data-action="copy">
<span class="material-symbols-outlined text-[18px]">content_copy</span>
</button>
<button class="action-btn p-1.5 rounded-md text-outline hover:bg-surfaceContainer hover:text-onSurface transition-colors" title="Regenerate" data-action="regenerate">
<span class="material-symbols-outlined text-[18px]">refresh</span>
</button>
<button class="action-btn p-1.5 rounded-md text-outline hover:bg-surfaceContainer hover:text-onSurface transition-colors" title="Good response" data-action="like">
<span class="material-symbols-outlined text-[18px]">thumb_up</span>
</button>
</div>
</div>`;
    }

    async streamResponse(element) {
        const contentElement = element.querySelector('.message-content');
        const typingIndicator = contentElement.querySelector('.typing-indicator');
        
        if (typingIndicator) {
            typingIndicator.remove();
        }

        let fullContent = '';
        
        try {
            const response = await fetch('/api/jarvis/stream', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    message: this.messages[this.messages.length - 1].content,
                    model: this.currentModel,
                    session_id: this.sessionId
                })
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const reader = response.body.getReader();
            const decoder = new TextDecoder();

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                const chunk = decoder.decode(value);
                const lines = chunk.split('\n');

                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        const data = line.slice(6);
                        if (data === '[DONE]') continue;

                        try {
                            const parsed = JSON.parse(data);
                            if (parsed.chunk) {
                                fullContent += parsed.chunk;
                                contentElement.innerHTML = this.formatMessage(fullContent);
                                
                                // Auto-scroll
                                const chatFeed = document.getElementById('chatFeed');
                                chatFeed.scrollTop = chatFeed.scrollHeight;
                            }
                        } catch (e) {
                            // Skip invalid JSON
                        }
                    }
                }
            }

            // Save assistant message
            this.messages.push({ role: 'assistant', content: fullContent });
            this.saveSession();

            // Bind action buttons
            this.bindActionButtons(element);

        } catch (error) {
            throw error;
        }
    }

    bindActionButtons(element) {
        element.querySelectorAll('.action-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                const action = btn.dataset.action;
                const content = element.querySelector('.message-content').textContent;

                switch (action) {
                    case 'copy':
                        this.copyToClipboard(content);
                        this.showToast('Copied to clipboard', 'success');
                        break;
                    case 'regenerate':
                        this.regenerateResponse();
                        break;
                    case 'like':
                        this.showToast('Thanks for the feedback!', 'success');
                        break;
                }
            });
        });
    }

    async regenerateResponse() {
        if (this.isStreaming) return;

        // Remove last assistant message
        this.messages.pop();
        
        // Remove last message from UI
        const container = document.getElementById('messagesContainer');
        const lastMessage = container.lastElementChild;
        if (lastMessage) {
            lastMessage.remove();
        }

        // Resend last user message
        const lastUserMessage = this.messages[this.messages.length - 1];
        if (lastUserMessage && lastUserMessage.role === 'user') {
            await this.sendMessage();
        }
    }

    formatMessage(content) {
        // Convert markdown-like syntax to HTML
        let formatted = this.escapeHtml(content);
        
        // Code blocks
        formatted = formatted.replace(/```(\w+)?\n([\s\S]*?)```/g, (match, lang, code) => {
            return `<div class="rounded-xl overflow-hidden border border-outlineVariant/30 bg-[#1e1e1e] my-4">
<div class="flex items-center justify-between px-4 py-2 bg-inverseSurface text-inverseOnSurface border-b border-white/10 font-code text-[12px]">
<span>${lang || 'code'}</span>
<button class="flex items-center gap-1 hover:text-white transition-colors" onclick="navigator.clipboard.writeText(\`${code.replace(/`/g, '\\`')}\`); this.innerHTML='Copied!'; setTimeout(() => this.innerHTML='<span class=\\'material-symbols-outlined text-[14px]\\'>content_copy</span> Copy', 1500);">
<span class="material-symbols-outlined text-[14px]">content_copy</span> Copy
</button>
</div>
<div class="p-4 overflow-x-auto">
<pre class="font-code text-code text-[#d4d4d4]"><code>${this.escapeHtml(code)}</code></pre>
</div>
</div>`;
        });

        // Inline code
        formatted = formatted.replace(/`([^`]+)`/g, '<code class="bg-surfaceContainer px-1.5 py-0.5 rounded font-code text-sm">$1</code>');

        // Bold
        formatted = formatted.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');

        // Italic
        formatted = formatted.replace(/\*([^*]+)\*/g, '<em>$1</em>');

        // Headers
        formatted = formatted.replace(/^### (.+)$/gm, '<h3 class="font-h2 text-h2 text-onSurface mb-3 mt-6">$1</h3>');
        formatted = formatted.replace(/^## (.+)$/gm, '<h2 class="font-h2 text-h2 text-onSurface mb-3 mt-6">$1</h2>');
        formatted = formatted.replace(/^# (.+)$/gm, '<h1 class="font-h1 text-h1 text-onBackground mb-4 mt-6">$1</h1>');

        // Lists
        formatted = formatted.replace(/^- (.+)$/gm, '<li class="ml-5">$1</li>');
        formatted = formatted.replace(/(<li[^>]*>.*<\/li>\n?)+/g, '<ul class="list-disc pl-5 space-y-2 text-onSurfaceVariant">$&</ul>');

        // Paragraphs
        formatted = formatted.replace(/\n\n/g, '</p><p class="mb-4">');
        formatted = '<p class="mb-4">' + formatted + '</p>';

        return formatted;
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    copyToClipboard(text) {
        navigator.clipboard.writeText(text).catch(err => {
            console.error('Copy failed:', err);
        });
    }

    handleFileUpload(files) {
        if (files.length === 0) return;
        
        this.showToast(`${files.length} file(s) attached`, 'info');
        // TODO: Implement file upload logic
    }

    newChat() {
        this.messages = [];
        this.sessionId = this.generateSessionId();
        document.getElementById('messagesContainer').innerHTML = '';
        document.getElementById('emptyState').classList.remove('hidden');
        this.showToast('New conversation started', 'info');
    }

    logout() {
        // TODO: Implement logout logic
        this.showToast('Logging out...', 'info');
    }

    loadSession() {
        // TODO: Load previous session from localStorage or API
    }

    saveSession() {
        // TODO: Save session to localStorage or API
    }

    autoResizeTextarea() {
        const textarea = document.getElementById('messageInput');
        textarea.addEventListener('input', () => {
            textarea.style.height = 'auto';
            textarea.style.height = Math.min(textarea.scrollHeight, 192) + 'px';
        });
    }

    showToast(message, type = 'info') {
        // Simple toast notification
        const toast = document.createElement('div');
        toast.className = `fixed bottom-20 right-6 px-4 py-2 rounded-lg shadow-lg text-sm font-medium z-50 transition-all duration-300 transform translate-y-0 opacity-100`;
        
        if (type === 'success') {
            toast.classList.add('bg-green-600', 'text-white');
        } else if (type === 'error') {
            toast.classList.add('bg-red-600', 'text-white');
        } else {
            toast.classList.add('bg-surfaceContainerHigh', 'text-onSurface', 'border', 'border-outlineVariant');
        }
        
        toast.textContent = message;
        document.body.appendChild(toast);
        
        setTimeout(() => {
            toast.classList.add('opacity-0', 'translate-y-2');
            setTimeout(() => toast.remove(), 300);
        }, 3000);
    }
}

// Initialize app when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.kautilyaChat = new KautilyaChat();
});
