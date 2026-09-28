import { useState, useRef, useEffect, useCallback } from "react";
import {
  Microphone, Stop, UploadSimple, FileAudio, Copy, Download,
  Gear, Pulse, Trash, CheckCircle, WarningCircle
} from "@phosphor-icons/react";
import { sttAPI } from "../../lib/api";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";

// Nemotron 3.5 supports 40 locales; surface the transcription-ready ones plus auto.
const LANGUAGES = [
  { id: "", name: "Auto-detect" },
  { id: "en", name: "English" },
  { id: "hi", name: "Hindi" },
  { id: "es", name: "Spanish" },
  { id: "fr", name: "French" },
  { id: "de", name: "German" },
  { id: "it", name: "Italian" },
  { id: "pt", name: "Portuguese" },
  { id: "ja", name: "Japanese" },
  { id: "ko", name: "Korean" },
  { id: "zh", name: "Mandarin" },
  { id: "ru", name: "Russian" },
  { id: "ar", name: "Arabic" },
];

// Live segmentation tuning. The model handles ~20-30s per call, so we slice the
// mic stream on natural pauses (and cap segment length) and transcribe each
// slice, appending the text for a live-updating transcript.
const SILENCE_THRESHOLD = 0.012; // RMS below this = silence
const SILENCE_HANG_MS = 800;     // pause this long after speech → finalize segment
const MAX_SEGMENT_MS = 14000;    // hard cap so we never exceed the model window
const MIN_SEGMENT_MS = 400;      // ignore blips shorter than this

function pickMimeType() {
  const candidates = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4", "audio/ogg"];
  if (typeof MediaRecorder === "undefined") return "";
  return candidates.find((t) => MediaRecorder.isTypeSupported(t)) || "";
}

