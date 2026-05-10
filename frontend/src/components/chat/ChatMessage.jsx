import { User, Robot, Code, Copy, Check, Play, Pause, ArrowsCounterClockwise, Clock } from "@phosphor-icons/react";
import React, { useState } from "react";
import ReactMarkdown from 'react-markdown';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { ttsAPI } from "../../lib/api";

export const ChatMessage = ({ message, isLast, onOpenArtifact, onRegenerate }) => {
  const isAssistant = message.role === 'assistant';
  const [copied, setCopied] = useState(false);
  const [isPlaying, setIsPlaying] = useState(false);
  const [audio, setAudio] = useState(null);

  const handleCopy = () => {
    navigator.clipboard.writeText(message.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handlePlay = async () => {
    if (isPlaying && audio) {
      audio.pause();
      setIsPlaying(false);
      return;
    }
    try {
      setIsPlaying(true);
      const audioBlob = await ttsAPI.revealIQ.synthesize(message.content, 'kokoro-hi', 'af_heart');
      const newAudio = new Audio(URL.createObjectURL(audioBlob));
      setAudio(newAudio);
      newAudio.play();
      newAudio.onended = () => setIsPlaying(false);
    } catch (error) {
      console.error('TTS failed:', error);
      setIsPlaying(false);
    }
  };

  return (
    <div className={`flex w-full gap-4 py-6 px-4 ${isAssistant ? 'bg-accent/20' : ''} group animate-fade-in`}>
      <div className="flex-shrink-0 mt-1">
        <div className={`w-8 h-8 rounded-lg flex items-center justify-center ${isAssistant ? 'bg-[var(--k-brand)]/10 text-[var(--k-brand)]' : 'bg-muted text-muted-foreground'}`}>
          {isAssistant ? <Robot className="w-5 h-5" weight="duotone" /> : <User className="w-5 h-5" />}
        </div>
      </div>
      
      <div className="flex-1 min-w-0 space-y-2">
        <div className="flex items-center justify-between">
          <span className="text-xs font-bold uppercase tracking-widest text-muted-foreground">
            {isAssistant ? (message.agentType || 'Kautilya AI') : 'You'}
          </span>
          <span className="text-[10px] text-muted-foreground/50">{message.timestamp}</span>
        </div>

        {message.thinking && (
          <div className="flex items-start gap-2 p-3 rounded-lg bg-indigo-500/5 border border-indigo-500/10 mb-4 animate-pulse">
            <Clock className="w-3.5 h-3.5 text-indigo-400 mt-0.5" />
            <div className="text-xs text-indigo-300/80 italic font-medium leading-relaxed">
              {message.thinking}
            </div>
          </div>
        )}

        <div className="prose prose-invert prose-sm max-w-none prose-pre:bg-black/50 prose-pre:border prose-pre:border-white/10 prose-code:text-[var(--k-brand)]">
          <ReactMarkdown
            components={{
              code({ node, inline, className, children, ...props }) {
                const match = /language-(\w+)/.exec(className || '');
                return !inline && match ? (
                  <div className="relative group/code my-4">
                    <div className="absolute right-3 top-3 z-10 opacity-0 group-hover/code:opacity-100 transition-opacity">
                      <button 
                        onClick={() => {
                          navigator.clipboard.writeText(String(children).replace(/\n$/, ''));
                          setCopied(true);
                          setTimeout(() => setCopied(false), 2000);
                        }}
                        className="p-1.5 rounded-md bg-white/10 hover:bg-white/20 text-white transition-colors"
                      >
                        {copied ? <Check className="w-3.5 h-3.5 text-green-400" /> : <Copy className="w-3.5 h-3.5" />}
                      </button>
                    </div>
                    <SyntaxHighlighter
                      style={vscDarkPlus}
                      language={match[1]}
                      PreTag="div"
                      className="rounded-xl !bg-[#0D0D0D] !border !border-white/5 !p-4 !m-0"
                      {...props}
                    >
                      {String(children).replace(/\n$/, '')}
                    </SyntaxHighlighter>
                  </div>
                ) : (
                  <code className={`${className} bg-white/5 px-1.5 py-0.5 rounded-md text-[var(--k-brand)]`} {...props}>
                    {children}
                  </code>
                );
              }
            }}
          >
            {message.content}
          </ReactMarkdown>
        </div>

        {message.hasArtifact && (
          <button
            onClick={() => onOpenArtifact?.(message)}
            className="mt-4 flex items-center gap-3 p-3 w-full rounded-xl border border-[var(--k-brand)]/20 bg-[var(--k-brand)]/5 hover:bg-[var(--k-brand)]/10 transition-all group/art"
          >
            <div className="w-10 h-10 rounded-lg bg-[var(--k-brand)]/10 flex items-center justify-center group-hover/art:scale-110 transition-transform">
               <Code className="w-5 h-5 text-[var(--k-brand)]" />
            </div>
            <div className="text-left flex-1">
               <div className="text-xs font-bold text-foreground">{message.artifactTitle || 'Analysis Result'}</div>
               <div className="text-[10px] text-muted-foreground uppercase tracking-widest">Click to expand artifact</div>
            </div>
          </button>
        )}

        {isAssistant && !message.thinking && (
          <div className="flex items-center gap-1 pt-2 opacity-0 group-hover:opacity-100 transition-opacity">
            <button 
              onClick={handlePlay}
              className={`p-2 rounded-md hover:bg-accent ${isPlaying ? 'text-[var(--k-brand)]' : 'text-muted-foreground'} transition-colors`}
              title="Play Response (Neha Kapoor)"
            >
              {isPlaying ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
            </button>
            <button 
              onClick={handleCopy}
              className="p-2 rounded-md hover:bg-accent text-muted-foreground transition-colors"
              title="Copy Message"
            >
              {copied ? <Check className="w-4 h-4 text-green-500" /> : <Copy className="w-4 h-4" />}
            </button>
            <button 
              onClick={() => onRegenerate?.(message)}
              className="p-2 rounded-md hover:bg-accent text-muted-foreground transition-colors"
              title="Regenerate Response"
            >
              <ArrowsCounterClockwise className="w-4 h-4" />
            </button>
          </div>
        )}
      </div>
    </div>
  );
};

export default ChatMessage;
