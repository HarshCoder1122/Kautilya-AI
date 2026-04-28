/**
 * KAUTILYA AI Cloud — Gemini/ChatGPT UI with Persistent Chat History
 * Features: localStorage chat persistence, sidebar history, markdown + code blocks,
 *           voice mode, optional Firebase Auth
 */

// ============== Global Image Viewer ==============
window.openImageViewer = function (url) {
    const modal = document.getElementById('imageViewerModal');
    const img = document.getElementById('fullscreenImage');
    if (modal && img) {
        img.src = url;
        modal.classList.add('show');
    }
};

// ============== Chat History Manager ==============
class ChatHistoryManager {
    constructor() {
        this.chats = {}; // In-memory storage (Removed localStorage)
        this.activeChatId = null;
    }

    getAllChats() {
        return this.chats;
    }

    getChat(chatId) {
        return this.chats[chatId] || null;
    }

    saveChat(chatId, chatData) {
        this.chats[chatId] = chatData;
    }

    deleteChat(chatId) {
        delete this.chats[chatId];
    }

    getActiveChatId() {
        return this.activeChatId;
    }

    setActiveChatId(chatId) {
        this.activeChatId = chatId;
    }

    getSortedChats() {
        return Object.entries(this.chats)
            .map(([id, data]) => ({ id, ...data }))
            .sort((a, b) => (b.updatedAt || 0) - (a.updatedAt || 0));
    }

    generateTitle(firstMessage) {
        const clean = firstMessage.trim();
        if (clean.length <= 40) return clean;
        return clean.substring(0, 37) + '...';
    }
}

// ============== Firebase Auth Manager ==============
class FirebaseAuthManager {
    constructor(app) {
        this.app = app; // JarvisCloudApp reference
        this.user = null;
        this.auth = typeof firebase !== 'undefined' ? firebase.auth() : null;
    }

    init() {
        if (!this.auth) {
            console.warn('[Auth] Firebase not loaded, running in guest mode');
            return;
        }
        this.auth.onAuthStateChanged((user) => {
            this.user = user;
            this.app.onAuthChanged(user);
            if (user) {
                this.app.syncHistory();
            }
        });
    }

    async signInWithGoogle() {
        if (!this.auth) return;
        const provider = new firebase.auth.GoogleAuthProvider();
        try {
            await this.auth.signInWithPopup(provider);
        } catch (e) {
            console.error('[Auth] Google sign-in failed:', e);
            alert('Sign-in failed: ' + e.message);
        }
    }

    async signInWithEmail(email, password) {
        if (!this.auth) return;
        try {
            await this.auth.signInWithEmailAndPassword(email, password);
        } catch (e) {
            console.error('[Auth] Email sign-in failed:', e);
            alert('Sign-in failed: ' + e.message);
        }
    }

    async signUpWithEmail(email, password) {
        if (!this.auth) return;
        try {
            await this.auth.createUserWithEmailAndPassword(email, password);
        } catch (e) {
            console.error('[Auth] Sign-up failed:', e);
            alert('Sign-up failed: ' + e.message);
        }
    }

    async signOut() {
        if (!this.auth) return;
        try {
            await this.auth.signOut();
        } catch (e) {
            console.error('[Auth] Sign-out failed:', e);
        }
    }

    async getIdToken() {
        if (!this.user) return null;
        try {
            return await this.user.getIdToken();
        } catch { return null; }
    }

    isLoggedIn() {
        return !!this.user;
    }
}

// ============== Main App ==============
class JarvisCloudApp {
    constructor() {
        this.sessionId = localStorage.getItem('jarvis_session') || '';
        this.isVoiceActive = false;
        this.mediaRecorder = null;
        this.audioChunks = [];
        this.ttsQueue = [];
        this.isSpeaking = false;
        this.lastTtsIndex = 0;
        this.isGeneratingAudioStream = false;
        this.isProcessing = false;
        this.isMuted = false;
        this.currentChatId = null;
        this.currentMessages = []; // {role, content} array
        this.selectedFiles = []; // Array of File objects

        this.history = new ChatHistoryManager();
        this.firebaseAuth = new FirebaseAuthManager(this);
        this.isSignUpMode = false;

        // UI Elements
        this.el = {
            chatHistory: document.getElementById('chatHistory'),
            welcomeScreen: document.getElementById('welcomeScreen'),
            commandInput: document.getElementById('commandInput'),
            submitBtn: document.getElementById('submitCommand'),
            voiceTrigger: document.getElementById('voiceModeTrigger'),
            recentList: document.getElementById('recentList'),
            newChatBtn: document.getElementById('newChatBtn'),

            // File Upload
            attachBtn: document.getElementById('attachBtn'),
            fileInput: document.getElementById('fileInput'),
            attachMenu: document.getElementById('attachMenu'),

            // Voice Overlay
            voiceOverlay: document.getElementById('voiceOverlay'),
            voiceStatus: document.getElementById('voiceStatus'),
            waveform: document.getElementById('waveform'),
            voiceMuteBtn: document.getElementById('voiceMuteBtn'),
            voiceEndBtn: document.getElementById('voiceEndBtn'),

            // Auth
            loginBtn: document.getElementById('loginBtn'),
            loginModal: document.getElementById('loginModal'),
            userAvatar: document.getElementById('userAvatar'),

            // Audio
            audioPlayer: document.getElementById('audioPlayer'),
            audioToggle: document.getElementById('audioToggle'),
            clearChat: document.getElementById('clearChat'),
            voiceBtn: document.getElementById('voiceBtn'),

            // Sidebar Profile
            sidebarProfile: document.getElementById('sidebarProfile'),
            sidebarAvatarImg: document.getElementById('sidebarAvatarImg'),
            sidebarUsername: document.getElementById('sidebarUsername'),
            openSettingsBtn: document.getElementById('openSettingsBtn'),

            // Settings Modal
            settingsModal: document.getElementById('settingsModal'),
            closeSettingsBtn: document.getElementById('closeSettingsModal'),
            saveSettingsBtn: document.getElementById('saveSettingsBtn'),

            // Image Viewer Modal
            imageViewerModal: document.getElementById('imageViewerModal'),
            fullscreenImage: document.getElementById('fullscreenImage'),
            closeImageViewerBtn: document.getElementById('closeImageViewer'),
            imgDownloadBtn: document.getElementById('imgDownloadBtn'),
            imgShareBtn: document.getElementById('imgShareBtn'),
            imgCopyBtn: document.getElementById('imgCopyBtn'),

            // Model Selector
            modelSelector: document.getElementById('modelSelector'),

            // Artifact Preview Panel
            artifactPanel: document.getElementById('artifactPanel'),
            artifactTitle: document.getElementById('artifactTitle'),
            artifactTypeIcon: document.querySelector('.artifact-type-icon'),
            artifactPreviewFrame: document.getElementById('artifactPreviewFrame'),
            artifactCodeView: document.getElementById('artifactCodeView'),
            artifactCodeContent: document.getElementById('artifactCodeContent'),
            artifactCopyBtn: document.getElementById('artifactCopyBtn'),
            artifactDownloadBtn: document.getElementById('artifactDownloadBtn'),
            artifactCloseBtn: document.getElementById('artifactCloseBtn'),
            artifactTabPreview: document.getElementById('artifactTabPreview'),
            artifactTabCode: document.getElementById('artifactTabCode')
        };

        // Artifact state
        this.currentArtifactCode = '';
        this.currentArtifactLang = '';

        this.init();
    }

    init() {
        this.loadSettings();
        this.renderWaveform();
        this.bindEvents();
        this.loadLastSession();
        this.renderSidebar();
        this.firebaseAuth.init();
        this.startHeartbeat();
    }

    loadSettings() {
        // Default TTS on
        this.ttsEnabled = localStorage.getItem('kautilya_tts') !== 'false';
        const ttsToggle = document.getElementById('settingTTS');
        if (ttsToggle) ttsToggle.checked = this.ttsEnabled;

        // Theme
        const theme = localStorage.getItem('kautilya_theme') || 'dark';
        if (theme === 'light') {
            document.body.classList.add('light-theme');
        }
        const themeSelect = document.getElementById('settingTheme');
        if (themeSelect) themeSelect.value = theme;

        // Profile Prefs
        const prefName = localStorage.getItem('kautilya_pref_name');
        const prefNameInput = document.getElementById('settingPreferredName');
        if (prefName && prefNameInput) prefNameInput.value = prefName;

        const prefWork = localStorage.getItem('kautilya_pref_work');
        const prefWorkSelect = document.getElementById('settingWorkFunction');
        if (prefWork && prefWorkSelect) prefWorkSelect.value = prefWork;

        const prefSystem = localStorage.getItem('kautilya_pref_system');
        const prefSystemTextarea = document.getElementById('settingPreferences');
        if (prefSystem && prefSystemTextarea) prefSystemTextarea.value = prefSystem;

        const notifyPref = localStorage.getItem('kautilya_notify');
        const notifyToggle = document.getElementById('settingNotifyResponse');
        if (notifyPref !== null && notifyToggle) notifyToggle.checked = notifyPref === 'true';

        // Set sidebar and settings badge/initials from display name if available
        const displayName = localStorage.getItem('kautilya_display_name') || '';
        const nameInput = document.getElementById('settingDisplayName');
        if (nameInput) nameInput.value = displayName;
        
        const badge = document.getElementById('settingsAvatarBadge');
        if (badge && displayName) badge.textContent = displayName.substring(0,2).toUpperCase();
    }

    async loadMemoryPrompt() {
        if (this.el.externalAiPrompt && this.el.externalAiPrompt.value) return; 
        try {
            const resp = await fetch('/api/memory/prompt');
            const data = await resp.json();
            if (data.prompt && this.el.externalAiPrompt) {
                this.el.externalAiPrompt.value = data.prompt;
            }
        } catch (e) {
            console.error('[Memory] Failed to load extraction prompt:', e);
        }
    }

