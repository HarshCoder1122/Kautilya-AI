import { Brain, Code, ChartBar, ArrowSquareOut, Play, Pause, Copy, Check, ArrowsClockwise, SpeakerHigh, StopCircle } from "@phosphor-icons/react";
import React, { useState, useRef } from "react";
import ReactMarkdown from 'react-markdown';
import { ThinkingTokens } from "./ThinkingTokens";
import { ReActSteps } from "./ReActSteps";
import { ttsAPI } from "../../lib/api";
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';

const agentBadge = {
  researcher: { icon: Brain, label: 'Researcher', color: 'text-blue-400', bg: 'bg-blue-400/10' },
  coder: { icon: Code, label: 'Code Interpreter', color: 'text-emerald-400', bg: 'bg-emerald-400/10' },
  sales: { icon: ChartBar, label: 'Sales Agent', color: 'text-amber-400', bg: 'bg-amber-400/10' },
};

export function ChatMessage({ message, onOpenArtifact, onRegenerate }) {
  const [copied, setCopied] = useState(false);
  const [isPlaying, setIsPlaying] = useState(false);
  const [isSynthesizing, setIsSynthesizing] = useState(false);
  const audioRef = useRef(null);

  const handleCopy = (text) => {
    const copyText = text || message.content || message.responseText || '';
    if (!copyText) return;
    navigator.clipboard.writeText(copyText).catch(() => {});
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const stopAudio = () => {
    if (audioRef.current) {
      try {
        // Could be AudioContext (streaming) or Audio element
        if (typeof audioRef.current.close === 'function') audioRef.current.close();
        else { audioRef.current.pause(); audioRef.current.currentTime = 0; }
      } catch {}
      audioRef.current = null;
    }
    setIsPlaying(false);
    setIsSynthesizing(false);
  };

  const handlePlayTTS = async () => {
    if (isPlaying) {
      stopAudio();
      if (window.speechSynthesis) window.speechSynthesis.cancel();
      return;
    }

    const textToSpeak = (message.content || message.responseText || '')
      .replace(/<think>[\s\S]*?<\/think>/g, '')
      .replace(/<artifact[\s\S]*?<\/artifact>/g, '')
      .replace(/```[\s\S]*?```/g, '')
      .replace(/[#*_~`>]/g, '')
      .trim()
      .slice(0, 600); // keep short for fast first-byte

    if (!textToSpeak) return;

    setIsSynthesizing(true);

    try {
      // Streaming PCM playback — first audio arrives within ~1s instead of waiting for full synthesis
      const SAMPLE_RATE = 24000;
      const response = await ttsAPI.revealIQ.stream(textToSpeak, 'swara-en', 'af_bella', 1.0);
      if (!response.ok) throw new Error(`TTS ${response.status}`);

      const ctx = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: SAMPLE_RATE });
      audioRef.current = ctx;
      let nextTime = ctx.currentTime + 0.05;
      let leftover = null;
      const reader = response.body.getReader();
      setIsSynthesizing(false);
      setIsPlaying(true);

      try {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          let combined = value;
          if (leftover) {
            const merged = new Uint8Array(leftover.length + value.length);
            merged.set(leftover); merged.set(value, leftover.length);
            combined = merged; leftover = null;
          }
          let len = combined.length;
          if (len % 2 !== 0) { leftover = combined.slice(len - 1); len -= 1; }
          if (len === 0) continue;
          const int16 = new Int16Array(combined.buffer, combined.byteOffset, len / 2);
          const float32 = new Float32Array(int16.length);
          for (let i = 0; i < int16.length; i++) float32[i] = int16[i] / 32768.0;
          const buf = ctx.createBuffer(1, float32.length, SAMPLE_RATE);
          buf.getChannelData(0).set(float32);
          const src = ctx.createBufferSource();
          src.buffer = buf; src.connect(ctx.destination);
          const t = Math.max(nextTime, ctx.currentTime + 0.01);
          src.start(t); nextTime = t + buf.duration;
        }
      } finally {
        reader.cancel().catch(() => {});
        setTimeout(() => { try { ctx.close(); } catch {} audioRef.current = null; setIsPlaying(false); }, (nextTime - ctx.currentTime + 0.5) * 1000);
      }
    } catch (error) {
      console.warn('Streaming TTS failed, falling back to browser speech:', error);
      setIsSynthesizing(false);
      if (window.speechSynthesis) {
        const utter = new SpeechSynthesisUtterance(textToSpeak.slice(0, 400));
        utter.rate = 1.1;
        utter.onend = () => setIsPlaying(false);
        utter.onerror = () => setIsPlaying(false);
        window.speechSynthesis.speak(utter);
        setIsPlaying(true);
      }
    }
  };

  if (message.role === 'user') {
    return (
      <div className="message-user flex justify-end animate-fade-up" data-testid={`message-${message.id}`}>
        <div className="max-w-[85%]">
          <div className="bg-[var(--k-brand)] text-white px-4 py-3 rounded-2xl rounded-br-md text-sm leading-relaxed shadow-lg shadow-[var(--k-brand)]/10">
            {message.content}
          </div>
          <div className="text-[10px] text-muted-foreground/50 mt-1 text-right font-medium">{message.timestamp}</div>
        </div>
      </div>
    );
  }

  const agent = message.agentType ? agentBadge[message.agentType] : null;
  const displayContent = (message.responseText || message.content || '')
    .replace(/<think>[\s\S]*?<\/think>/g, '')
    .trim();

  return (
    <div className="message-ai animate-fade-up group" data-testid={`message-${message.id}`}>
      {/* Agent Badge */}
      {agent && (
        <div className="flex items-center gap-2 mb-2">
          <div className={`flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[10px] font-bold tracking-wider uppercase ${agent.color} ${agent.bg}`}>
            <agent.icon className="w-3 h-3" weight="duotone" />
            {agent.label}
          </div>
        </div>
      )}

      {/* Thinking (streaming or collapsed) */}
      {!message.thinkingDone && message.thinking && (
        <div className="mb-3">
          <ThinkingTokens text={message.thinking} />
        </div>
      )}

      {message.thinkingDone && message.thinking && (
        <details className="mb-4 group/details" data-testid="thinking-details">
          <summary className="flex items-center gap-2 cursor-pointer text-[10px] uppercase tracking-widest font-bold text-muted-foreground/60 hover:text-[var(--k-yellow)] transition-colors list-none">
            <Brain className="w-3.5 h-3.5 text-[var(--k-yellow)]" weight="duotone" />
            <span>Process Analysis</span>
            <div className="h-px flex-1 bg-[var(--k-border)] ml-2 opacity-20" />
          </summary>
          <div className="mt-2 pl-4 border-l border-[var(--k-yellow)]/20 py-1">
            <p className="text-[11px] text-muted-foreground/80 font-mono leading-relaxed whitespace-pre-wrap italic">{message.thinking}</p>
          </div>
        </details>
      )}

      {/* ReAct step timeline (shows when agent used tools) */}
      {(message.reactSteps?.length > 0) && (
        <ReActSteps steps={message.reactSteps} isSynthesizing={message.isSynthesizing} />
      )}

      {/* Response with markdown */}
      <div className="text-sm text-foreground leading-relaxed prose prose-invert prose-sm max-w-none prose-pre:bg-transparent prose-pre:p-0 prose-pre:border-none">
        <ReactMarkdown
          components={{
            code({ node, inline, className, children, ...props }) {
              const match = /language-(\w+)/.exec(className || '');
              const lang = match ? match[1] : '';
              const codeString = String(children).replace(/\n$/, '');

              if (inline) {
                return <code className="bg-accent/50 px-1.5 py-0.5 rounded text-xs font-mono" {...props}>{children}</code>;
              }

              return (
                <div className="relative group/code my-4 rounded-xl overflow-hidden border border-[var(--k-border)] bg-black/40">
                  <div className="flex items-center justify-between px-4 py-2 bg-white/5 border-b border-white/5">
                    <span className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground/60">{lang || 'code'}</span>
                    <div className="flex items-center gap-1">
                      <button
                        onClick={() => handleCopy(codeString)}
                        className="p-1.5 rounded hover:bg-white/10 text-muted-foreground hover:text-foreground transition-all"
                        title="Copy Code"
                      >
                        <Copy className="w-3.5 h-3.5" />
                      </button>
                      <button
                        onClick={() => onOpenArtifact?.({
                          type: 'code',
                          title: `${lang.toUpperCase()} Implementation`,
                          code: codeString,
                          language: lang
                        })}
                        className="p-1.5 rounded hover:bg-white/10 text-muted-foreground hover:text-foreground transition-all"
                        title="Open in Canvas"
                      >
                        <ArrowSquareOut className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </div>
                  <SyntaxHighlighter
                    language={lang}
                    style={vscDarkPlus}
                    customStyle={{
                      margin: 0,
                      padding: '1rem',
                      fontSize: '0.8rem',
                      lineHeight: '1.5',
                      background: 'transparent',
                    }}
                    codeTagProps={{
                      style: { fontFamily: 'inherit' }
                    }}
                  >
                    {codeString}
                  </SyntaxHighlighter>
                </div>
              );
            }
          }}
        >
          {displayContent}
        </ReactMarkdown>
      </div>

      {/* Action Buttons */}
      <div className="flex items-center gap-1 mt-4 opacity-0 group-hover:opacity-100 transition-opacity duration-200">
        <button
          onClick={handlePlayTTS}
          disabled={isSynthesizing}
          className={`p-2 rounded-md transition-all duration-200 ${isPlaying ? 'bg-[var(--k-brand)]/10 text-[var(--k-brand)]' : 'hover:bg-accent text-muted-foreground hover:text-foreground'}`}
          title={isPlaying ? 'Stop voice' : 'Play Kautilya Voice'}
        >
          {isSynthesizing
            ? <SpeakerHigh className="w-4 h-4 animate-pulse" />
            : isPlaying
            ? <StopCircle className="w-4 h-4" weight="bold" />
            : <Play className="w-4 h-4" weight="bold" />}
        </button>

        <button
          onClick={() => handleCopy(displayContent)}
          className="p-2 rounded-md hover:bg-accent text-muted-foreground hover:text-foreground transition-all duration-200"
          title="Copy Message"
        >
          {copied ? <Check className="w-4 h-4 text-emerald-400" weight="bold" /> : <Copy className="w-4 h-4" weight="bold" />}
        </button>

        <button
          onClick={() => onRegenerate?.(message)}
          className="p-2 rounded-md hover:bg-accent text-muted-foreground hover:text-foreground transition-all duration-200"
          title="Regenerate Response"
        >
          <ArrowsClockwise className="w-4 h-4" weight="bold" />
        </button>
      </div>

      {/* Citations */}
      {message.citations && message.citations.length > 0 && (
        <div className="mt-6 space-y-2" data-testid="citations-panel">
          <span className="text-[9px] tracking-[0.25em] uppercase font-bold text-muted-foreground/40">Knowledge Sources</span>
          <div className="flex flex-wrap gap-2">
            {message.citations.map((cite) => (
              <a
                key={cite.id}
                href={cite.url}
                target="_blank"
                rel="noopener noreferrer"
                data-testid={`citation-${cite.id}`}
                className="flex items-center gap-2 px-3 py-2 rounded-lg border border-[var(--k-border)] bg-muted/5 hover:bg-accent hover:border-[var(--k-brand)]/20 transition-all duration-200 text-xs group/cite"
              >
                <div className="w-5 h-5 rounded bg-[var(--k-brand)]/10 flex items-center justify-center text-[var(--k-brand)] font-bold text-[10px]">
                  {cite.id}
                </div>
                <span className="text-foreground/90 font-medium truncate max-w-[150px]">{cite.title}</span>
                <ArrowSquareOut className="w-3 h-3 text-muted-foreground/40 group-hover/cite:text-[var(--k-brand)]" />
              </a>
            ))}
          </div>
        </div>
      )}

      {/* Artifact Button */}
      {message.hasArtifact && (
        <button
          data-testid="open-artifact-btn"
          onClick={() => onOpenArtifact?.()}
          className="mt-6 flex items-center gap-3 px-5 py-3 rounded-xl border border-[var(--k-brand)]/20 bg-[var(--k-brand)]/5 hover:bg-[var(--k-brand)]/10 transition-all duration-300 text-sm text-[var(--k-brand)] font-bold group/art shadow-sm"
        >
          <div className="w-8 h-8 rounded-lg bg-[var(--k-brand)]/10 flex items-center justify-center group-hover/art:scale-110 transition-transform">
            <Code className="w-4 h-4" weight="bold" />
          </div>
          <div className="flex flex-col items-start">
            <span className="text-foreground">{message.artifactTitle || 'Interactive Content'}</span>
            <span className="text-[10px] text-muted-foreground uppercase tracking-widest font-bold">Open in Canvas</span>
          </div>
        </button>
      )}

      <div className="text-[10px] text-muted-foreground/40 mt-4 flex items-center gap-2">
        <div className="w-1 h-1 rounded-full bg-[var(--k-border)]" />
        {message.timestamp}
      </div>
    </div>
  );
}
