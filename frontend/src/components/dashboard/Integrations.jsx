import { useState, useEffect } from "react";
import {
  Link, WhatsappLogo, SlackLogo, GoogleLogo,
  Lightning, CheckCircle, XCircle, ArrowSquareOut,
  PlugsConnected, Spinner, EnvelopeSimple,
  Cpu, Plus, Trash
} from "@phosphor-icons/react";
import api from "../../lib/api";

const PROVIDER_ICONS = {
  hubspot:         { icon: Lightning,     color: "text-orange-400",  bg: "bg-orange-400/10" },
  salesforce:      { icon: Lightning,     color: "text-blue-400",    bg: "bg-blue-400/10"   },
  zoho:            { icon: Lightning,     color: "text-green-400",   bg: "bg-green-400/10"  },
  google_calendar: { icon: GoogleLogo,    color: "text-red-400",     bg: "bg-red-400/10"    },
  whatsapp:        { icon: WhatsappLogo,  color: "text-emerald-400", bg: "bg-emerald-400/10"},
  slack:           { icon: SlackLogo,     color: "text-purple-400",  bg: "bg-purple-400/10" },
  zapier:          { icon: Lightning,     color: "text-amber-400",   bg: "bg-amber-400/10"  },
  gmail:           { icon: EnvelopeSimple, color: "text-rose-400",    bg: "bg-rose-400/10"   },
};

const CATEGORY_LABELS = { crm: "CRM", messaging: "Messaging", calendar: "Calendar", automation: "Automation" };

const MANUAL_FIELDS = {
  whatsapp:        [{ key: "access_token", label: "Access Token", type: "password" },
                    { key: "phone_number_id", label: "Phone Number ID", type: "text" },
                    { key: "business_account_id", label: "Business Account ID", type: "text" }],
  slack:           [{ key: "webhook_url", label: "Incoming Webhook URL", type: "url" }],
  zapier:          [{ key: "webhook_url", label: "Zap Webhook URL", type: "url" }],
  hubspot:         [{ key: "client_id", label: "Client ID", type: "text" },
                    { key: "client_secret", label: "Client Secret", type: "password" }],
  salesforce:      [{ key: "client_id", label: "Client ID", type: "text" },
                    { key: "client_secret", label: "Client Secret", type: "password" }],
  zoho:            [{ key: "client_id", label: "Client ID", type: "text" },
                    { key: "client_secret", label: "Client Secret", type: "password" }],
  google_calendar: [{ key: "client_id", label: "Client ID", type: "text" },
                    { key: "client_secret", label: "Client Secret", type: "password" }],
  gmail:           [{ key: "client_id", label: "Client ID", type: "text" },
                    { key: "client_secret", label: "Client Secret", type: "password" }],
};