export default function SpeechToTextStudio() {
  const [mode, setMode] = useState("live"); // live | upload
  const [language, setLanguage] = useState("");
  const [transcript, setTranscript] = useState("");
  const [isRecording, setIsRecording] = useState(false);
  const [isBusy, setIsBusy] = useState(false); // a segment/file is transcribing
  const [level, setLevel] = useState(0);        // mic level 0..1 for the meter
  const [error, setError] = useState("");
  const [copied, setCopied] = useState(false);
  const [ready, setReady] = useState(null);     // null=unknown, true/false
  const [fileName, setFileName] = useState("");

  // Live-capture refs
  const streamRef = useRef(null);
  const audioCtxRef = useRef(null);
  const analyserRef = useRef(null);
  const recorderRef = useRef(null);
  const chunksRef = useRef([]);
  const rafRef = useRef(null);
  const recordingRef = useRef(false);
  const speakingRef = useRef(false);
  const silenceStartRef = useRef(0);
  const segStartRef = useRef(0);
  const sendChainRef = useRef(Promise.resolve()); // serialize segment sends

  // Check Space/model readiness on mount; poll while warming up.
  useEffect(() => {
    let timer;
    let cancelled = false;
    const check = async () => {
      const s = await sttAPI.revealIQ.status();
      if (cancelled) return;
      const ok = !!(s && (s.ready || s.status === "healthy" && s.ready !== false));
      setReady(ok);
      if (!ok) timer = setTimeout(check, 6000);
    };
    check();
    return () => { cancelled = true; if (timer) clearTimeout(timer); };
  }, []);

  const appendTranscript = useCallback((text) => {
    const t = (text || "").trim();
    if (!t) return;
    setTranscript((prev) => (prev ? prev + " " + t : t));
  }, []);

  // Send one captured blob through the proxy and append its text. Chained so
  // segments are transcribed (and appended) strictly in order.
  const queueTranscribe = useCallback((blob, name) => {
    setIsBusy(true);
    sendChainRef.current = sendChainRef.current
      .then(async () => {
        try {
          const res = await sttAPI.revealIQ.transcribe(blob, language, name);
          appendTranscript(res.text);
        } catch (e) {
          // 503 = model warming; keep it soft and non-fatal for live mode.
          if (e.status === 503) setError("Model is warming up — keep talking, it'll catch up.");
          else setError(e.message || "Transcription failed");
        }
      })
      .finally(() => { if (!recordingRef.current) setIsBusy(false); });
    return sendChainRef.current;
  }, [language, appendTranscript]);

  // ---------- Live recording ----------
  const startSegment = useCallback(() => {
    if (!recordingRef.current || !streamRef.current) return;
    const mimeType = pickMimeType();
    let rec;
    try {
      rec = mimeType ? new MediaRecorder(streamRef.current, { mimeType })
                     : new MediaRecorder(streamRef.current);
    } catch {
      rec = new MediaRecorder(streamRef.current);
    }
    chunksRef.current = [];
    rec.ondataavailable = (e) => { if (e.data && e.data.size) chunksRef.current.push(e.data); };
    rec.onstop = () => {
      const blob = new Blob(chunksRef.current, { type: rec.mimeType || "audio/webm" });
      const dur = performance.now() - segStartRef.current;
      // Only transcribe segments that actually contain enough audio.
      if (blob.size > 2048 && dur >= MIN_SEGMENT_MS) {
        const ext = (rec.mimeType || "webm").includes("mp4") ? "mp4" : "webm";
        queueTranscribe(blob, `segment.${ext}`);
      }
      // Roll straight into the next segment if still recording.
      if (recordingRef.current) startSegment();
      else setIsBusy(false);
    };
    rec.start();
    recorderRef.current = rec;
    segStartRef.current = performance.now();
    speakingRef.current = false;
    silenceStartRef.current = 0;
  }, [queueTranscribe]);

  // Finalize current segment (VAD pause or max length) → onstop rolls the next.
  const flushSegment = useCallback(() => {
    const rec = recorderRef.current;
    if (rec && rec.state === "recording") rec.stop();
  }, []);

  const vadLoop = useCallback(() => {
    const analyser = analyserRef.current;
    if (!analyser || !recordingRef.current) return;
    const buf = new Float32Array(analyser.fftSize);
    analyser.getFloatTimeDomainData(buf);
    let sum = 0;
    for (let i = 0; i < buf.length; i++) sum += buf[i] * buf[i];
    const rms = Math.sqrt(sum / buf.length);
    setLevel(Math.min(1, rms * 8));

    const now = performance.now();
    const segMs = now - segStartRef.current;
    if (rms > SILENCE_THRESHOLD) {
      speakingRef.current = true;
      silenceStartRef.current = 0;
    } else if (speakingRef.current) {
      if (!silenceStartRef.current) silenceStartRef.current = now;
      else if (now - silenceStartRef.current > SILENCE_HANG_MS) {
        flushSegment(); // end of utterance
        rafRef.current = requestAnimationFrame(vadLoop);
        return;
      }
    }
    // Hard cap so a long monologue never blows past the model's window.
    if (segMs > MAX_SEGMENT_MS && speakingRef.current) flushSegment();

    rafRef.current = requestAnimationFrame(vadLoop);
  }, [flushSegment]);

  const startRecording = useCallback(async () => {
    setError("");
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true },
      });
      streamRef.current = stream;
      const Ctx = window.AudioContext || window.webkitAudioContext;
      const ctx = new Ctx();
      audioCtxRef.current = ctx;
      const source = ctx.createMediaStreamSource(stream);
      const analyser = ctx.createAnalyser();
      analyser.fftSize = 1024;
      source.connect(analyser);
      analyserRef.current = analyser;

      recordingRef.current = true;
      setIsRecording(true);
      startSegment();
      rafRef.current = requestAnimationFrame(vadLoop);
    } catch (e) {
      setError(e.name === "NotAllowedError"
        ? "Microphone permission denied."
        : (e.message || "Could not access microphone."));
    }
  }, [startSegment, vadLoop]);

  const teardownLive = useCallback(() => {
    recordingRef.current = false;
    if (rafRef.current) { cancelAnimationFrame(rafRef.current); rafRef.current = null; }
    try { if (recorderRef.current && recorderRef.current.state === "recording") recorderRef.current.stop(); } catch {}
    if (streamRef.current) { streamRef.current.getTracks().forEach((t) => t.stop()); streamRef.current = null; }
    if (audioCtxRef.current) { try { audioCtxRef.current.close(); } catch {} audioCtxRef.current = null; }
    analyserRef.current = null;
    setLevel(0);
  }, []);

  // Stop the mic + release resources when the user leaves the page.
  useEffect(() => () => teardownLive(), [teardownLive]);

  const stopRecording = useCallback(() => {
    teardownLive();
    setIsRecording(false);
  }, [teardownLive]);

  // ---------- File upload ----------
  const handleFile = useCallback(async (file) => {
    if (!file) return;
    setError("");
    setFileName(file.name);
    setIsBusy(true);
    try {
      const res = await sttAPI.revealIQ.transcribe(file, language, file.name);
      setTranscript((prev) => (prev ? prev + "\n\n" : "") + (res.text || "").trim());
    } catch (e) {
      setError(e.status === 503
        ? "Model is warming up — try again in ~20s."
        : (e.message || "Transcription failed"));
    } finally {
      setIsBusy(false);
    }
  }, [language]);

  const onDrop = useCallback((e) => {
    e.preventDefault();
    const f = e.dataTransfer.files && e.dataTransfer.files[0];
    if (f) handleFile(f);
  }, [handleFile]);

  // ---------- Transcript actions ----------
  const copyTranscript = () => {
    if (!transcript) return;
    navigator.clipboard.writeText(transcript);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };
  const downloadTranscript = () => {
    if (!transcript) return;
    const url = URL.createObjectURL(new Blob([transcript], { type: "text/plain" }));
    const a = document.createElement("a");
    a.href = url;
    a.download = `kautilya-transcript-${Date.now()}.txt`;
    a.click();
    URL.revokeObjectURL(url);
  };
  const clearAll = () => { setTranscript(""); setError(""); setFileName(""); };

  const wordCount = transcript.trim() ? transcript.trim().split(/\s+/).length : 0;

  return (
    <div className="h-full flex flex-col bg-background" data-testid="stt-studio">
      {/* Header */}
      <div className="px-8 py-6 border-b border-[var(--k-border)]">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-[var(--k-brand)] flex items-center justify-center">
            <Microphone className="w-5 h-5 text-white" weight="bold" />
          </div>
          <div>
            <h1 className="text-2xl font-medium k-heading tracking-tight text-foreground">STT Studio</h1>
            <p className="text-sm text-muted-foreground">RevealIQ streaming speech-to-text • Nemotron 3.5 (40 languages)</p>
          </div>
        </div>
      </div>

      <ScrollArea className="flex-1">
        <div className="max-w-4xl mx-auto px-8 py-8">
          {/* Readiness banner */}
          {ready === false && (
            <div className="mb-4 px-4 py-3 rounded-lg bg-amber-500/10 border border-amber-500/20 text-xs text-amber-500 flex items-center gap-2">
              <Pulse className="w-4 h-4 animate-spin" /> Engine is warming up (cold start) — transcription will work shortly.
            </div>
          )}

          <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
            {/* Config panel */}
            <div className="lg:col-span-2 space-y-4">
              <div className="p-5 rounded-xl border border-[var(--k-border)] bg-[var(--k-surface)] space-y-5">
                <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-widest text-muted-foreground">
                  <Gear className="w-3.5 h-3.5" /> Input
                </div>

                <Tabs value={mode} onValueChange={(v) => { if (isRecording) stopRecording(); setMode(v); setError(""); }}>
                  <TabsList className="grid grid-cols-2 h-9 text-xs">
                    <TabsTrigger value="live" className="text-[10px] uppercase font-bold tracking-wider">Live Mic</TabsTrigger>
                    <TabsTrigger value="upload" className="text-[10px] uppercase font-bold tracking-wider">Upload</TabsTrigger>
                  </TabsList>
                </Tabs>

                <div>
                  <label className="text-[10px] uppercase tracking-widest text-muted-foreground mb-1 block">Language</label>
                  <select
                    value={language}
                    onChange={(e) => setLanguage(e.target.value)}
                    className="w-full px-3 py-2 bg-background border border-[var(--k-border)] rounded-lg text-sm outline-none focus:border-[var(--k-brand)]"
                  >
                    {LANGUAGES.map((l) => <option key={l.id || "auto"} value={l.id}>{l.name}</option>)}
                  </select>
                </div>
              </div>

              <div className="px-3 py-2 rounded-lg bg-[var(--k-brand)]/10 border border-[var(--k-brand)]/20 text-xs text-[var(--k-brand)] flex items-center gap-2">
                <div className={`w-2 h-2 rounded-full ${ready ? "bg-emerald-400" : "bg-amber-400"} ${ready ? "animate-pulse" : ""}`} />
                {ready ? "Streaming ASR • sub-second on CPU" : "Connecting to engine…"}
              </div>
            </div>

            {/* Capture + transcript */}
            <div className="lg:col-span-3 space-y-4">
              {mode === "live" ? (
                <div className="p-6 rounded-xl border border-[var(--k-border)] bg-[var(--k-surface)] flex flex-col items-center gap-4">
                  {/* Mic level meter */}
                  <div className="flex items-end gap-1 h-16">
                    {[...Array(14)].map((_, i) => {
                      const active = isRecording && level * 14 > i;
                      return (
                        <div key={i}
                          className={`w-1.5 rounded-full transition-all duration-75 ${active ? "bg-[var(--k-brand)]" : "bg-[var(--k-border)]"}`}
                          style={{ height: active ? `${30 + Math.min(70, level * 100)}%` : "20%" }} />
                      );
                    })}
                  </div>

                  <button
                    onClick={isRecording ? stopRecording : startRecording}
                    className={`h-14 w-14 flex items-center justify-center rounded-full transition-colors ${
                      isRecording
                        ? "bg-rose-500 hover:bg-rose-600 text-white animate-pulse"
                        : "bg-[var(--k-brand)] hover:bg-[var(--k-brand-hover)] text-white"
                    }`}
                    title={isRecording ? "Stop" : "Start recording"}
                  >
                    {isRecording ? <Stop className="w-6 h-6" weight="fill" /> : <Microphone className="w-6 h-6" weight="fill" />}
                  </button>
                  <span className="text-xs text-muted-foreground">
                    {isRecording ? "Listening… speak naturally, pauses split segments" : "Tap to start live transcription"}
                  </span>
                </div>
              ) : (
                <label
                  onDragOver={(e) => e.preventDefault()}
                  onDrop={onDrop}
                  className="flex flex-col items-center justify-center gap-3 p-10 rounded-xl border-2 border-dashed border-[var(--k-border)] bg-[var(--k-surface)] cursor-pointer hover:border-[var(--k-brand)] transition-colors text-center"
                >
                  <input type="file" accept="audio/*" className="hidden"
                    onChange={(e) => handleFile(e.target.files && e.target.files[0])} />
                  <div className="w-12 h-12 rounded-xl bg-[var(--k-brand)]/10 flex items-center justify-center">
                    <UploadSimple className="w-6 h-6 text-[var(--k-brand)]" />
                  </div>
                  <div className="text-sm text-foreground font-medium">Drop an audio file or click to browse</div>
                  <div className="text-xs text-muted-foreground">wav, mp3, m4a, webm, ogg</div>
                  {fileName && (
                    <div className="flex items-center gap-1.5 text-xs text-[var(--k-brand)] mt-1">
                      <FileAudio className="w-3.5 h-3.5" /> {fileName}
                    </div>
                  )}
                </label>
              )}

              {/* Transcript */}
              <div className="relative">
                <textarea
                  value={transcript}
                  onChange={(e) => setTranscript(e.target.value)}
                  placeholder="Your transcript will appear here as you speak or after upload…"
                  className="w-full h-56 p-5 bg-[var(--k-surface)] border border-[var(--k-border)] rounded-xl text-sm text-foreground placeholder:text-muted-foreground/40 outline-none focus:border-[var(--k-brand)] resize-none leading-relaxed"
                />
                {isBusy && (
                  <div className="absolute top-3 right-4 flex items-center gap-1.5 text-[10px] text-[var(--k-brand)] font-medium">
                    <Pulse className="w-3.5 h-3.5 animate-spin" /> transcribing…
                  </div>
                )}
                <div className="absolute bottom-3 right-4 text-[10px] text-muted-foreground/40 font-mono">{wordCount} words</div>
              </div>

              {/* Actions */}
              <div className="flex items-center gap-2">
                <button onClick={copyTranscript} disabled={!transcript}
                  className="flex-1 h-10 flex items-center justify-center gap-2 rounded-xl border border-[var(--k-border)] text-sm font-medium text-foreground hover:bg-accent transition-colors disabled:opacity-40">
                  {copied ? <><CheckCircle className="w-4 h-4 text-emerald-400" weight="fill" /> Copied</> : <><Copy className="w-4 h-4" /> Copy</>}
                </button>
                <button onClick={downloadTranscript} disabled={!transcript}
                  title="Download .txt"
                  className="h-10 w-10 flex items-center justify-center rounded-xl border border-[var(--k-border)] text-muted-foreground hover:text-foreground hover:bg-accent transition-colors disabled:opacity-40">
                  <Download className="w-5 h-5" />
                </button>
                <button onClick={clearAll} disabled={!transcript && !error}
                  title="Clear"
                  className="h-10 w-10 flex items-center justify-center rounded-xl border border-[var(--k-border)] text-muted-foreground hover:text-foreground hover:bg-accent transition-colors disabled:opacity-40">
                  <Trash className="w-4 h-4" />
                </button>
              </div>

              {error && (
                <div className="p-3 rounded-xl border border-rose-500/20 bg-rose-500/5 text-sm text-rose-400 flex items-center gap-2">
                  <WarningCircle className="w-4 h-4 shrink-0" /> {error}
                </div>
              )}
            </div>
          </div>
        </div>
      </ScrollArea>
    </div>
  );
}
