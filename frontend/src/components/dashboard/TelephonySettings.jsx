import { useState, useEffect } from "react";
import { Phone, CheckCircle, Copy, Warning, PhoneIncoming, PhoneOutgoing } from "@phosphor-icons/react";
import { telephonyAPI, agentsAPI } from "../../lib/api";

/**
 * Telephony (Vobiz) setup — Dashboard → Settings → Telephony.
 *
 * OUTBOUND + Campaigns: save the Vobiz Auth ID / Token / Virtual Number here;
 * the dialer and Campaign Dialer read this config automatically.
 *
 * INBOUND: pick the agent that should answer calls, copy the generated
 * Answer URL, and paste it in the Vobiz portal against your virtual number
 * (Answer URL, method POST). Incoming calls then bridge into LiveKit and the
 * agent picks up.
 */
export default function TelephonySettings() {
  const [vobiz, setVobiz] = useState({ auth_id: "", auth_token: "", number: "", enabled: true });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saveStatus, setSaveStatus] = useState(null); // 'success' | 'error' | null

  const [agents, setAgents] = useState([]);
  const [inboundAgent, setInboundAgent] = useState("");
  const [inboundUrls, setInboundUrls] = useState(null);
  const [urlLoading, setUrlLoading] = useState(false);
  const [copied, setCopied] = useState("");

  useEffect(() => {
    (async () => {
      try {
        const cfg = await telephonyAPI.getConfig();
        const v = cfg?.vobiz || {};
        setVobiz({
          auth_id: v.auth_id || v.username || v.trunk_id || "",
          auth_token: v.auth_token || v.password || "",
          number: v.number || v.caller_id || "",
          enabled: v.enabled !== false,
        });
      } catch (e) { console.error("telephony config load failed", e); }
      try {
        const data = await agentsAPI.list();
        const list = data?.agents || (Array.isArray(data) ? data : []);
        setAgents(list);
        if (list.length && !inboundAgent) setInboundAgent(list[0].agent_id || list[0].id || "");
      } catch (e) { console.error("agents load failed", e); }
      setLoading(false);
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!inboundAgent) { setInboundUrls(null); return; }
    (async () => {
      try {
        setUrlLoading(true);
        const res = await telephonyAPI.inboundUrl(inboundAgent);
        setInboundUrls(res);
      } catch (e) {
        console.error("inbound url load failed", e);
        setInboundUrls(null);
      } finally {
        setUrlLoading(false);
      }
    })();
  }, [inboundAgent]);

  const handleSave = async () => {
    try {
      setSaving(true);
      setSaveStatus(null);
      await telephonyAPI.saveConfig({
        vobiz: {
          ...vobiz,
          // Write BOTH key shapes so the dialer + legacy readers all resolve
          caller_id: vobiz.number,
          username: vobiz.auth_id,
          password: vobiz.auth_token,
          enabled: true,
          status: "available",
        },
      });
      setSaveStatus("success");
      setTimeout(() => setSaveStatus(null), 2500);
    } catch (e) {
      console.error("telephony save failed", e);
      setSaveStatus("error");
    } finally {
      setSaving(false);
    }
  };

  const copyText = async (text, key) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(key);
      setTimeout(() => setCopied(""), 1800);
    } catch (e) { console.error("copy failed", e); }
  };

  const inputCls = "w-full px-4 py-3 text-sm bg-accent/20 border border-[var(--k-border)] rounded-xl text-foreground focus:ring-1 focus:ring-[var(--k-brand)] focus:outline-none";
  const labelCls = "text-[10px] font-bold uppercase tracking-widest text-muted-foreground";

  if (loading) {
    return <div className="py-10 text-sm text-muted-foreground animate-pulse">Loading telephony configuration…</div>;
  }

  return (
    <div className="space-y-8">
      {/* ===== Vobiz credentials (outbound + campaigns) ===== */}
      <div className="p-6 rounded-2xl border border-[var(--k-border)] bg-accent/10 space-y-5">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-[var(--k-brand)]/10 flex items-center justify-center">
            <PhoneOutgoing className="w-4.5 h-4.5 text-[var(--k-brand)]" />
          </div>
          <div>
            <h3 className="text-sm font-bold text-foreground">Vobiz Provider (Outbound &amp; Campaigns)</h3>
            <p className="text-xs text-muted-foreground">Outbound calls, campaign dialing and lead callbacks all use these credentials.</p>
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div className="space-y-1.5">
            <label className={labelCls}>Auth ID</label>
            <input
              data-testid="vobiz-auth-id"
              type="text"
              placeholder="e.g. MA1234567890"
              value={vobiz.auth_id}
              onChange={(e) => setVobiz({ ...vobiz, auth_id: e.target.value.trim() })}
              className={inputCls}
            />
          </div>
          <div className="space-y-1.5">
            <label className={labelCls}>Auth Token</label>
            <input
              data-testid="vobiz-auth-token"
              type="password"
              placeholder="Vobiz auth token"
              value={vobiz.auth_token}
              onChange={(e) => setVobiz({ ...vobiz, auth_token: e.target.value.trim() })}
              className={inputCls}
            />
          </div>
          <div className="space-y-1.5">
            <label className={labelCls}>Virtual Number</label>
            <input
              data-testid="vobiz-number"
              type="text"
              placeholder="e.g. +91802269XXXX"
              value={vobiz.number}
              onChange={(e) => setVobiz({ ...vobiz, number: e.target.value.trim() })}
              className={inputCls}
            />
          </div>
        </div>

        <div className="flex items-center justify-between">
          <p className="text-[11px] text-muted-foreground flex items-center gap-1.5">
            <Warning className="w-3.5 h-3.5" />
            Credentials are stored per-account and used server-side only.
          </p>
          <button
            data-testid="save-telephony"
            onClick={handleSave}
            disabled={saving || !vobiz.auth_id || !vobiz.auth_token || !vobiz.number}
            className="flex items-center gap-2 px-6 py-2 rounded-lg bg-[var(--k-brand)] text-white text-sm font-bold hover:bg-[var(--k-brand-hover)] transition-all shadow-lg shadow-[var(--k-brand)]/20 disabled:opacity-50"
          >
            {saving ? "Saving…" : saveStatus === "success" ? "Saved" : "Save Provider"}
            {!saving && saveStatus === "success" && <CheckCircle className="w-4 h-4" weight="fill" />}
          </button>
        </div>
        {saveStatus === "error" && (
          <p className="text-xs text-red-500">Save failed — please retry.</p>
        )}
      </div>

      {/* ===== Inbound setup ===== */}
      <div className="p-6 rounded-2xl border border-[var(--k-border)] bg-accent/10 space-y-5">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-[var(--k-brand)]/10 flex items-center justify-center">
            <PhoneIncoming className="w-4.5 h-4.5 text-[var(--k-brand)]" />
          </div>
          <div>
            <h3 className="text-sm font-bold text-foreground">Inbound Calls</h3>
            <p className="text-xs text-muted-foreground">Choose which agent answers incoming calls, then paste the Answer URL in your Vobiz portal.</p>
          </div>
        </div>

        <div className="space-y-1.5 max-w-md">
          <label className={labelCls}>Agent that answers inbound calls</label>
          <select
            data-testid="inbound-agent"
            value={inboundAgent}
            onChange={(e) => setInboundAgent(e.target.value)}
            className={inputCls}
          >
            {agents.length === 0 && <option value="">No agents yet — create one first</option>}
            {agents.map((a) => (
              <option key={a.agent_id || a.id} value={a.agent_id || a.id}>{a.name || a.agent_id}</option>
            ))}
          </select>
        </div>

        {urlLoading && <p className="text-xs text-muted-foreground animate-pulse">Generating URLs…</p>}

        {inboundUrls && (
          <div className="space-y-3">
            <div className="space-y-1.5">
              <label className={labelCls}>Answer URL (method: POST)</label>
              <div className="flex gap-2">
                <input readOnly value={inboundUrls.answer_url} className={`${inputCls} font-mono text-xs`} />
                <button
                  onClick={() => copyText(inboundUrls.answer_url, "answer")}
                  className="shrink-0 px-4 rounded-xl border border-[var(--k-border)] text-xs font-bold text-foreground hover:bg-accent/30 flex items-center gap-1.5"
                >
                  {copied === "answer" ? <CheckCircle className="w-4 h-4 text-green-500" weight="fill" /> : <Copy className="w-4 h-4" />}
                  {copied === "answer" ? "Copied" : "Copy"}
                </button>
              </div>
            </div>
            <div className="space-y-1.5">
              <label className={labelCls}>Events / Hangup URL (optional, method: POST)</label>
              <div className="flex gap-2">
                <input readOnly value={inboundUrls.events_url} className={`${inputCls} font-mono text-xs`} />
                <button
                  onClick={() => copyText(inboundUrls.events_url, "events")}
                  className="shrink-0 px-4 rounded-xl border border-[var(--k-border)] text-xs font-bold text-foreground hover:bg-accent/30 flex items-center gap-1.5"
                >
                  {copied === "events" ? <CheckCircle className="w-4 h-4 text-green-500" weight="fill" /> : <Copy className="w-4 h-4" />}
                  {copied === "events" ? "Copied" : "Copy"}
                </button>
              </div>
            </div>

            <div className="p-4 rounded-xl bg-accent/20 border border-[var(--k-border)] space-y-1.5">
              <p className="text-xs font-bold text-foreground flex items-center gap-1.5"><Phone className="w-3.5 h-3.5" /> How to enable inbound (one-time)</p>
              <ol className="text-[11px] text-muted-foreground list-decimal pl-4 space-y-1">
                <li>Open the <span className="font-semibold">Vobiz portal</span> → Numbers → select your virtual number ({vobiz.number || "your number"}).</li>
                <li>Set <span className="font-semibold">Answer URL</span> to the URL above, method <span className="font-mono">POST</span>.</li>
                <li>Optionally set the <span className="font-semibold">Hangup/Event URL</span> for post-call analytics.</li>
                <li>Save. Call your number — the selected agent will pick up.</li>
              </ol>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
