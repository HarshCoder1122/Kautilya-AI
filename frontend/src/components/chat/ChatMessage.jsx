import { Brain, Code, ChartBar, ArrowSquareOut } from "@phosphor-icons/react";
import ReactMarkdown from 'react-markdown';
import { ThinkingTokens } from "./ThinkingTokens";

const agentBadge = {
  researcher: { icon: Brain, label: 'Researcher', color: 'text-blue-400', bg: 'bg-blue-400/10' },
  coder: { icon: Code, label: 'Code Interpreter', color: 'text-emerald-400', bg: 'bg-emerald-400/10' },
  sales: { icon: ChartBar, label: 'Sales Agent', color: 'text-amber-400', bg: 'bg-amber-400/10' },
};

export function ChatMessage({ message, onOpenArtifact }) {
  if (message.role === 'user') {
    return (
      <div className="message-user flex justify-end animate-fade-up" data-testid={`message-${message.id}`}>
        <div className="max-w-[85%]">
          <div className="bg-[var(--k-brand)] text-white px-4 py-3 rounded-2xl rounded-br-md text-sm leading-relaxed">
            {message.content}
          </div>
          <div className="text-[10px] text-muted-foreground/50 mt-1 text-right">{message.timestamp}</div>
        </div>
      </div>
    );
  }

  const agent = message.agentType ? agentBadge[message.agentType] : null;

  return (
    <div className="message-ai animate-fade-up" data-testid={`message-${message.id}`}>
      {/* Agent Badge */}
      {agent && (
        <div className="flex items-center gap-2 mb-2">
          <div className={`flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[10px] font-medium ${agent.color} ${agent.bg}`}>
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
        <details className="mb-3 group" data-testid="thinking-details">
          <summary className="flex items-center gap-2 cursor-pointer text-xs text-muted-foreground hover:text-foreground transition-colors list-none">
            <Brain className="w-3.5 h-3.5 text-[var(--k-yellow)]" weight="duotone" />
            <span className="font-mono text-[11px]">Thinking completed</span>
            <span className="text-[10px] text-muted-foreground/40 ml-1 opacity-0 group-hover:opacity-100 transition-opacity">click to expand</span>
          </summary>
          <div className="mt-2 pl-4 border-l-2 border-[var(--k-yellow)]/20">
            <p className="text-[11px] text-muted-foreground/80 font-mono leading-relaxed whitespace-pre-wrap">{message.thinking}</p>
          </div>
        </details>
      )}

      {/* Response with markdown */}
      <div className="text-sm text-foreground leading-relaxed prose prose-invert prose-sm max-w-none">
        <ReactMarkdown>{(message.responseText || message.content || '').replace(/<think>[\s\S]*?<\/think>/g, '').trim()}</ReactMarkdown>
      </div>

      {/* Citations */}
      {message.citations && message.citations.length > 0 && (
        <div className="mt-4 space-y-1.5" data-testid="citations-panel">
          <span className="text-[10px] tracking-[0.2em] uppercase font-semibold text-muted-foreground">Sources</span>
          <div className="flex flex-wrap gap-2">
            {message.citations.map((cite) => (
              <a
                key={cite.id}
                href={cite.url}
      <div className="text-[10px] text-muted-foreground/50 mt-2">{message.timestamp}</div>
    </div>
  );
}
