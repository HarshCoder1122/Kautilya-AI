import { Brain } from "@phosphor-icons/react";
import { useEffect, useState } from "react";

export function ThinkingTokens({ text }) {
  const [visibleChars, setVisibleChars] = useState(0);
  const words = text.split(' ');

  useEffect(() => {
    const interval = setInterval(() => {
      setVisibleChars(prev => {
        if (prev >= text.length) {
          clearInterval(interval);
          return prev;
        }
        return prev + 2;
      });
    }, 30);
    return () => clearInterval(interval);
  }, [text]);

  const visibleText = text.slice(0, visibleChars);

  return (
    <div className="animate-fade-up" data-testid="thinking-tokens">
      <div className="flex items-center gap-2 mb-2">
        <div className="flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[10px] font-medium text-[var(--k-yellow)] bg-[var(--k-yellow)]/10">
          <Brain className="w-3 h-3 thinking-pulse" weight="duotone" />
          Thinking...
        </div>
      </div>
      <div className="pl-1 border-l-2 border-[var(--k-yellow)]/30 ml-1">
        <p className="text-xs text-muted-foreground font-mono leading-relaxed pl-3">
          <span className="text-[var(--k-yellow)]/80">&gt; </span>
          {visibleText}
          <span className="typing-cursor" />
        </p>
      </div>
    </div>
  );
}
