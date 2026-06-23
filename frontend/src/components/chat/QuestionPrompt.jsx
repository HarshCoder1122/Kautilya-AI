import React, { useEffect, useMemo, useRef, useState } from "react";
import { Question, PencilSimple, ArrowRight, Check } from "@phosphor-icons/react";
import { parseQuestion } from "../../lib/questionBlock";

/* ──────────────────────────────────────────────────────────────────────────
 * Interactive question prompt — Claude-style. The assistant emits a
 * ```question fenced block holding JSON. Two shapes are supported:
 *
 *  Single:  { "question": "…", "options": [{label,description}], allowCustom, multiSelect }
 *  Multiple (up to ~4 per task):
 *           { "questions": [ {question, options, allowCustom, multiSelect}, … ] }
 *
 * Single → click an option (or type custom / Skip) sends immediately.
 * Multiple → pick/type an answer for each, then one "Send" submits them all as
 * one labelled message. Rendered docked above the composer (see ChatMain), only
 * on the latest assistant turn.
 * ────────────────────────────────────────────────────────────────────────── */

function Placeholder() {
  return (
    <div className="my-3 rounded-xl border border-[var(--k-border)] bg-[var(--k-surface)]/60 px-4 py-3 text-xs text-muted-foreground/70 italic flex items-center gap-2" data-testid="question-prompt-loading">
      <Question className="w-4 h-4 text-[var(--k-brand)]" weight="duotone" />
      Preparing a question…
    </div>
  );
}

/* ── Single question: click-to-send (snappy) ──────────────────────────────── */
function SingleQuestion({ q, skipLabel, onSend, onSkip }) {
  const { question, options, allowCustom, multiSelect } = q;
  const [selected, setSelected] = useState([]);
  const [custom, setCustom] = useState("");
  const [showCustom, setShowCustom] = useState(false);
  const [active, setActive] = useState(0);
  const customRef = useRef(null);
  useEffect(() => { if (showCustom) customRef.current?.focus(); }, [showCustom]);

  // Send the QUESTION followed by the chosen answer, so the conversation reads
  // coherently (what was asked + what the user picked) instead of a bare label.
  const fmt = (ans) => `${question}\n${ans}`;
  const pickSingle = (i) => onSend(fmt(options[i].label));
  const toggleMulti = (i) => setSelected((p) => p.includes(i) ? p.filter((x) => x !== i) : [...p, i]);
  const submitMulti = () => selected.length && onSend(fmt(selected.sort((a, b) => a - b).map((i) => options[i].label).join(", ")));
  const submitCustom = () => custom.trim() && onSend(fmt(custom.trim()));

  const onKeyDown = (e) => {
    if (/^[1-9]$/.test(e.key)) {
      const i = parseInt(e.key, 10) - 1;
      if (i < options.length) { e.preventDefault(); setActive(i); multiSelect ? toggleMulti(i) : pickSingle(i); }
      return;
    }
    if (e.key === "ArrowDown") { e.preventDefault(); setActive((a) => Math.min(options.length - 1, a + 1)); }
    else if (e.key === "ArrowUp") { e.preventDefault(); setActive((a) => Math.max(0, a - 1)); }
    else if (e.key === "Enter" && !showCustom) { e.preventDefault(); multiSelect ? toggleMulti(active) : pickSingle(active); }
  };

  return (
    <div
      tabIndex={0}
      onKeyDown={onKeyDown}
      data-testid="question-prompt"
      className="my-4 rounded-xl border border-[var(--k-brand)]/40 bg-[var(--k-surface)] outline-none focus:ring-1 focus:ring-[var(--k-brand)]/50 w-full max-w-full min-w-0 overflow-hidden"
    >
      <div className="flex items-center gap-2 px-4 py-3 border-b border-[var(--k-border)]/60">
        <Question className="w-4 h-4 text-[var(--k-brand)] shrink-0" weight="duotone" />
        <span className="text-sm font-semibold text-foreground">{question}</span>
      </div>

      <div className="divide-y divide-[var(--k-border)]/40">
        {options.map((opt, i) => {
          const isSel = selected.includes(i);
          return (
            <button
              key={i}
              type="button"
              onClick={() => (multiSelect ? toggleMulti(i) : pickSingle(i))}
              onMouseEnter={() => setActive(i)}
              className={`w-full text-left flex items-start gap-3 px-4 py-3 transition-colors cursor-pointer hover:bg-[var(--k-brand)]/10 ${active === i ? "bg-[var(--k-brand)]/10" : ""}`}
            >
              <span className={`shrink-0 mt-0.5 flex items-center justify-center w-5 h-5 rounded ${
                multiSelect
                  ? `border ${isSel ? "bg-[var(--k-brand)] border-[var(--k-brand)]" : "border-[var(--k-border)]"}`
                  : "text-[11px] font-mono text-muted-foreground bg-accent/40 rounded-md"
              }`}>
                {multiSelect ? (isSel && <Check className="w-3.5 h-3.5 text-white" weight="bold" />) : i + 1}
              </span>
              <span className="min-w-0 flex-1">
                <span className="block text-sm text-foreground">{opt.label}</span>
                {opt.description && <span className="block text-xs text-muted-foreground mt-0.5">{opt.description}</span>}
              </span>
            </button>
          );
        })}

        {allowCustom && (
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
                <PencilSimple className="w-4 h-4 shrink-0" /> Something else
              </button>
            )}
          </div>
        )}
      </div>

      <div className="flex items-center justify-between px-4 py-2.5 border-t border-[var(--k-border)]/60 bg-black/10">
        <span className="text-[11px] text-muted-foreground/60 hidden sm:inline">
          {multiSelect ? "Pick one or more" : "Press 1–9 or click"}
        </span>
        <div className="flex items-center gap-2 ml-auto">
          <button type="button" onClick={onSkip}
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
    </div>
  );
}