    async syncExternalMemory() {
        const data = this.el.externalAiData.value.trim();
        if (!data) {
            alert('Please paste some data to sync.');
            return;
        }

        const btn = this.el.syncMemoryBtn;
        const originalContent = btn.innerHTML;
        btn.disabled = true;
        btn.innerHTML = '<span class="material-icons-round spinning">sync</span> Analyzing...';

        try {
            const token = await this.firebaseAuth.getIdToken();
            const resp = await fetch('/api/memory/sync', {
                method: 'POST',
                headers: { 
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${token}`
                },
                body: JSON.stringify({ 
                    external_text: data
                })
            });

            const result = await resp.json();
            if (result.success || result.status === 'success') {
                btn.innerHTML = '<span class="material-icons-round">check_circle</span> Synced!';
                btn.classList.add('success-btn');
                this.el.externalAiData.value = '';
                
                setTimeout(() => {
                    btn.innerHTML = originalContent;
                    btn.disabled = false;
                    btn.classList.remove('success-btn');
                }, 3000);
            } else {
                throw new Error(result.error || 'Sync failed');
            }
        } catch (e) {
            console.error('[Memory] Sync error:', e);
            alert('Memory sync failed: ' + e.message);
            btn.innerHTML = originalContent;
            btn.disabled = false;
        }
    }

    startHeartbeat() {
        /**
         * Pulse server every 60s to prevent Render free-tier sleeping.
         */
        setInterval(async () => {
            try {
                const resp = await fetch('/api/health');
                if (resp.ok) {
                    console.log('[Heartbeat] Server active');
                }
            } catch (e) {
                console.warn('[Heartbeat] Ping failed:', e);
            }
        }, 60000);
    }

    bindEvents() {
        // Text Input
        this.el.submitBtn.onclick = () => this.handleTextSubmit();

        // File Upload Binding
        if (this.el.attachBtn && this.el.fileInput && this.el.attachMenu) {
            // Toggle menu
            this.el.attachBtn.onclick = (e) => {
                e.stopPropagation();
                const isVisible = this.el.attachMenu.style.display === 'flex';
                this.el.attachMenu.style.display = isVisible ? 'none' : 'flex';
            };

            // Handle options
            this.el.attachMenu.querySelectorAll('.attach-option').forEach(btn => {
                btn.onclick = (e) => {
                    e.stopPropagation();
                    const type = btn.getAttribute('data-type');
                    this.el.attachMenu.style.display = 'none';

                    if (type === 'image') {
                        this.el.fileInput.accept = "image/*";
                    } else {
                        // All supported files
                        this.el.fileInput.accept = "image/*,audio/*,.pdf,.doc,.docx,.txt";
                    }
                    this.el.fileInput.click();
                };
            });

            // Close on outside click
            document.addEventListener('click', (e) => {
                if (this.el.attachMenu.style.display === 'flex' &&
                    !this.el.attachMenu.contains(e.target) &&
                    !this.el.attachBtn.contains(e.target)) {
                    this.el.attachMenu.style.display = 'none';
                }
            });

            this.el.fileInput.onchange = (e) => this.handleFileSelect(e);
        }
        this.el.commandInput.onkeydown = (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.handleTextSubmit();
            }
        };

        // Auto-resize textarea
        this.el.commandInput.addEventListener('input', () => {
            this.el.commandInput.style.height = 'auto';
            this.el.commandInput.style.height = Math.min(this.el.commandInput.scrollHeight, 160) + 'px';

            // Mood Detection
            this.detectMood(this.el.commandInput.value);
        });

        // Emoji Mouse Tracking
        const svgArea = document.getElementById('sidebarEmoji');
        if (svgArea) {
            document.addEventListener('mousemove', (e) => {
                const rect = svgArea.getBoundingClientRect();
                const emojiCenterX = rect.left + rect.width / 2;
                const emojiCenterY = rect.top + rect.height / 2;

                const dx = e.clientX - emojiCenterX;
                const dy = e.clientY - emojiCenterY;
                const distance = Math.sqrt(dx * dx + dy * dy);

                const maxMovement = 3;
                const moveDist = Math.min(distance / 60, maxMovement);
                const angle = Math.atan2(dy, dx);

                const moveX = Math.cos(angle) * moveDist;
                const moveY = Math.sin(angle) * moveDist;

                const pupilL = document.getElementById('pupilLeft');
                const pupilR = document.getElementById('pupilRight');

                if (pupilL && pupilR) {
                    pupilL.style.transform = `translate(calc(-50% + ${moveX}px), calc(-50% + ${moveY}px))`;
                    pupilR.style.transform = `translate(calc(-50% + ${moveX}px), calc(-50% + ${moveY}px))`;
                }
            });
        }

        // Voice Mode
        this.el.voiceTrigger.onclick = () => this.startVoiceMode();
        this.el.voiceEndBtn.onclick = () => this.endVoiceMode();
        this.el.voiceMuteBtn.onclick = () => this.toggleMute();

        // Tap to Interrupt (Voice Overlay)
        // With LiveKit, barge-in is handled natively by VAD on the server.
        // Tapping the overlay is a visual feedback only.
        if (this.el.voiceOverlay) {
            this.el.voiceOverlay.onclick = (e) => {
                if (e.target.closest('button')) return;
                // LiveKit handles interruption via VAD — no client-side action needed
            };
        }

        // Hide Audio Player (it's for backend TTS playback, user doesn't need to see it)
        if (this.el.audioPlayer) {
            this.el.audioPlayer.style.display = 'none';
        }

        // Extra Header Actions
        if (this.el.audioToggle) {
            this.el.audioToggle.onclick = () => {
                this.ttsEnabled = !this.ttsEnabled;
                this.el.audioToggle.innerText = this.ttsEnabled ? '🔊 TTS ON' : '🔇 TTS OFF';
                this.el.audioToggle.classList.toggle('btn-active', this.ttsEnabled);
            };
        }

        if (this.el.clearChat) {
            this.el.clearChat.onclick = () => {
                this.el.chatHistory.innerHTML = '';
                this.addMessage('KAUTILYA', 'Chat cleared. How may I assist you?');
            };
        }

        if (this.el.voiceBtn) {
            this.el.voiceBtn.onclick = () => this.startVoiceMode();
        }

        // Settings Modal
        const openSettings = () => {
            this.el.settingsModal.classList.add('show');
        };
        const closeSettings = () => {
            this.el.settingsModal.classList.remove('show');
        };

        if (this.el.openSettingsBtn) this.el.openSettingsBtn.onclick = (e) => {
            e.stopPropagation();
            openSettings();
        };

        // Clicking the profile section also opens settings
        if (this.el.sidebarProfile) this.el.sidebarProfile.onclick = () => openSettings();

        if (this.el.closeSettingsBtn) this.el.closeSettingsBtn.onclick = () => closeSettings();

        // Close on outside click for Settings Modal
        this.el.settingsModal.onclick = (e) => {
            if (e.target === this.el.settingsModal) closeSettings();
        };

        // Settings Tabs Logic
        const settingsTabs = document.querySelectorAll('.settings-tab');
        const settingsSections = document.querySelectorAll('.settings-section');
        
        settingsTabs.forEach(tab => {
            tab.addEventListener('click', () => {
                // Remove active class from all tabs and sections
                settingsTabs.forEach(t => t.classList.remove('active'));
                settingsSections.forEach(s => s.classList.remove('active'));
                
                // Add active class to clicked tab
                tab.classList.add('active');
                
                // Show corresponding section
                const targetId = tab.getAttribute('data-target');
                const targetSection = document.getElementById(targetId);
                if (targetSection) {
                    targetSection.classList.add('active');
                }
            });
        });

        // Initialize Textarea Auto-Resize
        const textarea = this.el.commandInput;
        if (textarea) {
            textarea.addEventListener('input', () => {
                textarea.style.height = 'auto';
                textarea.style.height = Math.min(textarea.scrollHeight, 150) + 'px'; // Max height 150px
            });
            // Initial resize
            textarea.style.height = 'auto';
            textarea.style.height = Math.min(textarea.scrollHeight, 150) + 'px';
        }

        if (this.el.saveSettingsBtn) this.el.saveSettingsBtn.onclick = async () => {
            // Save Name
            const newName = document.getElementById('settingDisplayName').value;
            if (newName && this.firebaseAuth && this.firebaseAuth.user) {
                try {
                    await this.firebaseAuth.user.updateProfile({ displayName: newName });
                    this.updateUserUI(this.firebaseAuth.user); // Refresh UI
                } catch (err) {
                    console.error("Failed to update Firebase profile name:", err);
                }
            }
            if (newName) localStorage.setItem('kautilya_display_name', newName);

            // Sync with sidebar and names
            const badge = document.getElementById('settingsAvatarBadge');
            const username = document.getElementById('sidebarUsername');
            const dropdownName = document.getElementById('dropdownUserName');
            
            if (newName) {
                if (username) username.textContent = newName;
                if (dropdownName) dropdownName.textContent = newName;
                if (!badge.classList.contains('has-photo')) {
                    badge.textContent = newName.substring(0,2).toUpperCase();
                }
            }

            // Save Preferences
            const prefName = document.getElementById('settingPreferredName')?.value;
            const prefWork = document.getElementById('settingWorkFunction')?.value;
            const prefSystem = document.getElementById('settingPreferences')?.value;
            
            if (prefName) localStorage.setItem('kautilya_pref_name', prefName);
            if (prefWork) localStorage.setItem('kautilya_pref_work', prefWork);
            if (prefSystem) localStorage.setItem('kautilya_pref_system', prefSystem);

            // Save Theme
            const themeSelect = document.getElementById('settingTheme');
            let theme = 'dark';
            if (themeSelect) {
                theme = themeSelect.value;
                localStorage.setItem('kautilya_theme', theme);
                if (theme === 'light') {
                    document.body.classList.add('light-theme');
                } else {
                    document.body.classList.remove('light-theme');
                }
            }

            // Save Notifications
            const notifySelect = document.getElementById('settingNotifyResponse');
            const notifyVal = notifySelect ? notifySelect.checked : true;
            if (notifySelect) {
                localStorage.setItem('kautilya_notify', notifyVal);
            }

            // Save TTS
            const ttsToggle = document.getElementById('settingTTS');
            if (ttsToggle) {
                this.ttsEnabled = ttsToggle.checked;
                localStorage.setItem('kautilya_tts', this.ttsEnabled);
            }

            // SERVER SYNC: Save to Firestore if logged in
            if (this.firebaseAuth.user) {
                try {
                    const token = await this.firebaseAuth.getIdToken();
                    await fetch('/api/user/settings', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'Authorization': `Bearer ${token}`
                        },
                        body: JSON.stringify({
                            display_name: newName,
                            preferred_name: prefName,
                            work_function: prefWork,
                            personal_preferences: prefSystem,
                            theme: theme,
                            tts_enabled: this.ttsEnabled,
                            notifications_enabled: notifyVal
                        })
                    });
                } catch (e) {
                    console.error('[Sync] Failed to save settings to server', e);
                }
            }

            closeSettings();
        };

        // New Chat
        if (this.el.newChatBtn) {
            this.el.newChatBtn.onclick = () => {
                this.startNewChat();
                document.getElementById('appSidebar').classList.remove('open');
            };
        }

        // Sidebar Toggle
        const sidebarToggle = document.getElementById('toggleSidebar');
        const appSidebar = document.getElementById('appSidebar');
        if (sidebarToggle && appSidebar) {
            sidebarToggle.onclick = () => {
                if (window.innerWidth <= 768) {
                    appSidebar.classList.toggle('open');
                } else {
                    appSidebar.classList.toggle('collapsed');
                }
            };
        }

        // Sidebar overlay close on mobile
        document.addEventListener('click', (e) => {
            const sidebar = document.getElementById('appSidebar');
            if (sidebar.classList.contains('open')) {
                // If clicked outside entirely OR clicked on the overlay part (width > 280px)
                // The sidebar itself is 280px. If e.target is sidebar and x > 280, it's the overlay.
                const isOverlayClick = (e.target === sidebar && e.clientX > 280);

                if ((!sidebar.contains(e.target) && !e.target.closest('.menu-btn')) || isOverlayClick) {
                    sidebar.classList.remove('open');
                }
            }
        });

        // Chip Clicks
        document.querySelectorAll('.chip').forEach(chip => {
            chip.onclick = () => {
                const prompt = chip.getAttribute('data-prompt');
                this.el.commandInput.value = prompt;
                this.handleTextSubmit();
            };
        });

        // Login button
        if (this.el.loginBtn) {
            this.el.loginBtn.onclick = () => this.toggleLoginModal(true);
        }

        // Close login modal
        const closeLogin = document.getElementById('closeLoginModal');
        if (closeLogin) {
            closeLogin.onclick = () => this.toggleLoginModal(false);
        }

        // Google Sign-In
        const googleBtn = document.getElementById('googleSignIn');
        if (googleBtn) {
            googleBtn.onclick = () => this.firebaseAuth.signInWithGoogle();
        }

        // Email Sign-In / Sign-Up
        const loginSubmit = document.getElementById('loginSubmit');
        if (loginSubmit) {
            loginSubmit.onclick = () => {
                const email = document.getElementById('loginEmail').value.trim();
                const pw = document.getElementById('loginPassword').value;
                if (!email || !pw) { alert('Please enter email and password'); return; }
                if (this.isSignUpMode) {
                    this.firebaseAuth.signUpWithEmail(email, pw);
                } else {
                    this.firebaseAuth.signInWithEmail(email, pw);
                }
            };
        }

        // Toggle Sign-Up mode
        const toggleSignUp = document.getElementById('toggleSignUp');
        if (toggleSignUp) {
            toggleSignUp.onclick = (e) => {
                e.preventDefault();
                this.isSignUpMode = !this.isSignUpMode;
                const submitBtn = document.getElementById('loginSubmit');
                if (submitBtn) submitBtn.textContent = this.isSignUpMode ? 'Sign Up' : 'Sign In';
                toggleSignUp.textContent = this.isSignUpMode ? 'Sign In' : 'Sign Up';
                const toggleP = toggleSignUp.parentElement;
                if (toggleP) toggleP.firstChild.textContent = this.isSignUpMode ? 'Already have an account? ' : "Don't have an account? ";
            };
        }

        // Image Viewer specific binding
        if (this.el.closeImageViewerBtn && this.el.imageViewerModal) {
            this.el.closeImageViewerBtn.onclick = () => {
                this.el.imageViewerModal.classList.remove('show');
                // clear src after transition
                setTimeout(() => {
                    if (this.el.fullscreenImage) this.el.fullscreenImage.src = '';
                }, 300);
            };
            this.el.imageViewerModal.onclick = (e) => {
                if (e.target === this.el.imageViewerModal) {
                    this.el.closeImageViewerBtn.click();
                }
            };
        }

        // Image Viewer Action Buttons
        if (this.el.imgDownloadBtn) {
            this.el.imgDownloadBtn.onclick = async () => {
                const imgSrc = this.el.fullscreenImage?.src;
                if (!imgSrc) return;
                try {
                    const resp = await fetch(imgSrc);
                    const blob = await resp.blob();
                    const url = URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = 'KAUTILYA_GENERATED_IMAGE.png';
                    document.body.appendChild(a);
                    a.click();
                    document.body.removeChild(a);
                    URL.revokeObjectURL(url);
                } catch (e) {
                    // Fallback: open in new tab
                    window.open(imgSrc, '_blank');
                }
            };
        }

        if (this.el.imgShareBtn) {
            this.el.imgShareBtn.onclick = async () => {
                const imgSrc = this.el.fullscreenImage?.src;
                if (!imgSrc) return;
                try {
                    if (navigator.share) {
                        const resp = await fetch(imgSrc);
                        const blob = await resp.blob();
                        const file = new File([blob], 'KAUTILYA_GENERATED_IMAGE.png', { type: blob.type });
                        await navigator.share({
                            title: 'KAUTILYA AI Generated Image',
                            text: 'Check out this image generated by KAUTILYA AI!',
                            files: [file]
                        });
                    } else {
                        await navigator.clipboard.writeText(imgSrc);
                        const btn = this.el.imgShareBtn;
                        const label = btn.querySelector('.action-label');
                        if (label) label.textContent = 'Link Copied!';
                        btn.classList.add('success');
                        setTimeout(() => {
                            if (label) label.textContent = 'Share';
                            btn.classList.remove('success');
                        }, 2000);
                    }
                } catch (e) {
                    // Fallback: copy URL to clipboard
                    try {
                        await navigator.clipboard.writeText(imgSrc);
                    } catch (e2) { /* silent */ }
                }
            };
        }

        if (this.el.imgCopyBtn) {
            this.el.imgCopyBtn.onclick = async () => {
                const imgSrc = this.el.fullscreenImage?.src;
                if (!imgSrc) return;
                try {
                    const resp = await fetch(imgSrc);
                    const blob = await resp.blob();
                    const pngBlob = blob.type === 'image/png' ? blob : await this._convertToPng(blob);
                    await navigator.clipboard.write([
                        new ClipboardItem({ 'image/png': pngBlob })
                    ]);
                    const btn = this.el.imgCopyBtn;
                    const icon = btn.querySelector('.material-icons-round');
                    const label = btn.querySelector('.action-label');
                    if (icon) icon.textContent = 'check';
                    if (label) label.textContent = 'Copied!';
                    btn.classList.add('success');
                    setTimeout(() => {
                        if (icon) icon.textContent = 'content_copy';
                        if (label) label.textContent = 'Copy';
                        btn.classList.remove('success');
                    }, 2000);
                } catch (e) {
                    // Fallback: copy URL as text
                    try {
                        await navigator.clipboard.writeText(imgSrc);
                        const btn = this.el.imgCopyBtn;
                        const label = btn.querySelector('.action-label');
                        if (label) label.textContent = 'URL Copied!';
                        btn.classList.add('success');
                        setTimeout(() => {
                            if (label) label.textContent = 'Copy';
                            btn.classList.remove('success');
                        }, 2000);
                    } catch (e2) { /* silent */ }
                }
            };
        }
    }

    // ============== Emoji Mood Detection ==============
    detectMood(text) {
        if (!text) text = "";
        text = text.toLowerCase();

        const angryWords = ['angry', 'hate', 'stupid', 'dumb', 'idiot', 'mad', 'furious', 'terrible', 'bad', 'suck', 'worst', 'shut up'];
        const happyWords = ['happy', 'love', 'great', 'awesome', 'good', 'nice', 'excellent', 'thanks', 'thank you', 'amazing', 'perfect', 'haha', 'lol'];
        const sadWords = ['sad', 'sorry', 'cry', 'depressed', 'help', 'hurt', 'pain'];

        let mood = 'default';
        if (text.length > 0) mood = 'typing';

        if (angryWords.some(w => text.includes(w))) mood = 'angry';
        else if (happyWords.some(w => text.includes(w))) mood = 'happy';
        else if (sadWords.some(w => text.includes(w))) mood = 'sad';

        const emoji = document.getElementById('sidebarEmoji');
        if (emoji) {
            emoji.className = `emoji-container mood-${mood}`;
        }
    }

    // ============== Chat Session Management ==============

    loadLastSession() {
        const lastChatId = this.history.getActiveChatId();
        if (lastChatId) {
            const chat = this.history.getChat(lastChatId);
            if (chat && chat.messages && chat.messages.length > 0) {
                this.currentChatId = lastChatId;
                this.currentMessages = chat.messages;
                this.renderMessages(this.currentMessages);
                return;
            }
        }
        // No valid chat — show welcome
        this.showWelcome();
    }

    startNewChat() {
        this.currentChatId = null;
        this.currentMessages = [];
        this.sessionId = ''; // Will get new session from server
        localStorage.removeItem('jarvis_session');
        this.showWelcome();
        this.renderSidebar();
    }

    createNewChatSession(firstMessage) {
        const chatId = 'chat_' + Date.now() + '_' + Math.random().toString(36).substr(2, 6);
        this.currentChatId = chatId;
        const title = this.history.generateTitle(firstMessage);
        this.history.saveChat(chatId, {
            title,
            messages: [],
            createdAt: Date.now(),
            updatedAt: Date.now(),
            sessionId: this.sessionId
        });
        this.history.setActiveChatId(chatId);
        return chatId;
    }

    saveCurrentChat() {
        if (!this.currentChatId) return;
        const existing = this.history.getChat(this.currentChatId) || {};
        this.history.saveChat(this.currentChatId, {
            ...existing,
            messages: this.currentMessages,
            updatedAt: Date.now(),
            sessionId: this.sessionId
        });
    }

    async syncHistory() {
        if (!this.firebaseAuth.user) return;

        try {
            const token = await this.firebaseAuth.getIdToken();
            const resp = await fetch('/api/jarvis/history', {
                headers: { 'Authorization': `Bearer ${token}` }
            });

            if (resp.ok) {
                const data = await resp.json();
                const remoteChats = data.chats || [];

                // Merge with local
                remoteChats.forEach(remote => {
                    const local = this.history.getChat(remote.session_id);
                    // If missing or remote is newer (simple check)
                    if (!local) {
                        // Create placeholder
                        this.history.saveChat(remote.session_id, {
                            id: remote.session_id,
                            title: remote.preview || "New Chat",
                            messages: [], // Empty implies need to fetch
                            updatedAt: new Date(remote.last_updated).getTime(),
                            sessionId: remote.session_id
                        });
                    }
                });

                this.renderSidebar(); // Changed from renderSidebarHistory to renderSidebar
            }
        } catch (e) {
            console.error('[Sync] History sync failed', e);
        }
    }

    async loadChat(chatId) {
        if (this.currentChatId === chatId) return;

        let chat = this.history.getChat(chatId);
        if (!chat) return;

        this.currentChatId = chatId;
        this.sessionId = chat.sessionId || chatId;
        localStorage.setItem('jarvis_session', this.sessionId);
        this.history.setActiveChatId(chatId);

        // Lazy load messages if empty and we are logged in
        if ((!chat.messages || chat.messages.length === 0) && this.firebaseAuth.user) {
            this.toggleThinking(true); // Show loading
            try {
                const token = await this.firebaseAuth.getIdToken();
                const resp = await fetch(`/api/jarvis/history/${chatId}`, {
                    headers: { 'Authorization': `Bearer ${token}` }
                });
                if (resp.ok) {
                    const data = await resp.json();
                    if (data.messages && data.messages.length > 0) {
                        chat.messages = data.messages;
                        this.history.saveChat(chatId, chat);
                    }
                }
            } catch (e) {
                console.error('[Sync] Load chat failed', e);
            } finally {
                this.toggleThinking(false);
            }
        }

        this.currentMessages = chat.messages || [];
        this.renderMessages(this.currentMessages); // Pass messages to renderMessages
        this.renderSidebar(); // Changed from renderSidebarHistory to renderSidebar

        // Update welcome screen visibility
        if (this.currentMessages.length === 0) {
            this.showWelcome();
        } else {
            this.hideWelcome();
        }

        // Close sidebar on mobile
        document.getElementById('appSidebar').classList.remove('open');
    }

    async deleteChatSession(chatId, e) {
        e.stopPropagation();
        if (!confirm("Are you sure you want to delete this chat?")) return;

        this.history.deleteChat(chatId);
        if (this.currentChatId === chatId) {
            this.startNewChat();
        }
        this.renderSidebar();

        if (this.firebaseAuth.user) {
            try {
                const token = await this.firebaseAuth.getIdToken();
                await fetch(`/api/jarvis/history/${chatId}`, {
                    method: 'DELETE',
                    headers: { 'Authorization': `Bearer ${token}` }
                });
            } catch (err) {
                console.error('[Delete] Failed to delete from server:', err);
            }
        }
    }

    // ============== Sidebar Rendering ==============

    renderSidebar() {
        const chats = this.history.getSortedChats();
        this.el.recentList.innerHTML = '';

        if (chats.length === 0) {
            this.el.recentList.innerHTML = `
                <div class="empty-history">
                    <span class="material-icons-round" style="font-size: 2rem; opacity: 0.3;">forum</span>
                    <span style="opacity: 0.4; font-size: 0.85rem;">No conversations yet</span>
                </div>
            `;
            return;
        }

        // Group by date
        const today = new Date();
        const groups = { today: [], yesterday: [], week: [], older: [] };

        chats.forEach(chat => {
            const chatDate = new Date(chat.updatedAt || chat.createdAt);
            const diff = Math.floor((today - chatDate) / (1000 * 60 * 60 * 24));
            if (diff === 0) groups.today.push(chat);
            else if (diff === 1) groups.yesterday.push(chat);
            else if (diff <= 7) groups.week.push(chat);
            else groups.older.push(chat);
        });

        const renderGroup = (label, items) => {
            if (items.length === 0) return;
            const groupLabel = document.createElement('div');
            groupLabel.className = 'recent-group-label';
            groupLabel.textContent = label;
            this.el.recentList.appendChild(groupLabel);

            items.forEach(chat => {
                const item = document.createElement('div');
                item.className = 'recent-item' + (chat.id === this.currentChatId ? ' active' : '');
                item.innerHTML = `
                    <span class="material-icons-round icon">chat_bubble_outline</span>
                    <span class="recent-title">${this.escapeHtml(chat.title || 'Untitled')}</span>
                    <button class="recent-delete" title="Delete">
                        <span class="material-icons-round">delete_outline</span>
                    </button>
                `;
                item.onclick = () => this.loadChat(chat.id);
                item.querySelector('.recent-delete').onclick = (e) => this.deleteChatSession(chat.id, e);
                this.el.recentList.appendChild(item);
            });
        };

        renderGroup('Today', groups.today);
        renderGroup('Yesterday', groups.yesterday);
        renderGroup('Previous 7 Days', groups.week);
        renderGroup('Older', groups.older);
    }

    // ============== Message Rendering ==============

    renderMessages(messages) {
        // Clear chat area
        this.el.chatHistory.innerHTML = '';
        this.el.chatHistory.appendChild(this.el.welcomeScreen);
        this.el.welcomeScreen.style.display = 'none';
        document.body.classList.remove('start-mode');

        messages.forEach(msg => {
            if (msg.role === 'user') {
                this.addUserMessageDOM(msg.content, msg.files);
            } else {
                this.addJarvisMessageDOM(msg.content);
            }
        });

        this.scrollToBottom();
    }

    addUserMessageDOM(text, files = []) {
        let extractedText = text;
        const localFiles = [...files];

        // Parse OpenAI-style Multimodal Arrays (from server history)
        if (Array.isArray(text)) {
            extractedText = "";
            text.forEach(item => {
                if (typeof item === 'string') {
                    extractedText += item + '\n';
                } else if (item.type === 'text' && item.text) {
                    extractedText += item.text + '\n';
                } else if (item.type === 'image_url' && item.image_url && item.image_url.url) {
                    // Convert server history image to local UI file object
                    if (!localFiles.some(f => f.data === item.image_url.url)) {
                        localFiles.push({
                            type: 'image/jpeg',
                            data: item.image_url.url,
                            name: 'History Image'
                        });
                    }
                }
            });
            extractedText = extractedText.trim();
        }

        const msg = document.createElement('div');
        msg.className = 'message user-msg';

        let fileHtml = '';
        if (localFiles.length > 0) {
            fileHtml = '<div class="message-files" style="display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 8px;">';
            localFiles.forEach(f => {
                if (f.type && f.type.startsWith('image/')) {
                    fileHtml += `<img src="${f.data}" class="chat-image" style="max-width: 200px; max-height: 200px; border-radius: 8px; cursor: pointer;" onclick="openImageViewer(this.src)" alt="${this.escapeHtml(f.name || 'Image')}">`;
                } else {
                    fileHtml += `<div class="chat-file-attachment">
                        <span class="material-icons-round">description</span>
                        <span>${this.escapeHtml(f.name || 'File')}</span>
                    </div>`;
                }
            });
            fileHtml += '</div>';
        }

        msg.innerHTML = `
            <div class="message-bg">
                ${fileHtml}
                ${extractedText ? `<div class="message-content">${this.escapeHtml(extractedText)}</div>` : ''}
            </div>
            <div class="message-avatar user-avatar">
                <span class="material-icons-round" style="font-size: 16px;">person</span>
            </div>
        `;
        this.el.chatHistory.appendChild(msg);
    }

    addJarvisMessageDOM(text, animate = false) {
        const msg = document.createElement('div');
        msg.className = 'message jarvis-msg';
        msg.innerHTML = `
            <div class="message-avatar jarvis-avatar">
                <img src="/static/kautilya_logo.png" class="jarvis-icon" alt="K">
            </div>
            <div class="message-bg">
                <div class="message-content">${animate ? '' : this.formatMarkdown(text)}</div>
                <div class="message-actions">
                    <button class="msg-action-btn copy-btn" title="Copy">
                        <span class="material-icons-round">content_copy</span>
                    </button>
                </div>
            </div>
        `;
        // Copy button
        msg.querySelector('.copy-btn').onclick = () => {
            navigator.clipboard.writeText(text).then(() => {
                const btn = msg.querySelector('.copy-btn span');
                btn.textContent = 'check';
                setTimeout(() => btn.textContent = 'content_copy', 1500);
            });
        };
        this.el.chatHistory.appendChild(msg);

        if (animate) {
            const contentEl = msg.querySelector('.message-content');
            contentEl.classList.add('typing-cursor');
            return contentEl;
        } else {
            // Render Math for static messages
            this.renderMath(msg.querySelector('.message-content'));
        }
    }

    async typeMessage(contentEl, text, speed = 12) {
        const words = text.split(/(\s+)/);
        let accumulated = '';
        const chunkSize = 2; // words per tick for fast feel

        for (let i = 0; i < words.length; i += chunkSize) {
            const chunk = words.slice(i, i + chunkSize).join('');
            accumulated += chunk;
            contentEl.innerHTML = this.formatMarkdown(accumulated);
            this.scrollToBottom();
            await new Promise(r => setTimeout(r, speed));
        }

        // Final render with complete text
        contentEl.innerHTML = this.formatMarkdown(text);
        contentEl.classList.remove('typing-cursor');
        this.renderMath(contentEl);
        this.scrollToBottom();
    }

    // ============== Text Chat Logic ==============

    async readFilesAsDataUrls(files) {
        const promises = files.map(file => {
            return new Promise(resolve => {
                const reader = new FileReader();
                reader.onload = (e) => resolve({
                    name: file.name,
                    type: file.type,
                    data: e.target.result
                });
                reader.readAsDataURL(file);
            });
        });
        return Promise.all(promises);
    }

    async handleTextSubmit() {
        const text = this.el.commandInput.value.trim();
        const hasFiles = this.selectedFiles.length > 0;

        if ((!text && !hasFiles) || this.isProcessing) return;

        this.el.commandInput.value = '';
        this.el.commandInput.style.height = 'auto';

        // Read files first (optimistic UI)
        let fileData = [];
        if (hasFiles) {
            try {
                fileData = await this.readFilesAsDataUrls(this.selectedFiles);
            } catch (e) { console.error("File read error", e); }
        }

        // If no active chat, create one
        if (!this.currentChatId) {
            this.createNewChatSession(text || (fileData.length ? 'Sent a file' : 'New Chat'));
        }

        // Remove start mode on first message
        document.body.classList.remove('start-mode');
        this.hideWelcome();

        // Add user message
        const msgObj = { role: 'user', content: text };
        if (fileData.length > 0) msgObj.files = fileData;

        this.currentMessages.push(msgObj);
        this.addUserMessageDOM(text, fileData);
        this.scrollToBottom();

        // Clear file preview immediately (optimistic UI) — files are already in this.selectedFiles for processCommand
        const previewArea = document.getElementById('filePreviewArea');
        if (previewArea) {
            previewArea.innerHTML = '';
            previewArea.style.display = 'none';
        }
        document.querySelector('.input-wrapper').classList.remove('has-files');

        // Save immediately
        this.saveCurrentChat();
        this.renderSidebar();

        await this.processCommand(text);
    }

    hideWelcome() {
        this.el.welcomeScreen.style.display = 'none';
        document.body.classList.remove('start-mode');
    }

    showWelcome() {
        this.el.chatHistory.innerHTML = '';
        this.el.chatHistory.appendChild(this.el.welcomeScreen);
        this.el.welcomeScreen.style.display = 'flex';
        document.body.classList.add('start-mode');
    }

    scrollToBottom() {
        requestAnimationFrame(() => {
            this.el.chatHistory.scrollTop = this.el.chatHistory.scrollHeight;
        });
    }

    // ============== Backend Logic ==============

    async processCommand(text, speakResponse = false) {
        this.isProcessing = true;
        const thinkingId = this.addThinkingBubble();

        try {
            const hasFiles = this.selectedFiles && this.selectedFiles.length > 0;
            const model = this.el.modelSelector ? this.el.modelSelector.value : 'daily'; // Get selected model
            let body;
            const headers = {
                'X-Session-ID': this.sessionId
            };

            this.ttsQueue = []; // clear TTS queue on new command
            this.isGeneratingAudioStream = true;

            const token = await this.firebaseAuth.getIdToken();
            if (token) headers['Authorization'] = `Bearer ${token}`;

            if (hasFiles) {
                const formData = new FormData();
                formData.append('text', text);
                formData.append('userName', this.firebaseAuth.user?.displayName || '');
                formData.append('model', model); // Send selected model in FormData
                this.selectedFiles.forEach(file => formData.append('files', file));
                body = formData;
            } else {
                headers['Content-Type'] = 'application/json';
                body = JSON.stringify({
                    text,
                    userName: this.firebaseAuth.user?.displayName || '',
                    model: model // Send selected model in JSON body
                });
            }

            const response = await fetch('/api/jarvis/command', {
                method: 'POST',
                headers,
                body
            });

            // Clear files after successful send
            if (hasFiles) {
                this.clearFiles();
            }

            this.removeThinkingBubble(thinkingId);

            // Prepare UI for streaming
            let fullText = "";
            this.lastTtsIndex = 0; // Reset TTS index
            const msgObj = { role: 'assistant', content: "" }; // placeholder
            this.currentMessages.push(msgObj);

            // Create the DOM element immediately
            const contentEl = this.addJarvisMessageDOM("", true); // animate=true adds typing cursor
            contentEl.classList.add('typing-cursor');

            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let sseBuffer = '';

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                sseBuffer += decoder.decode(value, { stream: true });
                const lines = sseBuffer.split('\n');

                // Keep the last incomplete line in the buffer
                sseBuffer = lines.pop();

                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        const jsonStr = line.slice(6);
                        if (jsonStr.trim() === '[DONE]') break;

                        try {
                            if (!jsonStr.trim() || !jsonStr.startsWith('{')) continue;

                            const data = JSON.parse(jsonStr);

                            if (data.session_id) {
                                this.sessionId = data.session_id;
                                localStorage.setItem('jarvis_session', this.sessionId);
                            }

                            // HANDLE STATUS
                            if (data.type === 'status' && data.message) {
                                fullText += `> 🔍 *${data.message}*\n\n`;
                                contentEl.innerHTML = this.formatMarkdown(fullText);
                                this.scrollToBottom();
                                continue;
                            }

                            if (data.chunk) {
                                fullText += data.chunk;

                                // Streaming TTS chunks based on punctuation
                                if (this.ttsEnabled && this.isVoiceActive) {
                                    let newText = fullText.substring(this.lastTtsIndex);
                                    let match = newText.match(/(.*?[.?!।\n]+)(\s*)/);
                                    if (match) {
                                        let sentenceToSpeak = match[1];
                                        this.lastTtsIndex += sentenceToSpeak.length + match[2].length;
                                        const cleanTTS = this.removeCommands(sentenceToSpeak).trim();
                                        if (cleanTTS) {
                                            this.queueTTS(cleanTTS);
                                        }
                                    }
                                }

                                const cleanText = this.removeCommands(fullText);
                                contentEl.innerHTML = this.formatMarkdown(cleanText);
                                this.scrollToBottom();
                            }
                        } catch (e) {
                            // ignore split chunks
                        }
                    }
                }
            }

            // Finalize
            contentEl.classList.remove('typing-cursor');
            this.renderMath(contentEl);
            // Hide backend commands from final stored message too (visual only, backend has full history)
            msgObj.content = this.removeCommands(fullText);

            this.isGeneratingAudioStream = false;

            // Flush any remaining text to TTS
            if (this.ttsEnabled && this.isVoiceActive) {
                let remainingText = fullText.substring(this.lastTtsIndex);
                let cleanRemaining = this.removeCommands(remainingText).trim();
                if (cleanRemaining) {
                    this.queueTTS(cleanRemaining);
                } else if (this.isVoiceActive && this.ttsQueue.length === 0 && !this.isSpeaking) {
                    // AI finished generating and nothing left to speak/is not currently speaking
                    this.startRecording(this.mediaRecorder.stream);
                }
            }

            // Check for Export Command
            const exportMatch = fullText.match(/\[EXPORT:\s*(pdf|docx|excel)\]/i);
            if (exportMatch) {
                const format = exportMatch[1].toLowerCase();
                this.triggerExport(format);
            }

            // Auto-open Artifact Preview Panel for HTML/SVG code blocks
            const msgContainer = contentEl.closest('.message');
            if (msgContainer) {
                const previewBtn = msgContainer.querySelector('.code-preview-btn');
                if (previewBtn) {
                    // Small delay to ensure DOM is fully rendered
                    setTimeout(() => {
                        this.openArtifactPanel(previewBtn);
                    }, 300);
                }
            }

            // Re-bind copy button with full text
            const copyBtn = contentEl.parentElement.querySelector('.copy-btn');
            if (copyBtn) {
                copyBtn.onclick = () => {
                    navigator.clipboard.writeText(fullText).then(() => {
                        const btn = copyBtn.querySelector('span');
                        btn.textContent = 'check';
                        setTimeout(() => btn.textContent = 'content_copy', 1500);
                    });
                };
            }

            this.saveCurrentChat();

            this.isProcessing = false;

            // Speak if voice mode (only if streaming TTS didn't already handle it)
            if (speakResponse && fullText && !this.ttsEnabled) {
                const spokenText = fullText.replace(/<think>[\s\S]*?<\/think>/g, '').trim();
                if (spokenText) this.queueTTS(spokenText);
            }

        } catch (e) {
            console.error(e);
            this.removeThinkingBubble(thinkingId);
            const errText = "I'm having trouble connecting to the cloud server.";
            this.addJarvisMessageDOM(errText);
            this.currentMessages.push({ role: 'assistant', content: errText });
            this.saveCurrentChat();
            this.isProcessing = false;
        }
    }

    // ============== File Handling ==============

    handleFileSelect(e) {
        const files = Array.from(e.target.files);
        if (!files.length) return;

        // Limit total files or size if needed
        const MAX_FILES = 5;
        if (this.selectedFiles.length + files.length > MAX_FILES) {
            alert(`You can only upload up to ${MAX_FILES} files.`);
            return;
        }

        this.selectedFiles = [...this.selectedFiles, ...files];
        this.updateFilePreview();

        // Reset input so same file can be selected again if needed
        e.target.value = '';

        // Add visual cue to input wrapper
        document.querySelector('.input-wrapper').classList.add('has-files');
    }

    updateFilePreview() {
        const previewArea = document.getElementById('filePreviewArea');
        previewArea.innerHTML = '';

        if (this.selectedFiles.length === 0) {
            previewArea.style.display = 'none';
            document.querySelector('.input-wrapper').classList.remove('has-files');
            return;
        }

        previewArea.style.display = 'flex';

        this.selectedFiles.forEach((file, index) => {
            const item = document.createElement('div');
            item.className = 'file-preview-item';
            item.title = file.name;

            const removeBtn = document.createElement('div');
            removeBtn.className = 'file-remove-btn';
            removeBtn.innerHTML = '<span class="material-icons-round" style="font-size: 12px;">close</span>';
            removeBtn.onclick = (e) => {
                e.stopPropagation();
                this.removeFile(index);
            };

            if (file.type.startsWith('image/')) {
                const img = document.createElement('img');
                img.src = URL.createObjectURL(file);
                item.appendChild(img);
            } else {
                const icon = document.createElement('span');
                icon.className = 'material-icons-round file-preview-icon';
                if (file.type.startsWith('audio/')) icon.textContent = 'audiotrack';
                else if (file.type === 'application/pdf') icon.textContent = 'picture_as_pdf';
                else icon.textContent = 'description';
                item.appendChild(icon);
            }

            item.appendChild(removeBtn);
            previewArea.appendChild(item);
        });
    }

    removeFile(index) {
        this.selectedFiles.splice(index, 1);
        this.updateFilePreview();
    }

    clearFiles() {
        this.selectedFiles = [];
        this.updateFilePreview();
    }

    async triggerExport(format) {
        const toastId = this.addThinkingBubble();
        const toastEl = document.getElementById(toastId);
        if (toastEl) toastEl.querySelector('.message-content').innerText = `Preparing ${format.toUpperCase()} export...`;

        try {
            const token = await this.firebaseAuth.getIdToken();
            const headers = { 'Content-Type': 'application/json' };
            if (token) headers['Authorization'] = `Bearer ${token}`;

            const resp = await fetch(`/api/export/${format}`, {
                method: 'POST',
                headers: headers,
                body: JSON.stringify({ history: this.currentMessages })
            });

            if (resp.ok) {
                const blob = await resp.blob();
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `jarvis_chat_${Date.now()}.${format === 'excel' ? 'xlsx' : format}`;
                document.body.appendChild(a);
                a.click();
                window.URL.revokeObjectURL(url);
                document.body.removeChild(a);
                if (toastEl) toastEl.remove();
            } else {
                alert("Export failed. Please try again.");
                if (toastEl) toastEl.remove();
            }
        } catch (e) {
            console.error("Export error:", e);
            alert("Export network error.");
            if (toastEl) toastEl.remove();
        }
    }

    addThinkingBubble() {
        const id = 'thinking-' + Date.now();
        const msg = document.createElement('div');
        msg.className = 'message jarvis-msg';
        msg.id = id;
        msg.innerHTML = `
            <div class="message-avatar jarvis-avatar">
                <img src="/static/kautilya_logo.png" class="jarvis-icon" alt="K">
            </div>
            <div class="message-bg">
                <div class="message-content thinking-content">
                    <span class="dot"></span>
                    <span class="dot"></span>
                    <span class="dot"></span>
                </div>
            </div>
        `;
        this.el.chatHistory.appendChild(msg);
        this.scrollToBottom();
        return id;
    }

    removeThinkingBubble(id) {
        const el = document.getElementById(id);
        if (el) el.remove();
    }

    toggleThinking(show) {
        const loaderId = 'global-loader-overlay';
        let loader = document.getElementById(loaderId);

        if (show) {
            if (!loader) {
                loader = document.createElement('div');
                loader.id = loaderId;
                loader.style.cssText = `
                    position: absolute;
                    top: 0; left: 0; right: 0; bottom: 0;
                    background: rgba(0,0,0,0.5);
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    z-index: 100;
                    backdrop-filter: blur(2px);
                `;
                loader.innerHTML = '<div class="splash-ring" style="width:40px;height:40px;"></div>';
                this.el.chatHistory.appendChild(loader);
            }
            loader.style.display = 'flex';
        } else {
            if (loader) loader.style.display = 'none';
        }
    }

    // ============== Markdown Rendering ==============

    configureMarked() {
        // Global copy function to avoid inline escaping hell
        if (!window.copyCode) {
            window.copyCode = function (btn) {
                const wrapper = btn.closest('.code-block-wrapper');
                const code = wrapper.querySelector('code').innerText;
                navigator.clipboard.writeText(code).then(() => {
                    const original = btn.innerHTML;
                    btn.innerHTML = '<span class="material-icons-round" style="font-size: 14px;">check</span> Copied!';
                    setTimeout(() => btn.innerHTML = original, 2000);
                });
            };
        }

        if (typeof marked !== 'undefined') {
            const renderer = new marked.Renderer();

            renderer.code = (codeInfo, fallbackLang) => {
                // Safely handle 'code' argument (marked.js v8+ passes an object)
                let safeCode = '';
                let language = fallbackLang || '';

                if (typeof codeInfo === 'object' && codeInfo !== null) {
                    safeCode = codeInfo.text || codeInfo.raw || '';
                    language = codeInfo.lang || language;
                } else if (typeof codeInfo === 'string') {
                    safeCode = codeInfo;
                }

                language = language.trim();

                let highlighted = safeCode;
                let validLang = false;

                // Use hljs global if available
                const highlighter = window.hljs || (typeof highlight !== 'undefined' ? highlight : null);

                try {
                    if (highlighter) {
                        validLang = !!(language && highlighter.getLanguage(language));
                        const ret = validLang ? highlighter.highlight(safeCode, { language }) : highlighter.highlightAuto(safeCode);

                        if (ret && ret.value) {
                            highlighted = String(ret.value);
                        } else if (typeof ret === 'string') {
                            highlighted = ret;
                        }
                    }
                } catch (e) {
                    console.warn("Highlight.js failed:", e);
                }

                // FINAL SAFETY NET: Ensure it is a string
                if (typeof highlighted !== 'string') {
                    console.error("Highlighted code is NOT a string:", highlighted);
                    highlighted = String(safeCode);
                }

                const langLabel = validLang ? language : (language || 'Code');

                // Detect previewable languages for artifact panel
                const previewableLangs = ['html', 'svg', 'mermaid', 'htm'];
                const isPreviewable = previewableLangs.includes((language || '').toLowerCase());
                const previewBtnHtml = isPreviewable ? `
                    <button class="code-preview-btn">
                        <span class="material-icons-round">play_arrow</span> Preview
                    </button>` : '';

                return `
                <div class="code-block-wrapper" data-lang="${(language || '').toLowerCase()}">
                    <div class="code-block-header">
                        <span class="code-lang">${langLabel}</span>
                        <div style="display:flex;gap:6px;align-items:center;">
                            ${previewBtnHtml}
                            <button class="code-copy-btn">
                                <span class="material-icons-round" style="font-size: 14px;">content_copy</span> Copy
                            </button>
                        </div>
                    </div>
                    <pre class="code-block-content"><code class="hljs ${language || ''}">${highlighted}</code></pre>
                </div>`;
            };

            marked.setOptions({
                renderer: renderer,
                breaks: true,
                gfm: true
            });
        }
    }

    removeCommands(text) {
        // Balanced bracket removal for [COMMAND: ...] tags to handle nested brackets (like in code)
        if (!text) return "";

        let result = "";
        let i = 0;
        const len = text.length;

        while (i < len) {
            // Check for start of a command tag
            if (text[i] === '[') {
                // Check if it matches our command pattern start
                const substring = text.substring(i);
                const match = substring.match(/^\[(IMAGE|SEARCH|WEATHER|NEWS|STOCK|PREDICT_STOCK|CRYPTO|MOVIE|CALCULATE|QUOTE|FACT|DEFINE|TRANSLATE|CONVERT|CURRENCY|WIKI|HOROSCOPE|RECIPE|RUN_PYTHON|CREATE_FILE|READ_FILE|LIST_DIR)(?::|\])/);

                if (match) {
                    // It is a command, find the balanced closing bracket
                    let depth = 0;
                    let j = i;
                    let foundEnd = false;
                    let inQuote = false;
                    let quoteChar = null;
                    let escaped = false;

                    for (; j < len; j++) {
                        const char = text[j];

                        // Handle escapes
                        if (escaped) {
                            escaped = false;
                            continue;
                        }

                        if (char === '\\') {
                            escaped = true;
                            continue;
                        }

                        // Handle quotes
                        if (char === '"' || char === "'") {
                            if (!inQuote) {
                                inQuote = true;
                                quoteChar = char;
                            } else if (char === quoteChar) {
                                inQuote = false;
                                quoteChar = null;
                            }
                        }

                        // Handle brackets (only if not in quote)
                        if (!inQuote) {
                            if (char === '[') depth++;
                            else if (char === ']') depth--;

                            if (depth === 0) {
                                i = j + 1; // Move index past the closing bracket
                                foundEnd = true;
                                break;
                            }
                        }
                    }

                    if (!foundEnd) {
                        // Incomplete command (streaming or syntax error). 
                        // CRITICAL FIX: Do NOT skip the rest of the text. 
                        // Treat as normal text so the user sees it.
                        result += text[i]; // Add the '['
                        i++; // Continue to next char
                        continue;
                    }
                    continue; // Skip appending this command to result (it was stripped)
                }
            }

            // specific check for IMG_URL which is added by backend for display, we WANT to show it (formatMarkdown handles it)
            // But wait, removeCommands is called BEFORE formatMarkdown? 
            // In processCommand: contentEl.innerHTML = this.formatMarkdown(cleanText);
            // And formatMarkdown handles [IMG_URL:...] replacement.
            // So we must NOT strip [IMG_URL:...] here. The regex above doesn't include IMG_URL. Good.

            result += text[i];
            i++;
        }
        return result;
    }

    formatMarkdown(text) {
        // Ensure marked is configured
        if (!this.markedConfigured) {
            this.configureMarked();
            this.markedConfigured = true;
        }

        // Handle <think> blocks first (preserve them)
        const thinkRegex = /<think>([\s\S]*?)(?:<\/think>|$)/g;
        let processed = text;
        const thinkBlocks = [];

        processed = processed.replace(thinkRegex, (match, content) => {
            const placeholder = `@@THINK_${thinkBlocks.length}@@`;
            thinkBlocks.push(content.trim());
            return placeholder;
        });

        // ─── Preserve Math Blocks before Markdown parsing ───
        // Marked.js treats backslashes, underscores, curly braces as markdown,
        // which mangles LaTeX like \frac{P \times R}{100} or \text{Interest}.
        const mathBlocks = [];
        const mathPlaceholder = (block) => {
            const id = `@@MATH_${mathBlocks.length}@@`;
            mathBlocks.push(block);
            return id;
        };
        // Display math: $$ ... $$ (can span multiple lines)
        processed = processed.replace(/\$\$([\s\S]*?)\$\$/g, (m) => mathPlaceholder(m));
        // Display math: \[ ... \]
        processed = processed.replace(/\\\[([\s\S]*?)\\\]/g, (m) => mathPlaceholder(m));
        // Inline math: $ ... $ (single line, non-greedy)
        processed = processed.replace(/\$([^\$\n]+?)\$/g, (m) => mathPlaceholder(m));
        // Inline math: \( ... \)
        processed = processed.replace(/\\\(([\s\S]*?)\\\)/g, (m) => mathPlaceholder(m));

        // Custom Image Parser for backend-generated images (api.airforce Flux-2-Dev)
        processed = processed.replace(/\[IMG_URL:\s*(.+?)\]/g, (match, url) => {
            const cleanUrl = url.trim();
            return `<div style="margin: 10px 0;">
                <img src="${cleanUrl}" class="chat-image" style="max-width: 100%; border-radius: 10px; cursor: pointer; box-shadow: 0 4px 15px rgba(0,0,0,0.3);" alt="AI Generated Image" loading="lazy">
            </div>`;
        });

        // Legacy Puter.js fallback (keep for backward compatibility with old chat history)
        processed = processed.replace(/\[PUTER_IMAGE:\s*(.+?)\]/g, (match, prompt) => {
            return `<div style="padding: 10px; background: rgba(255,255,255,0.05); border-radius: 10px; margin: 10px 0; border: 1px dashed rgba(255,255,255,0.2); text-align: center; color: #999;">
                ⚠️ Image generation for "${prompt.trim()}" — please re-request to generate with Flux AI.
            </div>`;
        });

        // Parse Markdown using marked.js
        let htmlContent = '';
        if (typeof marked !== 'undefined') {
            htmlContent = marked.parse(processed);
            if (typeof DOMPurify !== 'undefined') {
                htmlContent = DOMPurify.sanitize(htmlContent, {
                    ADD_TAGS: ['details', 'summary'],
                    ADD_ATTR: ['target']
                });
            }
        } else {
            htmlContent = this.escapeHtml(processed);
        }

        // Restore think blocks
        thinkBlocks.forEach((content, i) => {
            htmlContent = htmlContent.replace(`@@THINK_${i}@@`, `
                <details class="reasoning-details" open>
                    <summary><span class="material-icons-round" style="font-size:14px;vertical-align:middle;">psychology</span> Thought Process</summary>
                    <div class="reasoning-content">${this.escapeHtml(content)}</div>
                </details>
            `);
        });

        // ─── Restore Math Blocks ───
        mathBlocks.forEach((block, i) => {
            // Marked may wrap placeholders in <p> tags — handle both
            htmlContent = htmlContent.replace(`<p>@@MATH_${i}@@</p>`, block);
            htmlContent = htmlContent.replace(`@@MATH_${i}@@`, block);
        });

        return htmlContent;
    }

    // Helper to trigger math rendering on a specific element
    renderMath(element) {
        if (typeof renderMathInElement !== 'undefined' && element) {
            renderMathInElement(element, {
                delimiters: [
                    { left: '$$', right: '$$', display: true },
                    { left: '$', right: '$', display: false },
                    { left: '\\(', right: '\\)', display: false },
                    { left: '\\[', right: '\\]', display: true }
                ],
                throwOnError: false
            });
        }
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.innerText = text;
        return div.innerHTML;
    }

    // Convert any image blob to PNG (Clipboard API only supports PNG)
    _convertToPng(blob) {
        return new Promise((resolve, reject) => {
            const img = new Image();
            img.crossOrigin = 'anonymous';
            img.onload = () => {
                const canvas = document.createElement('canvas');
                canvas.width = img.naturalWidth;
                canvas.height = img.naturalHeight;
                const ctx = canvas.getContext('2d');
                ctx.drawImage(img, 0, 0);
                canvas.toBlob(pngBlob => {
                    if (pngBlob) resolve(pngBlob);
                    else reject(new Error('PNG conversion failed'));
                }, 'image/png');
            };
            img.onerror = () => reject(new Error('Image load failed'));
            img.src = URL.createObjectURL(blob);
        });
    }

    // ============== Voice Mode Logic (LiveKit) ==============

    async startVoiceMode() {
        if (typeof LiveKitVoiceClient === 'undefined') {
            alert("Voice engine not loaded. Please refresh the page.");
            return;
        }

        this.isVoiceActive = true;
        this.el.voiceOverlay.style.display = 'flex';
        document.body.classList.add('voice-active');
        this.renderWaveform();

        // Create LiveKit voice client (default Kautilya — no agentId)
        this._lkVoice = new LiveKitVoiceClient({
            participantName: this.firebaseAuth?.user?.displayName || 'User',
            onStatusChange: (status) => {
                this.updateVoiceStatus(status);
                // Animate waveform when agent speaks
                if (status.includes('speaking')) {
                    this.setWaveformActive(true);
                } else if (status.includes('Listening') || status.includes('Connected')) {
                    this.setWaveformActive(true); // subtle animation while listening
                } else {
                    this.setWaveformActive(false);
                }
            },
            onConnected: () => {
                this.updateVoiceStatus('Connected — Speak to Kautilya');
                this.setWaveformActive(true);
            },
            onDisconnected: () => {
                if (this.isVoiceActive) this.endVoiceMode();
            },
            onError: (msg) => {
                this.updateVoiceStatus('Error: ' + msg);
                setTimeout(() => {
                    if (this.isVoiceActive) this.endVoiceMode();
                }, 3000);
            }
        });

        await this._lkVoice.connect();
    }

    endVoiceMode() {
        this.isVoiceActive = false;
        this.el.voiceOverlay.style.display = 'none';
        document.body.classList.remove('voice-active');

        if (this._lkVoice) {
            this._lkVoice.disconnect();
            this._lkVoice = null;
        }

        this.isMuted = false;
        this.setWaveformActive(false);
        
        // Reset mute button state
        if (this.el.voiceMuteBtn) {
            this.el.voiceMuteBtn.classList.remove('muted');
            this.el.voiceMuteBtn.querySelector('span').innerText = 'mic';
        }
    }

    toggleMute() {
        if (!this._lkVoice || !this.isVoiceActive) return;
        
        this._lkVoice.toggleMute().then(muted => {
            this.isMuted = muted;
            this.el.voiceMuteBtn.classList.toggle('muted', this.isMuted);
            this.el.voiceMuteBtn.querySelector('span').innerText = this.isMuted ? 'mic_off' : 'mic';
        });
    }

    async queueTTS(text) {
        if (!this.ttsEnabled || !this.isVoiceActive) return;

        // Push a placeholder promise to keep order
        let resolveBlob;
        const blobPromise = new Promise(resolve => resolveBlob = resolve);
        this.ttsQueue.push(blobPromise);

        // Try to start playing immediately if nothing is currently playing
        if (!this.isSpeaking) {
            this.playNextTTS();
        }

        try {
            // Fetch audio concurrently in the background
            const resp = await fetch('/api/voice/speak/stream', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ text })
            });
            const blob = await resp.blob();
            resolveBlob(blob); // Resolve the promise in the queue with the downloaded blob
        } catch (e) {
            console.error("Failed to fetch TTS for chunk:", e);
            resolveBlob(null); // Resolve with null on error to skip
        }
    }

    async playNextTTS() {
        if (this.ttsQueue.length === 0) {
            this.isSpeaking = false;
            this.setWaveformActive(false);
            if (this.isVoiceActive && !this.isGeneratingAudioStream) {
                // Only start listening if the backend is also done generating
                this.startRecording(this.mediaRecorder.stream);
            }
            return;
        }

        this.isSpeaking = true;
        this.updateVoiceStatus("Speaking...");
        this.setWaveformActive(true);

        const blobPromise = this.ttsQueue.shift();
        const blob = await blobPromise; // Wait for background fetch to finish if it hasn't already

        if (!blob) {
            // If fetch failed, skip to next
            return this.playNextTTS();
        }

        try {
            const url = URL.createObjectURL(blob);
            this.el.audioPlayer.src = url;
            this.el.audioPlayer.play();

            this.el.audioPlayer.onended = () => {
                URL.revokeObjectURL(url);
                this.playNextTTS(); // Instantly trigger the next pre-downloaded chunk
            };
        } catch (e) {
            console.error(e);
            this.playNextTTS();
        }
    }

    // --- HUD Updates ---

    renderWaveform() {
        this.el.waveform.innerHTML = '';
        for (let i = 0; i < 4; i++) {
            const bar = document.createElement('div');
            bar.className = 'wave-bar';
            this.el.waveform.appendChild(bar);
        }
    }

    updateVoiceStatus(text) {
        this.el.voiceStatus.innerText = text;
    }

    setWaveformActive(isActive) {
        if (isActive) {
            this.el.waveform.classList.add('active');
            this._waveInterval = setInterval(() => {
                this.el.waveform.childNodes.forEach(bar => {
                    bar.style.height = `${10 + Math.random() * 40}px`;
                });
            }, 100);
        } else {
            this.el.waveform.classList.remove('active');
            clearInterval(this._waveInterval);
            this.el.waveform.childNodes.forEach(bar => {
                bar.style.height = '10px';
            });
        }
    }

    async syncUserSettings() {
        if (!this.firebaseAuth.user) return;
        try {
            const token = await this.firebaseAuth.getIdToken();
            const resp = await fetch('/api/user/settings', {
                headers: { 
                    'Authorization': `Bearer ${token}`,
                    'X-Session-ID': this.sessionId
                }
            });
            if (resp.ok) {
                const data = await resp.json();
                if (data.settings) {
                    const s = data.settings;
                    if (s.display_name) localStorage.setItem('kautilya_display_name', s.display_name);
                    if (s.preferred_name) localStorage.setItem('kautilya_pref_name', s.preferred_name);
                    if (s.work_function) localStorage.setItem('kautilya_pref_work', s.work_function);
                    if (s.personal_preferences) localStorage.setItem('kautilya_pref_system', s.personal_preferences);
                    if (s.theme) localStorage.setItem('kautilya_theme', s.theme);
                    if (s.tts_enabled !== undefined) localStorage.setItem('kautilya_tts', s.tts_enabled);
                    if (s.notifications_enabled !== undefined) localStorage.setItem('kautilya_notify', s.notifications_enabled);
                    
                    // Reload UI with new settings
                    this.loadSettings();
                }
            }
        } catch (e) {
            console.error('[Sync] Settings sync failed:', e);
        }
    }

    async updateAccountSection(user) {
        const accountEmail = document.getElementById('accountEmail');
        const sessionList = document.getElementById('sessionList');
        if (!accountEmail || !sessionList) return;

        accountEmail.textContent = user ? user.email : 'Not logged in';
        sessionList.innerHTML = '<div class="loading-spinner-small"></div>';

        if (!user) {
            sessionList.innerHTML = '<p style="color: var(--text-secondary); font-size: 0.9rem;">Please login to see account details.</p>';
            return;
        }

        try {
            const token = await this.firebaseAuth.getIdToken();
            const resp = await fetch('/api/user/account', {
                headers: { 
                    'Authorization': `Bearer ${token}`,
                    'X-Session-ID': this.sessionId
                }
            });
            if (resp.ok) {
                const data = await resp.json();
                
                // Display Provider
                const providerEl = document.getElementById('accountProvider');
                if (providerEl) providerEl.textContent = data.provider || 'Email';

                // Display Sessions
                sessionList.innerHTML = '';
                if (data.sessions && data.sessions.length > 0) {
                    data.sessions.forEach(session => {
                        const item = document.createElement('div');
                        item.className = 'session-item';
                        item.innerHTML = `
                            <div class="session-icon">
                                <span class="material-icons-round">${session.device.includes('Mobile') ? 'smartphone' : 'desktop_windows'}</span>
                            </div>
                            <div class="session-info">
                                <div class="session-device">${session.device} • ${session.browser}</div>
                                <div class="session-meta">${session.location} • ${session.last_active}</div>
                            </div>
                            ${session.is_current ? '<div class="session-badge">Current</div>' : ''}
                        `;
                        sessionList.appendChild(item);
                    });
                }
            }
        } catch (e) {
            console.error('[Account] Failed to fetch account info:', e);
            sessionList.innerHTML = '<p style="color: var(--text-danger); font-size: 0.85rem;">Failed to load session details.</p>';
        }
    }

    // ============== Auth State ==============

    onAuthChanged(user) {
        if (user) {
            // Logged in
            this.toggleLoginModal(false);
            this.updateUserUI(user);
            this.loadChatsFromServer();
            this.syncUserSettings(); // Sync settings on login
        } else {
            // Logged out
            this.updateUserUI(null);
            this.loadSettings(); // Reset to local defaults
        }
    }

    updateUserUI(user) {
        const avatar = this.el.userAvatar;
        const loginBtn = this.el.loginBtn;
        const dropdown = document.getElementById('profileDropdown');
        const wrapper = document.getElementById('profileWrapper');

        // Sidebar Elements
        const sidebarProfile = this.el.sidebarProfile;
        const sidebarAvatar = this.el.sidebarAvatarImg;
        const sidebarName = this.el.sidebarUsername;

        // Remove existing listeners to avoid dupes (for header avatar)
        if (avatar) {
            const newAvatar = avatar.cloneNode(true);
            avatar.parentNode.replaceChild(newAvatar, avatar);
            this.el.userAvatar = newAvatar;
        }

        if (user) {
            // Logged In
            const photoURL = user.photoURL || 'https://lh3.googleusercontent.com/a/default-user';
            const initial = (user.displayName || user.email || 'U')[0].toUpperCase();
            const displayName = user.displayName || 'User';

            // 1. Header Avatar
            if (this.el.userAvatar) {
                this.el.userAvatar.style.display = 'flex';
                this.el.userAvatar.innerHTML = user.photoURL
                    ? `<img src="${photoURL}" alt="${initial}" class="user-photo" referrerpolicy="no-referrer">`
                    : `<span class="user-initial">${initial}</span>`;

                this.el.userAvatar.onclick = (e) => {
                    e.stopPropagation();
                    dropdown.classList.toggle('show');
                    if (dropdown.classList.contains('show')) {
                        this.updateDropdownInfo(user);
                    }
                };
            }

            // 2. Sidebar Profile
            if (sidebarProfile) {
                sidebarProfile.style.display = 'flex';
                if (sidebarAvatar) sidebarAvatar.src = photoURL;
                if (sidebarName) sidebarName.textContent = displayName;

                // Fetch User Tier Status (Pro / Free)
                const statusEl = sidebarProfile.querySelector('.sidebar-status');
                if (statusEl) {
                    statusEl.textContent = "Loading...";
                    this.firebaseAuth.getIdToken().then(token => {
                        return fetch('/api/jarvis/status', {
                            headers: { 'Authorization': `Bearer ${token}` }
                        });
                    }).then(res => res.json()).then(data => {
                        if (data && data.role) {
                            statusEl.innerHTML = data.is_pro
                                ? `<span style="color: #FFD700; font-weight: bold;"><span class="material-icons-round" style="font-size: 14px; vertical-align: middle;">workspace_premium</span> ${data.role}</span>`
                                : data.role;
                        } else {
                            statusEl.textContent = "Free Plan";
                        }
                    }).catch(e => {
                        console.error('Failed to fetch user status', e);
                        statusEl.textContent = "Free Plan";
                    });
                }
            }

            // 3. Hide Login Button
            if (loginBtn) loginBtn.style.display = 'none';

            // 4. Update Settings Avatar Badge
            const settingsBadge = document.getElementById('settingsAvatarBadge');
            if (settingsBadge) {
                if (user.photoURL) {
                    settingsBadge.innerHTML = `<img src="${photoURL}" style="width: 100%; height: 100%; object-fit: cover;">`;
                    settingsBadge.classList.add('has-photo');
                } else {
                    settingsBadge.innerHTML = initial;
                }
            }
            
            // 5. Update Account Section information
            this.updateAccountSection(user);

            // Wire up dropdown items
            if (dropdown) {
                this.setupDropdownActions(user);
                // Close on click outside
                document.addEventListener('click', (e) => {
                    if (wrapper && !wrapper.contains(e.target)) {
                        dropdown.classList.remove('show');
                    }
                });
            }

        } else {
            // Logged Out (Guest)

            // 1. Hide Header Avatar
            if (this.el.userAvatar) this.el.userAvatar.style.display = 'none';

            // 2. Hide Sidebar Profile
            if (sidebarProfile) sidebarProfile.style.display = 'none';

            // 3. Show Login Button
            if (loginBtn) {
                loginBtn.style.display = 'flex';
                loginBtn.querySelector('.login-label').textContent = 'Sign In';
                loginBtn.onclick = () => this.toggleLoginModal(true);
            }

            if (dropdown) dropdown.classList.remove('show');
        }
    }

    async updateDropdownInfo(user) {
        document.getElementById('dropdownUserName').textContent = user.displayName || 'User';
        document.getElementById('dropdownUserEmail').textContent = user.email || '';

        const avatarEl = document.getElementById('dropdownAvatar');
        const initial = (user.displayName || user.email || 'U')[0].toUpperCase();
        avatarEl.innerHTML = user.photoURL
            ? `<img src="${user.photoURL}" alt="${initial}">`
            : initial;

        // Fetch memory count
        try {
            const token = await this.firebaseAuth.getIdToken();
            const res = await fetch('/api/memory', {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            if (res.ok) {
                const data = await res.json();
                document.getElementById('memoryCount').textContent = data.count || 0;
            }
        } catch (e) {
            console.error("Failed to fetch memory count", e);
        }
    }

    setupDropdownActions(user) {
        // Sign Out
        document.getElementById('dropdownSignOut').onclick = () => {
            if (confirm('Sign out of KAUTILYA AI?')) {
                this.firebaseAuth.signOut();
                document.getElementById('profileDropdown').classList.remove('show');
            }
        };

        // Clear Memory
        document.getElementById('dropdownClearMemory').onclick = async () => {
            if (confirm('Clear all your personalized memories? KAUTILYA AI will forget everything about you.')) {
                try {
                    const token = await this.firebaseAuth.getIdToken();
                    await fetch('/api/memory', {
                        method: 'DELETE',
                        headers: { 'Authorization': `Bearer ${token}` }
                    });
                    alert('Memory cleared.');
                    this.updateDropdownInfo(user); // refresh count
                } catch (e) {
                    alert('Failed to clear memory.');
                }
            }
        };

        // Info Modals
        const modal = document.getElementById('infoModalOverlay');
        const title = document.getElementById('infoModalTitle');
        const body = document.getElementById('infoModalBody');
        const close = document.getElementById('infoModalClose');

        const showModal = (header, content) => {
            title.textContent = header;
            body.innerHTML = content;
            modal.classList.add('show');
            document.getElementById('profileDropdown').classList.remove('show');
        };

        close.onclick = () => modal.classList.remove('show');
        modal.onclick = (e) => {
            if (e.target === modal) modal.classList.remove('show');
        };

        document.getElementById('dropdownFAQ').onclick = () => showModal('FAQs', this.getFAQContent());
        document.getElementById('dropdownTerms').onclick = () => showModal('Terms & Conditions', this.getTermsContent());
        document.getElementById('dropdownPrivacy').onclick = () => showModal('Privacy Policy', this.getPrivacyContent());
        document.getElementById('dropdownMemory').onclick = () => showModal('My Memory', 'KAUTILYA AI learns from your conversations to provide better, more personalized assistance.<br><br>The "My Memory" count shows how many personalized facts Kautilya has stored about you — your preferences, interests, and details you\'ve shared.<br><br>Use the "Clear Memory" option to reset this data at any time.');
    }

    getFAQContent() {
        return `
            <h3>What is KAUTILYA AI?</h3>
            <p>KAUTILYA AI is an advanced cloud AI assistant built by RevealIQ Industries, powered by state-of-the-art large language models. It is designed to help you with coding, creative writing, research, analysis, and everyday tasks — all with a uniquely Indian, culturally-rich personality inspired by the legendary strategist Chanakya.</p>
            <h3>Is it free?</h3>
            <p>Yes! KAUTILYA AI provides free access for personal use with optimized models. Upgrade to <strong>Kautilya Pro</strong> for extended context limits and premium features.</p>
            <h3>How does memory work?</h3>
            <p>When you are signed in, Kautilya remembers key details from your conversations — like your name, preferences, and interests — to make future interactions more personalized and helpful. Your memory data is stored securely and is private to your account. You can clear it anytime from the dropdown menu.</p>
            <h3>What makes Kautilya different?</h3>
            <p>Kautilya is not just another chatbot. It brings the strategic brilliance and cultural wisdom of ancient India to modern AI — think of it as your personal advisor with an Indian soul. It supports image generation, web search, voice mode, and much more.</p>
            <h3>Who built this?</h3>
            <p>KAUTILYA AI is created by Harsh, CEO & Founder of RevealIQ Industries. Built with ❤️ in India.</p>
        `;
    }

    getTermsContent() {
        return `
            <h3>Terms of Service</h3>
            <p><strong>KAUTILYA AI</strong> — by RevealIQ Industries</p>
            <p>By accessing and using KAUTILYA AI, you agree to the following terms:</p>
            <ul>
                <li><strong>Acceptable Use:</strong> You will not use the service for illegal, harmful, or abusive activities. This includes generating malicious content, attempting prompt injection, or any form of exploitation.</li>
                <li><strong>AI-Generated Content:</strong> Responses are generated by AI models and may not always be accurate. We do not guarantee the correctness, completeness, or reliability of AI outputs. Always verify critical information independently.</li>
                <li><strong>Account Conduct:</strong> We reserve the right to suspend or terminate accounts that abuse the service, attempt to bypass rate limits, or violate these terms.</li>
                <li><strong>Service Availability:</strong> KAUTILYA AI is provided "as-is" without warranty. We may modify, suspend, or discontinue the service at any time without prior notice.</li>
                <li><strong>Intellectual Property:</strong> The KAUTILYA AI platform, design, and branding are the intellectual property of RevealIQ Industries.</li>
            </ul>
            <p><em>Last updated: February 2026</em></p>
        `;
    }

    getPrivacyContent() {
        return `
            <h3>Privacy Policy</h3>
            <p><strong>KAUTILYA AI</strong> — by RevealIQ Industries</p>
            <p>Your privacy is important to us. Here's how we handle your data:</p>
            <ul>
                <li><strong>Conversations:</strong> Your chat history is stored to provide context within a session. Sign-in enables cloud sync across devices. Conversations are not shared with or sold to third parties.</li>
                <li><strong>Memory System:</strong> When signed in, Kautilya may store personalized facts (e.g., your name, preferences) to improve your experience. You can view stored memories via "My Memory" and delete them anytime using "Clear Memory".</li>
                <li><strong>Authentication:</strong> We use Firebase Authentication (Google Sign-In or Email/Password). We only access your display name, email, and profile photo for the purpose of personalizing your experience.</li>
                <li><strong>Data Storage:</strong> User data is stored securely using Firebase and encrypted at rest. We do not sell, rent, or trade your personal data.</li>
                <li><strong>Third-Party APIs:</strong> Your queries may be processed by third-party LLM providers (Google Gemini, Groq, OpenRouter) for generating responses. These providers have their own privacy policies.</li>
                <li><strong>Analytics:</strong> We may collect anonymous usage analytics to improve the service. No personally identifiable information is included in analytics.</li>
            </ul>
            <p><em>Last updated: February 2026</em></p>
        `;
    }

    // ============== Event Binding ==============
    // Event Binding consolidated in init/bindEvents above

    async syncChatsToServer() {
        const token = await this.firebaseAuth.getIdToken();
        if (!token) return;

        const chats = this.history.getAllChats();
        const chatIds = Object.keys(chats);
        if (chatIds.length === 0) return;

        try {
            await fetch('/api/chat/save', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${token}`
                },
                body: JSON.stringify({ chats })
            });
            console.log('[Sync] Uploaded', chatIds.length, 'chats to server');
        } catch (e) {
            console.error('[Sync] Upload failed:', e);
        }
    }

