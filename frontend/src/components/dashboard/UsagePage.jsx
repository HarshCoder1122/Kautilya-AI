import { useState, useEffect } from "react";
import { ScrollArea } from "@/components/ui/scroll-area";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";
import { ChartBar, Lightning, ArrowsClockwise, Info, Calendar, MagnifyingGlass } from "@phosphor-icons/react";
import { analyticsAPI, keysAPI } from "../../lib/api";

export default function UsagePage() {
  const [usageData, setUsageData] = useState(null);
  const [keysData, setKeysData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [keyStats, setKeyStats] = useState({});
  const [activeTab, setActiveTab] = useState("tokens");
  const [searchTerm, setSearchTerm] = useState("");

  useEffect(() => {
    loadUsageData();
  }, []);

  const loadUsageData = async () => {
    setLoading(true);
    try {
      const [usageRes, keysRes] = await Promise.all([
        analyticsAPI.getUsage().catch(() => ({})),
        keysAPI.list().catch(() => ({}))
      ]);
      
      setUsageData(usageRes);
      setKeysData(keysRes);
      
      const stats = {
        totalKeys: keysRes.keys?.length || 0,
        activeKeys: keysRes.keys?.filter(k => k.is_active).length || 0,
        totalUsage: keysRes.usage || {}
      };
      setKeyStats(stats);
    } catch (error) {
      console.error('Failed to load usage data:', error);
    } finally {
      setLoading(false);
    }
  };

  const fmt = (n) => Number(n || 0).toLocaleString('en-IN');

  const formatDate = (dateStr) => {
    if (!dateStr) return '';
    try {
      const parts = dateStr.split('-');
      if (parts.length === 3) {
        const date = new Date(parts[0], parts[1] - 1, parts[2]);
        return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
      }
      return dateStr;
    } catch (e) {
      return dateStr;
    }
  };

  // Map metric keys and configurations dynamically
  const tabsConfig = {
    tokens: {
      label: "LLM Tokens",
      dataKey: "tokens",
      color: "#FF6D3F",
      totalKey: "total_tokens",
      limitKey: "llm_tokens",
      defaultLimit: 1000000,
      unit: "tokens"
    },
    calls: {
      label: "Voice Calls",
      dataKey: "count",
      color: "#10B981",
      totalKey: "total_calls",
      limitKey: "voice_calls",
      defaultLimit: 1000,
      unit: "calls"
    },
    tts: {
      label: "TTS Characters",
      dataKey: "tts_chars",
      color: "#8B5CF6",
      totalKey: "tts_usage",
      limitKey: "tts_chars",
      defaultLimit: 500000,
      unit: "chars"
    },
    api: {
      label: "API Requests",
      dataKey: "api_calls",
      color: "#F59E0B",
      totalKey: "api_count",
      limitKey: "api_requests",
      defaultLimit: 50000,
      unit: "requests"
    }
  };

  const selectedConfig = tabsConfig[activeTab];

  const formatChartDate = (dateStr) => {
    if (!dateStr) return '';
    try {
      const parts = dateStr.split('-');
      if (parts.length === 3) {
        const date = new Date(parts[0], parts[1] - 1, parts[2]);
        return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
      }
      return dateStr;
    } catch (e) {
      return dateStr;
    }
  };

  // Map daily trend data
  const chartData = (usageData?.daily_usage || []).map((d) => ({
    name: formatChartDate(d.date), // e.g. "May 22"
    tokens: d.tokens || 0,
    count: d.count || 0,
    tts_chars: d.tts_chars || 0,
    api_calls: d.api_calls || 0,
    dateFull: d.date || ''
  }));

  // Daily usage table list sorted descending (newest first)
  const filteredDailyUsage = (usageData?.daily_usage || [])
    .filter(d => {
      const dateStr = d.date || '';
      const formatted = formatDate(dateStr);
      return dateStr.toLowerCase().includes(searchTerm.toLowerCase()) || 
             formatted.toLowerCase().includes(searchTerm.toLowerCase());
    })
    .sort((a, b) => (b.date || '').localeCompare(a.date || ''));

  return (
    <div className="h-full" data-testid="usage-page">
      {/* Header */}
      <div className="px-8 py-6 border-b border-[var(--k-border)]">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-medium k-heading tracking-tight text-foreground">Usage Dashboard</h1>
            <p className="text-sm text-muted-foreground mt-1">Track your API usage and token consumption per day</p>
          </div>
          <button 
            onClick={loadUsageData}
            disabled={loading}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg border border-[var(--k-border)] bg-[var(--k-surface)] hover:bg-[var(--k-surface-elevated)] text-foreground disabled:opacity-50 transition-colors"
          >
            <ArrowsClockwise className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </button>
        </div>
      </div>

      <ScrollArea className="h-[calc(100vh-140px)]">
        {loading && !usageData ? (
          <div className="flex flex-col items-center justify-center h-64 text-sm text-muted-foreground gap-2">
            <ArrowsClockwise className="w-6 h-6 animate-spin text-[var(--k-brand)]" />
            Loading usage statistics...
          </div>
        ) : (
          <div className="px-8 py-6 space-y-6">
            {/* Simulated Data Banner */}
            {usageData?.is_simulated && (
              <div className="flex items-start gap-3 p-4 rounded-xl border border-amber-500/20 bg-amber-500/10 text-amber-200 text-xs">
                <Info className="w-5 h-5 text-amber-400 shrink-0 mt-0.5" weight="fill" />
                <div>
                  <span className="font-semibold block mb-0.5 text-amber-300">Simulated Baseline Metrics Active</span>
                  Since this account has no historical API logs recorded in Firestore yet, Kautilya is displaying a realistic daily baseline. Real-time requests, chat sessions, and TTS consumption will populate here automatically.
                </div>
              </div>
            )}

            {/* Usage Summary Cards */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="p-5 rounded-xl border border-[var(--k-border)] bg-[var(--k-surface)]">
                <div className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">API Tokens (lifetime)</div>
                <div className="text-2xl font-medium k-heading tracking-tight text-foreground">
                  {fmt(usageData?.total_tokens)}
                </div>
                <div className="text-xs text-muted-foreground mt-2">
                  {keysData?.tier === 'pro' ? 'Pro Tier' : 'Free Tier'} · Daily cap: {fmt(keysData?.limits?.llm_tokens || (keysData?.tier === 'pro' ? 10000000 : 1000000))} tokens
                </div>
              </div>

              <div className="p-5 rounded-xl border border-[var(--k-border)] bg-[var(--k-surface)]">
                <div className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">TTS Characters (lifetime)</div>
                <div className="text-2xl font-medium k-heading tracking-tight text-foreground">
                  {fmt(usageData?.tts_usage)}
                </div>
                <div className="text-xs text-muted-foreground mt-2">
                  Daily cap: {fmt(keysData?.limits?.tts_chars || (keysData?.tier === 'pro' ? 5000000 : 500000))} characters
                </div>
              </div>

              <div className="p-5 rounded-xl border border-[var(--k-border)] bg-[var(--k-surface)]">
                <div className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">Developer API Calls (lifetime)</div>
                <div className="text-2xl font-medium k-heading tracking-tight text-foreground">
                  {fmt(usageData?.api_count)}
                </div>
                <div className="text-xs text-muted-foreground mt-2 flex flex-wrap gap-x-2">
                  <span>Chat: {fmt(usageData?.chat_count)}</span>
                  <span className="text-muted-foreground/30">|</span>
                  <span>STT: {fmt(usageData?.stt_usage)}s</span>
                </div>
              </div>
            </div>

            {/* Interactive Trend Chart Card */}
            <div className="p-5 rounded-xl border border-[var(--k-border)] bg-[var(--k-surface)]">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
                <div>
                  <h3 className="text-sm font-semibold text-foreground k-heading flex items-center gap-1.5">
                    <ChartBar className="w-4 h-4 text-[var(--k-brand)]" />
                    Daily Consumption Trends
                  </h3>
                  <p className="text-xs text-muted-foreground mt-0.5">Toggle tabs to view specific metrics across 14 days</p>
                </div>

                {/* Tab buttons */}
                <div className="flex flex-wrap p-0.5 rounded-lg bg-[var(--k-surface-elevated)] border border-[var(--k-border)]">
                  {Object.entries(tabsConfig).map(([key, cfg]) => (
                    <button
                      key={key}
                      onClick={() => setActiveTab(key)}
                      className={`px-3 py-1 text-xs font-medium rounded-md transition-all ${
                        activeTab === key
                          ? 'bg-[var(--k-surface)] text-foreground shadow-sm'
                          : 'text-muted-foreground hover:text-foreground'
                      }`}
                    >
                      {cfg.label}
                    </button>
                  ))}
                </div>
              </div>

              <div className="w-full">
                <ResponsiveContainer width="100%" height={220}>
                  <BarChart data={chartData} margin={{ top: 10, right: 10, left: -10, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="var(--k-border)" opacity={0.6} />
                    <XAxis dataKey="name" tick={{ fontSize: 11, fill: 'var(--k-text-secondary)' }} />
                    <YAxis tick={{ fontSize: 11, fill: 'var(--k-text-secondary)' }} tickFormatter={fmt} />
                    <Tooltip 
                      contentStyle={{ 
                        backgroundColor: 'var(--k-surface-elevated)', 
                        borderColor: 'var(--k-border)',
                        borderRadius: '8px'
                      }}
                      labelStyle={{ color: 'var(--k-text-secondary)', fontSize: '11px', fontWeight: 'bold' }}
                      itemStyle={{ color: selectedConfig.color }}
                      labelFormatter={(label, payload) => payload?.[0]?.payload?.dateFull ? formatDate(payload[0].payload.dateFull) : label}
                      formatter={(v) => [fmt(v), selectedConfig.label]} 
                    />
                    <Bar dataKey={selectedConfig.dataKey} fill={selectedConfig.color} radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>

              <div className="flex items-center justify-between text-xs text-muted-foreground mt-4 pt-3 border-t border-[var(--k-border)]/50">
                <div>
                  Peak Day: <span className="font-semibold text-foreground">{fmt(Math.max(...chartData.map((d) => d[selectedConfig.dataKey])))} {selectedConfig.unit}</span>
                </div>
                <div className="flex items-center gap-1">
                  <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
                  Live Updating
                </div>
              </div>
            </div>

            {/* Quick Stats Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 p-5 rounded-xl border border-[var(--k-border)] bg-[var(--k-surface)]">
              <div className="space-y-1">
                <div className="text-xs text-muted-foreground uppercase font-semibold tracking-wider">Today's Call Requests</div>
                <div className="text-xl font-medium text-foreground">{fmt(usageData?.daily_calls)}</div>
              </div>
              <div className="space-y-1">
                <div className="text-xs text-muted-foreground uppercase font-semibold tracking-wider">Failed Calls</div>
                <div className="text-xl font-medium text-rose-400">{fmt(usageData?.failed_calls)}</div>
              </div>
              <div className="space-y-1">
                <div className="text-xs text-muted-foreground uppercase font-semibold tracking-wider">Call Success Rate</div>
                <div className="text-xl font-medium text-emerald-400">{usageData?.success_rate || '0%'}</div>
              </div>
              <div className="space-y-1">
                <div className="text-xs text-muted-foreground uppercase font-semibold tracking-wider">API Keys Configured</div>
                <div className="text-xl font-medium text-indigo-400">{keyStats.activeKeys || 0} / {keyStats.totalKeys || 0}</div>
              </div>
            </div>

            {/* Day-by-Day Usage Table */}
            <div className="p-5 rounded-xl border border-[var(--k-border)] bg-[var(--k-surface)] space-y-4">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                <div>
                  <h3 className="text-sm font-semibold text-foreground k-heading flex items-center gap-1.5">
                    <Calendar className="w-4 h-4 text-indigo-400" />
                    Day-by-Day Consumption Detailed Breakdown
                  </h3>
                  <p className="text-xs text-muted-foreground mt-0.5">Granular table history showing precise metric points</p>
                </div>

                {/* Search Date */}
                <div className="relative w-full sm:w-64">
                  <MagnifyingGlass className="absolute left-3 top-2.5 w-4 h-4 text-muted-foreground" />
                  <input
                    type="text"
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                    placeholder="Search by date..."
                    className="w-full pl-9 pr-4 py-2 text-xs bg-[var(--k-surface-elevated)] border border-[var(--k-border)] rounded-lg text-foreground focus:outline-none focus:ring-1 focus:ring-[var(--k-brand)] placeholder:text-muted-foreground transition-all"
                  />
                </div>
              </div>

              <div className="overflow-x-auto rounded-lg border border-[var(--k-border)] bg-[var(--k-surface-elevated)]/30">
                <table className="w-full text-left border-collapse">
                  <thead>
                    <tr className="border-b border-[var(--k-border)] bg-[var(--k-surface-elevated)]/50 text-[11px] font-semibold text-muted-foreground uppercase tracking-wider">
                      <th className="px-5 py-3">Date</th>
                      <th className="px-5 py-3 text-right">LLM Tokens</th>
                      <th className="px-5 py-3 text-right">Voice Calls</th>
                      <th className="px-5 py-3 text-right">TTS Characters</th>
                      <th className="px-5 py-3 text-right">Developer API Calls</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[var(--k-border)]/50 text-xs">
                    {filteredDailyUsage.map((row) => (
                      <tr key={row.date} className="hover:bg-muted/5 transition-colors">
                        <td className="px-5 py-3 font-medium text-foreground">{formatDate(row.date)}</td>
                        <td className="px-5 py-3 text-right font-mono text-muted-foreground">{fmt(row.tokens)}</td>
                        <td className="px-5 py-3 text-right font-mono text-muted-foreground">{fmt(row.count)}</td>
                        <td className="px-5 py-3 text-right font-mono text-muted-foreground">{fmt(row.tts_chars)}</td>
                        <td className="px-5 py-3 text-right font-mono text-muted-foreground">{fmt(row.api_calls)}</td>
                      </tr>
                    ))}
                    {filteredDailyUsage.length === 0 && (
                      <tr>
                        <td colSpan={5} className="px-5 py-8 text-center text-muted-foreground">
                          No daily records found matching your filter criteria.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}
      </ScrollArea>
    </div>
  );
}