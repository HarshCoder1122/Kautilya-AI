import React, { useEffect, useMemo, useRef, useState } from "react";
import { Question, PencilSimple, ArrowRight, Check } from "@phosphor-icons/react";

/* ──────────────────────────────────────────────────────────────────────────
 * Interactive question prompt — Claude-style. When the assistant needs a
 * decision from the user it emits a ```question fenced block holding JSON:
 *
 *   {
 *     "question": "Which database should we use?",
 *     "options": [
 *       { "label": "Postgres", "description": "Relational, battle-tested" },
 *       { "label": "MongoDB" }
 *     ],
 *     "allowCustom": true,        // show a "Something else" free-text row
 *     "multiSelect": false        // checkboxes + Send instead of click-to-send
 *   }
 *
 * Picking an option (or typing a custom answer / Skip) sends that text back as
 * the user's next message via onAnswer(). The card is only interactive on the
 * latest message — older ones render as a read-only record of what was asked.
 * ────────────────────────────────────────────────────────────────────────── */

/** Tolerant parse of the fenced JSON — model output isn't always perfect, and
 * mid-stream the block is incomplete. Returns null until it's valid. */
function parseQuestion(raw) {
  const src = (raw || "").trim();
  if (!src) return null;
  let data;
  try {
    data = JSON.parse(src);
  } catch {
    // Salvage attempt: grab the outermost {...} (handles trailing prose).
    const a = src.indexOf("{");
    const b = src.lastIndexOf("}");
    if (a < 0 || b <= a) return null;
    try { data = JSON.parse(src.slice(a, b + 1)); } catch { return null; }
  }
  if (!data || typeof data !== "object") return null;
  const question = String(data.question || data.prompt || data.title || "").trim();
  const rawOpts = Array.isArray(data.options) ? data.options
    : Array.isArray(data.choices) ? data.choices : [];
  const options = rawOpts
    .map((o) => (typeof o === "string"
      ? { label: o.trim(), description: "" }
      : { label: String(o.label ?? o.text ?? o.value ?? "").trim(),
          description: String(o.description ?? o.detail ?? "").trim() }))
    .filter((o) => o.label);
  if (!question || options.length === 0) return null;
  return {
    question,
    options,
    allowCustom: data.allowCustom !== false, // default on
    multiSelect: Boolean(data.multiSelect || data.multi),
    skipLabel: typeof data.skipLabel === "string" ? data.skipLabel : "Skip",
  };
}

