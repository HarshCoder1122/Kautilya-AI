import { useState, useEffect } from "react";
import { ScrollArea } from "@/components/ui/scroll-area";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, PieChart, Pie, Cell } from "recharts";
import { ChartBar, Lightning, ArrowsClockwise } from "@phosphor-icons/react";
import { analyticsAPI, keysAPI } from "../../lib/api";

const COLORS = ['#0052FF', '#10B981', '#8B5CF6', '#F59E0B', '#EF4444'];

export default function UsagePage() {
  const [usageData, setUsageData] = useState(null);
  const [keysData, setKeysData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [keyStats, setKeyStats] = useState({});

  useEffect(() => {
    loadUsageData();
  }, []);

  const loadUsageData = async () => {
    setLoading(true);
    try {
      // Load usage data and API keys
      const [usageRes, keysRes] = await Promise.all([
        analyticsAPI.getUsage().catch(() => ({})),
        keysAPI.list().catch(() => ({}))
      ]);
      
      setUsageData(usageRes);
      setKeysData(keysRes);
      
      // Calculate key stats
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

  // Daily token consumption trend (last 14 days) — much more useful than a
  // single bar comparing different resource types with wildly different scales.
  const tokenTrend = (usageData?.daily_usage || []).map((d) => ({
    name: (d.date || '').slice(5), // MM-DD
    tokens: d.tokens || 0,
    calls: d.count || 0,
  }));

  const fmt = (n) => Number(n || 0).toLocaleString('en-IN');

  return (
    <div className="h-full" data-testid="usage-page">
      <div className="px-8 py-6 border-b border-[var(--k-border)]">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-medium k-heading tracking-tight text-foreground">Usage Dashboard</h1>
            <p className="text-sm text-muted-foreground mt-1">Track your API usage and token consumption</p>
          </div>
        </div>
      </div>

      <ScrollArea className="h-[calc(100vh-200px)]">
        {loading ? (
          <div className="px-8 py-6 text-center text-sm text-muted-foreground">Loading usage data...</div>
        ) : (
          <div className="px-8 py-6 space-y-6">
            {/* Usage Summary Cards */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="p-5 rounded-md border border-[var(--k-border)] bg-[var(--k-surface)]">
                <div className="text-sm font-semibold text-foreground mb-2">API Tokens (lifetime)</div>
                <div className="text-2xl font-medium k-heading tracking-tight text-foreground">
                  {fmt(usageData?.total_tokens)}
                </div>
                <div className="text-xs text-muted-foreground mt-1">
                  {keysData?.tier === 'pro' ? 'Pro Tier' : 'Free Tier'} · Daily cap: {fmt(keysData?.limits?.llm_tokens || (keysData?.tier === 'pro' ? 10000000 : 1000000))} tokens
                </div>
              </div>

              <div className="p-5 rounded-md border border-[var(--k-border)] bg-[var(--k-surface)]">
                <div className="text-sm font-semibold text-foreground mb-2">TTS Characters (lifetime)</div>
                <div className="text-2xl font-medium k-heading tracking-tight text-foreground">
                  {fmt(usageData?.tts_usage)}
                </div>
                <div className="text-xs text-muted-foreground mt-1">
                  Daily cap: {fmt(keysData?.limits?.tts_chars || (keysData?.tier === 'pro' ? 5000000 : 500000))} characters
                </div>
              </div>

              <div className="p-5 rounded-md border border-[var(--k-border)] bg-[var(--k-surface)]">
                <div className="text-sm font-semibold text-foreground mb-2">Developer API Calls (lifetime)</div>
                <div className="text-2xl font-medium k-heading tracking-tight text-foreground">
                  {fmt(usageData?.api_count)}
                </div>
                <div className="text-xs text-muted-foreground mt-1">
                  Chat messages: {fmt(usageData?.chat_count)} · STT: {fmt(usageData?.stt_usage)}s
                </div>
              </div>
            </div>

            {/* Usage Charts */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <div className="p-5 rounded-md border border-[var(--k-border)] bg-[var(--k-surface)]">
                <div className="flex items-center justify-between mb-4">
                  <div className="text-sm font-semibold text-foreground k-heading">Tokens — Last 14 days</div>
                  <div className="flex items-center gap-1 text-[10px] text-muted-foreground">
                    <ArrowsClockwise className="w-3 h-3" />
                    Live updating
                  </div>
                </div>
                <ResponsiveContainer width="100%" height={200}>
                  <BarChart data={tokenTrend}>
                    <CartesianGrid strokeDasharray="3 3" stroke="var(--k-border)" />
                    <XAxis dataKey="name" tick={{ fontSize: 11, fill: 'var(--k-text-secondary)' }} />
                    <YAxis tick={{ fontSize: 11, fill: 'var(--k-text-secondary)' }} tickFormatter={fmt} />
                    <Tooltip formatter={(v) => fmt(v)} />
                    <Bar dataKey="tokens" fill="#FF6D3F" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
                <div className="text-xs text-muted-foreground mt-2">
                  {tokenTrend.length > 0
                    ? `Peak day: ${fmt(Math.max(...tokenTrend.map((d) => d.tokens)))} tokens`
                    : 'No token activity in the last 14 days'}
                </div>
              </div>

              <div className="p-5 rounded-md border border-[var(--k-border)] bg-[var(--k-surface)]">
                <div className="text-sm font-semibold text-foreground mb-4 k-heading">API Keys</div>
                <div className="space-y-3">
                  <div className="flex items-center justify-between text-xs">
                    <span className="text-muted-foreground">Active Keys</span>
                    <span className="font-medium">{keyStats.activeKeys || 0}</span>
                  </div>
                  <div className="flex items-center justify-between text-xs">
                    <span className="text-muted-foreground">Total Keys</span>
                    <span className="font-medium">{keyStats.totalKeys || 0}</span>
                  </div>
                </div>
              </div>
            </div>

            {/* Detailed Usage Stats */}
            <div className="p-5 rounded-md border border-[var(--k-border)] bg-[var(--k-surface)]">
              <div className="text-sm font-semibold text-foreground mb-4 k-heading">Usage Statistics</div>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                <div className="space-y-1">
                  <div className="text-xs text-muted-foreground">Today's Calls</div>
                  <div className="text-lg font-medium">{fmt(usageData?.daily_calls)}</div>
                </div>
                <div className="space-y-1">
                  <div className="text-xs text-muted-foreground">Failed Calls</div>
                  <div className="text-lg font-medium text-red-400">{fmt(usageData?.failed_calls)}</div>
                </div>
                <div className="space-y-1">
                  <div className="text-xs text-muted-foreground">Success Rate</div>
                  <div className="text-lg font-medium text-green-400">{usageData?.success_rate || '0%'}</div>
                </div>
                <div className="space-y-1">
                  <div className="text-xs text-muted-foreground">Total Tokens</div>
                  <div className="text-lg font-medium">{fmt(usageData?.total_tokens)}</div>
                </div>
              </div>
            </div>
          </div>
        )}
      </ScrollArea>
    </div>
  );
}