import { useState, useEffect } from "react";
import { Phone, SmileyMelting, Smiley, SmileyNervous, ArrowSquareOut, Clock, Lightning, Play, Headphones, Article, X, Info } from "@phosphor-icons/react";
import { analyticsAPI, agentsAPI } from "../../lib/api";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Badge } from "@/components/ui/badge";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, PieChart, Pie, Cell } from "recharts";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";

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
      
      if (volumeData.buckets) {
        const chartData = volumeData.buckets.map(b => ({
          day: b.label,
          calls: b.count,
        }));
        setCallVolumeData(chartData);
      }
      
      setAgents(agentsData.agents || []);
      
      const logsPromises = (agentsData.agents || []).map(agent => 
        agentsAPI.getLogs(agent.agent_id).catch(() => ({ logs: [] }))
      );
      
      const logsResponses = await Promise.all(logsPromises);
      const allLogs = logsResponses.flatMap(r => r.logs || []);
      // Sort by date desc
      const sortedLogs = allLogs.sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
      setAgentLogs(sortedLogs.slice(0, 20)); 
      
    } catch (error) {
      console.error('Failed to load analytics:', error);
    } finally {
      setLoading(false);
    }
  };

  const sentimentData = [
    { name: 'Positive', value: agentLogs.filter(l => l.sentiment === 'positive').length || 0, fill: '#10B981' },
    { name: 'Neutral', value: agentLogs.filter(l => l.sentiment === 'neutral').length || 0, fill: '#F59E0B' },
    { name: 'Negative', value: agentLogs.filter(l => l.sentiment === 'negative').length || 0, fill: '#EF4444' },
  ];

  return (
    <div className="h-full flex flex-col bg-background" data-testid="call-analytics">
      <div className="px-8 py-6 border-b border-[var(--k-border)]">
        <h1 className="text-2xl font-medium k-heading tracking-tight text-foreground">Call Analytics</h1>
        <p className="text-sm text-muted-foreground mt-1">AI-powered call summaries and insights</p>
      </div>

      <ScrollArea className="flex-1">
        <div className="px-8 py-8 space-y-8">
          {loading ? (
            <div className="text-center py-20 text-sm text-muted-foreground animate-pulse">Analyzing call data...</div>
          ) : (
            <>
              {/* Stats Row */}
              <div className="grid grid-cols-4 gap-6">
                {[
                  { label: 'Total Calls', val: callStats.total_calls, color: 'text-foreground' },
                  { label: 'Failed Calls', val: callStats.failed_calls, color: 'text-rose-400' },
                  { label: 'Avg Sentiment', val: callStats.avg_sentiment.toFixed(1), color: 'text-[var(--k-brand)]' },
                  { label: 'Active Agents', val: agents.length, color: 'text-foreground' }
                ].map((stat, i) => (
                  <div key={i} className="p-6 rounded-2xl border border-[var(--k-border)] bg-[var(--k-surface)] shadow-sm">
                    <div className="text-[10px] tracking-[0.2em] uppercase text-muted-foreground font-bold mb-2">{stat.label}</div>
                    <div className={`text-3xl font-bold k-heading tracking-tighter ${stat.color}`}>{stat.val}</div>
                  </div>
                ))}
              </div>

              {/* Charts Row */}
              <div className="grid grid-cols-5 gap-6">
                <div className="col-span-3 p-6 rounded-2xl border border-[var(--k-border)] bg-[var(--k-surface)]">
                  <div className="text-sm font-bold text-foreground mb-6 k-heading tracking-tight">Call Volume Activity</div>
                  <ResponsiveContainer width="100%" height={220}>
                    <BarChart data={callVolumeData}>
                      <CartesianGrid strokeDasharray="3 3" stroke="var(--k-border)" vertical={false} />
                      <XAxis dataKey="day" tick={{ fontSize: 10, fill: 'var(--k-text-secondary)' }} axisLine={false} tickLine={false} />
                      <YAxis tick={{ fontSize: 10, fill: 'var(--k-text-secondary)' }} axisLine={false} tickLine={false} />
                      <Tooltip 
                        cursor={{fill: 'var(--k-brand)', opacity: 0.05}}
                        contentStyle={{ background: 'var(--k-surface-elevated)', border: '1px solid var(--k-border)', borderRadius: '12px', fontSize: '11px', boxShadow: '0 10px 15px -3px rgb(0 0 0 / 0.1)' }} 
                      />
                      <Bar dataKey="calls" fill="var(--k-brand)" radius={[4, 4, 0, 0]} barSize={32} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>

                <div className="col-span-2 p-6 rounded-2xl border border-[var(--k-border)] bg-[var(--k-surface)]">
                  <div className="text-sm font-bold text-foreground mb-6 k-heading tracking-tight">Sentiment Breakdown</div>
                  <div className="flex flex-col items-center justify-center h-[220px]">
                    <ResponsiveContainer width="100%" height={160}>
                      <PieChart>
                        <Pie data={sentimentData} cx="50%" cy="50%" innerRadius={55} outerRadius={75} paddingAngle={4} dataKey="value" stroke="none">
                          {sentimentData.map((entry, i) => (
                            <Cell key={i} fill={entry.fill} />
                          ))}
                        </Pie>
                      </PieChart>
                    </ResponsiveContainer>
                    <div className="flex gap-4 mt-4">
                      {sentimentData.map((item, i) => (
                        <div key={i} className="flex items-center gap-1.5">
                          <div className="w-2 h-2 rounded-full" style={{ background: item.fill }} />
                          <span className="text-[10px] font-bold text-muted-foreground uppercase">{item.name}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              </div>

              {/* Call Log */}
              <div>
                <div className="flex items-center justify-between mb-6">
                   <div className="text-base font-bold text-foreground k-heading flex items-center gap-2">
                    <Phone className="w-5 h-5 text-[var(--k-brand)]" weight="duotone" />
                    Recent Call Recordings
                  </div>
                </div>
                
                {agentLogs.length === 0 ? (
                  <div className="text-center py-20 border border-dashed border-[var(--k-border)] rounded-2xl">
                    <Headphones className="w-10 h-10 mx-auto text-muted-foreground/30 mb-4" />
                    <div className="text-sm text-muted-foreground">No call sessions found. Start a campaign to see logs.</div>
                  </div>
                ) : (
                  <div className="grid grid-cols-1 gap-3">
                    {agentLogs.map((log) => {
                      const sent = sentimentIcons[log.sentiment] || sentimentIcons.neutral;
                      const callDate = log.created_at ? new Date(log.created_at).toLocaleString('en-IN', {
                        day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit'
                      }) : 'Unknown';
                      
                      return (
                        <div
                          key={log.id}
                          onClick={() => setSelectedCall(log)}
                          className="group p-5 rounded-xl border border-[var(--k-border)] bg-[var(--k-surface)] hover:bg-[var(--k-surface-elevated)] transition-all duration-300 cursor-pointer flex items-center gap-6"
                        >
                          <div className="w-12 h-12 rounded-full bg-accent/50 flex items-center justify-center group-hover:scale-110 transition-transform flex-shrink-0">
                            <Play className="w-5 h-5 text-[var(--k-brand)]" weight="fill" />
                          </div>
                          
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-3 mb-1">
                               <span className="text-sm font-bold text-foreground truncate">
                                  {log.to_number || 'Inbound Call'}
                               </span>
                               <Badge className={`bg-transparent border ${sent.color.replace('text-', 'border-')}/30 ${sent.color} text-[9px] px-1.5 py-0 uppercase font-bold`}>
                                  {log.sentiment || 'neutral'}
                               </Badge>
                            </div>
                            <p className="text-xs text-muted-foreground truncate max-w-2xl">{log.summary || 'Click to view call details and transcript...'}</p>
                          </div>

                          <div className="text-right flex-shrink-0">
                             <div className="flex items-center justify-end gap-1.5 text-xs font-bold text-foreground mb-1">
                                <Clock className="w-3.5 h-3.5 text-muted-foreground" />
                                {log.duration || '0:45'}
                             </div>
                             <div className="text-[10px] text-muted-foreground font-medium">{callDate}</div>
                          </div>

                          <div className="opacity-0 group-hover:opacity-100 transition-opacity pl-4 border-l border-[var(--k-border)]">
                             <button className="p-2 rounded-lg bg-[var(--k-brand)] text-white shadow-lg shadow-[var(--k-brand)]/20">
                                <Article className="w-4 h-4" />
                             </button>
                          </div>
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

      {/* Call Detail Dialog */}
      <Dialog open={!!selectedCall} onOpenChange={() => setSelectedCall(null)}>
        <DialogContent className="sm:max-w-[800px] max-h-[90vh] p-0 overflow-hidden bg-[var(--k-surface)] border-[var(--k-border)] shadow-2xl">
          <DialogHeader className="sr-only">
            <DialogTitle>Call Details</DialogTitle>
            <DialogDescription>Full recording, transcript, and AI summary of the call.</DialogDescription>
          </DialogHeader>
          {selectedCall && (
            <div className="flex flex-col h-full">
               <div className="px-6 py-5 border-b border-[var(--k-border)] bg-[var(--k-surface-elevated)] flex items-center justify-between">
                  <div className="flex items-center gap-4">
                     <div className="w-10 h-10 rounded-full bg-[var(--k-brand)]/10 flex items-center justify-center">
                        <Phone className="w-5 h-5 text-[var(--k-brand)]" weight="duotone" />
                     </div>
                     <div>
                        <h3 className="text-base font-bold text-foreground k-heading">{selectedCall.to_number || 'Incoming Session'}</h3>
                        <div className="flex items-center gap-2 mt-0.5">
                           <span className="text-[10px] text-muted-foreground uppercase font-bold">{new Date(selectedCall.created_at).toLocaleString()}</span>
                           <div className="w-1 h-1 rounded-full bg-muted-foreground/30" />
                           <span className="text-[10px] text-[var(--k-brand)] font-bold uppercase">{selectedCall.duration || '0:00'}</span>
                        </div>
                     </div>
                  </div>
                  <button onClick={() => setSelectedCall(null)} className="p-2 rounded-full hover:bg-accent transition-colors">
                     <X className="w-4 h-4 text-muted-foreground" />
                  </button>
               </div>

               <ScrollArea className="flex-1 p-8">
                  <div className="space-y-8">
                     {/* Audio Player Placeholder */}
                     <div className="p-6 rounded-2xl bg-black/20 border border-white/5 flex flex-col items-center">
                        <div className="w-full flex items-center gap-4 mb-4">
                           <button className="w-12 h-12 rounded-full bg-[var(--k-brand)] flex items-center justify-center text-white flex-shrink-0 shadow-lg shadow-[var(--k-brand)]/20">
                              <Play className="w-6 h-6 ml-0.5" weight="fill" />
                           </button>
                           <div className="flex-1">
                              <div className="h-1 w-full bg-white/10 rounded-full relative overflow-hidden">
                                 <div className="absolute left-0 top-0 h-full w-1/3 bg-[var(--k-brand)]" />
                              </div>
                              <div className="flex justify-between text-[10px] text-muted-foreground mt-2 font-mono">
                                 <span>0:15</span>
                                 <span>{selectedCall.duration || '0:45'}</span>
                              </div>
                           </div>
                        </div>
                        <p className="text-[10px] text-muted-foreground italic flex items-center gap-1.5">
                           <Headphones className="w-3 h-3" />
                           Recording is stored securely on LiveKit S3 storage
                        </p>
                     </div>

                     {/* AI Summary */}
                     <div className="space-y-3">
                        <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-widest text-muted-foreground">
                           <Lightning className="w-4 h-4 text-[var(--k-yellow)]" weight="fill" />
                           AI Session Summary
                        </div>
                        <div className="p-5 rounded-2xl bg-accent/10 border border-[var(--k-border)]">
                           <p className="text-sm text-foreground leading-relaxed italic">"{selectedCall.summary || 'AI was unable to generate a summary for this short interaction.'}"</p>
                        </div>
                     </div>

                     {/* Transcript */}
                     <div className="space-y-4">
                        <div className="flex items-center justify-between">
                           <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-widest text-muted-foreground">
                              <Article className="w-4 h-4 text-[var(--k-brand)]" weight="fill" />
                              Conversation Transcript
                           </div>
                           <Badge className="bg-accent/50 text-muted-foreground border-none text-[10px] px-2 py-0.5">Real-time STT</Badge>
                        </div>
                        
                        <div className="space-y-4 font-sans">
                           {selectedCall.transcript && selectedCall.transcript.length > 0 ? (
                             selectedCall.transcript.map((t, i) => (
                               <div key={i} className={`flex ${t.role === 'agent' ? 'justify-start' : 'justify-end'}`}>
                                  <div className={`max-w-[80%] rounded-2xl p-4 text-sm ${
                                    t.role === 'agent' 
                                      ? 'bg-accent/20 border border-[var(--k-border)] rounded-bl-none text-foreground' 
                                      : 'bg-[var(--k-brand)] text-white rounded-br-none'
                                  }`}>
                                     <div className="text-[9px] uppercase font-bold opacity-50 mb-1">{t.role === 'agent' ? 'AI Agent' : 'Customer'}</div>
                                     <p className="leading-relaxed">{t.text}</p>
                                  </div>
                               </div>
                             ))
                           ) : (
                             <div className="p-6 rounded-2xl border border-dashed border-[var(--k-border)] text-center">
                                <p className="text-sm text-muted-foreground">Transcript data unavailable for this call ID.</p>
                             </div>
                           )}
                        </div>
                     </div>
                  </div>
               </ScrollArea>

               <div className="px-6 py-4 border-t border-[var(--k-border)] bg-[var(--k-surface-elevated)] flex items-center justify-between">
                  <div className="flex items-center gap-4">
                     <div className="flex items-center gap-1.5">
                        <span className="text-[10px] text-muted-foreground uppercase font-bold">Call Score</span>
                        <span className="text-sm font-bold text-[var(--k-green)]">{selectedCall.sentiment_score || 85}</span>
                     </div>
                     <div className="w-px h-4 bg-[var(--k-border)]" />
                     <div className="flex items-center gap-1.5">
                        <span className="text-[10px] text-muted-foreground uppercase font-bold">Status</span>
                        <span className="text-xs text-foreground font-medium capitalize">{selectedCall.status || 'completed'}</span>
                     </div>
                  </div>
                  <button className="flex items-center gap-2 px-4 py-1.5 rounded-lg border border-[var(--k-border)] text-xs font-bold text-muted-foreground hover:bg-accent hover:text-foreground transition-all">
                     <ArrowSquareOut className="w-3.5 h-3.5" />
                     Export Log
                  </button>
               </div>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