export default function Integrations() {
  const [integrations, setIntegrations] = useState([]);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState(null);
  const [formValues, setFormValues] = useState({});
  const [saving, setSaving] = useState(null);
  const [disconnecting, setDisconnecting] = useState(null);
  const [toast, setToast] = useState(null);

  const [customServers, setCustomServers] = useState([]);
  const [customStatus, setCustomStatus] = useState({});
  const [showAddForm, setShowAddForm] = useState(false);
  const [newServerForm, setNewServerForm] = useState({ key: "", url: "", description: "", category: "Custom" });
  const [addingServer, setAddingServer] = useState(false);
  const [expandedCustom, setExpandedCustom] = useState(null);

  useEffect(() => { load(); }, []);

  const loadCustomServers = async () => {
    try {
      const [srvRes, statusRes] = await Promise.all([
        api.get("/api/integrations/mcp/custom"),
        api.get("/api/mcp/status")
      ]);
      setCustomServers(srvRes.data.servers || []);
      
      const statusMap = {};
      (statusRes.data.servers || []).forEach(s => {
        if (s.is_custom) {
          statusMap[s.key] = s;
        }
      });
      setCustomStatus(statusMap);
    } catch (e) {
      console.error("Failed to load custom MCP servers", e);
    }
  };

  const load = async () => {
    setLoading(true);
    try {
      const res = await api.get('/api/integrations');
      setIntegrations(res.data.integrations || []);
      await loadCustomServers();
    } catch (e) {
      showToast("Failed to load integrations", "error");
    } finally {
      setLoading(false);
    }
  };

  const handleAddCustomServer = async () => {
    if (!newServerForm.key || !newServerForm.url) {
      showToast("Server key and URL are required", "error");
      return;
    }
    setAddingServer(true);
    try {
      await api.post("/api/integrations/mcp/custom", newServerForm);
      showToast("Custom MCP Server added successfully");
      setShowAddForm(false);
      setNewServerForm({ key: "", url: "", description: "", category: "Custom" });
      await loadCustomServers();
    } catch (e) {
      showToast("Failed to add server: " + (e.response?.data?.error || e.message), "error");
    } finally {
      setAddingServer(false);
    }
  };

  const handleToggleCustomServer = async (srv) => {
    try {
      const updated = { ...srv, enabled: !srv.enabled };
      await api.post("/api/integrations/mcp/custom", updated);
      showToast(srv.enabled ? "Server disabled" : "Server enabled");
      await loadCustomServers();
    } catch (e) {
      showToast("Failed to update server: " + (e.response?.data?.error || e.message), "error");
    }
  };

  const handleDeleteCustomServer = async (key) => {
    if (!window.confirm(`Are you sure you want to delete custom MCP server '${key}'?`)) {
      return;
    }
    try {
      await api.delete(`/api/integrations/mcp/custom/${key}`);
      showToast("Custom MCP Server deleted");
      await loadCustomServers();
    } catch (e) {
      showToast("Failed to delete server: " + (e.response?.data?.error || e.message), "error");
    }
  };

  const showToast = (msg, type = "success") => {
    setToast({ msg, type });
    setTimeout(() => setToast(null), 3000);
  };

  const handleSave = async (provider) => {
    setSaving(provider);
    try {
      await api.post(`/api/integrations/${provider}/save`, formValues[provider] || {});
      showToast("Credentials saved");
      setExpanded(null);
      await load();
    } catch (e) {
      showToast("Save failed: " + (e.response?.data?.error || e.message), "error");
    } finally {
      setSaving(null);
    }
  };

  const handleOAuth = async (provider) => {
    try {
      const res = await api.get(`/api/integrations/${provider}/connect`);
      const url = res.data.redirect_url;
      if (!url) { showToast("Save client_id first", "error"); return; }
      const popup = window.open(url, "_blank", "width=600,height=700");
      const handler = (e) => {
        if (e.data?.kt_integration_connected) {
          window.removeEventListener("message", handler);
          popup?.close();
          load();
          showToast("Connected!");
        }
      };
      window.addEventListener("message", handler);
    } catch (e) {
      showToast(e.response?.data?.error || "OAuth failed", "error");
    }
  };

  const handleDisconnect = async (provider) => {
    setDisconnecting(provider);
    try {
      await api.post(`/api/integrations/${provider}/disconnect`);
      showToast("Disconnected");
      await load();
    } catch (e) {
      showToast("Disconnect failed", "error");
    } finally {
      setDisconnecting(null);
    }
  };

  const grouped = integrations.reduce((acc, item) => {
    const cat = item.category || "other";
    (acc[cat] = acc[cat] || []).push(item);
    return acc;
  }, {});

  return (
    <div className="h-full flex flex-col bg-background">
      {/* Header */}
      <div className="px-8 py-6 border-b border-[var(--k-border)]">
        <h1 className="text-2xl font-medium k-heading tracking-tight text-foreground">Integrations</h1>
        <p className="text-sm text-muted-foreground mt-1">Connect Kautilya AI to your CRM, messaging, and automation tools</p>
      </div>

      {/* Toast */}
      {toast && (
        <div className={`fixed top-4 right-4 z-50 px-4 py-2.5 rounded-xl text-sm font-medium shadow-lg transition-all
          ${toast.type === "error" ? "bg-rose-500/20 text-rose-300 border border-rose-500/30" : "bg-emerald-500/20 text-emerald-300 border border-emerald-500/30"}`}>
          {toast.msg}
        </div>
      )}

      <div className="flex-1 overflow-y-auto px-8 py-6">
        {loading ? (
          <div className="flex items-center justify-center h-40 text-muted-foreground">
            <Spinner className="w-6 h-6 animate-spin mr-2" /> Loading integrations…
          </div>
        ) : (
          <div className="space-y-8 max-w-3xl">
            {Object.entries(grouped).map(([cat, items]) => (
              <section key={cat}>
                <h3 className="text-xs font-semibold uppercase tracking-widest text-muted-foreground mb-3">
                  {CATEGORY_LABELS[cat] || cat}
                </h3>
                <div className="space-y-2">
                  {items.map((item) => {
                    const meta = PROVIDER_ICONS[item.id] || { icon: PlugsConnected, color: "text-muted-foreground", bg: "bg-accent" };
                    const Icon = meta.icon;
                    const isOpen = expanded === item.id;
                    const fields = MANUAL_FIELDS[item.id] || [];
                    const isOAuth = item.auth_type === "oauth";

                    return (
                      <div key={item.id} className="rounded-xl border border-[var(--k-border)] bg-[var(--k-surface)] overflow-hidden">
                        {/* Row */}
                        <div className="flex items-center gap-4 p-4">
                          <div className={`w-10 h-10 rounded-lg ${meta.bg} flex items-center justify-center flex-shrink-0`}>
                            <Icon className={`w-5 h-5 ${meta.color}`} weight="duotone" />
                          </div>
                          <div className="flex-1 min-w-0">
                            <div className="text-sm font-medium text-foreground">{item.label}</div>
                            <div className="text-xs text-muted-foreground capitalize">{item.category}</div>
                          </div>
                          <div className="flex items-center gap-2">
                            {item.connected ? (
                              <>
                                <span className="flex items-center gap-1 text-xs text-emerald-400 font-medium">
                                  <CheckCircle className="w-3.5 h-3.5" weight="fill" /> Connected
                                </span>
                                <button
                                  onClick={() => handleDisconnect(item.id)}
                                  disabled={disconnecting === item.id}
                                  className="px-3 py-1.5 text-xs rounded-lg border border-rose-500/30 text-rose-400 hover:bg-rose-500/10 transition-colors disabled:opacity-50"
                                >
                                  {disconnecting === item.id ? "…" : "Disconnect"}
                                </button>
                              </>
                            ) : (
                              <span className="flex items-center gap-1 text-xs text-muted-foreground">
                                <XCircle className="w-3.5 h-3.5" /> Not connected
                              </span>
                            )}
                            <button
                              onClick={() => setExpanded(isOpen ? null : item.id)}
                              className="px-3 py-1.5 text-xs rounded-lg bg-[var(--k-brand)]/10 text-[var(--k-brand)] hover:bg-[var(--k-brand)]/20 transition-colors"
                            >
                              {isOpen ? "Close" : "Configure"}
                            </button>
                          </div>
                        </div>

                        {/* Expand panel */}
                        {isOpen && (
                          <div className="border-t border-[var(--k-border)] p-4 space-y-3 bg-white/2">
                            {fields.map(f => (
                              <div key={f.key}>
                                <label className="block text-xs text-muted-foreground mb-1">{f.label}</label>
                                <input
                                  type={f.type === "password" ? "password" : "text"}
                                  placeholder={f.type === "password" ? "••••••••" : f.label}
                                  className="w-full bg-background border border-[var(--k-border)] rounded-lg px-3 py-2 text-sm text-foreground outline-none focus:border-[var(--k-brand)] transition-colors"
                                  value={(formValues[item.id] || {})[f.key] || ""}
                                  onChange={e => setFormValues(prev => ({
                                    ...prev,
                                    [item.id]: { ...(prev[item.id] || {}), [f.key]: e.target.value }
                                  }))}
                                />
                              </div>
                            ))}

                            <div className="flex items-center gap-2 pt-1">
                              <button
                                onClick={() => handleSave(item.id)}
                                disabled={saving === item.id}
                                className="px-4 py-1.5 text-xs rounded-lg bg-[var(--k-brand)] text-white font-medium hover:bg-[var(--k-brand-hover)] transition-colors disabled:opacity-50"
                              >
                                {saving === item.id ? "Saving…" : "Save Credentials"}
                              </button>
                              {isOAuth && (
                                <button
                                  onClick={() => handleOAuth(item.id)}
                                  className="flex items-center gap-1.5 px-4 py-1.5 text-xs rounded-lg border border-[var(--k-border)] text-foreground hover:bg-accent transition-colors"
                                >
                                  <ArrowSquareOut className="w-3.5 h-3.5" />
                                  Connect via OAuth
                                </button>
                              )}
                            </div>
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </section>
            ))}

            {/* Custom MCP Servers Section */}
            <section className="mt-12 pt-8 border-t border-[var(--k-border)]">
              <div className="flex items-center justify-between mb-4">
                <div>
                  <h3 className="text-sm font-semibold uppercase tracking-widest text-muted-foreground">Custom MCP Servers</h3>
                  <p className="text-xs text-muted-foreground mt-1">
                    Connect Kautilya AI to your own custom tools and APIs using the Model Context Protocol (SSE transport).
                  </p>
                </div>
                <button
                  onClick={() => {
                    setNewServerForm({ key: "", url: "", description: "", category: "Custom" });
                    setShowAddForm(!showAddForm);
                  }}
                  className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg bg-[var(--k-brand)] text-white font-medium hover:bg-[var(--k-brand-hover)] transition-all shadow-sm"
                >
                  <Plus className="w-3.5 h-3.5" />
                  {showAddForm ? "Cancel" : "Add Custom Server"}
                </button>
              </div>

              {/* Add Form */}
              {showAddForm && (
                <div className="mb-6 p-4 rounded-xl border border-[var(--k-border)] bg-[var(--k-surface)] space-y-4 animate-in fade-in slide-in-from-top-2 duration-200">
                  <div className="text-xs font-semibold uppercase tracking-wider text-[var(--k-brand)]">Add New Custom MCP Server</div>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    <div>
                      <label className="block text-xs text-muted-foreground mb-1">Server Key (Unique alphanumeric identifier)</label>
                      <input
                        type="text"
                        placeholder="e.g. jira, local_db"
                        className="w-full bg-background border border-[var(--k-border)] rounded-lg px-3 py-2 text-sm text-foreground outline-none focus:border-[var(--k-brand)] transition-colors"
                        value={newServerForm.key}
                        onChange={e => setNewServerForm(p => ({ ...p, key: e.target.value.toLowerCase().replace(/[^a-z0-9_-]/g, '') }))}
                      />
                    </div>
                    <div>
                      <label className="block text-xs text-muted-foreground mb-1">SSE Endpoint URL</label>
                      <input
                        type="text"
                        placeholder="e.g. http://localhost:5000/sse"
                        className="w-full bg-background border border-[var(--k-border)] rounded-lg px-3 py-2 text-sm text-foreground outline-none focus:border-[var(--k-brand)] transition-colors"
                        value={newServerForm.url}
                        onChange={e => setNewServerForm(p => ({ ...p, url: e.target.value }))}
                      />
                    </div>
                    <div className="md:col-span-2">
                      <label className="block text-xs text-muted-foreground mb-1">Description</label>
                      <input
                        type="text"
                        placeholder="What tools does this server provide?"
                        className="w-full bg-background border border-[var(--k-border)] rounded-lg px-3 py-2 text-sm text-foreground outline-none focus:border-[var(--k-brand)] transition-colors"
                        value={newServerForm.description}
                        onChange={e => setNewServerForm(p => ({ ...p, description: e.target.value }))}
                      />
                    </div>
                  </div>
                  <div className="flex justify-end gap-2 pt-1">
                    <button
                      onClick={handleAddCustomServer}
                      disabled={addingServer}
                      className="px-4 py-1.5 text-xs rounded-lg bg-[var(--k-brand)] text-white font-medium hover:bg-[var(--k-brand-hover)] transition-colors disabled:opacity-50 flex items-center gap-1.5"
                    >
                      {addingServer ? <Spinner className="w-3.5 h-3.5 animate-spin" /> : null}
                      {addingServer ? "Connecting..." : "Add Server"}
                    </button>
                  </div>
                </div>
              )}

              {/* Custom Servers List */}
              {customServers.length === 0 ? (
                <div className="flex flex-col items-center justify-center p-8 rounded-xl border border-[var(--k-border)] bg-[var(--k-surface)]/50 text-center">
                  <Cpu className="w-8 h-8 text-muted-foreground/40 mb-2" weight="thin" />
                  <div className="text-sm font-medium text-muted-foreground">No Custom MCP Servers</div>
                  <p className="text-xs text-muted-foreground/60 max-w-sm mt-1">
                    Add your own custom tools by hosting an SSE server and registering its endpoint.
                  </p>
                </div>
              ) : (
                <div className="space-y-2">
                  {customServers.map(srv => {
                    const status = customStatus[srv.key];
                    const state = srv.enabled ? (status?.state || "connecting") : "disabled";
                    const error = status?.error;
                    const tools = status?.tools || [];
                    const isExpanded = expandedCustom === srv.key;

                    return (
                      <div key={srv.key} className="rounded-xl border border-[var(--k-border)] bg-[var(--k-surface)] overflow-hidden transition-all duration-200 hover:border-[var(--k-border-hover)]">
                        <div className="flex items-center gap-4 p-4">
                          <div className={`w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0 ${
                            state === 'active' ? 'bg-emerald-400/10' :
                            state === 'disabled' ? 'bg-zinc-400/10' :
                            'bg-rose-400/10'
                          }`}>
                            <Cpu className={`w-5 h-5 ${
                              state === 'active' ? 'text-emerald-400' :
                              state === 'disabled' ? 'text-zinc-400' :
                              'text-rose-400'
                            }`} weight="duotone" />
                          </div>
                          
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2">
                              <span className="text-sm font-semibold text-foreground tracking-tight uppercase">{srv.key}</span>
                              {state === 'active' ? (
                                <span className="px-1.5 py-0.5 rounded text-[10px] font-medium bg-emerald-400/10 text-emerald-400 flex items-center gap-1 border border-emerald-400/20">
                                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" /> Active
                                </span>
                              ) : state === 'disabled' ? (
                                <span className="px-1.5 py-0.5 rounded text-[10px] font-medium bg-zinc-400/10 text-zinc-400 border border-zinc-400/20">
                                  Disabled
                                </span>
                              ) : (
                                <span className="px-1.5 py-0.5 rounded text-[10px] font-medium bg-rose-400/10 text-rose-400 border border-rose-400/20">
                                  Error
                                </span>
                              )}
                            </div>
                            <div className="text-xs text-muted-foreground mt-0.5 truncate max-w-md">{srv.description || srv.url}</div>
                          </div>

                          <div className="flex items-center gap-2">
                            {state === 'active' && (
                              <span className="text-[11px] text-muted-foreground font-medium mr-2">
                                {tools.length} tool{tools.length !== 1 ? 's' : ''}
                              </span>
                            )}
                            
                            <button
                              onClick={() => handleToggleCustomServer(srv)}
                              className={`px-2.5 py-1.5 text-xs font-medium rounded-lg border transition-all ${
                                srv.enabled 
                                  ? 'border-zinc-500/30 text-zinc-400 hover:bg-zinc-500/10'
                                  : 'border-[var(--k-brand)]/30 text-[var(--k-brand)] hover:bg-[var(--k-brand)]/10'
                              }`}
                            >
                              {srv.enabled ? "Disable" : "Enable"}
                            </button>

                            <button
                              onClick={() => setExpandedCustom(isExpanded ? null : srv.key)}
                              disabled={!srv.enabled || tools.length === 0}
                              className="px-2.5 py-1.5 text-xs font-medium rounded-lg bg-[var(--k-brand)]/10 text-[var(--k-brand)] hover:bg-[var(--k-brand)]/20 transition-all disabled:opacity-40"
                            >
                              {isExpanded ? "Hide" : "Tools"}
                            </button>

                            <button
                              onClick={() => handleDeleteCustomServer(srv.key)}
                              className="p-1.5 rounded-lg border border-rose-500/30 text-rose-400 hover:bg-rose-500/10 transition-colors"
                              title="Delete server"
                            >
                              <Trash className="w-4 h-4" />
                            </button>
                          </div>
                        </div>

                        {/* Error Message */}
                        {state === 'error' && error && (
                          <div className="px-4 pb-4 text-xs text-rose-400 bg-rose-500/5 border-t border-[var(--k-border)]/50 pt-2 font-mono">
                            Error: {error}
                          </div>
                        )}

                        {/* Expanded Tools List */}
                        {isExpanded && tools.length > 0 && (
                          <div className="px-4 pb-4 border-t border-[var(--k-border)] bg-zinc-950/20 pt-3 space-y-2 animate-in fade-in slide-in-from-top-1 duration-200">
                            <div className="text-[11px] font-bold text-muted-foreground uppercase tracking-wider">Available Tools:</div>
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                              {tools.map(t => (
                                <div key={t.name} className="p-2 rounded-lg bg-zinc-900/40 border border-[var(--k-border)]/40 flex flex-col gap-0.5">
                                  <div className="text-xs font-semibold font-mono text-[var(--k-brand)]">{t.name}</div>
                                  <div className="text-[10px] text-muted-foreground line-clamp-1">{t.underlying}</div>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </section>
          </div>
        )}
      </div>
    </div>
  );
}
