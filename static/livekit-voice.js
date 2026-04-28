/**
 * LiveKit Voice Client — Kautilya AI + RevealIQ Dashboard
 * Provides a universal LiveKit WebRTC voice integration for:
 *   1. Dashboard Agent "Web Call" mode (with agentId context)
 *   2. Webapp chat voice mode (default Kautilya agent)
 *
 * Requires: livekit-client UMD bundle loaded via CDN
 */

class LiveKitVoiceClient {
    /**
     * @param {Object} opts - Configuration options
     * @param {string} [opts.agentId] - Dashboard agent ID (sends agent context to LiveKit worker)
     * @param {string} [opts.participantName] - Display name for the participant
     * @param {Function} [opts.onStatusChange] - Callback: (statusText) => void
     * @param {Function} [opts.onConnected] - Callback when connected
     * @param {Function} [opts.onDisconnected] - Callback when disconnected
     * @param {Function} [opts.onError] - Callback: (errorMessage) => void
     */
    constructor(opts = {}) {
        this.room = null;
        this.isConnected = false;
        this.isMuted = false;
        this.agentId = opts.agentId || '';
        this.participantName = opts.participantName || 'User';
        this._audioElements = [];

        // Callbacks
        this.onStatusChange = opts.onStatusChange || (() => {});
        this.onConnected = opts.onConnected || (() => {});
        this.onDisconnected = opts.onDisconnected || (() => {});
        this.onError = opts.onError || (() => {});
    }

    _setStatus(text) {
        this.onStatusChange(text);
    }

    /**
     * Connect to a LiveKit voice room.
     * Fetches a JWT from /api/livekit/token, connects, and enables the microphone.
     */
    async connect() {
        if (this.isConnected) {
            console.warn('[LiveKit] Already connected');
            return;
        }

        try {
            this._setStatus('Connecting...');

            // 1. Fetch Token from Backend
            const body = { participantName: this.participantName };
            if (this.agentId) body.agentId = this.agentId;

            const response = await fetch('/api/livekit/token', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body)
            });
            const data = await response.json();

            if (!data.token) {
                throw new Error(data.error || 'Failed to get LiveKit token');
            }
            
            const wsUrl = data.wsUrl || 'wss://your-project.livekit.cloud';
            if (!data.wsUrl || wsUrl === 'wss://your-project.livekit.cloud') {
                console.warn('[LiveKit] Using placeholder or missing LiveKit URL. Please ensure LIVEKIT_URL is set in backend.');
            }

            // 2. Ensure SDK is loaded
            if (typeof LivekitClient === 'undefined') {
                throw new Error('LivekitClient library not loaded. Include the CDN script.');
            }

            // 3. Create Room
            this.room = new LivekitClient.Room({
                adaptiveStream: true,
                dynacast: true,
            });

            // 4. Setup audio track listeners
            this.room
                .on(LivekitClient.RoomEvent.TrackSubscribed, (track, publication, participant) => {
                    if (track.kind === LivekitClient.Track.Kind.Audio) {
                        const el = track.attach();
                        document.body.appendChild(el);
                        this._audioElements.push(el);
                        this._setStatus('Agent speaking...');
                        console.log('[LiveKit] Audio track subscribed — agent speaking');
                    }
                })
                .on(LivekitClient.RoomEvent.TrackUnsubscribed, (track) => {
                    track.detach().forEach(el => el.remove());
                })
                .on(LivekitClient.RoomEvent.ActiveSpeakersChanged, (speakers) => {
                    if (!this.isConnected) return;
                    const agentSpeaking = speakers.some(s => !s.isLocal);
                    if (agentSpeaking) {
                        this._setStatus('Agent speaking...');
                    } else {
                        this._setStatus('Listening...');
                    }
                })
                .on(LivekitClient.RoomEvent.Disconnected, () => {
                    this._handleDisconnect();
                });

            // 5. Connect to Room
            console.log(`[LiveKit] Connecting to ${wsUrl} room=${data.roomName}...`);
            await this.room.connect(wsUrl, data.token);
            
            // 6. Enable Microphone
            await this.room.localParticipant.setMicrophoneEnabled(true);

            this.isConnected = true;
            this.isMuted = false;
            this._setStatus('Connected — Speak now');
            this.onConnected();
            console.log('[LiveKit] Connected successfully');

        } catch (error) {
            console.error('[LiveKit] Connection error:', error);
            this._setStatus('Connection failed');
            this.onError(error.message);
        }
    }

    /**
     * Disconnect from the LiveKit room.
     */
    async disconnect() {
        if (this.room) {
            try {
                await this.room.disconnect();
            } catch (e) {
                console.warn('[LiveKit] Disconnect error:', e);
            }
        }
        this._handleDisconnect();
    }

    /**
     * Toggle microphone mute state.
     * @returns {boolean} New muted state
     */
    async toggleMute() {
        if (!this.room || !this.isConnected) return this.isMuted;
        
        this.isMuted = !this.isMuted;
        await this.room.localParticipant.setMicrophoneEnabled(!this.isMuted);
        this._setStatus(this.isMuted ? 'Muted' : 'Listening...');
        return this.isMuted;
    }

    /**
     * Internal disconnect handler — cleans up audio elements and resets state.
     */
    _handleDisconnect() {
        this.isConnected = false;
        this.isMuted = false;
        
        // Clean up attached audio elements
        this._audioElements.forEach(el => {
            try { el.remove(); } catch (e) {}
        });
        this._audioElements = [];
        
        this._setStatus('Disconnected');
        this.onDisconnected();
        this.room = null;
    }
}

// Make accessible globally
window.LiveKitVoiceClient = LiveKitVoiceClient;
