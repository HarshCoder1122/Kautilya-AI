import { useState, useEffect, useRef, useCallback } from "react";
import { X, Microphone, MicrophoneSlash, Phone, PhoneDisconnect, WifiHigh, WifiSlash } from "@phosphor-icons/react";
import { getAuthHeaders } from "../../lib/api";

// Force same-origin when served from *.revealiq.in so the proxy is used (see lib/api.js).
const _hn = (typeof window !== 'undefined' ? window.location.hostname : '') || '';
const API_BASE_URL = /(^|\.)revealiq\.in$/i.test(_hn)
  ? window.location.origin
  : (process.env.REACT_APP_API_URL || (_hn === 'localhost' ? 'http://localhost:5000' : window.location.origin));

// Pre-warm: kick off the livekit-client dynamic import as soon as this
// module loads (i.e. when the chat page renders), not when the user taps
// the Live button. The import() resolves in ~200-400ms on a cold cache —
// doing it eagerly hides that latency behind normal page activity.
// The promise is module-scoped so it's shared across mounts.
const _livekitImportPromise = import('livekit-client').catch(() => null);

const STATES = {
  IDLE: 'idle',
  CONNECTING: 'connecting',
  LISTENING: 'listening',
  SPEAKING: 'speaking',
  ERROR: 'error',
};

function AudioOrb({ state }) {
  const bars = Array.from({ length: 12 });
  return (
    <div className="relative flex items-center justify-center w-36 h-36">
      {/* Outer glow ring */}
      <div className={`absolute inset-0 rounded-full transition-all duration-700 ${
        state === STATES.SPEAKING
          ? 'bg-indigo-500/20 scale-110 animate-pulse'
          : state === STATES.LISTENING
          ? 'bg-emerald-500/15 scale-105'
          : 'bg-white/5'
      }`} />
      {/* Middle ring */}
      <div className={`absolute inset-4 rounded-full transition-all duration-500 ${
        state === STATES.SPEAKING
          ? 'bg-indigo-500/30'
          : state === STATES.LISTENING
          ? 'bg-emerald-500/20'
          : state === STATES.CONNECTING
          ? 'bg-amber-500/20 animate-spin-slow'
          : 'bg-white/10'
      }`} />
      {/* Center orb */}
      <div className={`relative z-10 w-20 h-20 rounded-full flex items-center justify-center shadow-2xl transition-all duration-500 ${
        state === STATES.SPEAKING
          ? 'bg-gradient-to-br from-indigo-500 to-violet-600 scale-110 shadow-indigo-500/40'
          : state === STATES.LISTENING
          ? 'bg-gradient-to-br from-emerald-400 to-teal-600 scale-105 shadow-emerald-500/30'
          : state === STATES.CONNECTING
          ? 'bg-gradient-to-br from-amber-400 to-orange-500 shadow-amber-500/30'
          : state === STATES.ERROR
          ? 'bg-gradient-to-br from-red-500 to-rose-600 shadow-red-500/30'
          : 'bg-gradient-to-br from-indigo-600 to-violet-700 shadow-indigo-500/20'
      }`}>
        <span className="text-white text-2xl font-black k-heading">K</span>
      </div>
      {/* Audio bars (visible when speaking or listening) */}
      {(state === STATES.SPEAKING || state === STATES.LISTENING) && (
        <div className="absolute inset-0 flex items-center justify-center">
          {bars.map((_, i) => (
            <div
              key={i}
              className={`w-0.5 rounded-full mx-px transition-all ${
                state === STATES.SPEAKING ? 'bg-indigo-400/60' : 'bg-emerald-400/60'
              }`}
              style={{
                height: `${20 + Math.sin(i * 0.8) * 30}px`,
                animationDelay: `${i * 60}ms`,
                animation: 'audio-bar 0.8s ease-in-out infinite alternate',
              }}
            />
          ))}
        </div>
      )}
    </div>
  );
}

