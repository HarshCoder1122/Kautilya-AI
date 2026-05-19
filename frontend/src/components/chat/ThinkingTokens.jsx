import { Brain } from "@phosphor-icons/react";
import { useEffect, useState } from "react";

const THINKING_PHRASES = [
  "Analyzing request...",
  "Routing to agent...",
  "Gathering context...",
  "Drafting response..."
];

export function ThinkingTokens({ text }) {
  // If the parent passes specific text (like a status), we use it. 
  // Otherwise, we shuffle through generic phrases.
  const [phraseIndex, setPhraseIndex] = useState(0);

  useEffect(() => {
    const interval = setInterval(() => {
      setPhraseIndex(prev => (prev + 1) % THINKING_PHRASES.length);
    }, 2000); // Change phrase every 2 seconds
    return () => clearInterval(interval);
  }, []);

  const displayPhrase = text && text.trim() && !text.includes("Reading your question...") 
    ? text 
    : THINKING_PHRASES[phraseIndex];

  return (
    <div className="animate-fade-up" data-testid="thinking-tokens">
      <div className="flex items-center gap-2 mb-2">
        <div className="flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[10px] font-medium text-[var(--k-yellow)] bg-[var(--k-yellow)]/10 border border-[var(--k-yellow)]/20">
          <Brain className="w-3 h-3 thinking-pulse" weight="duotone" />
          Thinking...
        </div>
      </div>
      <div className="pl-3 border-l-2 border-[var(--k-yellow)]/30 ml-1.5">
        <p className="text-[11px] text-muted-foreground/70 font-mono leading-relaxed italic transition-opacity duration-300">
          {displayPhrase}
          <span className="typing-cursor ml-1" />
        </p>
      </div>
    </div>
  );
}

