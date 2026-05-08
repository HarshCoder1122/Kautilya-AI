import { useState, useEffect } from "react";
import { Phone, SmileyMelting, Smiley, SmileyNervous, ArrowSquareOut, Clock, Lightning } from "@phosphor-icons/react";
import { analyticsAPI, agentsAPI } from "@/lib/api";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Badge } from "@/components/ui/badge";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, PieChart, Pie, Cell } from "recharts";

const sentimentIcons = {
  positive: { icon: Smiley, color: 'text-[var(--k-green)]', bg: 'bg-[var(--k-green)]/10' },
  neutral: { icon: SmileyNervous, color: 'text-[var(--k-yellow)]', bg: 'bg-[var(--k-yellow)]/10' },
  negative: { icon: SmileyMelting, color: 'text-red-400', bg: 'bg-red-400/10' },
};

export default function CallAnalytics() {
  const [selectedCall, setSelectedCall] = useState(null);
  const [callVolumeData, setCallVolumeData] = useState([]);
  const [callStats, setCallStats] = useState({ total_calls: 0, failed_calls: 0, avg_sentiment: 0 });
  const [agentLogs, setAgentLogs] = useState([]);
  const [agents, setAgents] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadAnalytics();
    loadAgents();
  }, []);

  const loadAnalytics = async () => {
    try {
      setLoading(true);
      const [volumeData, agentsData] = await Promise.all([
        analyticsAPI.getCallVolume(),
        agentsAPI.list(),
      ]);
      
      setCallStats({
        total_calls: volumeData.total_calls || 0,
        failed_calls: volumeData.failed_calls || 0,
        avg_sentiment: volumeData.avg_sentiment || 0,
      });
      
      // Transform buckets to chart format
      if (volumeData.buckets) {
        const chartData = volumeData.buckets.map(b => ({
          day: b.label,
          calls: b.count,
        }));
        setCallVolumeData(chartData);
      }
      
      setAgents(agentsData.agents || []);
      
      // Load agent logs for recent calls
      const logsPromises = (agentsData.agents || []).map(agent => 
        agentsAPI.getLogs(agent.agent_id).catch(() => ({ logs: [] }))
      );
      
      const logsResponses = await Promise.all(logsPromises);
      const allLogs = logsResponses.flatMap(r => r.logs || []);
      setAgentLogs(allLogs.slice(0, 10)); // Show recent 10 calls
      
    } catch (error) {
      console.error('Failed to load analytics:', error);
    } finally {
      setLoading(false);
    }
  };

  const loadAgents = async () => {
    try {
      const data = await agentsAPI.list();
      setAgents(data.agents || []);
    } catch (error) {
      console.error('Failed to load agents:', error);
    }
  };

  const sentimentData = [
    { name: 'Positive', value: agentLogs.filter(l => l.sentiment === 'positive').length || 0, fill: '#10B981' },
    { name: 'Neutral', value: agentLogs.filter(l => l.sentiment === 'neutral').length || 0, fill: '#F59E0B' },
    { name: 'Negative', value: agentLogs.filter(l => l.sentiment === 'negative').length || 0, fill: '#EF4444' },
  ];

  return (
    <div className="h-full" data-testid="call-analytics">
      <div className="px-8 py-6 border-b border-[var(--k-border)]">
        <h1 className="text-2xl font-medium k-heading tracking-tight text-foreground">Call Analytics</h1>
        <p className="text-sm text-muted-foreground mt-1">AI-powered call summaries and insights</p>
      </div>

      <ScrollArea className="h-[calc(100vh-120px)]">
        <div className="px-8 py-6 space-y-6">
          {loading ? (
            <div className="text-center py-8 text-sm text-muted-foreground">Loading analytics...</div>
          ) : (
            <>
              {/* Stats Row */}
              <div className="grid grid-cols-4 gap-4">
                <div className="p-4 rounded-md border border-[var(--k-border)] bg-[var(--k-surface)]">
                  <div className="text-[10px] tracking-[0.15em] uppercase text-muted-foreground font-semibold">Total Calls</div>
                  <div className="text-2xl font-medium k-heading tracking-tight text-foreground mt-1">{callStats.total_calls}</div>
                  <div className="text-xs text-muted-foreground mt-0.5">All time</div>
                </div>
                <div className="p-4 rounded-md border border-[var(--k-border)] bg-[var(--k-surface)]">
                  <div className="text-[10px] tracking-[0.15em] uppercase text-muted-foreground font-semibold">Failed Calls</div>
                  <div className="text-2xl font-medium k-heading tracking-tight text-red-400 mt-1">{callStats.failed_calls}</div>
                  <div className="text-xs text-muted-foreground mt-0.5">Errors</div>
                </div>
                <div className="p-4 rounded-md border border-[var(--k-border)] bg-[var(--k-surface)]">
                  <div className="text-[10px] tracking-[0.15em] uppercase text-muted-foreground font-semibold">Avg Sentiment</div>
                  <div className="text-2xl font-medium k-heading tracking-tight text-foreground mt-1">{callStats.avg_sentiment.toFixed(1)}</div>
                  <div className="text-xs text-muted-foreground mt-0.5">Score</div>
                </div>
                <div className="p-4 rounded-md border border-[var(--k-border)] bg-[var(--k-surface)]">
                  <div className="text-[10px] tracking-[0.15em] uppercase text-muted-foreground font-semibold">Active Agents</div>
                  <div className="text-2xl font-medium k-heading tracking-tight text-foreground mt-1">{agents.length}</div>
                  <div className="text-xs text-muted-foreground mt-0.5">Configured</div>
                </div>
              </div>

              {/* Charts Row */}
              <div className="grid grid-cols-2 gap-4">
                <div className="p-4 rounded-md border border-[var(--k-border)] bg-[var(--k-surface)]">
                  <div className="text-xs font-semibold text-foreground mb-3 k-heading">Call Volume by Day</div>
                  <ResponsiveContainer width="100%" height={180}>
                    <BarChart data={callVolumeData}>
                      <CartesianGrid strokeDasharray="3 3" stroke="var(--k-border)" />
                      <XAxis dataKey="day" tick={{ fontSize: 11, fill: 'var(--k-text-secondary)' }} axisLine={false} tickLine={false} />
                      <YAxis tick={{ fontSize: 11, fill: 'var(--k-text-secondary)' }} axisLine={false} tickLine={false} />
                      <Tooltip contentStyle={{ background: 'var(--k-surface-elevated)', border: '1px solid var(--k-border)', borderRadius: '6px', fontSize: '12px' }} />
                      <Bar dataKey="calls" fill="#0052FF" radius={[3, 3, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>

                <div className="p-4 rounded-md border border-[var(--k-border)] bg-[var(--k-surface)]">
                  <div className="text-xs font-semibold text-foreground mb-3 k-heading">Sentiment Distribution</div>
                  <div className="flex items-center justify-center gap-8">
                    <ResponsiveContainer width={160} height={160}>
                      <PieChart>
                        <Pie data={sentimentData} cx="50%" cy="50%" innerRadius={50} outerRadius={70} paddingAngle={3} dataKey="value">
                          {sentimentData.map((entry, i) => (
                            <Cell key={i} fill={entry.fill} />
                          ))}
                        </Pie>
                      </PieChart>
                    </ResponsiveContainer>
                    <div className="space-y-2">
                      {sentimentData.map((item, i) => (
                        <div key={i} className="flex items-center gap-2">
                          <div className="w-2.5 h-2.5 rounded-full" style={{ background: item.fill }} />
                          <span className="text-xs text-muted-foreground">{item.name}</span>
                          <span className="text-xs font-medium text-foreground">{item.value}%</span>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              </div>

              {/* Call Log */}
              <div>
                <div className="text-xs font-semibold text-foreground mb-3 k-heading flex items-center gap-2">
                  <Phone className="w-4 h-4 text-[var(--k-brand)]" weight="duotone" />
                  Recent Calls
                </div>
                {agentLogs.length === 0 ? (
                  <div className="text-center py-8 text-sm text-muted-foreground">No calls recorded yet</div>
                ) : (
                  <div className="space-y-3">
                    {agentLogs.map((log) => {
                      const sent = sentimentIcons[log.sentiment] || sentimentIcons.neutral;
                      const callDate = log.created_at ? new Date(log.created_at).toLocaleString() : 'Unknown';
                      const duration = log.duration || 'N/A';
                      const summary = log.summary || 'No summary available';
                      const score = log.sentiment_score || 0;
                      return (
                        <div
                          key={log.call_id || log.id}
                          data-testid={`call-card-${log.call_id || log.id}`}
                          onClick={() => setSelectedCall(selectedCall?.call_id === log.call_id ? null : log)}
                          className="p-4 rounded-md border border-[var(--k-border)] bg-[var(--k-surface)] hover:bg-[var(--k-surface-elevated)] transition-all duration-200 cursor-pointer"
                        >
                          <div className="flex items-start justify-between">
                            <div className="flex-1">
                              <div className="flex items-center gap-2 mb-1">
                                <span className="text-sm font-medium text-foreground">Call #{log.call_id || log.id?.slice(0, 8)}</span>
                                <span className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded-full text-[10px] ${sent.color} ${sent.bg}`}>
                                  <sent.icon className="w-3 h-3" weight="fill" />
                                  {log.sentiment || 'neutral'}
                                </span>
                              </div>
                              <p className="text-xs text-muted-foreground">{summary}</p>
                            </div>
                            <div className="text-right ml-4 shrink-0">
                              <div className="flex items-center gap-1 text-xs text-muted-foreground">
                                <Clock className="w-3 h-3" />
                                {duration}
                              </div>
                              <div className="text-[10px] text-muted-foreground/60 mt-0.5">{callDate}</div>
                            </div>
                          </div>

                          {selectedCall?.call_id === log.call_id && (
                            <div className="mt-3 pt-3 border-t border-[var(--k-border)] animate-fade-up">
                              <div className="flex items-center gap-4 mb-2">
                                <div className="flex items-center gap-1.5">
                                  <span className="text-[10px] text-muted-foreground uppercase tracking-wider">Score</span>
                                  <span className="text-sm font-bold" style={{ color: score >= 80 ? '#10B981' : score >= 60 ? '#F59E0B' : '#EF4444' }}>{score}</span>
                                </div>
                                <div className="flex items-center gap-1.5">
                                  <span className="text-[10px] text-muted-foreground uppercase tracking-wider">Status</span>
                                  <span className="text-xs text-foreground">{log.status || 'completed'}</span>
                                </div>
                              </div>
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            </>
          )}
        </div>
      </ScrollArea>
    </div>
  );
}
