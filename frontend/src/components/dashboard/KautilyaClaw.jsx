import { useState, useEffect, useCallback, useRef } from "react";
import {
  Sparkle, TelegramLogo, WhatsappLogo, SlackLogo, DiscordLogo, GoogleLogo,
  ChatCircleDots, PaperPlaneTilt,
  Lightning, Brain, Robot, CheckCircle, WarningCircle, Trash, FloppyDisk,
  ArrowSquareOut, CircleNotch, Power, Plus, Info, Copy, CaretRight,
} from "@phosphor-icons/react";
import { clawAPI } from "../../lib/api";

const MODELS = [
  { id: "kautilya-daily", label: "Daily", icon: Lightning, desc: "Fast everyday chat" },
  { id: "kautilya-pro", label: "Pro", icon: Brain, desc: "Deep reasoning" },
  { id: "kautilya-coder", label: "Coder", icon: Robot, desc: "Agentic + code" },
];

// OpenClaw-native channels we can actually chat through. Telegram + WhatsApp
// are live; the rest are the feasible-next ones (webhook + token pattern).
const CHANNELS = [
  { id: "web", name: "Web Chat", icon: ChatCircleDots, color: "#0052FF", live: true, web: true },
  { id: "telegram", name: "Telegram", icon: TelegramLogo, color: "#229ED9", live: true },
  { id: "whatsapp", name: "WhatsApp", icon: WhatsappLogo, color: "#25D366", live: true },
  { id: "slack", name: "Slack", icon: SlackLogo, color: "#611f69", live: false },
  { id: "discord", name: "Discord", icon: DiscordLogo, color: "#5865F2", live: false },
  { id: "googlechat", name: "Google Chat", icon: GoogleLogo, color: "#1A73E8", live: false },
];

