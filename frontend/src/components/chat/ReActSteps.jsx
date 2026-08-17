import {
  MagnifyingGlass, Calculator, Code, Globe, Spinner, CheckCircle,
  WarningCircle, ArrowSquareOut, EnvelopeSimple, Calendar,
  WhatsappLogo, SlackLogo, Lightning, Receipt, FilePlus, FileText, FolderOpen
} from "@phosphor-icons/react";

const TOOL_META = {
  web_search:  { icon: MagnifyingGlass, label: "Web Search",  color: "text-blue-400",   bg: "bg-blue-400/10",   border: "border-blue-400/20" },
  calculator:  { icon: Calculator,      label: "Calculator",  color: "text-emerald-400", bg: "bg-emerald-400/10", border: "border-emerald-400/20" },
  code_run:    { icon: Code,            label: "Code",         color: "text-violet-400",  bg: "bg-violet-400/10",  border: "border-violet-400/20" },
  python:      { icon: Code,            label: "Python",       color: "text-violet-400",  bg: "bg-violet-400/10",  border: "border-violet-400/20" },
  scrape:      { icon: Globe,           label: "Web Scrape",  color: "text-amber-400",   bg: "bg-amber-400/10",   border: "border-amber-400/20" },
  gmail:       { icon: EnvelopeSimple,  label: "Gmail",       color: "text-rose-400",    bg: "bg-rose-400/10",    border: "border-rose-400/20" },
  calendar:    { icon: Calendar,        label: "Calendar",    color: "text-rose-400",    bg: "bg-rose-400/10",    border: "border-rose-400/20" },
  whatsapp:    { icon: WhatsappLogo,    label: "WhatsApp",    color: "text-emerald-400", bg: "bg-emerald-400/10", border: "border-emerald-400/20" },
  slack:       { icon: SlackLogo,       label: "Slack",       color: "text-purple-400",  bg: "bg-purple-400/10",  border: "border-purple-400/20" },
  hubspot:     { icon: Lightning,       label: "HubSpot",     color: "text-orange-400",  bg: "bg-orange-400/10",  border: "border-orange-400/20" },
  invoice:     { icon: Receipt,         label: "GST Invoice", color: "text-teal-400",    bg: "bg-teal-400/10",    border: "border-teal-400/20" },
  file_write:  { icon: FilePlus,        label: "Computer",    color: "text-sky-400",     bg: "bg-sky-400/10",     border: "border-sky-400/20" },
  file_read:   { icon: FileText,        label: "Computer",    color: "text-sky-400",     bg: "bg-sky-400/10",     border: "border-sky-400/20" },
  file_list:   { icon: FolderOpen,      label: "Computer",    color: "text-sky-400",     bg: "bg-sky-400/10",     border: "border-sky-400/20" },
};

const DEFAULT_TOOL = { icon: Globe, label: "Tool", color: "text-muted-foreground", bg: "bg-accent", border: "border-border" };

function StatusIcon({ status }) {
  if (status === "running") return <Spinner className="w-3.5 h-3.5 animate-spin text-amber-400" weight="bold" />;
  if (status === "done")    return <CheckCircle className="w-3.5 h-3.5 text-emerald-400" weight="fill" />;
  if (status === "error")   return <WarningCircle className="w-3.5 h-3.5 text-red-400" weight="fill" />;
  if (status === "empty")   return <WarningCircle className="w-3.5 h-3.5 text-amber-400" weight="fill" />;
  return null;
}

function SourceChips({ sources }) {
  if (!sources || sources.length === 0) return null;
  return (
    <div className="flex flex-wrap gap-1.5 mt-2">
      {sources.map((s, i) => (
        <a
          key={i}
          href={s.url}
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center gap-1 px-2 py-0.5 rounded-full bg-blue-400/5 border border-blue-400/15 text-[10px] text-blue-300/80 hover:text-blue-300 hover:border-blue-400/30 transition-colors max-w-[160px] truncate"
        >
          <span className="truncate">{s.title || s.url}</span>
          <ArrowSquareOut className="w-2.5 h-2.5 flex-shrink-0 opacity-60" />
        </a>
      ))}
    </div>
  );
}

function StepCard({ step, index, isSynthesizing, isLast }) {
  const meta = TOOL_META[step.tool] || DEFAULT_TOOL;
  const Icon = meta.icon;

  return (
    <div className="relative flex gap-3">
      {/* Vertical connector line */}
      {!isLast && (
        <div className="absolute left-[17px] top-8 bottom-0 w-px bg-[var(--k-border)] opacity-40" />
      )}

      {/* Tool icon bubble */}
      <div className={`flex-shrink-0 w-9 h-9 rounded-full flex items-center justify-center mt-0.5 ${meta.bg} border ${meta.border}`}>
        <Icon className={`w-4 h-4 ${meta.color}`} weight="duotone" />
      </div>

      {/* Step content */}
      <div className="flex-1 min-w-0 pb-4">
        <div className="flex items-center gap-2 mb-0.5">
          <span className={`text-[10px] font-bold uppercase tracking-widest ${meta.color}`}>{meta.label}</span>
          <StatusIcon status={step.status} />
        </div>

        {/* Input (truncated) */}
        <p className="text-xs text-foreground/80 font-medium truncate leading-snug">
          {step.input}
        </p>

        {/* Preview / result */}
        {step.preview && step.status !== "running" && (
          <p className={`text-[11px] mt-1 ${
            step.status === "error" ? "text-red-400/80" :
            step.status === "empty" ? "text-amber-400/80" :
            "text-muted-foreground"
          }`}>
            {step.preview}
          </p>
        )}

        {/* Source chips for web_search */}
        {step.tool === "web_search" && step.status === "done" && (
          <SourceChips sources={step.sources} />
        )}

        {/* Running pulse */}
        {step.status === "running" && (
          <div className="flex items-center gap-1 mt-1">
            <span className="text-[10px] text-amber-400/70 animate-pulse">Running…</span>
          </div>
        )}
      </div>
    </div>
  );
}

export function ReActSteps({ steps, isSynthesizing }) {
  if (!steps || steps.length === 0) return null;

  return (
    <div className="mb-5 p-3 rounded-xl border border-[var(--k-border)] bg-[var(--k-surface)]/50 space-y-0 w-full max-w-full min-w-0 overflow-hidden">
      {/* Header */}
      <div className="flex items-center gap-2 mb-3 pb-2 border-b border-[var(--k-border)]/50">
        <div className="w-1.5 h-1.5 rounded-full bg-[var(--k-brand)] animate-pulse" />
        <span className="text-[10px] uppercase tracking-[0.2em] font-bold text-muted-foreground/60">
          {isSynthesizing ? "Synthesizing answer…" : "Research steps"}
        </span>
      </div>

      {/* Step cards */}
      <div className="space-y-0">
        {steps.map((step, i) => (
          <StepCard
            key={step.id}
            step={step}
            index={i}
            isSynthesizing={isSynthesizing}
            isLast={i === steps.length - 1}
          />
        ))}
      </div>

      {/* Synthesis indicator */}
      {isSynthesizing && (
        <div className="flex items-center gap-2 mt-2 pt-2 border-t border-[var(--k-border)]/30">
          <Spinner className="w-3 h-3 animate-spin text-[var(--k-brand)]" weight="bold" />
          <span className="text-[11px] text-[var(--k-brand)]/80 font-medium">Writing final answer…</span>
        </div>
      )}
    </div>
  );
}
