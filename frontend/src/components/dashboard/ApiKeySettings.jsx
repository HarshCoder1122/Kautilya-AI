import { useState, useEffect } from "react";
import { Key, Trash, Eye, EyeSlash, Plus, CheckCircle, Copy, ChartBar, Warning } from "@phosphor-icons/react";
import { keysAPI } from "../../lib/api";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Badge } from "@/components/ui/badge";

export default function ApiKeySettings() {
  const [keys, setKeys] = useState([]);
  const [usage, setUsage] = useState({});
  const [limits, setLimits] = useState({});
  const [tier, setTier] = useState('free');
  const [loading, setLoading] = useState(true);
  const [newKeyName, setNewKeyName] = useState("");
  const [isCreating, setIsCreating] = useState(false);
  const [notification, setNotification] = useState(null);
  const [showFullKeys, setShowFullKeys] = useState({});

  useEffect(() => {
    loadKeys();
  }, []);

  const loadKeys = async () => {
    try {
      setLoading(true);
      const data = await keysAPI.list();
      setKeys(data.keys || []);
      setUsage(data.usage || {});
      setLimits(data.limits || {});
      setTier(data.tier || 'free');
    } catch (error) {
      console.error('Failed to load keys:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleCreateKey = async () => {
    if (!newKeyName.trim()) return;
    try {
      setIsCreating(true);
      const result = await keysAPI.create({ name: newKeyName });
      loadKeys();
      setNewKeyName("");
      showNotification(`Key "${result.name}" created! Make sure to copy it now.`);
      // Temporarily show the full key
      setShowFullKeys(prev => ({ ...prev, [result.key_id]: result.key }));
    } catch (error) {
      console.error('Failed to create key:', error);
      alert(error.response?.data?.error || 'Failed to create key');
    } finally {
      setIsCreating(false);
    }
  };

  const handleRevokeKey = async (keyHash) => {
    if (!confirm("Are you sure you want to revoke this API key? This action is permanent.")) return;
    try {
      await keysAPI.revoke(keyHash);
      loadKeys();
      showNotification('API key revoked');
    } catch (error) {
      console.error('Failed to revoke key:', error);
    }
  };

  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text);
    showNotification('Copied to clipboard');
  };

  const showNotification = (message) => {
    setNotification(message);
    setTimeout(() => setNotification(null), 4000);
  };

  return (
    <div className="h-full flex flex-col" data-testid="api-key-settings">
      <div className="mb-6">
        <h2 className="text-xl font-medium k-heading tracking-tight text-foreground">Kautilya API Keys</h2>
        <p className="text-sm text-muted-foreground mt-1">Manage keys to access Kautilya AI's platform programmatically.</p>
      </div>

      {notification && (
        <div className="mb-6 px-4 py-3 rounded-md bg-[var(--k-brand)]/10 border border-[var(--k-brand)]/20 text-[var(--k-brand)] text-sm flex items-center justify-between animate-fade-in">
          <div className="flex items-center gap-2">
            <CheckCircle className="w-4 h-4" />
            {notification}
          </div>
          <button onClick={() => setNotification(null)} className="text-xs opacity-50 hover:opacity-100">Dismiss</button>
        </div>
      )}

      {/* Usage Overview */}
      <div className="grid grid-cols-2 gap-4 mb-8">
        <div className="p-4 rounded-xl border border-[var(--k-border)] bg-[var(--k-surface)]">
          <div className="flex items-center gap-2 mb-2">
            <ChartBar className="w-4 h-4 text-[var(--k-brand)]" />
            <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Monthly Usage</span>
          </div>
          <div className="flex items-end justify-between">
            <div>
              <div className="text-2xl font-bold k-heading text-foreground">
                {((usage.llm_tokens || 0) / 1000).toFixed(1)}k
              </div>
              <div className="text-[10px] text-muted-foreground">Tokens used</div>
            </div>
            <div className="text-right">
              <div className="text-sm font-medium text-foreground">
                {limits.llm_tokens ? `${((limits.llm_tokens - (usage.llm_tokens || 0)) / 1000).toFixed(1)}k` : 'Unlimited'}
              </div>
              <div className="text-[10px] text-muted-foreground">Remaining</div>
            </div>
          </div>
          <div className="mt-3 w-full h-1.5 bg-accent rounded-full overflow-hidden">
             <div 
               className="h-full bg-[var(--k-brand)] transition-all duration-500" 
               style={{ width: `${Math.min(100, (usage.llm_tokens || 0) / (limits.llm_tokens || 1) * 100)}%` }}
             />
          </div>
        </div>

        <div className="p-4 rounded-xl border border-[var(--k-border)] bg-[var(--k-surface)]">
          <div className="flex items-center gap-2 mb-2">
            <Key className="w-4 h-4 text-[var(--k-brand)]" />
            <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Plan Tier</span>
          </div>
          <div className="flex items-center justify-between">
            <div>
              <div className="text-xl font-bold k-heading text-foreground uppercase tracking-tight">{tier}</div>
              <div className="text-[10px] text-muted-foreground">Current Status</div>
            </div>
            <Badge className={tier === 'pro' ? 'bg-[var(--k-brand)]/10 text-[var(--k-brand)] border-none' : 'bg-accent text-muted-foreground border-none'}>
              {tier === 'pro' ? 'Premium Access' : 'Limited Free'}
            </Badge>
          </div>
          <button className="mt-3 w-full py-1.5 rounded-md bg-accent hover:bg-[var(--k-border)] transition-colors text-[10px] font-bold uppercase tracking-wider text-foreground">
            View Limits
          </button>
        </div>
      </div>

      {/* Create Key */}
      <div className="p-5 rounded-xl border border-[var(--k-border)] bg-[var(--k-surface)] mb-8">
        <h3 className="text-sm font-semibold text-foreground mb-4">Create a New API Key</h3>
        <div className="flex gap-3">
          <input
            type="text"
            placeholder="Key name (e.g., Mobile App, CRM Integration)"
            value={newKeyName}
            onChange={(e) => setNewKeyName(e.target.value)}
            className="flex-1 px-3 py-2 text-sm bg-[var(--k-surface-elevated)] border border-[var(--k-border)] rounded-md text-foreground focus:outline-none focus:ring-1 focus:ring-[var(--k-brand)]"
          />
          <button
            onClick={handleCreateKey}
            disabled={isCreating || !newKeyName.trim()}
            className="flex items-center gap-2 px-6 py-2 rounded-md bg-[var(--k-brand)] text-white text-sm font-medium hover:bg-[var(--k-brand-hover)] transition-all duration-200 disabled:opacity-50"
          >
            <Plus className="w-4 h-4" />
            {isCreating ? 'Creating...' : 'Create Key'}
          </button>
        </div>
      </div>

      {/* Key List */}
      <div className="space-y-4">
        <h3 className="text-xs font-bold uppercase tracking-widest text-muted-foreground mb-4">Active Keys</h3>
        {loading ? (
          <div className="text-center py-8 text-sm text-muted-foreground">Fetching your keys...</div>
        ) : keys.length === 0 ? (
          <div className="text-center py-12 border border-dashed border-[var(--k-border)] rounded-xl">
            <Key className="w-8 h-8 mx-auto text-muted-foreground/30 mb-3" />
            <div className="text-sm text-muted-foreground">You don't have any active API keys.</div>
          </div>
        ) : (
          keys.map((k) => (
            <div key={k.key_hash} className="p-4 rounded-xl border border-[var(--k-border)] bg-[var(--k-surface)] group hover:border-[var(--k-brand)]/30 transition-all">
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-3">
                  <div className="w-8 h-8 rounded-lg bg-accent flex items-center justify-center">
                    <Key className="w-4 h-4 text-muted-foreground" />
                  </div>
                  <div>
                    <div className="text-sm font-semibold text-foreground">{k.name}</div>
                    <div className="text-[10px] text-muted-foreground">Created {new Date(k.created_at).toLocaleDateString()}</div>
                  </div>
                </div>
                <div className="flex items-center gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                  <button 
                    onClick={() => handleRevokeKey(k.key_hash)}
                    className="p-1.5 rounded-md hover:bg-rose-500/10 text-muted-foreground hover:text-rose-400 transition-colors"
                    title="Revoke Key"
                  >
                    <Trash className="w-4 h-4" />
                  </button>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <div className="flex-1 px-3 py-2 bg-accent/50 border border-[var(--k-border)] rounded-md font-mono text-xs text-foreground">
                  {showFullKeys[k.key_id] || k.preview}
                </div>
                {showFullKeys[k.key_id] && (
                  <button 
                    onClick={() => copyToClipboard(showFullKeys[k.key_id])}
                    className="p-2 rounded-md bg-[var(--k-brand)]/10 text-[var(--k-brand)] hover:bg-[var(--k-brand)]/20 transition-colors"
                  >
                    <Copy className="w-4 h-4" />
                  </button>
                )}
              </div>
            </div>
          ))
        )}
      </div>

      <div className="mt-8 p-4 rounded-xl border border-[var(--k-yellow)]/20 bg-[var(--k-yellow)]/5 flex items-start gap-3">
        <Warning className="w-5 h-5 text-[var(--k-yellow)] flex-shrink-0 mt-0.5" />
        <div className="text-xs text-muted-foreground leading-relaxed">
          <strong className="text-[var(--k-yellow)]">Security Reminder:</strong> Your API keys carry the full weight of your account permissions. Never share them on client-side code, GitHub, or other public platforms.
        </div>
      </div>
    </div>
  );
}