export function QuestionPrompt({ code, interactive = true, onAnswer }) {
  const data = useMemo(() => parseQuestion(code), [code]);
  const [selected, setSelected] = useState([]);   // indices (multiSelect)
  const [custom, setCustom] = useState("");
  const [showCustom, setShowCustom] = useState(false);
  const [answered, setAnswered] = useState(null);  // the text that was sent
  const [active, setActive] = useState(0);          // keyboard cursor
  const customRef = useRef(null);
  const rootRef = useRef(null);

  useEffect(() => { if (showCustom) customRef.current?.focus(); }, [showCustom]);

  // Still streaming / unparseable → quiet placeholder so the bubble isn't ugly.
  if (!data) {
    return (
      <div className="my-3 rounded-xl border border-[var(--k-border)] bg-[var(--k-surface)]/60 px-4 py-3 text-xs text-muted-foreground/70 italic flex items-center gap-2" data-testid="question-prompt-loading">
        <Question className="w-4 h-4 text-[var(--k-brand)]" weight="duotone" />
        Preparing a question…
      </div>
    );
  }

  const { question, options, allowCustom, multiSelect, skipLabel } = data;
  const locked = !interactive || answered !== null;

  const send = (text) => {
    const t = (text || "").trim();
    if (!t || locked) return;
    setAnswered(t);
    onAnswer?.(t);
  };

  const pickSingle = (i) => {
    if (locked) return;
    send(options[i].label);
  };

  const toggleMulti = (i) => {
    if (locked) return;
    setSelected((prev) => prev.includes(i) ? prev.filter((x) => x !== i) : [...prev, i]);
  };

  const submitMulti = () => {
    if (locked || selected.length === 0) return;
    send(selected.sort((a, b) => a - b).map((i) => options[i].label).join(", "));
  };

  const submitCustom = () => {
    if (custom.trim()) send(custom.trim());
  };

  // Keyboard: 1-9 jump to an option, ↑/↓ move, Enter activates.
  const onKeyDown = (e) => {
    if (locked) return;
    if (/^[1-9]$/.test(e.key)) {
      const i = parseInt(e.key, 10) - 1;
      if (i < options.length) {
        e.preventDefault();
        setActive(i);
        if (!multiSelect) pickSingle(i); else toggleMulti(i);
      }
      return;
    }
    if (e.key === "ArrowDown") { e.preventDefault(); setActive((a) => Math.min(options.length - 1, a + 1)); }
    else if (e.key === "ArrowUp") { e.preventDefault(); setActive((a) => Math.max(0, a - 1)); }
    else if (e.key === "Enter" && !showCustom) {
      e.preventDefault();
      if (!multiSelect) pickSingle(active); else toggleMulti(active);
    }
  };

  return (
    <div
      ref={rootRef}
      tabIndex={locked ? -1 : 0}
      onKeyDown={onKeyDown}
      data-testid="question-prompt"
      className={`my-4 rounded-xl border bg-[var(--k-surface)] outline-none w-full max-w-full min-w-0 overflow-hidden transition-opacity ${
        locked ? "border-[var(--k-border)] opacity-80" : "border-[var(--k-brand)]/40 focus:ring-1 focus:ring-[var(--k-brand)]/50"
      }`}
    >
      {/* Question header */}
      <div className="flex items-center gap-2 px-4 py-3 border-b border-[var(--k-border)]/60">
        <Question className="w-4 h-4 text-[var(--k-brand)] shrink-0" weight="duotone" />
        <span className="text-sm font-semibold text-foreground">{question}</span>
      </div>

      {/* Options */}
      <div className="divide-y divide-[var(--k-border)]/40">
        {options.map((opt, i) => {
          const isSel = selected.includes(i);
          const isAnswer = answered && (answered === opt.label || answered.split(", ").includes(opt.label));
          return (
            <button
              key={i}
              type="button"
              disabled={locked && !isAnswer}
              onClick={() => (multiSelect ? toggleMulti(i) : pickSingle(i))}
              onMouseEnter={() => setActive(i)}
              className={`w-full text-left flex items-start gap-3 px-4 py-3 transition-colors ${
                locked ? "cursor-default" : "cursor-pointer hover:bg-[var(--k-brand)]/10"
              } ${active === i && !locked ? "bg-[var(--k-brand)]/10" : ""} ${isAnswer ? "bg-[var(--k-brand)]/15" : ""}`}
            >
              {/* number / checkbox */}
              <span className={`shrink-0 mt-0.5 flex items-center justify-center w-5 h-5 rounded ${
                multiSelect
                  ? `border ${isSel ? "bg-[var(--k-brand)] border-[var(--k-brand)]" : "border-[var(--k-border)]"}`
                  : "text-[11px] font-mono text-muted-foreground bg-accent/40 rounded-md"
              }`}>
                {multiSelect ? (isSel && <Check className="w-3.5 h-3.5 text-white" weight="bold" />) : i + 1}
              </span>
              <span className="min-w-0 flex-1">
                <span className="block text-sm text-foreground">{opt.label}</span>
                {opt.description && (
                  <span className="block text-xs text-muted-foreground mt-0.5">{opt.description}</span>
                )}
              </span>
              {isAnswer && <Check className="w-4 h-4 text-[var(--k-brand)] shrink-0 mt-0.5" weight="bold" />}
            </button>
          );
        })}

        {/* Custom answer row */}
        {allowCustom && !locked && (
          <div className="px-4 py-2.5">
            {showCustom ? (
              <div className="flex items-center gap-2">
                <PencilSimple className="w-4 h-4 text-muted-foreground shrink-0" />
                <input
                  ref={customRef}
                  value={custom}
                  onChange={(e) => setCustom(e.target.value)}
                  onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); submitCustom(); } }}
                  placeholder="Type your answer…"
                  className="flex-1 bg-transparent text-sm text-foreground placeholder:text-muted-foreground/60 outline-none border-b border-[var(--k-border)] focus:border-[var(--k-brand)] py-1"
                />
                <button type="button" onClick={submitCustom} disabled={!custom.trim()}
                  className="p-1.5 rounded text-[var(--k-brand)] hover:bg-[var(--k-brand)]/10 disabled:opacity-40" title="Send">
                  <ArrowRight className="w-4 h-4" weight="bold" />
                </button>
              </div>
            ) : (
              <button type="button" onClick={() => setShowCustom(true)}
                className="flex items-center gap-3 text-left w-full text-sm text-muted-foreground hover:text-foreground transition-colors">
                <PencilSimple className="w-4 h-4 shrink-0" />
                Something else
              </button>
            )}
          </div>
        )}
      </div>

      {/* Footer: multiSelect Send + Skip */}
      {!locked && (
        <div className="flex items-center justify-between px-4 py-2.5 border-t border-[var(--k-border)]/60 bg-black/10">
          <span className="text-[11px] text-muted-foreground/60 hidden sm:inline">
            {multiSelect ? "Pick one or more" : "Press 1–9 or click"}
          </span>
          <div className="flex items-center gap-2 ml-auto">
            <button type="button" onClick={() => send(skipLabel)}
              className="px-3 py-1.5 rounded-md text-xs text-muted-foreground hover:text-foreground hover:bg-accent transition-colors">
              {skipLabel}
            </button>
            {multiSelect && (
              <button type="button" onClick={submitMulti} disabled={selected.length === 0}
                className="px-3 py-1.5 rounded-md text-xs font-semibold bg-[var(--k-brand)] text-white hover:opacity-90 disabled:opacity-40 transition-opacity flex items-center gap-1.5">
                Send <ArrowRight className="w-3.5 h-3.5" weight="bold" />
              </button>
            )}
          </div>
        </div>
      )}

      {answered && (
        <div className="px-4 py-2 border-t border-[var(--k-border)]/60 text-[11px] text-muted-foreground italic">
          Answered: {answered}
        </div>
      )}
    </div>
  );
}

export default QuestionPrompt;
