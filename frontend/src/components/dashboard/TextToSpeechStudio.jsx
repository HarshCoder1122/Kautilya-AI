import { useState, useRef, useEffect, useCallback } from "react";
import {
  Play, Pause, Stop, Download, Waveform, Gear,
  Sparkle, SpeakerHigh, Pulse, ArrowCounterClockwise
} from "@phosphor-icons/react";
import { ttsAPI } from "../../lib/api";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";

const SAMPLE_RATE = 24000;

const VOICE_NAMES = {
  'af_heart':   'Priya Sharma (Sweet)',
  'af_bella':   'Ananya Singh (Professional)',
  'af_nicole':  'Neha Kapoor (Expressive)',
  'af_sky':     'Sneha Reddy (Soft)',
  'am_adam':    'Arjun Mehta (Deep)',
  'am_michael': 'Rahul Verma (Narrator)',
  'hf_alpha':   'Aarav Kumar (Hindi Male)',
  'hf_beta':    'Vihaan Sharma (Hindi Female)',
};

export default function TextToSpeechStudio() {
  const [provider, setProvider] = useState('revealIQ');
  const [text, setText] = useState('');
  const [status, setStatus] = useState('idle'); // idle | loading | playing | done | error
  const [errorMsg, setErrorMsg] = useState('');
  const [downloadUrl, setDownloadUrl] = useState(null);

  // RevealIQ
  const [model, setModel] = useState('swara-en');
  const [voice, setVoice] = useState('af_bella');
  const [speed, setSpeed] = useState(1.0);

  // Other providers
  const [cartesiaVoice, setCartesiaVoice] = useState(ttsAPI.cartesia.getVoices()[0].id);
  const [elevenVoice, setElevenVoice]     = useState(ttsAPI.elevenLabs.getVoices()[0].id);
  const [sarvamLang, setSarvamLang]       = useState(ttsAPI.sarvam.getLanguages()[0].id);

  const audioCtxRef    = useRef(null);
  const audioInstRef   = useRef(null);  // for non-streaming providers
  const scheduledNodes = useRef([]);
  const nextTimeRef    = useRef(0);
  const leftoverRef    = useRef(null);  // leftover bytes from odd-length chunks
  const pcmChunksRef   = useRef([]);    // collect raw PCM for download
  const readerRef      = useRef(null);

  useEffect(() => {
    return () => { stopAll(); };
  }, []);

  const stopAll = useCallback(() => {
    // cancel streaming reader
    if (readerRef.current) { try { readerRef.current.cancel(); } catch {} readerRef.current = null; }
    // stop web audio nodes
    scheduledNodes.current.forEach(n => { try { n.stop(); n.disconnect(); } catch {} });
    scheduledNodes.current = [];
    if (audioCtxRef.current) { try { audioCtxRef.current.close(); } catch {} audioCtxRef.current = null; }
    // stop HTML5 audio
    if (audioInstRef.current) { audioInstRef.current.pause(); audioInstRef.current = null; }
    leftoverRef.current = null;
    pcmChunksRef.current = [];
    nextTimeRef.current = 0;
  }, []);

  const handleStop = () => { stopAll(); setStatus('idle'); };

  // ---------- RevealIQ streaming ----------
  const playRevealIQ = async () => {
    stopAll();
    pcmChunksRef.current = [];
    leftoverRef.current = null;

    // CRITICAL: AudioContext MUST be created at the exact sample rate the
    // TTS stream uses. If the browser's default (44100 or 48000) differs
    // from SAMPLE_RATE (24000), the browser resamples every buffer chunk —
    // which introduces pitch shifts, pops, and audible breaks between
    // chunks. Lock it to SAMPLE_RATE so no resampling ever happens.
    const ctx = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: SAMPLE_RATE });
    audioCtxRef.current = ctx;
    // Give a 150ms head-start buffer instead of 10ms. The decode + schedule
    // loop runs in the main thread; at 10ms it regularly falls behind the
    // playhead on slower connections, causing glitches / silence gaps.
    // 150ms is inaudible as delay but prevents underruns on every device.
    nextTimeRef.current = ctx.currentTime + 0.15;

    setStatus('loading');
    setDownloadUrl(null);

    let response;
    try {
      response = await ttsAPI.revealIQ.stream(text, model, voice, speed);
      if (!response.ok) throw new Error(`TTS error: ${response.status}`);
    } catch (e) {
      setStatus('error');
      setErrorMsg(e.message);
      return;
    }

    setStatus('playing');
    const reader = response.body.getReader();
    readerRef.current = reader;

    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        // Combine leftover bytes from previous chunk
        let combined = value;
        if (leftoverRef.current) {
          const merged = new Uint8Array(leftoverRef.current.length + value.length);
          merged.set(leftoverRef.current);
          merged.set(value, leftoverRef.current.length);
          combined = merged;
          leftoverRef.current = null;
        }

        // Handle odd byte count (Int16 = 2 bytes each)
        let processLen = combined.length;
        if (processLen % 2 !== 0) {
          leftoverRef.current = combined.slice(processLen - 1);
          processLen -= 1;
        }

        if (processLen === 0) continue;

        // Collect for download
        pcmChunksRef.current.push(combined.slice(0, processLen));

        // Convert Int16 → Float32
        const int16 = new Int16Array(combined.buffer, combined.byteOffset, processLen / 2);
        const float32 = new Float32Array(int16.length);
        for (let i = 0; i < int16.length; i++) float32[i] = int16[i] / 32768.0;

        // Schedule with a safety floor: never schedule more than 50ms
        // behind the current playhead (catches up after a stall) but
        // always keep at least 80ms of lookahead so the chunk plays
        // gaplessly. This replaces the 10ms floor that caused breaks.
        const buf = ctx.createBuffer(1, float32.length, SAMPLE_RATE);
        buf.getChannelData(0).set(float32);
        const src = ctx.createBufferSource();
        src.buffer = buf;
        src.connect(ctx.destination);
        const now = ctx.currentTime;
        const t = Math.max(nextTimeRef.current, now + 0.08);
        src.start(t);
        nextTimeRef.current = t + buf.duration;
        scheduledNodes.current.push(src);
      }
    } catch (e) {
      if (e.name !== 'AbortError') { setStatus('error'); setErrorMsg(e.message); return; }
    } finally {
      readerRef.current = null;
    }

    // Build WAV blob for download
    if (pcmChunksRef.current.length > 0) {
      const totalBytes = pcmChunksRef.current.reduce((s, c) => s + c.length, 0);
      const merged = new Uint8Array(totalBytes);
      let offset = 0;
      for (const c of pcmChunksRef.current) { merged.set(c, offset); offset += c.length; }
      const wav = pcmToWav(merged.buffer, SAMPLE_RATE, 1);
      setDownloadUrl(URL.createObjectURL(new Blob([wav], { type: 'audio/wav' })));
    }

    setStatus('done');
  };

  // ---------- Other providers (WAV/MP3 blob) ----------
  const playProvider = async () => {
    stopAll();
    setStatus('loading');
    setDownloadUrl(null);
    try {
      let blob;
      if (provider === 'cartesia')   blob = await ttsAPI.cartesia.synthesize(text, cartesiaVoice);
      else if (provider === 'elevenLabs') blob = await ttsAPI.elevenLabs.synthesize(text, elevenVoice);
      else if (provider === 'sarvam')     blob = await ttsAPI.sarvam.synthesize(text, sarvamLang);
      const url = URL.createObjectURL(blob);
      setDownloadUrl(url);
      const audio = new Audio(url);
      audioInstRef.current = audio;
      audio.onended = () => setStatus('done');
      audio.onerror = () => setStatus('error');
      await audio.play();
      setStatus('playing');
    } catch (e) {
      setStatus('error');
      setErrorMsg(e.message || 'Synthesis failed');
    }
  };

  const handleGenerate = () => {
    if (!text.trim()) return;
    setErrorMsg('');
    if (provider === 'revealIQ') playRevealIQ();
    else playProvider();
  };

  // Replay last generated audio from the cached WAV/blob URL without
  // hitting the backend again — instant for the user.
  const handleReplay = () => {
    if (!downloadUrl) return;
    stopAll();
    setStatus('playing');
    const audio = new Audio(downloadUrl);
    audioInstRef.current = audio;
    audio.onended = () => setStatus('done');
    audio.onerror = () => setStatus('error');
    audio.play().catch(() => setStatus('error'));
  };

  const handleDownload = () => {
    if (!downloadUrl) return;
    const a = document.createElement('a');
    a.href = downloadUrl;
    a.download = `kautilya-tts-${Date.now()}.wav`;
    a.click();
  };

  const voices = ttsAPI.revealIQ.getVoices(model);
  const isLoading = status === 'loading';
  const isPlaying = status === 'playing';
  const isDone    = status === 'done';

  return (
    <div className="h-full flex flex-col bg-background" data-testid="tts-studio">
      {/* Header */}
      <div className="px-8 py-6 border-b border-[var(--k-border)]">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-[var(--k-brand)] flex items-center justify-center">
            <Waveform className="w-5 h-5 text-white" weight="bold" />
          </div>
          <div>
            <h1 className="text-2xl font-medium k-heading tracking-tight text-foreground">Voice Studio</h1>
            <p className="text-sm text-muted-foreground">Neural TTS with real-time streaming</p>
          </div>
        </div>
      </div>

      <ScrollArea className="flex-1">
        <div className="max-w-4xl mx-auto px-8 py-8">
          <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">

            {/* Config panel */}
            <div className="lg:col-span-2 space-y-4">
              <div className="p-5 rounded-xl border border-[var(--k-border)] bg-[var(--k-surface)] space-y-5">
                <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-widest text-muted-foreground">
                  <Gear className="w-3.5 h-3.5" /> Engine
                </div>

                <Tabs value={provider} onValueChange={v => { stopAll(); setStatus('idle'); setProvider(v); }}>
                  <TabsList className="grid grid-cols-2 h-9 text-xs mb-4">
                    {['revealIQ', 'sarvam', 'cartesia', 'elevenLabs'].slice(0,2).map(p => (
                      <TabsTrigger key={p} value={p} className="text-[10px] uppercase font-bold tracking-wider">{p}</TabsTrigger>
                    ))}
                  </TabsList>
                  <TabsList className="grid grid-cols-2 h-9 text-xs">
                    {['cartesia', 'elevenLabs'].map(p => (
                      <TabsTrigger key={p} value={p} className="text-[10px] uppercase font-bold tracking-wider">{p}</TabsTrigger>
                    ))}
                  </TabsList>
                </Tabs>

                {provider === 'revealIQ' && (
                  <div className="space-y-3">
                    <div>
                      <label className="text-[10px] uppercase tracking-widest text-muted-foreground mb-1 block">Language</label>
                      <select
                        value={model}
                        onChange={e => { setModel(e.target.value); setVoice(e.target.value.includes('hi') ? 'hf_alpha' : 'af_heart'); }}
                        className="w-full px-3 py-2 bg-background border border-[var(--k-border)] rounded-lg text-sm outline-none focus:border-[var(--k-brand)]"
                      >
                        <option value="swara-en">SWARA EN (English)</option>
                        <option value="swara-hi">SWARA HI (Hindi)</option>
                      </select>
                    </div>
                    <div>
                      <label className="text-[10px] uppercase tracking-widest text-muted-foreground mb-1 block">Voice</label>
                      <select
                        value={voice}
                        onChange={e => setVoice(e.target.value)}
                        className="w-full px-3 py-2 bg-background border border-[var(--k-border)] rounded-lg text-sm outline-none focus:border-[var(--k-brand)]"
                      >
                        {voices.map(v => <option key={v} value={v}>{VOICE_NAMES[v] || v}</option>)}
                      </select>
                    </div>
                    <div>
                      <label className="text-[10px] uppercase tracking-widest text-muted-foreground mb-1 block">
                        Speed — {speed.toFixed(1)}x
                      </label>
                      <input
                        type="range" min="0.5" max="2.0" step="0.1"
                        value={speed}
                        onChange={e => setSpeed(parseFloat(e.target.value))}
                        className="w-full accent-[var(--k-brand)]"
                      />
                    </div>
                  </div>
                )}

                {provider === 'cartesia' && (
                  <div>
                    <label className="text-[10px] uppercase tracking-widest text-muted-foreground mb-1 block">Voice</label>
                    <select value={cartesiaVoice} onChange={e => setCartesiaVoice(e.target.value)}
                      className="w-full px-3 py-2 bg-background border border-[var(--k-border)] rounded-lg text-sm outline-none focus:border-[var(--k-brand)]">
                      {ttsAPI.cartesia.getVoices().map(v => <option key={v.id} value={v.id}>{v.name}</option>)}
                    </select>
                  </div>
                )}

                {provider === 'elevenLabs' && (
                  <div>
                    <label className="text-[10px] uppercase tracking-widest text-muted-foreground mb-1 block">Voice</label>
                    <select value={elevenVoice} onChange={e => setElevenVoice(e.target.value)}
                      className="w-full px-3 py-2 bg-background border border-[var(--k-border)] rounded-lg text-sm outline-none focus:border-[var(--k-brand)]">
                      {ttsAPI.elevenLabs.getVoices().map(v => <option key={v.id} value={v.id}>{v.name}</option>)}
                    </select>
                  </div>
                )}

                {provider === 'sarvam' && (
                  <div>
                    <label className="text-[10px] uppercase tracking-widest text-muted-foreground mb-1 block">Language</label>
                    <select value={sarvamLang} onChange={e => setSarvamLang(e.target.value)}
                      className="w-full px-3 py-2 bg-background border border-[var(--k-border)] rounded-lg text-sm outline-none focus:border-[var(--k-brand)]">
                      {ttsAPI.sarvam.getLanguages().map(l => <option key={l.id} value={l.id}>{l.name}</option>)}
                    </select>
                  </div>
                )}
              </div>

              {/* Latency badge for RevealIQ */}
              {provider === 'revealIQ' && (
                <div className="px-3 py-2 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-xs text-emerald-400 flex items-center gap-2">
                  <div className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
                  Real-time PCM streaming • ~300ms TTFB
                </div>
              )}
            </div>

            {/* Input + Playback */}
            <div className="lg:col-span-3 space-y-4">
              <div className="relative">
                <textarea
                  value={text}
                  onChange={e => setText(e.target.value)}
                  placeholder="Type or paste text to synthesize..."
                  className="w-full h-52 p-5 bg-[var(--k-surface)] border border-[var(--k-border)] rounded-xl text-sm text-foreground placeholder:text-muted-foreground/40 outline-none focus:border-[var(--k-brand)] resize-none transition-colors leading-relaxed"
                />
                <div className="absolute bottom-3 right-4 text-[10px] text-muted-foreground/40 font-mono">{text.length}</div>
              </div>

              {/* Action bar */}
              <div className="flex items-center gap-2">
                <button
                  onClick={handleGenerate}
                  disabled={isLoading || isPlaying || !text.trim()}
                  className="flex-1 h-11 flex items-center justify-center gap-2 rounded-xl bg-[var(--k-brand)] text-white text-sm font-semibold hover:bg-[var(--k-brand-hover)] transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  {isLoading
                    ? <><Pulse className="w-4 h-4 animate-spin" /> Processing…</>
                    : <><Sparkle className="w-4 h-4" weight="fill" /> Generate</>
                  }
                </button>

                {/* Play Again — instant replay from cached blob, no backend hit */}
                {(isDone && downloadUrl) && (
                  <button onClick={handleReplay}
                    title="Play again"
                    className="h-11 w-11 flex items-center justify-center rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 hover:bg-emerald-500/20 transition-colors">
                    <Play className="w-5 h-5" weight="fill" />
                  </button>
                )}

                {(isPlaying || isLoading) && (
                  <button onClick={handleStop}
                    title="Stop"
                    className="h-11 w-11 flex items-center justify-center rounded-xl border border-[var(--k-border)] text-muted-foreground hover:text-foreground hover:bg-accent transition-colors">
                    <Stop className="w-5 h-5" weight="fill" />
                  </button>
                )}

                {downloadUrl && (
                  <button onClick={handleDownload}
                    title="Download WAV"
                    className="h-11 w-11 flex items-center justify-center rounded-xl border border-[var(--k-border)] text-muted-foreground hover:text-foreground hover:bg-accent transition-colors">
                    <Download className="w-5 h-5" />
                  </button>
                )}

                {(isDone || status === 'error') && (
                  <button onClick={() => { stopAll(); setStatus('idle'); setDownloadUrl(null); }}
                    title="Clear & start over"
                    className="h-11 w-11 flex items-center justify-center rounded-xl border border-[var(--k-border)] text-muted-foreground hover:text-foreground hover:bg-accent transition-colors">
                    <ArrowCounterClockwise className="w-4 h-4" />
                  </button>
                )}
              </div>

              {/* Status / waveform display */}
              {isLoading && (
                <div className="p-5 rounded-xl border border-[var(--k-brand)]/20 bg-[var(--k-brand)]/5 flex items-center gap-3">
                  <div className="flex items-end gap-0.5 h-8">
                    {[...Array(8)].map((_, i) => (
                      <div key={i} className="w-1 bg-[var(--k-brand)] rounded-full animate-pulse"
                        style={{ height: `${Math.random() * 100}%`, animationDelay: `${i * 80}ms` }} />
                    ))}
                  </div>
                  <span className="text-sm text-[var(--k-brand)] font-medium">Synthesizing…</span>
                </div>
              )}

              {isPlaying && (
                <div className="p-5 rounded-xl border border-emerald-500/20 bg-emerald-500/5 flex items-center gap-3">
                  <div className="flex items-end gap-0.5 h-8">
                    {[...Array(8)].map((_, i) => (
                      <div key={i} className="w-1 bg-emerald-400 rounded-full"
                        style={{
                          animation: 'audio-bar 0.8s ease-in-out infinite alternate',
                          animationDelay: `${i * 100}ms`,
                          height: '60%'
                        }} />
                    ))}
                  </div>
                  <SpeakerHigh className="w-4 h-4 text-emerald-400" weight="fill" />
                  <span className="text-sm text-emerald-400 font-medium">Playing…</span>
                </div>
              )}

              {isDone && downloadUrl && (
                <div className="p-4 rounded-xl border border-[var(--k-border)] bg-[var(--k-surface)] flex items-center gap-3">
                  <div className="w-9 h-9 rounded-lg bg-[var(--k-brand)]/10 flex items-center justify-center">
                    <SpeakerHigh className="w-4 h-4 text-[var(--k-brand)]" weight="duotone" />
                  </div>
                  <div className="flex-1 text-sm text-foreground">Audio ready</div>
                  <button onClick={handleDownload}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[var(--k-brand)]/10 text-[var(--k-brand)] text-xs font-medium hover:bg-[var(--k-brand)]/20 transition-colors">
                    <Download className="w-3.5 h-3.5" /> Download WAV
                  </button>
                </div>
              )}

              {status === 'error' && (
                <div className="p-4 rounded-xl border border-rose-500/20 bg-rose-500/5 text-sm text-rose-400">
                  {errorMsg || 'Synthesis failed'}
                </div>
              )}
            </div>
          </div>
        </div>
      </ScrollArea>

      <style>{`
        @keyframes audio-bar {
          from { transform: scaleY(0.3); }
          to   { transform: scaleY(1.2); }
        }
      `}</style>
    </div>
  );
}

// Build a valid WAV file from raw Int16 PCM bytes
function pcmToWav(pcmBuffer, sampleRate, channels) {
  const dataLen   = pcmBuffer.byteLength;
  const buffer    = new ArrayBuffer(44 + dataLen);
  const view      = new DataView(buffer);
  const writeStr  = (off, str) => { for (let i = 0; i < str.length; i++) view.setUint8(off + i, str.charCodeAt(i)); };
  writeStr(0,  'RIFF');
  view.setUint32(4,  36 + dataLen, true);
  writeStr(8,  'WAVE');
  writeStr(12, 'fmt ');
  view.setUint32(16, 16, true);
  view.setUint16(20, 1,  true);
  view.setUint16(22, channels, true);
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * channels * 2, true);
  view.setUint16(32, channels * 2, true);
  view.setUint16(34, 16, true);
  writeStr(36, 'data');
  view.setUint32(40, dataLen, true);
  new Uint8Array(buffer, 44).set(new Uint8Array(pcmBuffer));
  return buffer;
}