    async loadChatsFromServer() {
        const token = await this.firebaseAuth.getIdToken();
        if (!token) return;

        try {
            const resp = await fetch('/api/chat/history', {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            if (!resp.ok) return;
            const data = await resp.json();
            const serverChats = data.chats || {};

            // Merge: server chats fill in any missing ones locally
            const localChats = this.history.getAllChats();
            let merged = false;
            for (const [id, chat] of Object.entries(serverChats)) {
                if (!localChats[id]) {
                    this.history.saveChat(id, chat);
                    merged = true;
                }
            }
            if (merged) {
                this.renderSidebar();
            }

            // Upload any local-only chats to server
            this.syncChatsToServer();

            console.log('[Sync] Loaded chats from server');
        } catch (e) {
            console.error('[Sync] Load failed:', e);
        }
    }

    // ============== Login Modal ==============

    toggleLoginModal(show) {
        if (this.el.loginModal) {
            this.el.loginModal.classList.toggle('show', show);
        }
    }

    // ============== Artifact Preview Panel ==============

    openArtifactPanel(triggerBtn) {
        const wrapper = triggerBtn.closest('.code-block-wrapper');
        if (!wrapper) return;

        const codeEl = wrapper.querySelector('code');
        const rawCode = codeEl ? codeEl.innerText : '';
        const lang = (wrapper.dataset.lang || '').toLowerCase();

        if (!rawCode.trim()) return;

        this.currentArtifactCode = rawCode;
        this.currentArtifactLang = lang;

        // Try to find a combined HTML document by looking for CSS/JS blocks in the same message
        let fullHtml = rawCode;
        if (lang === 'html' || lang === 'htm') {
            const messageEl = wrapper.closest('.message');
            if (messageEl) {
                fullHtml = this._combineCodeBlocks(messageEl, rawCode);
            }
        }

        // Set title
        const titleMap = { 'html': 'HTML Document', 'htm': 'HTML Document', 'svg': 'SVG Graphic', 'mermaid': 'Mermaid Diagram' };
        const iconMap = { 'html': 'web', 'htm': 'web', 'svg': 'image', 'mermaid': 'account_tree' };
        this.el.artifactTitle.textContent = titleMap[lang] || 'Preview';
        this.el.artifactTypeIcon.textContent = iconMap[lang] || 'code';

        // Render in iframe
        this._renderArtifactPreview(fullHtml, lang);

        // Show code in code view tab
        this.el.artifactCodeContent.textContent = rawCode;

        // Activate preview tab
        this.switchArtifactTab('preview');

        // Open panel
        this.el.artifactPanel.classList.add('open');
        document.body.classList.add('artifact-open');

        // Auto-collapse sidebar on desktop to make room
        const appSidebar = document.getElementById('appSidebar');
        if (appSidebar && window.innerWidth > 768) {
            appSidebar.classList.add('collapsed');
        }

        // Bind events (safe to call multiple times)
        this._bindArtifactEvents();
    }

    _renderArtifactPreview(code, lang) {
        const iframe = this.el.artifactPreviewFrame;

        if (lang === 'svg') {
            // Wrap SVG in a minimal HTML page
            const svgHtml = `<!DOCTYPE html><html><head><meta charset="UTF-8"><style>body{margin:0;display:flex;justify-content:center;align-items:center;min-height:100vh;background:#1a1a1b;}</style></head><body>${code}</body></html>`;
            iframe.srcdoc = svgHtml;
        } else if (lang === 'mermaid') {
            // Render Mermaid diagram using CDN
            const mermaidHtml = `<!DOCTYPE html><html><head><meta charset="UTF-8">
            <script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"><\/script>
            <style>body{margin:20px;background:#1a1a1b;display:flex;justify-content:center;}.mermaid{color:#e3e3e3;}</style>
            </head><body><div class="mermaid">${code.replace(/</g, '&lt;').replace(/>/g, '&gt;')}</div>
            <script>mermaid.initialize({startOnLoad:true,theme:'dark'});<\/script></body></html>`;
            iframe.srcdoc = mermaidHtml;
        } else {
            // HTML — check if it's a full document or a fragment
            let htmlDoc = code;
            if (!code.toLowerCase().includes('<!doctype') && !code.toLowerCase().includes('<html')) {
                // Wrap fragment in a proper document
                htmlDoc = `<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"><style>body{font-family:'Inter','Segoe UI',system-ui,sans-serif;margin:0;padding:20px;}</style></head><body>${code}</body></html>`;
            }
            iframe.srcdoc = htmlDoc;
        }

        // Show iframe, hide code view
        iframe.style.display = 'block';
        this.el.artifactCodeView.style.display = 'none';
    }

    _combineCodeBlocks(messageEl, htmlCode) {
        // Look for CSS and JS code blocks in the same message
        let combinedCSS = '';
        let combinedJS = '';

        const allWrappers = messageEl.querySelectorAll('.code-block-wrapper');
        allWrappers.forEach(w => {
            const wLang = (w.dataset.lang || '').toLowerCase();
            const wCode = w.querySelector('code')?.innerText || '';
            if (wLang === 'css') combinedCSS += wCode + '\n';
            else if (wLang === 'javascript' || wLang === 'js') combinedJS += wCode + '\n';
        });

        if (!combinedCSS && !combinedJS) return htmlCode;

        // If the HTML already has </head> or </body>, inject into those
        let result = htmlCode;
        if (combinedCSS) {
            const styleTag = `<style>${combinedCSS}</style>`;
            if (result.includes('</head>')) {
                result = result.replace('</head>', styleTag + '</head>');
            } else if (result.includes('<body')) {
                result = result.replace(/<body/i, styleTag + '<body');
            } else {
                result = styleTag + result;
            }
        }
        if (combinedJS) {
            const scriptTag = `<script>${combinedJS}<\/script>`;
            if (result.includes('</body>')) {
                result = result.replace('</body>', scriptTag + '</body>');
            } else {
                result += scriptTag;
            }
        }

        return result;
    }

    closeArtifactPanel() {
        this.el.artifactPanel.classList.remove('open');
        document.body.classList.remove('artifact-open');

        // Clear iframe after animation
        setTimeout(() => {
            this.el.artifactPreviewFrame.srcdoc = '';
            this.currentArtifactCode = '';
            this.currentArtifactLang = '';
        }, 400);
    }

    switchArtifactTab(tab) {
        if (tab === 'preview') {
            this.el.artifactPreviewFrame.style.display = 'block';
            this.el.artifactCodeView.style.display = 'none';
            this.el.artifactTabPreview.classList.add('active');
            this.el.artifactTabCode.classList.remove('active');
        } else {
            this.el.artifactPreviewFrame.style.display = 'none';
            this.el.artifactCodeView.style.display = 'block';
            this.el.artifactTabPreview.classList.remove('active');
            this.el.artifactTabCode.classList.add('active');
        }
    }

    downloadArtifact() {
        if (!this.currentArtifactCode) return;

        const extMap = { 'html': 'html', 'htm': 'html', 'svg': 'svg', 'mermaid': 'md', 'css': 'css', 'javascript': 'js', 'js': 'js' };
        const ext = extMap[this.currentArtifactLang] || 'txt';
        const mimeMap = { 'html': 'text/html', 'svg': 'image/svg+xml', 'css': 'text/css', 'js': 'text/javascript' };
        const mime = mimeMap[ext] || 'text/plain';

        const blob = new Blob([this.currentArtifactCode], { type: mime });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `kautilya_artifact_${Date.now()}.${ext}`;
        document.body.appendChild(a);
        a.click();
        URL.revokeObjectURL(url);
        document.body.removeChild(a);
    }

    _bindArtifactEvents() {
        if (this._artifactEventsBound) return;
        this._artifactEventsBound = true;

        // Close button
        this.el.artifactCloseBtn.onclick = () => this.closeArtifactPanel();

        // Tab switching
        this.el.artifactTabPreview.onclick = () => this.switchArtifactTab('preview');
        this.el.artifactTabCode.onclick = () => this.switchArtifactTab('code');

        // Copy
        this.el.artifactCopyBtn.onclick = () => {
            if (!this.currentArtifactCode) return;
            navigator.clipboard.writeText(this.currentArtifactCode).then(() => {
                const icon = this.el.artifactCopyBtn.querySelector('span');
                icon.textContent = 'check';
                setTimeout(() => icon.textContent = 'content_copy', 1500);
            });
        };

        // Download
        this.el.artifactDownloadBtn.onclick = () => this.downloadArtifact();

        // Close on Escape key
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && this.el.artifactPanel.classList.contains('open')) {
                this.closeArtifactPanel();
            }
        });
    }
}

