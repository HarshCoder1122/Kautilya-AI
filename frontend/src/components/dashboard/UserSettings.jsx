import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { User, Key, Bell, Shield, Palette, CaretRight, CheckCircle, Warning, GoogleLogo, Crown, Database, Trash, Eye, EnvelopeSimple } from "@phosphor-icons/react";
import { ScrollArea } from "@/components/ui/scroll-area";
import { billingAPI, userAPI, getAuthHeaders } from "../../lib/api";
import ApiKeySettings from "./ApiKeySettings";

export default function UserSettings({ user }) {
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState('profile');
  const [billingConfig, setBillingConfig] = useState(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [profileSettings, setProfileSettings] = useState({
    preferred_name: "",
    display_name: "",
    work_function: "",
    personal_preferences: "",
  });
  const [saveStatus, setSaveStatus] = useState(null); // 'success' | 'error' | null
  const [myData, setMyData] = useState(null);
  const [myDataLoading, setMyDataLoading] = useState(false);
  const [deletionState, setDeletionState] = useState(null); // null | 'confirm' | 'submitting' | 'done'
  const [deletionReason, setDeletionReason] = useState('');
  const [unsubStatus, setUnsubStatus] = useState(null); // null | 'saving' | 'done' | 'error'

  useEffect(() => {
    loadBillingStatus();
    loadProfileSettings();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const loadBillingStatus = async () => {
    try {
      const config = await billingAPI.getConfig();
      setBillingConfig(config);
    } catch (error) {
      console.error("Failed to load billing status:", error);
    }
  };

  const loadProfileSettings = async () => {
    setLoading(true);
    try {
      const data = await userAPI.getSettings();
      if (data && data.settings) {
        setProfileSettings({
          preferred_name: data.settings.preferred_name || "",
          display_name: data.settings.display_name || user?.displayName || "",
          work_function: data.settings.work_function || "",
          personal_preferences: data.settings.personal_preferences || "",
        });
      }
    } catch (error) {
      console.error("Failed to load user settings:", error);
    } finally {
      setLoading(false);
    }
  };

  const handleSaveSettings = async (e) => {
    if (e) e.preventDefault();
    setSaving(true);
    setSaveStatus(null);
    try {
      await userAPI.saveSettings({
        ...profileSettings,
        display_name: profileSettings.display_name || user?.displayName || "",
      });
      setSaveStatus('success');
      setTimeout(() => setSaveStatus(null), 3000);
    } catch (error) {
      console.error("Failed to save settings:", error);
      setSaveStatus('error');
    } finally {
      setSaving(false);
    }
  };

  const goToBilling = () => navigate('/dashboard/billing');

  const loadMyData = async () => {
    if (myData || myDataLoading) return;
    setMyDataLoading(true);
    try {
      const resp = await fetch('/api/user/my-data', { headers: { ...getAuthHeaders() } });
      const data = await resp.json();
      setMyData(data);
    } catch { setMyData(null); } finally { setMyDataLoading(false); }
  };

  const handleUnsubscribe = async () => {
    setUnsubStatus('saving');
    try {
      await fetch('/api/user/unsubscribe', { method: 'POST', headers: { ...getAuthHeaders() } });
      setUnsubStatus('done');
      setMyData(prev => prev ? { ...prev, consent: { ...prev.consent, marketing_opt_in: false } } : prev);
    } catch { setUnsubStatus('error'); }
  };

  const handleDeleteRequest = async () => {
    setDeletionState('submitting');
    try {
      await fetch('/api/user/data-deletion', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
        body: JSON.stringify({ reason: deletionReason }),
      });
      setDeletionState('done');
    } catch { setDeletionState('confirm'); }
  };

  useEffect(() => {
    if (activeTab === 'mydata') loadMyData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeTab]);

  const tabs = [
    { id: 'profile', label: 'Profile', icon: User },
    { id: 'apikeys', label: 'API Keys', icon: Key },
    { id: 'preferences', label: 'Preferences', icon: Palette },
    { id: 'security', label: 'Security', icon: Shield },
    { id: 'mydata', label: 'My Data', icon: Database },
  ];

  const isPro = billingConfig?.is_pro || billingConfig?.tier === 'pro';

  return (
    <div className="h-full flex flex-col bg-background" data-testid="user-settings">
      {/* Header */}
      <div className="px-4 py-4 sm:px-8 sm:py-6 border-b border-[var(--k-border)]">
        <h1 className="text-xl sm:text-2xl font-medium k-heading tracking-tight text-foreground">Settings</h1>
        <p className="text-xs sm:text-sm text-muted-foreground mt-1">Manage your account, preferences, and API integrations</p>
      </div>

      <div className="flex-1 flex flex-col md:flex-row overflow-hidden">
        {/* Settings Nav — top scrollable tabs on mobile, sidebar on md+ */}
        <div className="md:w-56 flex-shrink-0 border-b md:border-b-0 md:border-r border-[var(--k-border)] md:py-6 md:px-3">
          {/* Mobile: horizontal scrollable pills */}
          <div className="flex md:hidden overflow-x-auto gap-1 px-3 py-2 scrollbar-none">
            {tabs.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`flex-shrink-0 flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-semibold transition-all ${
                  activeTab === tab.id
                    ? 'bg-[var(--k-brand)] text-white'
                    : 'bg-accent text-muted-foreground'
                }`}
              >
                <tab.icon className="w-3.5 h-3.5" weight={activeTab === tab.id ? 'fill' : 'regular'} />
                {tab.label}
              </button>
            ))}
          </div>
          {/* Desktop: vertical list */}
          <div className="hidden md:block space-y-1">
            {tabs.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`w-full flex items-center justify-between px-3 py-2 rounded-md transition-all duration-200 ${
                  activeTab === tab.id
                    ? 'bg-[var(--k-brand)]/10 text-[var(--k-brand)] font-medium'
                    : 'text-muted-foreground hover:bg-accent hover:text-foreground'
                }`}
              >
                <div className="flex items-center gap-2.5">
                  <tab.icon className="w-4 h-4" weight={activeTab === tab.id ? 'fill' : 'regular'} />
                  <span className="text-sm">{tab.label}</span>
                </div>
                {activeTab === tab.id && <CaretRight className="w-3 h-3" />}
              </button>
            ))}
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-hidden min-w-0">
          <ScrollArea className="h-full px-4 py-4 sm:px-8 sm:py-8">
            <div className="max-w-2xl">
              {activeTab === 'profile' && (
                <div className="space-y-8 animate-fade-up">
                  <section>
                    <h3 className="text-sm font-semibold uppercase tracking-widest text-muted-foreground mb-4">Account Information</h3>
                    <div className="flex flex-col sm:flex-row items-start sm:items-center gap-4 sm:gap-6 p-4 sm:p-6 rounded-2xl bg-white/5 border border-white/5">
                      <div className="relative group flex-shrink-0">
                        {user?.photoURL ? (
                          <img src={user.photoURL} alt="" className="w-16 h-16 sm:w-20 sm:h-20 rounded-full object-cover border-2 border-[var(--k-brand)]/20" />
                        ) : (
                          <div className="w-16 h-16 sm:w-20 sm:h-20 rounded-full bg-accent flex items-center justify-center text-2xl font-bold text-muted-foreground">
                            {user?.displayName?.charAt(0) || 'U'}
                          </div>
                        )}
                      </div>
                      <div className="space-y-1 min-w-0">
                        <div className="text-lg font-semibold text-foreground flex items-center gap-2">
                          {profileSettings.preferred_name || user?.displayName || 'User'}
                          {isPro && <Crown className="w-5 h-5 text-amber-400" weight="fill" />}
                        </div>
                        <div className="text-sm text-muted-foreground flex items-center gap-2">
                          {user?.email}
                          <Badge className="bg-emerald-500/10 text-emerald-400 border-none text-[10px] uppercase">Verified</Badge>
                        </div>
                        <div className="pt-2 flex items-center gap-2 text-xs text-muted-foreground">
                          <GoogleLogo className="w-3.5 h-3.5" />
                          <span>Connected via Google Auth</span>
                        </div>
                      </div>
                    </div>
                  </section>

                  {/* AI Personalization Section */}
                  <section className="space-y-4">
                    <h3 className="text-sm font-semibold uppercase tracking-widest text-muted-foreground">AI Personalization</h3>
                    <div className="p-6 rounded-2xl bg-white/5 border border-white/5 space-y-4">
                      <form onSubmit={handleSaveSettings} className="space-y-4">
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                          <div className="space-y-1.5">
                            <label className="text-xs font-semibold text-muted-foreground" htmlFor="preferred-name">
                              Preferred Name
                            </label>
                            <input
                              id="preferred-name"
                              type="text"
                              value={profileSettings.preferred_name}
                              onChange={(e) => setProfileSettings({ ...profileSettings, preferred_name: e.target.value })}
                              placeholder="How AI should address you, e.g., Harsh"
                              className="w-full px-3 py-2 rounded-lg border border-[var(--k-border)] bg-[var(--k-surface)] text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-[var(--k-brand)] focus:border-[var(--k-brand)] transition-colors"
                            />
                          </div>
                          <div className="space-y-1.5">
                            <label className="text-xs font-semibold text-muted-foreground" htmlFor="work-function">
                              Role / Profession
                            </label>
                            <input
                              id="work-function"
                              type="text"
                              value={profileSettings.work_function}
                              onChange={(e) => setProfileSettings({ ...profileSettings, work_function: e.target.value })}
                              placeholder="e.g., Founder, Software Engineer"
                              className="w-full px-3 py-2 rounded-lg border border-[var(--k-border)] bg-[var(--k-surface)] text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-[var(--k-brand)] focus:border-[var(--k-brand)] transition-colors"
                            />
                          </div>
                        </div>
                        
                        <div className="space-y-1.5">
                          <label className="text-xs font-semibold text-muted-foreground" htmlFor="personal-preferences">
                            Custom System Instructions / AI Persona Settings
                          </label>
                          <textarea
                            id="personal-preferences"
                            value={profileSettings.personal_preferences}
                            onChange={(e) => setProfileSettings({ ...profileSettings, personal_preferences: e.target.value })}
                            placeholder="Provide custom instructions on how Kautilya AI should behave, speak, or format its replies. (e.g., 'Be extremely concise', 'Do not use corporate jargon', 'Explain math/code step by step')"
                            rows={4}
                            className="w-full px-3 py-2 rounded-lg border border-[var(--k-border)] bg-[var(--k-surface)] text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-[var(--k-brand)] focus:border-[var(--k-brand)] transition-colors resize-none"
                          />
                        </div>

                        <div className="flex items-center justify-between pt-2 border-t border-[var(--k-border)]">
                          <div className="h-6">
                            {saveStatus === 'success' && (
                              <span className="text-xs text-emerald-400 flex items-center gap-1.5 animate-fade-in">
                                <CheckCircle className="w-4.5 h-4.5" weight="fill" /> Settings saved successfully!
                              </span>
                            )}
                            {saveStatus === 'error' && (
                              <span className="text-xs text-rose-400 flex items-center gap-1.5 animate-fade-in">
                                <Warning className="w-4.5 h-4.5" weight="fill" /> Failed to save settings
                              </span>
                            )}
                          </div>
                          <button
                            type="submit"
                            disabled={saving}
                            className="px-4 py-2 rounded-lg bg-[var(--k-brand)] text-white text-sm font-semibold hover:bg-[var(--k-brand-hover)] active:scale-[0.98] transition-all disabled:opacity-50 flex items-center gap-2"
                          >
                            {saving ? 'Saving...' : 'Save Personalization'}
                          </button>
                        </div>
                      </form>
                    </div>
                  </section>

                  <section className="space-y-4">
                    <h3 className="text-sm font-semibold uppercase tracking-widest text-muted-foreground">Subscription</h3>
                    <div className="p-4 rounded-xl border border-[var(--k-border)] bg-[var(--k-surface)] flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                      <div>
                        <div className="text-sm font-medium text-foreground">
                          {isPro ? 'Kautilya Pro Tier' : 'Daily Free Tier'}
                        </div>
                        <div className="text-xs text-muted-foreground">
                          {isPro 
                            ? 'Unlimited models, NVIDIA NIM access, and high-priority support.' 
                            : 'Access to base models and limited daily tokens.'}
                        </div>
                      </div>
                      <button
                        onClick={goToBilling}
                        className="px-4 py-1.5 rounded-md bg-[var(--k-brand)] text-white text-xs font-semibold hover:bg-[var(--k-brand-hover)] transition-colors"
                      >
                        {isPro ? 'Manage Plan' : 'Upgrade / Top-up'}
                      </button>
                    </div>
                  </section>
                </div>
              )}

              {activeTab === 'apikeys' && <ApiKeySettings />}

              {activeTab === 'preferences' && (
                <div className="space-y-6 animate-fade-up">
                   <h3 className="text-sm font-semibold uppercase tracking-widest text-muted-foreground">Interface Preferences</h3>
                   <div className="space-y-4">
                      <div className="flex items-center justify-between p-4 rounded-xl border border-[var(--k-border)]">
                        <div>
                          <div className="text-sm font-medium text-foreground">Experimental Features</div>
                          <div className="text-xs text-muted-foreground">Access upcoming tools before they are released</div>
                        </div>
                        <div className="w-10 h-5 bg-[var(--k-brand)]/20 rounded-full relative">
                          <div className="absolute right-1 top-1 w-3 h-3 bg-[var(--k-brand)] rounded-full"></div>
                        </div>
                      </div>
                      <div className="flex items-center justify-between p-4 rounded-xl border border-[var(--k-border)] opacity-50">
                        <div>
                          <div className="text-sm font-medium text-foreground">Compact Sidebar</div>
                          <div className="text-xs text-muted-foreground">Minimize the navigation to show more content</div>
                        </div>
                        <div className="w-10 h-5 bg-accent rounded-full relative">
                           <div className="absolute left-1 top-1 w-3 h-3 bg-muted-foreground/30 rounded-full"></div>
                        </div>
                      </div>
                   </div>
                </div>
              )}

              {activeTab === 'security' && (
                <div className="space-y-6 animate-fade-up">
                  <h3 className="text-sm font-semibold uppercase tracking-widest text-muted-foreground">Security & Access</h3>
                  <div className="p-5 rounded-2xl bg-white/5 border border-white/5 space-y-3">
                    <div className="text-sm font-semibold text-foreground">Authentication</div>
                    <div className="flex items-center gap-3">
                      <GoogleLogo className="w-5 h-5 text-white/60" weight="bold" />
                      <div className="text-sm text-muted-foreground">Signed in via Google OAuth — no password stored</div>
                      <CheckCircle className="w-4 h-4 text-emerald-400 ml-auto" weight="fill" />
                    </div>
                  </div>
                  <div className="p-5 rounded-2xl bg-white/5 border border-white/5 space-y-2">
                    <div className="text-sm font-semibold text-foreground mb-2">Security practices</div>
                    {[
                      "API keys stored as SHA-256 hashes — never in plaintext",
                      "Firebase Auth tokens validated on every API request",
                      "TLS 1.2+ encryption on all data in transit",
                      "Content Security Policy (CSP) + HSTS enforced",
                    ].map(item => (
                      <div key={item} className="flex items-center gap-2 text-xs text-muted-foreground">
                        <CheckCircle className="w-3.5 h-3.5 text-emerald-400 flex-shrink-0" weight="fill" />
                        {item}
                      </div>
                    ))}
                  </div>
                  <div className="p-5 rounded-2xl bg-white/5 border border-white/5 space-y-2">
                    <div className="text-sm font-semibold text-foreground">Report a security issue</div>
                    <div className="text-xs text-muted-foreground">Found a vulnerability? Email us directly — we respond within 24 hours.</div>
                    <a href="mailto:support@revealiq.in?subject=Security%20Issue%20Report"
                       className="inline-block mt-1 text-xs text-indigo-400 hover:text-indigo-300 transition-colors">
                      support@revealiq.in
                    </a>
                  </div>
                </div>
              )}

              {activeTab === 'mydata' && (
                <div className="space-y-6 animate-fade-up">
                  <div>
                    <h3 className="text-sm font-semibold uppercase tracking-widest text-muted-foreground mb-1">My Data</h3>
                    <p className="text-xs text-muted-foreground">Your rights under the Digital Personal Data Protection Act, 2023 (India).</p>
                  </div>

                  {/* Data summary */}
                  <div className="p-5 rounded-2xl bg-white/5 border border-white/5 space-y-3">
                    <div className="flex items-center gap-2 text-sm font-semibold text-foreground mb-3">
                      <Eye className="w-4 h-4 text-indigo-400" weight="duotone" />
                      Data We Hold About You
                    </div>
                    {myDataLoading ? (
                      <div className="text-xs text-muted-foreground animate-pulse">Loading your data summary…</div>
                    ) : myData ? (
                      <div className="space-y-2 text-xs">
                        <div className="grid grid-cols-2 gap-x-4 gap-y-2">
                          <span className="text-muted-foreground">Name:</span><span className="text-foreground">{myData.profile?.name || user?.displayName || '—'}</span>
                          <span className="text-muted-foreground">Email:</span><span className="text-foreground">{myData.profile?.email || user?.email || '—'}</span>
                          <span className="text-muted-foreground">Joined:</span><span className="text-foreground">{myData.profile?.joined_at ? new Date(myData.profile.joined_at).toLocaleDateString('en-IN') : '—'}</span>
                          <span className="text-muted-foreground">Chat sessions:</span><span className="text-foreground">{myData.data_held?.chat_sessions ?? '—'}</span>
                          <span className="text-muted-foreground">API keys (active):</span><span className="text-foreground">{myData.data_held?.api_keys_active ?? '—'}</span>
                          <span className="text-muted-foreground">Voice data retained:</span><span className="text-emerald-400 font-medium">No</span>
                          <span className="text-muted-foreground">Age confirmed:</span>
                          <span className={myData.consent?.age_confirmed ? 'text-emerald-400 font-medium' : 'text-amber-400 font-medium'}>
                            {myData.consent?.age_confirmed ? 'Yes' : 'Not yet'}
                          </span>
                          <span className="text-muted-foreground">Marketing emails:</span>
                          <span className={myData.consent?.marketing_opt_in ? 'text-foreground' : 'text-muted-foreground'}>
                            {myData.consent?.marketing_opt_in ? 'Opted in' : 'Opted out'}
                          </span>
                        </div>
                        <div className="mt-3 text-[10px] text-muted-foreground/50">
                          Data processed by: Google Firebase (USA), HuggingFace (USA), Razorpay (India), Resend (USA).
                          {" "}<a href="/privacy" className="underline hover:text-muted-foreground">Full details →</a>
                        </div>
                      </div>
                    ) : (
                      <button onClick={loadMyData} className="text-xs text-indigo-400 hover:underline">Load data summary</button>
                    )}
                  </div>

                  {/* Marketing emails */}
                  <div className="p-5 rounded-2xl bg-white/5 border border-white/5">
                    <div className="flex items-center gap-2 text-sm font-semibold text-foreground mb-2">
                      <EnvelopeSimple className="w-4 h-4 text-indigo-400" weight="duotone" />
                      Marketing Emails
                    </div>
                    <p className="text-xs text-muted-foreground mb-4">
                      You receive re-engagement and feature announcement emails from Kautilya AI. You can opt out any time — transactional emails (billing, security) are unaffected.
                    </p>
                    {unsubStatus === 'done' || myData?.consent?.marketing_opt_in === false ? (
                      <div className="flex items-center gap-2 text-xs text-emerald-400">
                        <CheckCircle className="w-4 h-4" weight="fill" />
                        You are unsubscribed from marketing emails.
                      </div>
                    ) : (
                      <button
                        onClick={handleUnsubscribe}
                        disabled={unsubStatus === 'saving'}
                        className="px-4 py-2 rounded-lg border border-[var(--k-border)] text-xs font-medium text-muted-foreground hover:text-foreground hover:border-indigo-500/40 transition-all disabled:opacity-50"
                      >
                        {unsubStatus === 'saving' ? 'Saving…' : 'Unsubscribe from marketing emails'}
                      </button>
                    )}
                  </div>

                  {/* Data request */}
                  <div className="p-5 rounded-2xl bg-white/5 border border-white/5 space-y-3">
                    <div className="text-sm font-semibold text-foreground">Request Your Data or Corrections</div>
                    <p className="text-xs text-muted-foreground">
                      To request a full copy of your personal data or to correct inaccurate data, email us with the subject line <strong>"Data Access Request"</strong> or <strong>"Data Correction Request"</strong>. We will respond within 7 business days.
                    </p>
                    <a href="mailto:support@revealiq.in?subject=Data%20Access%20Request"
                       className="inline-block px-4 py-2 rounded-lg border border-[var(--k-border)] text-xs font-medium text-indigo-400 hover:text-indigo-300 hover:border-indigo-500/40 transition-all">
                      support@revealiq.in
                    </a>
                  </div>

                  {/* Account deletion */}
                  <div className="p-5 rounded-2xl bg-rose-500/5 border border-rose-500/10 space-y-3">
                    <div className="flex items-start gap-3">
                      <Trash className="w-5 h-5 text-rose-400 flex-shrink-0 mt-0.5" weight="duotone" />
                      <div>
                        <div className="text-sm font-semibold text-rose-400">Delete My Account & Data</div>
                        <p className="text-xs text-rose-400/70 mt-1">
                          Right to Erasure under DPDP Act 2023. Chat history is deleted immediately. Account metadata is purged within 7 business days. Billing records (7 years, GST law) and security logs (5 years, CERT-In) are retained as legally required.
                        </p>
                      </div>
                    </div>
                    {deletionState === 'done' || myData?.deletion_requested ? (
                      <div className="flex items-center gap-2 text-xs text-amber-400">
                        <Warning className="w-4 h-4" weight="fill" />
                        Deletion request received. We will complete this within 7 business days and email you a confirmation.
                      </div>
                    ) : deletionState === 'confirm' ? (
                      <div className="space-y-3">
                        <textarea
                          value={deletionReason}
                          onChange={e => setDeletionReason(e.target.value)}
                          placeholder="Optional: why are you leaving? (helps us improve)"
                          className="w-full bg-black/20 border border-rose-500/20 rounded-lg px-3 py-2 text-xs text-foreground placeholder:text-muted-foreground/40 resize-none focus:outline-none focus:border-rose-500/50"
                          rows={3}
                        />
                        <div className="flex gap-2">
                          <button
                            onClick={handleDeleteRequest}
                            disabled={deletionState === 'submitting'}
                            className="px-4 py-2 rounded-lg bg-rose-500 hover:bg-rose-600 text-white text-xs font-semibold transition-all disabled:opacity-50"
                          >
                            {deletionState === 'submitting' ? 'Submitting…' : 'Confirm — delete my account'}
                          </button>
                          <button
                            onClick={() => setDeletionState(null)}
                            className="px-4 py-2 rounded-lg border border-[var(--k-border)] text-xs text-muted-foreground hover:text-foreground transition-all"
                          >
                            Cancel
                          </button>
                        </div>
                      </div>
                    ) : (
                      <button
                        onClick={() => setDeletionState('confirm')}
                        className="w-full py-2.5 rounded-lg border border-rose-500/30 text-rose-400 text-sm font-medium hover:bg-rose-500 hover:text-white transition-all"
                      >
                        Request Account Deletion
                      </button>
                    )}
                  </div>

                  <div className="text-xs text-muted-foreground/50 leading-relaxed">
                    Grievance Officer: <strong className="text-muted-foreground">Harsh Vardhan</strong> ·{" "}
                    <a href="mailto:support@revealiq.in" className="underline hover:text-muted-foreground">support@revealiq.in</a>
                    {" "}· Responds within 24 hours · Resolves within 15 business days
                  </div>
                </div>
              )}
            </div>
          </ScrollArea>
        </div>
      </div>
    </div>
  );
}

function Badge({ children, className }) {
  return (
    <span className={`px-2 py-0.5 rounded-md border text-[10px] font-bold tracking-wider ${className}`}>
      {children}
    </span>
  );
}