export default function KautilyaClaw() {
  const [loading, setLoading] = useState(true);
  const [cfg, setCfg] = useState(null);
  const [open, setOpen] = useState(null); // which channel panel is expanded

  const refresh = useCallback(async () => {
    try {
      const d = await clawAPI.get();
      setCfg(d || { configured: false });
    } catch {
      setCfg({ configured: false });
    } finally {
      setLoading(false);
    }
  }, []);
  useEffect(() => { refresh(); }, [refresh]);

  const configured = !!cfg?.configured;

  return (
    <div className="flex flex-col h-full min-h-0">
      <div className="flex items-center gap-3 px-5 py-4 border-b border-[var(--k-border)]">
        <div className="w-10 h-10 rounded-xl bg-[var(--k-brand)]/15 flex items-center justify-center shrink-0">
          <Sparkle className="w-5 h-5 text-[var(--k-brand)]" weight="duotone" />
        </div>
        <div>
          <h1 className="text-base font-semibold k-heading text-foreground">🦞 KautilyaClaw</h1>
          <p className="text-xs text-muted-foreground">
            Your own 24/7 AI agent in your chat apps — runs on your Kautilya account &amp; limits
          </p>
        </div>
      </div>

      <div className="flex-1 min-h-0 overflow-auto">
        <div className="max-w-2xl mx-auto px-5 py-6 space-y-5">
          {loading ? (
            <div className="flex items-center justify-center py-20 text-muted-foreground gap-2">
              <CircleNotch className="w-5 h-5 animate-spin" /> Loading…
            </div>
          ) : (
            <>
              {configured && <BrainCard cfg={cfg} onSaved={refresh} />}

              <div>
                <div className="text-xs font-semibold text-muted-foreground mb-2 px-1">CHANNELS</div>
                <div className="space-y-2">
                  {CHANNELS.map((ch) => (
                    <ChannelRow
                      key={ch.id} ch={ch} cfg={cfg}
                      expanded={open === ch.id}
                      onToggle={() => setOpen(open === ch.id ? null : ch.id)}
                      onChanged={refresh}
                    />
                  ))}
                </div>
              </div>

              {!configured && (
                <p className="text-xs text-muted-foreground text-center px-6">
                  Connect a channel above to spin up your Claw. It replies using your own
                  Kautilya models, integrations, and tier limits — no extra keys.
                </p>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}

function ChannelRow({ ch, cfg, expanded, onToggle, onChanged }) {
  const connected = ch.id === "telegram" ? cfg?.telegram?.configured
    : ch.id === "whatsapp" ? cfg?.whatsapp?.configured : false;
  const subtitle = ch.web ? "Free · chat here, no token needed"
    : connected ? "Connected" : ch.live ? "Tap to connect" : "Coming soon";

  return (
    <div className="rounded-xl border border-[var(--k-border)] bg-[var(--k-surface)] overflow-hidden">
      <button
        onClick={ch.live ? onToggle : undefined}
        disabled={!ch.live}
        className={`w-full flex items-center gap-3 px-4 py-3 text-left ${ch.live ? "hover:bg-accent/50" : "opacity-60 cursor-default"}`}
      >
        <div className="w-9 h-9 rounded-lg flex items-center justify-center shrink-0" style={{ background: `${ch.color}22` }}>
          <ch.icon className="w-5 h-5" weight="duotone" style={{ color: ch.color }} />
        </div>
        <div className="flex-1 min-w-0">
          <div className="text-sm font-semibold text-foreground">{ch.name}</div>
          <div className="text-[11px] text-muted-foreground">{subtitle}</div>
        </div>
        {ch.web ? (
          <CaretRight className={`w-4 h-4 text-muted-foreground transition-transform ${expanded ? "rotate-90" : ""}`} />
        ) : connected ? (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-500/15 text-emerald-500">
            <CheckCircle className="w-3 h-3" weight="fill" /> Live
          </span>
        ) : !ch.live ? (
          <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-zinc-500/15 text-zinc-400">Soon</span>
        ) : (
          <CaretRight className={`w-4 h-4 text-muted-foreground transition-transform ${expanded ? "rotate-90" : ""}`} />
        )}
      </button>

      {expanded && ch.live && (
        <div className="px-4 pb-4 pt-1 border-t border-[var(--k-border)]">
          {ch.id === "web" && <ClawWebChat onChanged={onChanged} />}
          {ch.id === "telegram" && <TelegramPanel cfg={cfg} onChanged={onChanged} />}
          {ch.id === "whatsapp" && <WhatsAppPanel cfg={cfg} onChanged={onChanged} />}
        </div>
      )}
    </div>
  );
}

// ───────────────────────── Web Chat (free, zero-setup) ─────────────────────────
function ClawWebChat({ onChanged }) {
  const [msgs, setMsgs] = useState([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const endRef = useRef(null);

  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth" }); }, [msgs, busy]);

  const send = async () => {
    const text = input.trim();
    if (!text || busy) return;
    const first = msgs.length === 0;
    setInput("");
    setMsgs((m) => [...m, { role: "user", text }]);
    setBusy(true);
    try {
      const r = await clawAPI.web.chat(text);
      setMsgs((m) => [...m, { role: "assistant", text: r?.reply || "…" }]);
      if (first) onChanged?.(); // first message creates the Claw → reveal settings
    } catch (e) {
      setMsgs((m) => [...m, { role: "assistant", text: "⚠️ " + (e?.response?.data?.error || "Failed to reply.") }]);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="pt-3">
      <div className="h-72 overflow-auto rounded-lg border border-[var(--k-border)] bg-[var(--k-bg)] p-3 space-y-2">
        {msgs.length === 0 && (
          <div className="text-xs text-muted-foreground text-center py-12">Say hi to your Claw 👋</div>
        )}
        {msgs.map((m, i) => (
          <div key={i} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
            <div className={`max-w-[80%] px-3 py-2 rounded-2xl text-sm whitespace-pre-wrap ${
              m.role === "user"
                ? "bg-[var(--k-brand)] text-white"
                : "bg-[var(--k-surface)] border border-[var(--k-border)] text-foreground"}`}>
              {m.text}
            </div>
          </div>
        ))}
        {busy && (
          <div className="flex justify-start">
            <div className="px-3 py-2 rounded-2xl bg-[var(--k-surface)] border border-[var(--k-border)]">
              <CircleNotch className="w-4 h-4 animate-spin text-muted-foreground" />
            </div>
          </div>
        )}
        <div ref={endRef} />
      </div>
      <div className="flex gap-2 mt-2">
        <input
          value={input} onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter") send(); }}
          placeholder="Message your Claw…"
          className="flex-1 px-3 py-2.5 rounded-lg bg-[var(--k-bg)] border border-[var(--k-border)] text-sm text-foreground outline-none focus:border-[var(--k-brand)]"
        />
        <button onClick={send} disabled={busy || !input.trim()}
                className="px-3.5 py-2.5 rounded-lg bg-[var(--k-brand)] text-white disabled:opacity-50">
          <PaperPlaneTilt className="w-4 h-4" weight="fill" />
        </button>
      </div>
    </div>
  );
}

// ───────────────────────── Telegram ─────────────────────────
function TelegramPanel({ cfg, onChanged }) {
  const tg = cfg?.telegram || {};
  const [token, setToken] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  const connect = async () => {
    setErr("");
    if (!token.trim() || !token.includes(":")) { setErr("Paste a valid @BotFather token (123456:ABC…)."); return; }
    setBusy(true);
    try { await clawAPI.telegram.setup({ telegram_token: token.trim() }); onChanged(); }
    catch (e) { setErr(e?.response?.data?.error || "Connect failed."); }
    finally { setBusy(false); }
  };
  const disconnect = async () => {
    if (!window.confirm("Disconnect Telegram? The bot will stop responding.")) return;
    setBusy(true); try { await clawAPI.telegram.remove(); onChanged(); } finally { setBusy(false); }
  };

  if (tg.configured) {
    return (
      <div className="pt-3 space-y-3">
        <Row label="Bot" value={`@${tg.bot_username}`} />
        <div className="flex gap-2">
          <a href={tg.bot_link} target="_blank" rel="noreferrer"
             className="flex items-center gap-1.5 px-3 py-2 rounded-md text-sm font-medium bg-[var(--k-brand)] text-white hover:opacity-90">
            <ArrowSquareOut className="w-4 h-4" /> Open in Telegram
          </a>
          <button onClick={disconnect} disabled={busy}
                  className="flex items-center gap-1.5 px-3 py-2 rounded-md text-sm text-rose-400 hover:bg-rose-500/10 ml-auto">
            <Trash className="w-4 h-4" /> Disconnect
          </button>
        </div>
      </div>
    );
  }
  return (
    <div className="pt-3 space-y-3">
      <Steps items={[
        <>Open <A href="https://t.me/BotFather">@BotFather</A> → send <Code>/newbot</Code></>,
        <>Copy the token and paste below</>,
      ]} />
      <input value={token} onChange={(e) => setToken(e.target.value)} placeholder="123456789:ABCdef_token"
             className="w-full px-3 py-2.5 rounded-lg bg-[var(--k-bg)] border border-[var(--k-border)] text-sm text-foreground outline-none focus:border-[var(--k-brand)]" />
      {err && <ErrBox msg={err} />}
      <button onClick={connect} disabled={busy}
              className="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg text-sm font-semibold bg-[var(--k-brand)] text-white hover:opacity-90 disabled:opacity-60">
        {busy ? <CircleNotch className="w-4 h-4 animate-spin" /> : <Plus className="w-4 h-4" />} Connect Telegram
      </button>
    </div>
  );
}

// ───────────────────────── WhatsApp ─────────────────────────
function WhatsAppPanel({ cfg, onChanged }) {
  const wa = cfg?.whatsapp || {};
  const [phoneId, setPhoneId] = useState("");
  const [token, setToken] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  const connect = async () => {
    setErr("");
    if (!phoneId.trim() || !token.trim()) { setErr("Phone Number ID and access token are required."); return; }
    setBusy(true);
    try { await clawAPI.whatsapp.setup({ phone_number_id: phoneId.trim(), access_token: token.trim() }); onChanged(); }
    catch (e) { setErr(e?.response?.data?.error || "Connect failed."); }
    finally { setBusy(false); }
  };
  const disconnect = async () => {
    if (!window.confirm("Disconnect WhatsApp?")) return;
    setBusy(true); try { await clawAPI.whatsapp.remove(); onChanged(); } finally { setBusy(false); }
  };

  if (wa.configured) {
    return (
      <div className="pt-3 space-y-3">
        <Row label="Phone Number ID" value={wa.phone_number_id} />
        <p className="text-[11px] text-muted-foreground">
          In your Meta app → WhatsApp → Configuration, set this Callback URL + Verify Token, then subscribe to <b>messages</b>:
        </p>
        <CopyRow label="Callback URL" value={wa.webhook_url} />
        <CopyRow label="Verify Token" value={wa.verify_token} />
        <button onClick={disconnect} disabled={busy}
                className="flex items-center gap-1.5 px-3 py-2 rounded-md text-sm text-rose-400 hover:bg-rose-500/10">
          <Trash className="w-4 h-4" /> Disconnect
        </button>
      </div>
    );
  }
  return (
    <div className="pt-3 space-y-3">
      <Steps items={[
        <>Create a Meta app → add <b>WhatsApp</b> (Cloud API)</>,
        <>Copy the <b>Phone number ID</b> &amp; a <b>permanent access token</b></>,
        <>Paste below — we'll give you the webhook URL to finish in Meta</>,
      ]} />
      <input value={phoneId} onChange={(e) => setPhoneId(e.target.value)} placeholder="Phone number ID"
             className="w-full px-3 py-2.5 rounded-lg bg-[var(--k-bg)] border border-[var(--k-border)] text-sm text-foreground outline-none focus:border-[var(--k-brand)]" />
      <input value={token} onChange={(e) => setToken(e.target.value)} placeholder="Permanent access token"
             className="w-full px-3 py-2.5 rounded-lg bg-[var(--k-bg)] border border-[var(--k-border)] text-sm text-foreground outline-none focus:border-[var(--k-brand)]" />
      {err && <ErrBox msg={err} />}
      <button onClick={connect} disabled={busy}
              className="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg text-sm font-semibold bg-[var(--k-brand)] text-white hover:opacity-90 disabled:opacity-60">
        {busy ? <CircleNotch className="w-4 h-4 animate-spin" /> : <Plus className="w-4 h-4" />} Connect WhatsApp
      </button>
    </div>
  );
}

// ───────────────────────── Brain settings (shared) ─────────────────────────
function BrainCard({ cfg, onSaved }) {
  const [name, setName] = useState(cfg.name || "");
  const [model, setModel] = useState(cfg.model || "kautilya-daily");
  const [prompt, setPrompt] = useState(cfg.system_prompt || "");
  const [enabled, setEnabled] = useState(cfg.enabled !== false);
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState(false);

  const save = async (patch) => {
    setBusy(true); setSaved(false);
    try {
      await clawAPI.update({ name, model, system_prompt: prompt, enabled, ...patch });
      if (patch && "enabled" in patch) setEnabled(patch.enabled);
      setSaved(true); onSaved();
    } finally { setBusy(false); }
  };

  return (
    <div className="rounded-2xl border border-[var(--k-border)] bg-[var(--k-surface)] p-5 space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-foreground">Agent settings</h2>
        <button onClick={() => save({ enabled: !enabled })} disabled={busy}
                className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-semibold ${enabled ? "bg-emerald-500/15 text-emerald-500" : "bg-zinc-500/15 text-zinc-400"}`}>
          <Power className="w-3.5 h-3.5" /> {enabled ? "Live" : "Paused"}
        </button>
      </div>
      <Field label="Name">
        <input value={name} onChange={(e) => setName(e.target.value)} placeholder="My Assistant"
               className="w-full px-3 py-2.5 rounded-lg bg-[var(--k-bg)] border border-[var(--k-border)] text-sm text-foreground outline-none focus:border-[var(--k-brand)]" />
      </Field>
      <Field label="Model"><ModelPicker model={model} setModel={setModel} /></Field>
      <Field label="Personality / instructions">
        <textarea value={prompt} onChange={(e) => setPrompt(e.target.value)} rows={3}
                  placeholder="e.g. You are my witty productivity assistant. Keep replies short."
                  className="w-full px-3 py-2.5 rounded-lg bg-[var(--k-bg)] border border-[var(--k-border)] text-sm text-foreground outline-none focus:border-[var(--k-brand)] resize-y" />
      </Field>
      <div className="flex items-center gap-3">
        <button onClick={() => save()} disabled={busy}
                className="flex items-center gap-2 px-4 py-2.5 rounded-lg text-sm font-semibold bg-[var(--k-brand)] text-white hover:opacity-90 disabled:opacity-60">
          {busy ? <CircleNotch className="w-4 h-4 animate-spin" /> : <FloppyDisk className="w-4 h-4" />} Save
        </button>
        {saved && <span className="flex items-center gap-1 text-xs text-emerald-500"><CheckCircle className="w-4 h-4" weight="fill" /> Saved</span>}
      </div>
    </div>
  );
}

// ───────────────────────── bits ─────────────────────────
function ModelPicker({ model, setModel }) {
  return (
    <div className="grid grid-cols-3 gap-2">
      {MODELS.map((m) => (
        <button key={m.id} onClick={() => setModel(m.id)}
                className={`flex flex-col items-start gap-1 p-3 rounded-lg border text-left ${model === m.id ? "border-[var(--k-brand)] bg-[var(--k-brand)]/10" : "border-[var(--k-border)] hover:bg-accent"}`}>
          <m.icon className={`w-4 h-4 ${model === m.id ? "text-[var(--k-brand)]" : "text-muted-foreground"}`} weight="duotone" />
          <span className="text-xs font-semibold text-foreground">{m.label}</span>
          <span className="text-[10px] text-muted-foreground leading-tight">{m.desc}</span>
        </button>
      ))}
    </div>
  );
}
function Field({ label, children }) {
  return <div><label className="block text-xs font-medium text-muted-foreground mb-1.5">{label}</label>{children}</div>;
}
function Row({ label, value }) {
  return <div className="flex items-center justify-between text-sm"><span className="text-muted-foreground">{label}</span><span className="font-medium text-foreground">{value}</span></div>;
}
function CopyRow({ label, value }) {
  const [done, setDone] = useState(false);
  const copy = () => { navigator.clipboard?.writeText(value || ""); setDone(true); setTimeout(() => setDone(false), 1500); };
  return (
    <div>
      <div className="text-[11px] text-muted-foreground mb-1">{label}</div>
      <div className="flex items-center gap-2">
        <code className="flex-1 px-2.5 py-2 rounded-lg bg-[var(--k-bg)] border border-[var(--k-border)] text-[11px] text-foreground break-all">{value}</code>
        <button onClick={copy} className="p-2 rounded-md border border-[var(--k-border)] hover:bg-accent shrink-0">
          {done ? <CheckCircle className="w-4 h-4 text-emerald-500" weight="fill" /> : <Copy className="w-4 h-4 text-muted-foreground" />}
        </button>
      </div>
    </div>
  );
}
function Steps({ items }) {
  return (
    <div className="rounded-lg border border-[var(--k-border)] bg-[var(--k-bg)]/40 p-3">
      <div className="flex items-center gap-2 text-xs font-semibold text-foreground mb-2"><Info className="w-4 h-4 text-[var(--k-brand)]" /> Quick setup</div>
      <ol className="text-xs text-muted-foreground space-y-1 list-decimal list-inside">{items.map((it, i) => <li key={i}>{it}</li>)}</ol>
    </div>
  );
}
function A({ href, children }) { return <a className="text-[var(--k-brand)]" href={href} target="_blank" rel="noreferrer">{children}</a>; }
function Code({ children }) { return <code className="px-1 rounded bg-accent">{children}</code>; }
function ErrBox({ msg }) {
  return <div className="flex items-start gap-2 px-3 py-2.5 rounded-lg bg-rose-500/10 border border-rose-500/20 text-rose-400 text-xs"><WarningCircle className="w-4 h-4 shrink-0 mt-0.5" /><span>{msg}</span></div>;
}