/* ── Multiple questions: answer each, then one Send ───────────────────────── */
function MultiQuestion({ questions, intro, skipLabel, onSend, onSkip }) {
  // picks[i] = array of selected option labels for question i; customs[i] = text.
  const [picks, setPicks] = useState(() => questions.map(() => []));
  const [customs, setCustoms] = useState(() => questions.map(() => ""));

  const setPick = (qi, label, multi) => {
    setPicks((prev) => {
      const next = prev.map((a) => a.slice());
      if (multi) next[qi] = next[qi].includes(label) ? next[qi].filter((l) => l !== label) : [...next[qi], label];
      else next[qi] = next[qi][0] === label ? [] : [label]; // toggle/replace
      return next;
    });
  };
  const setCustomAt = (qi, val) => setCustoms((prev) => { const n = prev.slice(); n[qi] = val; return n; });

  const answerFor = (qi) => {
    const c = customs[qi].trim();
    if (c) return c;
    return picks[qi].join(", ");
  };
  const answeredCount = questions.reduce((n, _q, qi) => n + (answerFor(qi) ? 1 : 0), 0);
  const allAnswered = answeredCount === questions.length;

  const submit = () => {
    if (!allAnswered) return;
    const lines = questions.map((q, qi) => `${q.question} — ${answerFor(qi)}`);
    onSend(lines.join("\n"));
  };

  return (
    <div data-testid="question-prompt-multi"
      className="my-4 rounded-xl border border-[var(--k-brand)]/40 bg-[var(--k-surface)] w-full max-w-full min-w-0 overflow-hidden">
      <div className="flex items-center gap-2 px-4 py-3 border-b border-[var(--k-border)]/60">
        <Question className="w-4 h-4 text-[var(--k-brand)] shrink-0" weight="duotone" />
        <span className="text-sm font-semibold text-foreground">{intro || "A few quick questions"}</span>
        <span className="ml-auto text-[11px] text-muted-foreground/60">{answeredCount}/{questions.length}</span>
      </div>

      <div className="divide-y divide-[var(--k-border)]/40 max-h-[46vh] overflow-y-auto">
        {questions.map((q, qi) => (
          <div key={qi} className="px-4 py-3">
            <div className="text-sm text-foreground mb-2">
              <span className="text-[var(--k-brand)] font-semibold mr-1.5">{qi + 1}.</span>{q.question}
            </div>
            <div className="flex flex-wrap gap-1.5">
              {q.options.map((opt, oi) => {
                const isSel = picks[qi].includes(opt.label) && !customs[qi].trim();
                return (
                  <button key={oi} type="button"
                    title={opt.description || undefined}
                    onClick={() => { setCustomAt(qi, ""); setPick(qi, opt.label, q.multiSelect); }}
                    className={`px-3 py-1.5 rounded-full text-xs border transition-colors ${
                      isSel
                        ? "bg-[var(--k-brand)] border-[var(--k-brand)] text-white"
                        : "border-[var(--k-border)] text-foreground hover:bg-[var(--k-brand)]/10"
                    }`}>
                    {opt.label}
                  </button>
                );
              })}
            </div>
            {q.allowCustom && (
              <div className="flex items-center gap-2 mt-2">
                <PencilSimple className="w-3.5 h-3.5 text-muted-foreground shrink-0" />
                <input
                  value={customs[qi]}
                  onChange={(e) => { setCustomAt(qi, e.target.value); if (e.target.value.trim()) setPicks((p) => { const n = p.map((a) => a.slice()); n[qi] = []; return n; }); }}
                  placeholder="or type your own…"
                  className="flex-1 bg-transparent text-xs text-foreground placeholder:text-muted-foreground/50 outline-none border-b border-[var(--k-border)]/60 focus:border-[var(--k-brand)] py-0.5"
                />
              </div>
            )}
          </div>
        ))}
      </div>

      <div className="flex items-center justify-between px-4 py-2.5 border-t border-[var(--k-border)]/60 bg-black/10">
        <button type="button" onClick={onSkip}
          className="px-3 py-1.5 rounded-md text-xs text-muted-foreground hover:text-foreground hover:bg-accent transition-colors">
          {skipLabel}
        </button>
        <button type="button" onClick={submit} disabled={!allAnswered}
          className="px-3.5 py-1.5 rounded-md text-xs font-semibold bg-[var(--k-brand)] text-white hover:opacity-90 disabled:opacity-40 transition-opacity flex items-center gap-1.5">
          Send {allAnswered ? "" : `(${answeredCount}/${questions.length})`} <ArrowRight className="w-3.5 h-3.5" weight="bold" />
        </button>
      </div>
    </div>
  );
}

