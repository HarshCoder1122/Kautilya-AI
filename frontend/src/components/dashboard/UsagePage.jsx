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

  // Mock data for charts
  const usageChartData = [
    { name: 'LLM Tokens', used: usageData?.total_tokens || 0, limit: 10000000 },
    { name: 'TTS Chars', used: usageData?.tts_usage || 0, limit: 5000000 },
    { name: 'STT Secs', used: usageData?.stt_usage || 0, limit: 6000 }
  ];

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
                <div className="text-sm font-semibold text-foreground mb-2">API Tokens Used</div>
                <div className="text-2xl font-medium k-heading tracking-tight text-foreground">
                  {usageData?.total_tokens?.toLocaleString() || '0'}
                </div>
                <div className="text-xs text-muted-foreground mt-1">
                  Free Tier: 1,000,000 tokens
                </div>
              </div>
              
              <div className="p-5 rounded-md border border-[var(--k-border)] bg-[var(--k-surface)]">
                <div className="text-sm font-semibold text-foreground mb-2">TTS Characters Used</div>
                <div className="text-2xl font-medium k-heading tracking-tight text-foreground">
                  {usageData?.tts_usage?.toLocaleString() || '0'}
                </div>
                <div className="text-xs text-muted-foreground mt-1">
                  Free Tier: 500,000 characters
                </div>
              </div>
              
              <div className="p-5 rounded-md border border-[var(--k-border)] bg-[var(--k-surface)]">
                <div className="text-sm font-semibold text-foreground mb-2">STT Seconds Used</div>
                <div className="text-2xl font-medium k-heading tracking-tight text-foreground">
                  {usageData?.stt_usage || '0'}s
                </div>
                <div className="text-xs text-muted-foreground mt-1">
                  Free Tier: 6,000 seconds
                </div>
              </div>
            </div>

            {/* Usage Charts */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <div className="p-5 rounded-md border border-[var(--k-border)] bg-[var(--k-surface)]">
                <div className="flex items-center justify-between mb-4">
                  <div className="text-sm font-semibold text-foreground k-heading">Token Usage</div>
                  <div className="flex items-center gap-1 text-[10px] text-muted-foreground">
                    <ArrowsClockwise className="w-3 h-3" />
                    Live updating
                  </div>
                </div>
                <ResponsiveContainer width="100%" height={200}>
                  <BarChart data={usageChartData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="var(--k-border)" />
                    <XAxis dataKey="name" tick={{ fontSize: 11, fill: 'var(--k-text-secondary)' }} />
                    <YAxis tick={{ fontSize: 11, fill: 'var(--k-text-secondary)' }} />
                    <Tooltip />
                    <Bar dataKey="used" fill="#0052FF" />
                  </BarChart>
                </ResponsiveContainer>
                <div className="text-xs text-muted-foreground mt-2">
                  {usageData?.total_tokens 
                    ? `${((usageData.total_tokens / 10000000) * 100).toFixed(2)}% of limit used`
                    : '0% of limit used'}
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
                  <div className="text-xs text-muted-foreground">Daily API Calls</div>
                  <div className="text-lg font-medium">{usageData?.daily_calls || 0}</div>
                </div>
                <div className="space-y-1">
                  <div className="text-xs text-muted-foreground">Failed Calls</div>
                  <div className="text-lg font-medium text-red-400">{usageData?.failed_calls || 0}</div>
                </div>
                <div className="space-y-1">
                  <div className="text-xs text-muted-foreground">Success Rate</div>
                  <div className="text-lg font-medium text-green-400">{usageData?.success_rate || '0%'}</div>
                </div>
                <div className="space-y-1">
                  <div className="text-xs text-muted-foreground">Total Tokens</div>
                  <div className="text-lg font-medium">{(usageData?.total_tokens || 0).toLocaleString()}</div>
                </div>
              </div>
            </div>
          </div>
        )}
      </ScrollArea>
    </div>
  );
}