// ============== Global Helpers ==============

function copyCodeBlock(btn) {
    const codeEl = btn.closest('.code-block').querySelector('code');
    const text = codeEl.innerText;
    navigator.clipboard.writeText(text).then(() => {
        btn.innerHTML = '<span class="material-icons-round">check</span> Copied!';
        setTimeout(() => {
            btn.innerHTML = '<span class="material-icons-round">content_copy</span> Copy';
        }, 2000);
    });
}

// ============== Boot ==============

document.addEventListener('DOMContentLoaded', () => {
    const splash = document.getElementById('splashScreen');
    console.log('[Splash] Init found:', splash);

    if (splash) {
        // Failsafe: Click to dismiss
        splash.addEventListener('click', () => {
            console.log('[Splash] Manual dismiss');
            splash.classList.add('hidden');
            if (!window.jarvis) {
                try {
                    window.jarvis = new JarvisCloudApp();
                } catch (e) {
                    console.error('[Splash] App init failed:', e);
                }
            }
        });

        // Show splash for ~3s, then shrink toward header logo and init app
        setTimeout(() => {
            console.log('[Splash] Shrinking...');
            splash.classList.add('shrink-out');

            // After shrink animation completes, hide splash and boot app
            setTimeout(() => {
                console.log('[Splash] Hiding and booting app...');
                splash.classList.add('hidden');
                try {
                    window.jarvis = new JarvisCloudApp();
                    console.log('[Splash] App booted');
                } catch (e) {
                    console.error('[Splash] App boot error:', e);
                    alert("Error starting KAUTILYA AI: " + e.message);
                }
            }, 600);
        }, 3000);
    } else {
        console.error('[Splash] Element not found!');
        try {
            window.jarvis = new JarvisCloudApp();
        } catch (e) {
            console.error('[Splash] App boot error (no splash):', e);
        }
    }
});

