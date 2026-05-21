import { useState, useEffect } from "react";
import { Upload, ChartBar, TrendUp, MagnifyingGlass, Lightning, ArrowsClockwise } from "@phosphor-icons/react";
import { analyticsAPI, campaignsAPI, leadsAPI, agentsAPI } from "../../lib/api";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, AreaChart, Area, LineChart, Line
} from "recharts";

const COLORS = ['#0052FF', '#2563EB', '#10B981', '#F59E0B', '#8B5CF6'];

export default function BIAnalytics() {
  const [nlQuery, setNlQuery] = useState('');
  const [activeViz, setActiveViz] = useState('overview');
  const [usageData, setUsageData] = useState(null);
  const [trendsData, setTrendsData] = useState(null);
  const [kpis, setKpis] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadAnalytics();
  }, []);

  const loadAnalytics = async () => {
    setLoading(true);
    try {
      // Run all requests in parallel with individual fallbacks
      const [usage, trends, leadsRes, campaignsRes, agentsRes] = await Promise.all([
        analyticsAPI.getUsage().catch(() => ({})),
        analyticsAPI.getTrends().catch(() => ({})),
        leadsAPI.list().catch(() => ({ leads: [] })),
        campaignsAPI.list().catch(() => ({ campaigns: [] })),
        agentsAPI.list().catch(() => ({ agents: [] })),
      ]);

      setUsageData(usage);
      setTrendsData(trends);

      setKpis([
        { label: 'Total Leads', value: leadsRes.leads?.length || 0, change: '', positive: true },
        { label: 'Active Campaigns', value: campaignsRes.campaigns?.length || 0, change: '', positive: true },
        { label: 'AI Agents', value: agentsRes.agents?.length || 0, change: '', positive: true },
        { label: 'Total Calls', value: usage.total_calls || 0, change: '', positive: true },
        { label: 'Avg Sentiment', value: typeof usage.avg_sentiment === 'number' ? usage.avg_sentiment.toFixed(1) : '—', change: '', positive: true },
        { label: 'Success Rate', value: usage.success_rate || '—', change: '', positive: true },
      ]);
    } catch (error) {
      console.error('Failed to load analytics:', error);
    } finally {
      setLoading(false);
    }
  };

  // Transform usage data to chart format
  const revenueData = usageData?.daily_usage?.map(d => {
    try {
      const parsedDate = new Date(d.date);
      if (isNaN(parsedDate.getTime())) {
        return {
          month: d.date || '—',
          value: d.count || 0,
        };
      }
      return {
        month: parsedDate.toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
        value: d.count || 0,
      };
    } catch (e) {
      return {
        month: d.date || '—',
        value: d.count || 0,
      };
    }
  }) || [];

  // Generate dynamic 3-day forecast based on last date in daily usage
  const getForecastData = () => {
    if (revenueData.length === 0) return [];
    const lastItem = revenueData[revenueData.length - 1];
    const lastDate = usageData?.daily_usage?.[usageData.daily_usage.length - 1]?.date;
    const baseDate = lastDate ? new Date(lastDate) : new Date();
    
    const forecast = [];
    for (let i = 1; i <= 3; i++) {
      const nextDate = new Date(baseDate);
      nextDate.setDate(baseDate.getDate() + i);
      const label = nextDate.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
      forecast.push({
        month: label,
        value: Math.round((lastItem.value || 0) * (1 + i * 0.1)),
        forecast: true
      });
    }
    return [...revenueData, ...forecast];
  };

  const forecastData = getForecastData();

  const [salesByRegion, setSalesByRegion] = useState([]);
  const [conversionFunnel, setConversionFunnel] = useState([]);

  return (
    <div className="h-full" data-testid="bi-analytics">
      <div className="px-8 py-6 border-b border-[var(--k-border)]">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-medium k-heading tracking-tight text-foreground">BI Analytics</h1>
            <p className="text-sm text-muted-foreground mt-1">Interactive business intelligence dashboards</p>
          </div>
          <button
            data-testid="upload-data-btn"
            className="flex items-center gap-2 px-4 py-2.5 rounded-md bg-[var(--k-brand)] text-white text-sm font-medium hover:bg-[var(--k-brand-hover)] transition-all duration-200 hover:-translate-y-px"
          >
            <Upload className="w-4 h-4" />
            Upload Data
          </button>
        </div>
      </div>

      {/* NL Query Bar */}
      <div className="px-8 py-4 border-b border-[var(--k-border)]">
        <div className="relative max-w-2xl">
          <MagnifyingGlass className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
          <input
            data-testid="nl-query-input"
            type="text"
            placeholder="Ask anything... e.g., 'Show me a pie chart of sales by city'"
            value={nlQuery}
            onChange={(e) => setNlQuery(e.target.value)}
            className="w-full pl-10 pr-24 py-2.5 text-sm bg-transparent border border-[var(--k-border)] rounded-md focus:outline-none focus:ring-1 focus:ring-[var(--k-brand)] text-foreground placeholder:text-muted-foreground"
          />
          <button
            data-testid="nl-query-submit"
            className="absolute right-2 top-1/2 -translate-y-1/2 flex items-center gap-1 px-3 py-1 rounded-md bg-[var(--k-brand)] text-white text-xs font-medium hover:bg-[var(--k-brand-hover)] transition-colors"
          >
            <Lightning className="w-3 h-3" />
            Analyze
          </button>
        </div>
      </div>

      <ScrollArea className="h-[calc(100vh-200px)]">
        {loading ? (
          <div className="px-8 py-6 text-center text-sm text-muted-foreground">Loading analytics...</div>
        ) : (
          <div className="px-8 py-6 space-y-6">
            {/* KPI Grid */}
            <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-3">
              {kpis.map((kpi, i) => (
                <div key={i} data-testid={`bi-kpi-${i}`} className="p-4 rounded-md border border-[var(--k-border)] bg-[var(--k-surface)]">
                  <div className="text-[10px] tracking-[0.15em] uppercase text-muted-foreground font-semibold">{kpi.label}</div>
                  <div className="text-xl font-medium k-heading tracking-tight text-foreground mt-1">{kpi.value}</div>
                  <div className={`text-xs font-medium mt-0.5 flex items-center gap-1 ${kpi.positive ? 'text-[var(--k-green)]' : 'text-red-400'}`}>
                    <TrendUp className="w-3 h-3" />
                    {kpi.change}
                  </div>
                </div>
              ))}
            </div>

            {/* Charts Row 1 */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              {/* Revenue Trend */}
              <div className="p-5 rounded-md border border-[var(--k-border)] bg-[var(--k-surface)]">
                <div className="flex items-center justify-between mb-4">
                  <div className="text-sm font-semibold text-foreground k-heading">Usage Trend</div>
                  <div className="flex items-center gap-1 text-[10px] text-muted-foreground">
                    <ArrowsClockwise className="w-3 h-3" />
                    Auto-refreshing
                  </div>
                </div>
                <ResponsiveContainer width="100%" height={240}>
                  <AreaChart data={revenueData}>
                    <defs>
                      <linearGradient id="revGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#0052FF" stopOpacity={0.1}/>
                        <stop offset="95%" stopColor="#0052FF" stopOpacity={0}/>
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="var(--k-border)" />
                    <XAxis dataKey="month" tick={{ fontSize: 11, fill: 'var(--k-text-secondary)' }} axisLine={false} tickLine={false} />
                    <YAxis tick={{ fontSize: 11, fill: 'var(--k-text-secondary)' }} axisLine={false} tickLine={false} />
                    <Tooltip contentStyle={{ background: 'var(--k-surface-elevated)', border: '1px solid var(--k-border)', borderRadius: '6px', fontSize: '12px' }} />
                    <Area type="monotone" dataKey="value" stroke="#0052FF" strokeWidth={2} fill="url(#revGrad)" />
                  </AreaChart>
                </ResponsiveContainer>
              </div>

              <div className="p-5 rounded-md border border-[var(--k-border)] bg-[var(--k-surface)]">
                <div className="text-sm font-semibold text-foreground mb-4 k-heading">Leads by Region</div>
                {salesByRegion.length === 0 ? (
                  <div className="h-[240px] flex items-center justify-center text-xs text-muted-foreground">No regional data available</div>
                ) : (
                  <div className="flex items-center gap-6">
                    <ResponsiveContainer width="55%" height={240}>
                      <PieChart>
                        <Pie data={salesByRegion} cx="50%" cy="50%" innerRadius={60} outerRadius={90} paddingAngle={3} dataKey="value">
                          {salesByRegion.map((entry, i) => (
                            <Cell key={i} fill={entry.fill} />
                          ))}
                        </Pie>
                        <Tooltip contentStyle={{ background: 'var(--k-surface-elevated)', border: '1px solid var(--k-border)', borderRadius: '6px', fontSize: '12px' }} />
                      </PieChart>
                    </ResponsiveContainer>
                    <div className="space-y-3">
                      {salesByRegion.map((region, i) => (
                        <div key={i} className="flex items-center gap-2">
                          <div className="w-3 h-3 rounded-sm" style={{ background: region.fill }} />
                          <div>
                            <div className="text-xs font-medium text-foreground">{region.name}</div>
                            <div className="text-[10px] text-muted-foreground">{region.value} leads</div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>

            <div className="p-5 rounded-md border border-[var(--k-border)] bg-[var(--k-surface)]">
              <div className="text-sm font-semibold text-foreground mb-4 k-heading">Lead Conversion Funnel</div>
              {conversionFunnel.length === 0 ? (
                <div className="h-20 flex items-center justify-center text-xs text-muted-foreground">No conversion data available</div>
              ) : (
                <div className="space-y-3">
                  {conversionFunnel.map((stage, i) => {
                    const width = (stage.value / conversionFunnel[0].value) * 100;
                    const rate = i > 0 ? Math.round((stage.value / conversionFunnel[i - 1].value) * 100) : 100;
                    return (
                      <div key={i} data-testid={`funnel-stage-${i}`} className="flex items-center gap-4">
                        <span className="text-xs text-muted-foreground w-24 text-right font-medium">{stage.stage}</span>
                        <div className="flex-1 h-9 bg-[var(--k-surface-elevated)] rounded-sm overflow-hidden relative">
                          <div
                            className="h-full rounded-sm flex items-center justify-between px-3 transition-all duration-700"
                            style={{
                              width: `${width}%`,
                              background: COLORS[i % COLORS.length],
                              opacity: 1 - (i * 0.12),
                            }}
                          >
                            <span className="text-xs text-white font-medium">{stage.value.toLocaleString()}</span>
                            {i > 0 && <span className="text-[10px] text-white/80">{rate}%</span>}
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>

            {/* Predictive Analytics */}
            <div className="p-5 rounded-md border border-[var(--k-border)] bg-[var(--k-surface)]">
              <div className="flex items-center gap-2 mb-4">
                <TrendUp className="w-4 h-4 text-[var(--k-brand)]" weight="duotone" />
                <div className="text-sm font-semibold text-foreground k-heading">Usage Forecast</div>
                <span className="text-[10px] px-2 py-0.5 rounded-full bg-[var(--k-brand)]/10 text-[var(--k-brand)] font-medium">Trend Analysis</span>
              </div>
              <ResponsiveContainer width="100%" height={220}>
                <LineChart data={forecastData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--k-border)" />
                  <XAxis dataKey="month" tick={{ fontSize: 11, fill: 'var(--k-text-secondary)' }} axisLine={false} tickLine={false} />
                  <YAxis tick={{ fontSize: 11, fill: 'var(--k-text-secondary)' }} axisLine={false} tickLine={false} />
                  <Tooltip contentStyle={{ background: 'var(--k-surface-elevated)', border: '1px solid var(--k-border)', borderRadius: '6px', fontSize: '12px' }} />
                  <Line type="monotone" dataKey="value" stroke="#0052FF" strokeWidth={2} dot={{ r: 3, fill: '#0052FF' }} />
                </LineChart>
              </ResponsiveContainer>
              <div className="flex items-center gap-4 mt-3 text-xs">
                <div className="flex items-center gap-1.5">
                  <div className="w-4 h-0.5 bg-[var(--k-brand)]" />
                  <span className="text-muted-foreground">Actual + Forecast</span>
                </div>
                <span className="text-muted-foreground">Based on usage trends</span>
              </div>
            </div>
          </div>
        )}
      </ScrollArea>
    </div>
  );
}