export function LiveKitVoice({ onClose, agentId }) {
  const [voiceState, setVoiceState] = useState(STATES.CONNECTING);
  const [isMuted, setIsMuted] = useState(false);
  const [statusText, setStatusText] = useState('Connecting to Kautilya…');
  const [error, setError] = useState(null);
  const [connectionQuality, setConnectionQuality] = useState('good');

  const roomRef = useRef(null);
  const localTrackRef = useRef(null);

  const cleanup = useCallback(() => {
    if (localTrackRef.current) {
      try { localTrackRef.current.stop(); } catch (_) {}
      localTrackRef.current = null;
    }
    if (roomRef.current) {
      try { roomRef.current.disconnect(); } catch (_) {}
      roomRef.current = null;
    }
    // Remove any audio elements attached to the body during the session
    document.querySelectorAll('audio[data-livekit]').forEach(el => el.remove());
  }, []);

  useEffect(() => {
    let mounted = true;

    async function connect() {
      try {
        // 1 + 2 in parallel: token fetch and livekit-client import have no
        // dependency on each other. On a warm cache the import resolves in
        // <5ms; on a cold cache it runs concurrently with the network round-
        // trip so users see no extra wait.
        const [resp, LiveKitModule] = await Promise.all([
          fetch(`${API_BASE_URL}/api/livekit/token`, {
            method: 'POST',
            headers: { ...getAuthHeaders(), 'Content-Type': 'application/json' },
            body: JSON.stringify({ agentId: agentId || '', participantName: 'Kautilya User' }),
          }),
          _livekitImportPromise,
        ]);

        if (!LiveKitModule) throw new Error('LiveKit client not installed. Run: yarn add livekit-client');
        if (!resp.ok) {
          const err = await resp.json().catch(() => ({}));
          throw new Error(err.error || `Token request failed (${resp.status})`);
        }

        const { token, wsUrl } = await resp.json();
        if (!token || !wsUrl) throw new Error('Invalid token response from server');

        const { Room, RoomEvent, Track, createLocalAudioTrack, ConnectionQuality } = LiveKitModule;

        if (!mounted) return;

        // 3. Create room and attach events
        const room = new Room({
          adaptiveStream: true,
          dynacast: true,
          audioCaptureDefaults: { noiseSuppression: true, echoCancellation: true },
        });
        roomRef.current = room;

        room.on(RoomEvent.Connected, () => {
          if (!mounted) return;
          setVoiceState(STATES.LISTENING);
          setStatusText('Listening…');
        });

        room.on(RoomEvent.Disconnected, () => {
          if (!mounted) return;
          setVoiceState(STATES.IDLE);
          setStatusText('Disconnected');
        });

        room.on(RoomEvent.ConnectionQualityChanged, (quality) => {
          if (!mounted) return;
          setConnectionQuality(quality === ConnectionQuality.Poor ? 'poor' : 'good');
        });

        // Detect agent speaking (remote audio track)
        room.on(RoomEvent.TrackSubscribed, (track, publication, participant) => {
          if (!mounted) return;
          if (track.kind === Track.Kind.Audio) {
            // Attach remote track to an <audio> element for playback
            const audioEl = track.attach();
            audioEl.autoplay = true;
            audioEl.setAttribute('data-livekit', '1');
            document.body.appendChild(audioEl);
            setVoiceState(STATES.SPEAKING);
            setStatusText('Kautilya is speaking…');
          }
        });

        room.on(RoomEvent.TrackUnsubscribed, (track) => {
          if (!mounted) return;
          if (track.kind === Track.Kind.Audio) {
            track.detach().forEach(el => el.remove());
            setVoiceState(STATES.LISTENING);
            setStatusText('Listening…');
          }
        });

        room.on(RoomEvent.ConnectionStateChanged, (state) => {
          if (!mounted) return;
          if (state === 'reconnecting') setStatusText('Reconnecting…');
        });

        // 4. Connect to room
        await room.connect(wsUrl, token);

        // 5. Publish mic
        const audioTrack = await createLocalAudioTrack({
          noiseSuppression: true,
          echoCancellation: true,
        });
        localTrackRef.current = audioTrack;
        await room.localParticipant.publishTrack(audioTrack);

      } catch (err) {
        console.error('[LiveKit]', err);
        if (mounted) {
          setVoiceState(STATES.ERROR);
          setError(err.message || 'Connection failed');
          setStatusText('Connection failed');
        }
      }
    }

    connect();
    return () => {
      mounted = false;
      cleanup();
    };
  }, [agentId, cleanup]);

  const toggleMute = () => {
    if (localTrackRef.current) {
      if (isMuted) {
        localTrackRef.current.unmute?.();
      } else {
        localTrackRef.current.mute?.();
      }
      setIsMuted(prev => !prev);
    }
  };

  const handleDisconnect = () => {
    cleanup();
    onClose();
  };

  return (
    <div
      className="fixed inset-0 z-50 flex flex-col items-center justify-center bg-black/90 backdrop-blur-xl"
      style={{ background: 'radial-gradient(ellipse at center, #0d0f1a 0%, #080a0f 100%)' }}
    >
      {/* Connection quality indicator */}
      <div className="absolute top-6 right-6 flex items-center gap-1.5 text-xs text-muted-foreground">
        {connectionQuality === 'poor'
          ? <WifiSlash className="w-3.5 h-3.5 text-amber-400" />
          : <WifiHigh className="w-3.5 h-3.5 text-emerald-400" />}
        <span className={connectionQuality === 'poor' ? 'text-amber-400' : 'text-emerald-400/70'}>
          {connectionQuality === 'poor' ? 'Poor signal' : 'Connected'}
        </span>
      </div>

      {/* Close button */}
      <button
        onClick={handleDisconnect}
        className="absolute top-5 left-5 p-2 rounded-full hover:bg-white/10 text-white/60 hover:text-white transition-all"
      >
        <X className="w-5 h-5" />
      </button>

      {/* Brand */}
      <div className="absolute top-6 left-1/2 -translate-x-1/2 flex items-center gap-2">
        <span className="text-sm font-bold text-white/50 tracking-widest uppercase k-heading">Kautilya Live</span>
      </div>

      {/* Orb */}
      <div className="flex flex-col items-center gap-8">
        <AudioOrb state={voiceState} />

        {/* Status */}
        <div className="text-center space-y-1">
          <p className="text-white text-lg font-semibold tracking-tight">
            {voiceState === STATES.SPEAKING ? 'Kautilya' : 'You'}
          </p>
          <p className={`text-sm transition-colors duration-300 ${
            voiceState === STATES.ERROR ? 'text-red-400' :
            voiceState === STATES.CONNECTING ? 'text-amber-400' :
            voiceState === STATES.SPEAKING ? 'text-indigo-300' :
            'text-emerald-300'
          }`}>
            {error || statusText}
          </p>
        </div>

        {/* Controls */}
        <div className="flex items-center gap-5 mt-4">
          {/* Mute */}
          <button
            onClick={toggleMute}
            disabled={voiceState === STATES.CONNECTING || voiceState === STATES.ERROR}
            className={`w-14 h-14 rounded-full flex items-center justify-center transition-all duration-200 shadow-lg ${
              isMuted
                ? 'bg-red-500/20 border border-red-500/40 text-red-400'
                : 'bg-white/10 border border-white/15 text-white hover:bg-white/20'
            } disabled:opacity-30 disabled:cursor-not-allowed`}
            title={isMuted ? 'Unmute' : 'Mute'}
          >
            {isMuted
              ? <MicrophoneSlash className="w-6 h-6" weight="fill" />
              : <Microphone className="w-6 h-6" weight="fill" />}
          </button>

          {/* End call */}
          <button
            onClick={handleDisconnect}
            className="w-16 h-16 rounded-full bg-red-500 hover:bg-red-600 flex items-center justify-center text-white shadow-xl shadow-red-500/30 transition-all duration-200 hover:scale-105"
            title="End call"
          >
            <PhoneDisconnect className="w-7 h-7" weight="fill" />
          </button>
        </div>

        {voiceState === STATES.ERROR && (
          <button
            onClick={() => window.location.reload()}
            className="text-xs text-indigo-400 hover:text-indigo-300 underline mt-2"
          >
            Retry connection
          </button>
        )}
      </div>

      {/* Hint */}
      <p className="absolute bottom-8 text-[11px] text-white/25 tracking-widest uppercase">
        {voiceState === STATES.LISTENING ? 'Speak naturally — Kautilya is listening' : ''}
      </p>

      <style>{`
        @keyframes audio-bar {
          from { transform: scaleY(0.4); }
          to   { transform: scaleY(1.4); }
        }
        .animate-spin-slow {
          animation: spin 3s linear infinite;
        }
        @keyframes spin { 100% { transform: rotate(360deg); } }
      `}</style>
    </div>
  );
}
