import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { User, Key, Bell, Shield, Palette, CaretRight, CheckCircle, Warning, GoogleLogo, Crown } from "@phosphor-icons/react";
import { ScrollArea } from "@/components/ui/scroll-area";
import { billingAPI, userAPI } from "../../lib/api";
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

  const tabs = [
    { id: 'profile', label: 'Profile', icon: User },
    { id: 'apikeys', label: 'API Keys', icon: Key },
    { id: 'preferences', label: 'Preferences', icon: Palette },
    { id: 'security', label: 'Security', icon: Shield },
  ];

  const isPro = billingConfig?.is_pro || billingConfig?.tier === 'pro';

  return (
    <div className="h-full flex flex-col bg-background" data-testid="user-settings">
      {/* Header */}
      <div className="px-8 py-6 border-b border-[var(--k-border)]">
        <h1 className="text-2xl font-medium k-heading tracking-tight text-foreground">Settings</h1>
        <p className="text-sm text-muted-foreground mt-1">Manage your account, preferences, and API integrations</p>
      </div>

      <div className="flex-1 flex overflow-hidden">
        {/* Settings Nav */}
        <div className="w-64 border-r border-[var(--k-border)] py-6 px-3">
          <div className="space-y-1">
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
        <div className="flex-1 overflow-hidden">
          <ScrollArea className="h-full px-8 py-8">
            <div className="max-w-2xl">
              {activeTab === 'profile' && (
                <div className="space-y-8 animate-fade-up">
                  <section>
                    <h3 className="text-sm font-semibold uppercase tracking-widest text-muted-foreground mb-4">Account Information</h3>
                    <div className="flex items-center gap-6 p-6 rounded-2xl bg-white/5 border border-white/5">
                      <div className="relative group">
                        {user?.photoURL ? (
                          <img src={user.photoURL} alt="" className="w-20 h-20 rounded-full object-cover border-2 border-[var(--k-brand)]/20" />
                        ) : (
                          <div className="w-20 h-20 rounded-full bg-accent flex items-center justify-center text-2xl font-bold text-muted-foreground">
                            {user?.displayName?.charAt(0) || 'U'}
                          </div>
                        )}
                      </div>
                      <div className="space-y-1">
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
                    <div className="p-4 rounded-xl border border-[var(--k-border)] bg-[var(--k-surface)] flex items-center justify-between">
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
                   <div className="p-6 rounded-2xl bg-rose-500/5 border border-rose-500/10">
                      <div className="flex items-start gap-3 text-rose-400 mb-4">
                        <Warning className="w-5 h-5 flex-shrink-0" />
                        <div>
                          <div className="text-sm font-semibold">Danger Zone</div>
                          <div className="text-xs text-rose-400/70 mt-1">Actions here are permanent and cannot be undone.</div>
                        </div>
                      </div>
                      <button className="w-full py-2.5 rounded-lg border border-rose-500/30 text-rose-400 text-sm font-medium hover:bg-rose-500 hover:text-white transition-all">
                        Delete Account & Data
                      </button>
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