export function QuestionPrompt({ code, interactive = true, onAnswer, onSkip }) {
  const data = useMemo(() => parseQuestion(code), [code]);
  const [answered, setAnswered] = useState(null);

  if (!data) return <Placeholder />;

  const locked = !interactive || answered !== null;
  const send = (text) => {
    const t = (text || "").trim();
    if (!t || locked) return;
    setAnswered(t);
    onAnswer?.(t);
  };
  // Skip = the user chose not to answer. Dismiss the card WITHOUT sending any
  // message (no "skip" text); the parent hides it so the chat just moves on.
  const skip = () => { if (!locked) onSkip?.(); };

  // Once answered, the dock unmounts (a new message becomes the latest) — but
  // show a compact confirmation for the brief overlap / non-interactive case.
  if (locked) {
    return (
      <div className="my-4 rounded-xl border border-[var(--k-border)] bg-[var(--k-surface)]/80 px-4 py-3 flex items-center gap-2 text-xs text-muted-foreground" data-testid="question-prompt-locked">
        <Check className="w-4 h-4 text-[var(--k-brand)] shrink-0" weight="bold" />
        {answered ? <span className="truncate">Sent: {answered.replace(/\n/g, " · ")}</span> : <span>Question answered.</span>}
      </div>
    );
  }

  return data.questions.length === 1
    ? <SingleQuestion q={data.questions[0]} skipLabel={data.skipLabel} onSend={send} onSkip={skip} />
    : <MultiQuestion questions={data.questions} intro={data.intro} skipLabel={data.skipLabel} onSend={send} onSkip={skip} />;
}

export default QuestionPrompt;
