import { useState, useEffect } from "react";
import { Crown, Lightning, Coin, CheckCircle, ArrowUp, Wallet, CreditCard } from "@phosphor-icons/react";
import { ScrollArea } from "@/components/ui/scroll-area";
import { billingAPI } from "../../lib/api";

const PRESET_CREDITS = [100, 250, 500, 1000];

export default function Billing({ user }) {
  const [config, setConfig] = useState(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [customAmount, setCustomAmount] = useState("");
  const [scriptLoaded, setScriptLoaded] = useState(false);
  const [recoverId, setRecoverId] = useState("");
  const [recoverMsg, setRecoverMsg] = useState(null);

  useEffect(() => {
    loadConfig();
    loadRazorpayScript();
  }, []);

  const loadRazorpayScript = () => {
    if (window.Razorpay) { setScriptLoaded(true); return; }
    const s = document.createElement("script");
    s.src = "https://checkout.razorpay.com/v1/checkout.js";
    s.async = true;
    s.onload = () => setScriptLoaded(true);
    document.body.appendChild(s);
  };

  const loadConfig = async () => {
    try {
      setLoading(true);
      const c = await billingAPI.getConfig();
      setConfig(c);
      // Cache tier so the chat upgrade card never shows to PRO users.
      try { localStorage.setItem('k_is_pro', (c?.is_pro || c?.tier === 'pro') ? '1' : '0'); } catch {}
    } catch (e) {
      console.error("Failed to load billing config", e);
    } finally {
      setLoading(false);
    }
  };

  const openCheckout = ({ order, amount, planType, description }) => {
    if (!scriptLoaded || !window.Razorpay) {
      alert("Payment SDK still loading — please try again in a moment.");
      return;
    }
    const opts = {
      key: config.razorpay_key_id,
      amount: order.amount,
      currency: order.currency || "INR",
      name: "Kautilya AI",
      description,
      prefill: { name: user?.displayName || "", email: user?.email || "" },
      theme: { color: "#FF6D3F" },
      handler: async (resp) => {
        try {
          await billingAPI.verifyPayment({
            razorpay_order_id: order.id,
            razorpay_payment_id: resp.razorpay_payment_id,
            razorpay_signature: resp.razorpay_signature,
            plan_type: planType,
            amount,
          });
          await loadConfig();
          alert(planType === "pro" ? "🎉 Welcome to Kautilya Pro!" : `✅ ₹${amount} added to your balance.`);
        } catch (e) {
          alert("Payment verification failed. If you were charged, contact support.");
        }
      },
    };
    if (planType === "pro") {
      opts.subscription_id = order.id;
      delete opts.amount;
      delete opts.currency;
    }
    const rzp = new window.Razorpay(opts);
    rzp.open();
  };

  const handleUpgradePro = async () => {
    if (!config) return;
    try {
      setBusy(true);
      const order = await billingAPI.createOrder(599, "pro_subscription");
      openCheckout({ order, amount: 599, planType: "pro", description: "Kautilya Pro — Monthly" });
    } catch (e) {
      alert("Failed to start upgrade. Please try again.");
    } finally {
      setBusy(false);
    }
  };

  const handleRecover = async () => {
    const pid = recoverId.trim();
    if (!pid.startsWith("pay_")) {
      setRecoverMsg({ ok: false, text: "Payment ID should start with 'pay_' (e.g. pay_NXabc123)." });
      return;
    }
    try {
      setBusy(true);
      setRecoverMsg(null);
      const res = await billingAPI.reconcilePayment(pid);
      if (res.already_processed) {
        setRecoverMsg({ ok: true, text: "This payment was already credited." });
      } else {
        setRecoverMsg({
          ok: true,
          text: `✅ Credited ₹${Number(res.credited).toFixed(2)}. New balance: ₹${Number(res.new_balance).toFixed(2)}.`,
        });
      }
      await loadConfig();
      setRecoverId("");
    } catch (e) {
      const detail = e?.response?.data?.error || e?.message || "Unknown error";
      setRecoverMsg({ ok: false, text: `Failed: ${detail}` });
    } finally {
      setBusy(false);
    }
  };

  const handleAddCredits = async (rawAmount) => {
    const amount = Number(rawAmount);
    if (!amount || amount < 10) {
      alert("Minimum top-up is ₹10.");
      return;
    }
    try {
      setBusy(true);
      const order = await billingAPI.createOrder(amount, "pay_as_you_go");
      openCheckout({ order, amount, planType: "pay_as_you_go", description: `Pay-As-You-Go — ₹${amount}` });
    } catch (e) {
      alert("Failed to create payment. Please try again.");
    } finally {
      setBusy(false);
    }
  };

  const isPro = !!(config?.is_pro || config?.tier === "pro");
  const credits = Number(config?.credits || 0);
  const usage = config?.usage || { chat_count: 0, daily_limit: 30 };
  const pricePerMsg = Number(config?.payg_price_per_message || 0.5);
  const usedPct = usage.daily_limit > 0
    ? Math.min(100, Math.round((usage.chat_count / usage.daily_limit) * 100))
    : 0;
  const remainingPaygMessages = Math.floor(credits / pricePerMsg);

  return (
    <div className="h-full flex flex-col bg-background" data-testid="billing-page">
      <div className="px-6 md:px-8 py-6 border-b border-[var(--k-border)]">
        <h1 className="text-2xl font-medium k-heading tracking-tight text-foreground">Billing</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Manage your plan, top-up Pay-As-You-Go credits, and track daily usage.
        </p>
      </div>

      <ScrollArea className="flex-1">
        <div className="px-6 md:px-8 py-8 max-w-5xl mx-auto space-y-8">
          {loading && (
            <div className="text-sm text-muted-foreground">Loading billing details…</div>
          )}

          {!loading && (
            <>
              {/* Snapshot cards */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <SnapshotCard
                  label="Current Plan"
                  value={isPro ? "Kautilya Pro" : "Free Tier"}
                  hint={isPro ? "Unlimited daily messages" : `${usage.daily_limit ?? 30} messages/day`}
                  icon={isPro ? Crown : Lightning}
                  accent={isPro ? "text-amber-400" : "text-[var(--k-brand)]"}
                />
                <SnapshotCard
                  label="Today's Usage"
                  value={isPro ? `${usage.chat_count} messages` : `${usage.chat_count} / ${usage.daily_limit}`}
                  hint={isPro ? "No daily cap" : `${usedPct}% of daily quota`}
                  icon={CheckCircle}
                  accent="text-emerald-400"
                  progress={isPro ? null : usedPct}
                />
                <SnapshotCard
                  label="PAYG Balance"
                  value={`₹${credits.toFixed(2)}`}
                  hint={
                    credits > 0
                      ? `~${remainingPaygMessages} extra messages available`
                      : "Top-up to keep chatting after daily limit"
                  }
                  icon={Wallet}
                  accent="text-sky-400"
                />
              </div>


              {/* Pro plan */}
              <section className="rounded-2xl border border-[var(--k-border)] bg-[var(--k-surface)] overflow-hidden">
                <div className="p-6 md:p-8 flex flex-col md:flex-row gap-6 md:items-center md:justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 text-amber-400 mb-2">
                      <Crown weight="fill" className="w-5 h-5" />
                      <span className="text-xs font-semibold uppercase tracking-widest">Kautilya Pro</span>
                    </div>
                    <div className="flex items-baseline gap-2">
                      <span className="text-4xl font-bold k-heading text-foreground">₹599</span>
                      <span className="text-sm text-muted-foreground">/ month</span>
                    </div>
                    <ul className="mt-4 space-y-2 text-sm text-muted-foreground">
                      <Feature>Unlimited in-app daily messages</Feature>
                      <Feature>10,000 Developer API calls/day (100× the free quota)</Feature>
                      <Feature>Access to all models incl. Kautilya Pro & Coder</Feature>
                      <Feature>Higher per-minute rate limits (20/min)</Feature>
                      <Feature>PAYG credits cover anything beyond your daily cap</Feature>
                    </ul>
                  </div>
                  <div className="md:w-64 flex md:flex-col gap-3">
                    {isPro ? (
                      <div className="w-full px-4 py-3 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-sm font-medium text-center">
                        ✓ Active
                      </div>
                    ) : (
                      <button
                        onClick={handleUpgradePro}
                        disabled={busy || !scriptLoaded}
                        className="w-full px-4 py-3 rounded-lg bg-[var(--k-brand)] text-white text-sm font-semibold hover:bg-[var(--k-brand-hover)] transition-colors disabled:opacity-50 flex items-center justify-center gap-2"
                      >
                        <ArrowUp className="w-4 h-4" />
                        {busy ? "Processing…" : "Upgrade to Pro"}
                      </button>
                    )}
                  </div>
                </div>
              </section>

              {/* PAYG */}
              <section className="rounded-2xl border border-[var(--k-border)] bg-[var(--k-surface)] p-6 md:p-8">
                <div className="flex items-center gap-2 text-sky-400 mb-1">
                  <Coin weight="fill" className="w-5 h-5" />
                  <span className="text-xs font-semibold uppercase tracking-widest">Pay-As-You-Go</span>
                </div>
                <h3 className="text-xl font-semibold k-heading text-foreground">Top-up credits</h3>
                <p className="text-sm text-muted-foreground mt-1">
                  Hit your free daily limit? Credits kick in automatically — only ₹{pricePerMsg.toFixed(2)} per message,
                  no expiry, no subscription.
                </p>

                <div className="mt-6 grid grid-cols-2 md:grid-cols-4 gap-3">
                  {PRESET_CREDITS.map((amt) => (
                    <button
                      key={amt}
                      onClick={() => handleAddCredits(amt)}
                      disabled={busy || !scriptLoaded}
                      className="px-4 py-4 rounded-xl border border-[var(--k-border)] hover:border-[var(--k-brand)] hover:bg-[var(--k-brand)]/5 transition-all text-left disabled:opacity-50"
                    >
                      <div className="text-lg font-bold text-foreground">₹{amt}</div>
                      <div className="text-[11px] text-muted-foreground mt-0.5">
                        ~{Math.floor(amt / pricePerMsg)} messages
                      </div>
                    </button>
                  ))}
                </div>

                <div className="mt-6 flex flex-col md:flex-row gap-3 md:items-end">
                  <div className="flex-1">
                    <label className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
                      Custom amount (INR)
                    </label>
                    <div className="mt-1.5 flex items-center gap-2 px-3 py-2 rounded-lg border border-[var(--k-border)] bg-background focus-within:border-[var(--k-brand)]">
                      <span className="text-muted-foreground text-sm">₹</span>
                      <input
                        type="number"
                        min="10"
                        step="10"
                        placeholder="e.g. 150"
                        value={customAmount}
                        onChange={(e) => setCustomAmount(e.target.value)}
                        className="flex-1 bg-transparent outline-none text-sm text-foreground"
                      />
                    </div>
                  </div>
                  <button
                    onClick={() => handleAddCredits(customAmount)}
                    disabled={busy || !scriptLoaded || !customAmount}
                    className="px-5 py-2.5 rounded-lg bg-[var(--k-brand)] text-white text-sm font-semibold hover:bg-[var(--k-brand-hover)] transition-colors disabled:opacity-50 flex items-center justify-center gap-2"
                  >
                    <CreditCard className="w-4 h-4" />
                    Add Credits
                  </button>
                </div>
              </section>

              {/* Recover missing payment */}
              <section className="rounded-2xl border border-amber-500/20 bg-amber-500/5 p-6 md:p-8">
                <div className="flex items-center gap-2 text-amber-400 mb-1">
                  <Wallet weight="fill" className="w-5 h-5" />
                  <span className="text-xs font-semibold uppercase tracking-widest">Payment didn't reflect?</span>
                </div>
                <p className="text-sm text-muted-foreground mt-1">
                  If Razorpay charged you but credits/Pro didn't show up, paste your <strong>Payment ID</strong>
                  {" "}(from the Razorpay confirmation email or SMS — starts with <span className="k-mono">pay_</span>)
                  below and we'll reconcile it instantly.
                </p>
                <div className="mt-4 flex flex-col md:flex-row gap-3">
                  <input
                    type="text"
                    placeholder="pay_NXabc123..."
                    value={recoverId}
                    onChange={(e) => setRecoverId(e.target.value)}
                    className="flex-1 px-3 py-2.5 rounded-lg border border-[var(--k-border)] bg-background text-sm text-foreground outline-none focus:border-amber-400 k-mono"
                  />
                  <button
                    onClick={handleRecover}
                    disabled={busy || !recoverId.trim()}
                    className="px-5 py-2.5 rounded-lg bg-amber-500 text-white text-sm font-semibold hover:bg-amber-600 transition-colors disabled:opacity-50"
                  >
                    Recover Payment
                  </button>
                </div>
                {recoverMsg && (
                  <div className={`mt-3 text-sm ${recoverMsg.ok ? "text-emerald-400" : "text-rose-400"}`}>
                    {recoverMsg.text}
                  </div>
                )}
              </section>

              {/* FAQ */}
              <section className="rounded-2xl border border-[var(--k-border)] bg-[var(--k-surface)] p-6 md:p-8 space-y-4">
                <h3 className="text-sm font-semibold uppercase tracking-widest text-muted-foreground">How it works</h3>
                <Faq q="When are PAYG credits used?">
                  Credits kick in <strong>only after</strong> you cross your daily message quota. Each in-app message costs ₹{pricePerMsg.toFixed(2)}. While you're under the daily cap, usage is free.
                </Faq>
                <Faq q="Do credits expire?">No. Your top-up balance carries forward until used.</Faq>
                <Faq q="Can I cancel Pro anytime?">
                  Yes — cancel from Razorpay's subscription email or contact support. Access continues until the end of the billing cycle.
                </Faq>
              </section>
            </>
          )}
        </div>
      </ScrollArea>
    </div>
  );
}

function SnapshotCard({ label, value, hint, icon: Icon, accent, progress }) {
  return (
    <div className="rounded-2xl border border-[var(--k-border)] bg-[var(--k-surface)] p-5">
      <div className="flex items-center justify-between">
        <span className="text-[11px] font-semibold uppercase tracking-widest text-muted-foreground">{label}</span>
        <Icon className={`w-5 h-5 ${accent}`} weight="duotone" />
      </div>
      <div className="mt-3 text-2xl font-semibold k-heading text-foreground">{value}</div>
      <div className="mt-1 text-xs text-muted-foreground">{hint}</div>
      {progress != null && (
        <div className="mt-3 h-1.5 rounded-full bg-[var(--k-border)] overflow-hidden">
          <div
            className="h-full bg-[var(--k-brand)] transition-all"
            style={{ width: `${progress}%` }}
          />
        </div>
      )}
    </div>
  );
}

function Feature({ children }) {
  return (
    <li className="flex items-start gap-2">
      <CheckCircle weight="fill" className="w-4 h-4 text-emerald-400 mt-0.5 flex-shrink-0" />
      <span>{children}</span>
    </li>
  );
}

function Faq({ q, children }) {
  return (
    <div>
      <div className="text-sm font-medium text-foreground">{q}</div>
      <div className="text-xs text-muted-foreground mt-1 leading-relaxed">{children}</div>
    </div>
  );
}
