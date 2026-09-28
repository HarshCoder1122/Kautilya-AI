import { useState, useEffect } from "react";
import { Sparkle, CheckCircle, PencilSimple, ArrowClockwise, Warning } from "@phosphor-icons/react";
import { userAPI } from "../../lib/api";

const CUSTOM_ID = "custom";

/**
 * Personality picker — Dashboard → Settings → Preferences.
 *
 * Built-in personas come from the backend (personalities_spec.py); the prompt
 * text itself never leaves the server. A custom persona is described in plain
 * language, written by Kautilya, then editable before saving.
 */
export default function PersonalitySettings() {
  const [personalities, setPersonalities] = useState([]);
  const [selected, setSelected] = useState("kautilya");
  const [customText, setCustomText] = useState("");
  const [customName, setCustomName] = useState("");
  const [description, setDescription] = useState("");
  const [generating, setGenerating] = useState(false);
  const [saving, setSaving] = useState(false);
  const [status, setStatus] = useState(null); // 'saved' | 'error' | 'genError'
  const [showBuilder, setShowBuilder] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const [list, settings] = await Promise.all([
          userAPI.getPersonalities(),
          userAPI.getSettings(),
        ]);
        setPersonalities(list?.personalities || []);
        const s = settings?.settings || {};
        setSelected(s.personality || list?.default || "kautilya");
        setCustomText(s.custom_personality || "");
        setCustomName(s.custom_personality_name || "");
        if (s.personality === CUSTOM_ID) setShowBuilder(true);
      } catch (e) {
        console.error("Failed to load personalities:", e);
      }
    })();
  }, []);

  const persist = async (payload) => {
    setSaving(true);
    setStatus(null);
    try {
      await userAPI.saveSettings(payload);
      setStatus("saved");
      setTimeout(() => setStatus(null), 2500);
    } catch (e) {
      console.error("Failed to save personality:", e);
      setStatus("error");
    } finally {
      setSaving(false);
    }
  };

  const choose = (id) => {
    setSelected(id);
    if (id === CUSTOM_ID) {
      setShowBuilder(true);
      // Don't persist "custom" until there's actually a custom persona saved,
      // otherwise the user gets the house voice with no explanation.
      if (!customText.trim()) return;
    }
    persist({ personality: id });
  };

  const generate = async () => {
    if (!description.trim() || generating) return;
    setGenerating(true);
    setStatus(null);
    try {
      const res = await userAPI.generatePersonality({
        description: description.trim(),
        name: customName.trim(),
      });
      setCustomText(res.personality || "");
      if (!customName.trim() && res.name) setCustomName(res.name);
    } catch (e) {
      console.error("Failed to generate personality:", e);
      setStatus("genError");
    } finally {
      setGenerating(false);
    }
  };

  const saveCustom = () =>
    persist({
      personality: CUSTOM_ID,
      custom_personality: customText.trim(),
      custom_personality_name: customName.trim() || "Custom",
    });

  return (
    <div className="space-y-5">
      <div>
        <h3 className="text-sm font-semibold uppercase tracking-widest text-muted-foreground">
          Personality
        </h3>
        <p className="mt-1.5 text-xs text-muted-foreground/80 max-w-2xl">
          How Kautilya talks to you. Voice only — every personality still refuses to invent
          facts, and still tells you when something is about to break.
        </p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-3">
        {personalities.map((p) => {
          const active = selected === p.id;
          return (
            <button
              key={p.id}
              type="button"
              onClick={() => choose(p.id)}
              className={`group text-left p-4 rounded-2xl border transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--k-brand)]/60 ${
                active
                  ? "border-[var(--k-brand)] bg-[var(--k-brand)]/[0.07] shadow-[0_0_0_1px_var(--k-brand)]"
                  : "border-[var(--k-border)] hover:border-white/20 hover:bg-white/[0.03]"
              }`}
            >
              <div className="flex items-start gap-3">
                <span className="text-xl leading-none mt-0.5" aria-hidden="true">
                  {p.emoji}
                </span>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-1.5">
                    <span className="text-sm font-semibold text-foreground truncate">
                      {p.name}
                    </span>
                    {active && (
                      <CheckCircle
                        className="w-3.5 h-3.5 text-[var(--k-brand)] shrink-0"
                        weight="fill"
                      />
                    )}
                  </div>
                  <div className="text-[11px] text-muted-foreground mt-0.5">{p.tagline}</div>
                  <div className="text-[11px] leading-relaxed text-muted-foreground/70 mt-1.5">
                    {p.description}
                  </div>
                </div>
              </div>
            </button>
          );
        })}

        {/* Custom persona card */}
        <button
          type="button"
          onClick={() => choose(CUSTOM_ID)}
          className={`group text-left p-4 rounded-2xl border border-dashed transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--k-brand)]/60 ${
            selected === CUSTOM_ID
              ? "border-[var(--k-brand)] bg-[var(--k-brand)]/[0.07]"
              : "border-[var(--k-border)] hover:border-white/25 hover:bg-white/[0.03]"
          }`}
        >
          <div className="flex items-start gap-3">
            <Sparkle className="w-5 h-5 text-[var(--k-brand)] mt-0.5 shrink-0" weight="fill" />
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-1.5">
                <span className="text-sm font-semibold text-foreground truncate">
                  {customName || "Build your own"}
                </span>
                {selected === CUSTOM_ID && customText && (
                  <CheckCircle
                    className="w-3.5 h-3.5 text-[var(--k-brand)] shrink-0"
                    weight="fill"
                  />
                )}
              </div>
              <div className="text-[11px] text-muted-foreground mt-0.5">
                {customText ? "Your custom personality" : "Describe it, Kautilya writes it"}
              </div>
              <div className="text-[11px] leading-relaxed text-muted-foreground/70 mt-1.5">
                Tell it how to talk — tone, humour, bluntness, length — and it becomes that
                for every chat.
              </div>
            </div>
          </div>
        </button>
      </div>

      {/* Custom builder */}
      {showBuilder && (
        <div className="p-5 rounded-2xl border border-[var(--k-border)] bg-white/[0.02] space-y-4 animate-fade-up">
          <div className="flex items-center gap-2">
            <PencilSimple className="w-4 h-4 text-[var(--k-brand)]" weight="bold" />
            <span className="text-sm font-semibold text-foreground">Custom personality</span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <div className="sm:col-span-1">
              <label className="block text-[11px] uppercase tracking-wider text-muted-foreground mb-1.5">
                Name
              </label>
              <input
                type="text"
                value={customName}
                onChange={(e) => setCustomName(e.target.value)}
                placeholder="e.g. Night Shift"
                maxLength={60}
                className="w-full px-3 py-2 text-sm rounded-xl bg-black/20 border border-[var(--k-border)] text-foreground placeholder:text-muted-foreground/50 focus:outline-none focus:border-[var(--k-brand)]/60 transition-colors"
              />
            </div>
            <div className="sm:col-span-2">
              <label className="block text-[11px] uppercase tracking-wider text-muted-foreground mb-1.5">
                Describe the personality
              </label>
              <input
                type="text"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && generate()}
                placeholder="A sarcastic Mumbai founder who hates jargon and answers in 2 lines"
                maxLength={2000}
                className="w-full px-3 py-2 text-sm rounded-xl bg-black/20 border border-[var(--k-border)] text-foreground placeholder:text-muted-foreground/50 focus:outline-none focus:border-[var(--k-brand)]/60 transition-colors"
              />
            </div>
          </div>

          <button
            type="button"
            onClick={generate}
            disabled={!description.trim() || generating}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium bg-[var(--k-brand)] text-black hover:brightness-110 active:scale-[0.98] disabled:opacity-40 disabled:cursor-not-allowed transition-all"
          >
            {generating ? (
              <>
                <ArrowClockwise className="w-4 h-4 animate-spin" weight="bold" />
                Writing it…
              </>
            ) : (
              <>
                <Sparkle className="w-4 h-4" weight="fill" />
                {customText ? "Rewrite with Kautilya" : "Generate with Kautilya"}
              </>
            )}
          </button>

          {status === "genError" && (
            <div className="flex items-center gap-2 text-xs text-amber-400">
              <Warning className="w-3.5 h-3.5" weight="fill" />
              Couldn't generate that right now — try again, or write it yourself below.
            </div>
          )}

          <div>
            <label className="block text-[11px] uppercase tracking-wider text-muted-foreground mb-1.5">
              Instructions {customText && <span className="normal-case tracking-normal text-muted-foreground/60">— edit freely</span>}
            </label>
            <textarea
              value={customText}
              onChange={(e) => setCustomText(e.target.value)}
              rows={8}
              maxLength={4000}
              placeholder={"- You open with the answer, never a preamble.\n- You keep replies under four sentences unless asked to go deep.\n- You never use corporate filler…"}
              className="w-full px-3 py-2.5 text-sm leading-relaxed rounded-xl bg-black/20 border border-[var(--k-border)] text-foreground placeholder:text-muted-foreground/40 focus:outline-none focus:border-[var(--k-brand)]/60 transition-colors font-mono resize-y"
            />
            <div className="mt-1 text-[11px] text-muted-foreground/60">
              {customText.length}/4000 · Applies to every chat until you switch personality.
            </div>
          </div>

          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={saveCustom}
              disabled={!customText.trim() || saving}
              className="px-4 py-2 rounded-xl text-sm font-medium border border-[var(--k-border)] text-foreground hover:bg-white/5 active:scale-[0.98] disabled:opacity-40 disabled:cursor-not-allowed transition-all"
            >
              {saving ? "Saving…" : "Save & activate"}
            </button>
            {status === "saved" && (
              <span className="inline-flex items-center gap-1.5 text-xs text-emerald-400">
                <CheckCircle className="w-3.5 h-3.5" weight="fill" />
                Saved
              </span>
            )}
            {status === "error" && (
              <span className="inline-flex items-center gap-1.5 text-xs text-red-400">
                <Warning className="w-3.5 h-3.5" weight="fill" />
                Couldn't save
              </span>
            )}
          </div>
        </div>
      )}

      {status === "saved" && !showBuilder && (
        <div className="inline-flex items-center gap-1.5 text-xs text-emerald-400">
          <CheckCircle className="w-3.5 h-3.5" weight="fill" />
          Personality updated
        </div>
      )}
    </div>
  );
}