// Event delegation for code copy buttons, preview buttons, and images
document.addEventListener('click', function (e) {
    const previewBtn = e.target.closest('.code-preview-btn');
    if (previewBtn && window.jarvis) {
        window.jarvis.openArtifactPanel(previewBtn);
        return;
    }

    const btn = e.target.closest('.code-copy-btn');
    if (btn) {
        let codeBlock = btn.closest('.code-block');
        if (!codeBlock) codeBlock = btn.closest('.code-block-wrapper');
        if (!codeBlock) return;

        // Try to get text from code element, fallback to pre
        const codeEl = codeBlock.querySelector('code');
        const text = codeEl ? codeEl.innerText : codeBlock.querySelector('pre').innerText;

        if (text) {
            navigator.clipboard.writeText(text).then(() => {
                const originalHtml = btn.innerHTML;
                btn.innerHTML = '<span class="material-icons-round" style="font-size:14px;">check</span>';
                btn.classList.add('copied');

                setTimeout(() => {
                    btn.innerHTML = originalHtml;
                    btn.classList.remove('copied');
                }, 2000);
            }).catch(err => {
                console.error('Copy failed:', err);
                btn.innerHTML = '<span class="material-icons-round" style="font-size:14px;">error</span>';
                setTimeout(() => {
                    btn.innerHTML = '<span class="material-icons-round">content_copy</span> Copy';
                }, 2000);
            });
        }
        return;
    }

    const img = e.target.closest('.chat-image');
    if (img && typeof window.openImageViewer === 'function') {
        window.openImageViewer(img.src);
    }
});

document.addEventListener('error', function (e) {
    if (e.target && e.target.tagName && e.target.tagName.toLowerCase() === 'img' && e.target.classList.contains('chat-image')) {
        e.target.style.display = 'none';
        const fallback = document.createElement('div');
        fallback.innerHTML = '⚠️ Image failed to load.';
        fallback.style.color = '#999';
        if (e.target.parentElement) {
            e.target.parentElement.appendChild(fallback);
        }
    }
}, true);
