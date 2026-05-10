import { Brain, Code, ChartBar, ArrowSquareOut, Play, Pause, Copy, Check, ArrowsClockwise, SpeakerHigh } from "@phosphor-icons/react";
import React, { useState, useRef } from "react";
import ReactMarkdown from 'react-markdown';
import { ThinkingTokens } from "./ThinkingTokens";
import { ttsAPI } from "../../lib/api";

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

  const handleCopy = () => {
    navigator.clipboard.writeText(message.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handlePlayTTS = async () => {
    if (isPlaying) {
      audioRef.current?.pause();
      setIsPlaying(false);
      return;
    }

    if (audioRef.current) {
      audioRef.current.play();
      setIsPlaying(true);
      return;
    }

    try {
      setIsSynthesizing(true);
      // Using Neha Kapoor (Swara-EN) - Model: kokoro-en, Voice: af_heart
      const audioBlob = await ttsAPI.revealIQ.synthesize(
        message.content.replace(/<think>[\s\S]*?<\/think>/g, '').trim(),
        'kokoro-en',
        'af_heart'
      );
      
      const url = URL.createObjectURL(audioBlob);
      const audio = new Audio(url);
      audioRef.current = audio;
      
      audio.onended = () => {
        setIsPlaying(false);
        URL.revokeObjectURL(url);
        audioRef.current = null;
      };

      audio.play();
      setIsPlaying(true);
    } catch (error) {
      console.error('TTS Failed:', error);
      alert('Voice synthesis failed. Please try again.');
    } finally {
      setIsSynthesizing(false);
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

      {/* Response with markdown */}
      <div className="text-sm text-foreground leading-relaxed prose prose-invert prose-sm max-w-none prose-pre:bg-black/40 prose-pre:border prose-pre:border-white/5">
        <ReactMarkdown>{(message.responseText || message.content || '').replace(/<think>[\s\S]*?<\/think>/g, '').trim()}</ReactMarkdown>
      </div>

      {/* Action Buttons */}
      <div className="flex items-center gap-1 mt-4 opacity-0 group-hover:opacity-100 transition-opacity duration-200">
        <button
          onClick={handlePlayTTS}
          disabled={isSynthesizing}
          className={`p-2 rounded-md transition-all duration-200 ${isPlaying ? 'bg-[var(--k-brand)]/10 text-[var(--k-brand)]' : 'hover:bg-accent text-muted-foreground hover:text-foreground'}`}
          title="Play Neha's Voice"
        >
          {isSynthesizing ? <SpeakerHigh className="w-4 h-4 animate-pulse" /> : isPlaying ? <Pause className="w-4 h-4" weight="bold" /> : <Play className="w-4 h-4" weight="bold" />}
        </button>
        
        <button
          onClick={handleCopy}
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
          onClick={onOpenArtifact}
          className="mt-6 flex items-center gap-3 px-5 py-3 rounded-xl border border-[var(--k-brand)]/20 bg-[var(--k-brand)]/5 hover:bg-[var(--k-brand)]/10 transition-all duration-300 text-sm text-[var(--k-brand)] font-bold group/art shadow-sm"
        >
          <div className="w-8 h-8 rounded-lg bg-[var(--k-brand)]/10 flex items-center justify-center group-hover/art:scale-110 transition-transform">
            <Code className="w-4 h-4" weight="bold" />
          </div>
          <div className="flex flex-col items-start">
            <span className="text-foreground">Interactive Content</span>
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
