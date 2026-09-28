import { useState, useEffect } from "react";
import { useSearchParams } from "react-router-dom";
import { Phone, SmileyMelting, Smiley, SmileyNervous, ArrowSquareOut, Clock, Lightning, Play, Headphones, Article, ArrowLeft, Info, EnvelopeSimple, CalendarBlank, IdentificationCard, ChatCircleDots } from "@phosphor-icons/react";
import { analyticsAPI, agentsAPI } from "../../lib/api";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Badge } from "@/components/ui/badge";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, PieChart, Pie, Cell } from "recharts";

const sentimentIcons = {
  positive: { icon: Smiley, color: 'text-[var(--k-green)]', bg: 'bg-[var(--k-green)]/10' },
  neutral: { icon: SmileyNervous, color: 'text-[var(--k-yellow)]', bg: 'bg-[var(--k-yellow)]/10' },
  negative: { icon: SmileyMelting, color: 'text-red-400', bg: 'bg-red-400/10' },
};

// Normalise a single transcript turn's role to 'agent' | 'customer'
function normRole(role) {
  const r = String(role || '').toLowerCase();
  if (['agent', 'assistant', 'ai', 'bot'].includes(r)) return 'agent';
  return 'customer';
}

// Build a renderable transcript from a call log. Prefers the structured
// `transcript_json` ([{role,text}]); falls back to a JSON string; and finally
// parses the flat "ROLE: text\nROLE: text" format the voice agent saves.
function getTranscript(log) {
  if (!log) return [];
  const tj = log.transcript_json;
  if (Array.isArray(tj) && tj.length) {
    return tj.map(t => ({ role: normRole(t.role), text: t.text || t.content || '' }));
  }
  const raw = log.transcript;
  if (Array.isArray(raw)) return raw.map(t => ({ role: normRole(t.role), text: t.text || t.content || '' }));
  if (typeof raw === 'string' && raw.trim()) {
    // Try JSON-array first, then the "ROLE: text" line format.
    try {
      const p = JSON.parse(raw);
      if (Array.isArray(p)) return p.map(t => ({ role: normRole(t.role), text: t.text || t.content || '' }));
    } catch { /* not JSON — fall through to line parsing */ }
    const turns = [];
    for (const line of raw.split('\n')) {
      const m = line.match(/^\s*([A-Za-z_]+)\s*:\s*(.*)$/);
      if (m && m[2].trim()) {
        turns.push({ role: normRole(m[1]), text: m[2].trim() });
      } else if (turns.length && line.trim()) {
        turns[turns.length - 1].text += ' ' + line.trim();
      }
    }
    return turns;
  }
  return [];
}

const sentKey = (s) => {
  const v = String(s || 'neutral').toLowerCase();
  if (['positive', 'happy', 'satisfied'].includes(v)) return 'positive';
  if (['negative', 'frustrated', 'angry'].includes(v)) return 'negative';
  return 'neutral';
};

// Phone (dialed/received SIP) vs Web (in-browser) call, from the log's
// call_type / channel fields.
const callType = (log) => {
  const t = String(log?.call_type || '').toLowerCase();
  const ch = String(log?.channel || '').toLowerCase();
  if (t === 'phone' || ch.includes('sip') || ch.includes('phone'))
    return { label: 'Phone', icon: '📞', cls: 'border-[var(--k-brand)]/40 text-[var(--k-brand)]' };
  if (t === 'web' || ch.includes('web'))
    return { label: 'Web', icon: '🌐', cls: 'border-[var(--k-green)]/40 text-[var(--k-green)]' };
  return { label: 'Call', icon: '•', cls: 'border-muted-foreground/30 text-muted-foreground' };
};

// Icon per integration action type shown in the "Actions taken" panel.
const actionMeta = {
  email: { label: 'Email', emoji: '✉️', Icon: EnvelopeSimple, color: 'text-[var(--k-brand)]' },
  calendar: { label: 'Calendar', emoji: '📅', Icon: CalendarBlank, color: 'text-[var(--k-yellow)]' },
  crm: { label: 'CRM', emoji: '🗂️', Icon: IdentificationCard, color: 'text-[var(--k-green)]' },
  slack: { label: 'Slack', emoji: '💬', Icon: ChatCircleDots, color: 'text-purple-400' },
};

// Last 10 digits of any phone field — robust match across +91 / spaces / leading 0
const phoneDigits = (v) => String(v || '').replace(/\D/g, '').slice(-10);

// Every phone-ish field a call log might carry, for matching against a lead.
const logPhones = (log) => [log.lead_phone, log.to_number, log.from_number, log.dialed_number]
  .map(phoneDigits).filter(Boolean);

// Safely coerce a Firestore Timestamp, ISO string, or number to a Date
function toDate(val) {
  if (!val) return null;
  if (val instanceof Date) return val;
  if (typeof val === 'object' && typeof val.toDate === 'function') return val.toDate();
  if (typeof val === 'object' && val.seconds) return new Date(val.seconds * 1000);
  return new Date(val);
}

export default function CallAnalytics() {
  const [selectedCall, setSelectedCall] = useState(null);
  const [callVolumeData, setCallVolumeData] = useState([]);
  const [callStats, setCallStats] = useState({ total_calls: 0, failed_calls: 0, avg_sentiment: 0 });
  const [agentLogs, setAgentLogs] = useState([]);
  const [agents, setAgents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchParams, setSearchParams] = useSearchParams();

  useEffect(() => {
    loadAnalytics();
  }, []);

  // Deep-link: Leads (or anywhere) can open a person's call detail via
  // /dashboard/calls?call=<logId> or ?phone=<number>. Match once logs arrive.
  useEffect(() => {
    if (loading || !agentLogs.length || selectedCall) return;
    const callId = searchParams.get('call');
    const phone = searchParams.get('phone');
    if (!callId && !phone) return;
    let match = null;
    if (callId) match = agentLogs.find(l => l.id === callId);
    if (!match && phone) {
      const want = phoneDigits(phone);
      match = agentLogs.find(l => logPhones(l).includes(want));
    }
    if (match) setSelectedCall(match);
  }, [loading, agentLogs, searchParams, selectedCall]);

  // Clear the deep-link param when the user leaves the detail view so a
  // back-navigation doesn't immediately re-open the same call.
  const closeDetail = () => {
    setSelectedCall(null);
    if (searchParams.get('call') || searchParams.get('phone')) {
      searchParams.delete('call');
      searchParams.delete('phone');
      setSearchParams(searchParams, { replace: true });
    }
  };

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
    { name: 'Positive', value: agentLogs.filter(l => sentKey(l.sentiment) === 'positive').length || 0, fill: '#10B981' },
    { name: 'Neutral', value: agentLogs.filter(l => sentKey(l.sentiment) === 'neutral').length || 0, fill: '#F59E0B' },
    { name: 'Negative', value: agentLogs.filter(l => sentKey(l.sentiment) === 'negative').length || 0, fill: '#EF4444' },
  ];

  // ---- Full-page call detail (replaces the old cramped modal) ----
  if (selectedCall) {
    const call = selectedCall;
    const sk = sentKey(call.sentiment);
    const sent = sentimentIcons[sk] || sentimentIcons.neutral;
    const SentIcon = sent.icon;
    const transcript = getTranscript(call);
    const contactFields = [
      { label: 'Name', val: call.lead_name },
      { label: 'Company', val: call.lead_company },
      { label: 'Email', val: call.lead_email },
      { label: 'Phone', val: call.lead_phone || call.to_number || call.from_number },
      { label: 'Intent', val: call.intent },
    ].filter(f => f.val);
    const recordingUrl = call.recording_url || call.recording || call.audio_url;
    const title = call.lead_name || call.to_number || call.from_number || 'Inbound Call';
    const when = toDate(call.created_at)?.toLocaleString('en-IN', {
      day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit'
    }) ?? '';

    return (
      <div className="h-full flex flex-col bg-background" data-testid="call-analytics-detail">
        {/* Sticky header bar with Back */}
        <div className="px-4 sm:px-8 py-4 border-b border-[var(--k-border)] bg-[var(--k-surface)] flex items-center gap-4 sticky top-0 z-10">
          <button
            onClick={closeDetail}
            className="flex items-center gap-2 px-3 py-1.5 rounded-lg border border-[var(--k-border)] text-xs font-bold text-muted-foreground hover:bg-accent hover:text-foreground transition-all flex-shrink-0"
          >
            <ArrowLeft className="w-4 h-4" />
            Back
          </button>
          <div className="w-10 h-10 rounded-full bg-[var(--k-brand)]/10 flex items-center justify-center flex-shrink-0">
            <Phone className="w-5 h-5 text-[var(--k-brand)]" weight="duotone" />
          </div>
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-3">
              <h1 className="text-lg font-bold text-foreground k-heading truncate">{title}</h1>
              <Badge className={`bg-transparent border ${sent.color.replace('text-', 'border-')}/30 ${sent.color} text-[9px] px-1.5 py-0 uppercase font-bold flex items-center gap-1`}>
                <SentIcon className="w-3 h-3" weight="fill" /> {sk}
              </Badge>
              {(() => { const ct = callType(call); return (
                <Badge className={`bg-transparent border ${ct.cls} text-[9px] px-1.5 py-0 font-bold`}>
                  {ct.icon} {ct.label}
                </Badge>
              ); })()}
            </div>
            <div className="flex items-center gap-2 mt-0.5">
              <span className="text-[11px] text-muted-foreground">{when}</span>
              <div className="w-1 h-1 rounded-full bg-muted-foreground/30" />
              <span className="text-[11px] text-[var(--k-brand)] font-bold flex items-center gap-1"><Clock className="w-3 h-3" />{call.duration || '0:00'}</span>
            </div>
          </div>
          <button className="hidden sm:flex items-center gap-2 px-4 py-1.5 rounded-lg border border-[var(--k-border)] text-xs font-bold text-muted-foreground hover:bg-accent hover:text-foreground transition-all flex-shrink-0">
            <ArrowSquareOut className="w-3.5 h-3.5" />
            Export
          </button>
        </div>

        <ScrollArea className="flex-1">
          <div className="max-w-6xl mx-auto px-4 sm:px-8 py-8">
            {/* Audio player — full width */}
            <div className="p-5 rounded-2xl bg-[var(--k-surface-elevated)] border border-[var(--k-border)] mb-6">
              {recordingUrl ? (
                <audio controls src={recordingUrl} className="w-full" />
              ) : (
                <div className="flex items-center gap-4">
                  <button className="w-12 h-12 rounded-full bg-[var(--k-brand)] flex items-center justify-center text-white flex-shrink-0 shadow-lg shadow-[var(--k-brand)]/20">
                    <Play className="w-6 h-6 ml-0.5" weight="fill" />
                  </button>
                  <div className="flex-1">
                    <div className="h-1.5 w-full bg-white/10 rounded-full relative overflow-hidden">
                      <div className="absolute left-0 top-0 h-full w-1/3 bg-[var(--k-brand)]" />
                    </div>
                    <div className="flex justify-between text-[10px] text-muted-foreground mt-2 font-mono">
                      <span>0:00</span>
                      <span>{call.duration || '0:45'}</span>
                    </div>
                  </div>
                  <p className="hidden md:flex text-[10px] text-muted-foreground italic items-center gap-1.5 flex-shrink-0">
                    <Headphones className="w-3 h-3" /> Recording stored on LiveKit S3
                  </p>
                </div>
              )}
            </div>

            {/* Main + sidebar grid */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              {/* Main column: summary + transcript */}
              <div className="lg:col-span-2 space-y-6">
                {/* AI Summary */}
                <div className="p-6 rounded-2xl bg-[var(--k-surface)] border border-[var(--k-border)]">
                  <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-widest text-muted-foreground mb-3">
                    <Lightning className="w-4 h-4 text-[var(--k-yellow)]" weight="fill" />
                    AI Session Summary
                  </div>
                  <p className="text-sm text-foreground leading-relaxed">{call.summary || 'AI was unable to generate a summary for this short interaction.'}</p>
                  {Array.isArray(call.topics) && call.topics.length > 0 && (
                    <div className="flex flex-wrap gap-1.5 mt-4">
                      {call.topics.map((t, i) => (
                        <Badge key={i} className="bg-[var(--k-brand)]/10 text-[var(--k-brand)] border-none text-[10px] px-2 py-0.5">{t}</Badge>
                      ))}
                    </div>
                  )}
                </div>

                {/* Transcript */}
                <div className="p-6 rounded-2xl bg-[var(--k-surface)] border border-[var(--k-border)]">
                  <div className="flex items-center justify-between mb-5">
                    <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-widest text-muted-foreground">
                      <Article className="w-4 h-4 text-[var(--k-brand)]" weight="fill" />
                      Conversation Transcript
                    </div>
                    <Badge className="bg-accent/50 text-muted-foreground border-none text-[10px] px-2 py-0.5">Real-time STT</Badge>
                  </div>
                  <div className="space-y-4">
                    {transcript.length > 0 ? transcript.map((t, i) => (
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
                    )) : (
                      <div className="p-6 rounded-2xl border border-dashed border-[var(--k-border)] text-center">
                        <p className="text-sm text-muted-foreground">Transcript data unavailable for this call.</p>
                      </div>
                    )}
                  </div>
                </div>
              </div>

              {/* Sidebar: contact + follow-ups + meta */}
              <div className="space-y-6">
                {/* Extracted Contact */}
                {(contactFields.length > 0 || call.lead_score != null) && (
                  <div className="p-6 rounded-2xl bg-[var(--k-surface)] border border-[var(--k-border)]">
                    <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-widest text-muted-foreground mb-4">
                      <Info className="w-4 h-4 text-[var(--k-brand)]" weight="fill" />
                      Extracted Contact
                    </div>
                    <div className="space-y-3">
                      {contactFields.map((f, i) => (
                        <div key={i} className="min-w-0">
                          <div className="text-[9px] uppercase tracking-wider text-muted-foreground font-bold mb-0.5">{f.label}</div>
                          <div className="text-sm text-foreground break-words" title={String(f.val)}>{f.val}</div>
                        </div>
                      ))}
                      {call.lead_score != null && (
                        <div className="pt-3 border-t border-[var(--k-border)] flex items-center justify-between">
                          <span className="text-[9px] uppercase tracking-wider text-muted-foreground font-bold">Lead Score</span>
                          <span className="text-lg font-bold text-[var(--k-green)] k-heading">{call.lead_score}/10</span>
                        </div>
                      )}
                    </div>
                  </div>
                )}

                {/* Automated Follow-ups */}
                {Array.isArray(call.actions) && call.actions.length > 0 && (
                  <div className="p-6 rounded-2xl bg-[var(--k-surface)] border border-[var(--k-border)]">
                    <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-widest text-muted-foreground mb-4">
                      <Lightning className="w-4 h-4 text-[var(--k-green)]" weight="fill" />
                      Automated Follow-ups
                    </div>
                    <div className="space-y-3">
                      {call.actions.map((a, i) => {
                        const meta = actionMeta[a.type] || { Icon: Lightning, color: 'text-muted-foreground' };
                        const AIcon = meta.Icon;
                        const failed = a.status === 'failed';
                        return (
                          <div key={i} className="flex items-start gap-3">
                            <div className={`w-8 h-8 rounded-lg bg-accent/30 flex items-center justify-center flex-shrink-0 ${meta.color}`}>
                              <AIcon className="w-4 h-4" weight="fill" />
                            </div>
                            <div className="flex-1 min-w-0">
                              <div className="flex items-center gap-2">
                                <span className="text-sm text-foreground font-medium truncate">{a.label}</span>
                                <Badge className={`text-[8px] px-1.5 py-0 uppercase font-bold border flex-shrink-0 ${failed ? 'border-red-400/30 text-red-400' : 'border-[var(--k-green)]/30 text-[var(--k-green)]'} bg-transparent`}>
                                  {failed ? 'failed' : 'done'}
                                </Badge>
                              </div>
                              {a.detail && <div className="text-[11px] text-muted-foreground break-words mt-0.5">{a.detail}</div>}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}

                {/* Meta */}
                <div className="p-6 rounded-2xl bg-[var(--k-surface)] border border-[var(--k-border)] space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] text-muted-foreground uppercase font-bold">Status</span>
                    <span className="text-xs text-foreground font-medium capitalize">{call.status || 'completed'}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] text-muted-foreground uppercase font-bold">Sentiment</span>
                    <span className={`text-xs font-bold capitalize ${sent.color}`}>{sk}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] text-muted-foreground uppercase font-bold">Duration</span>
                    <span className="text-xs text-foreground font-medium">{call.duration || '0:00'}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </ScrollArea>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col bg-background" data-testid="call-analytics">
      <div className="px-4 sm:px-8 py-6 border-b border-[var(--k-border)]">
        <h1 className="text-2xl font-medium k-heading tracking-tight text-foreground">Call Analytics</h1>
        <p className="text-sm text-muted-foreground mt-1">AI-powered call summaries and insights</p>
      </div>

      <ScrollArea className="flex-1">
        <div className="px-4 sm:px-8 py-8 space-y-8">
          {loading ? (
            <div className="text-center py-20 text-sm text-muted-foreground animate-pulse">Analyzing call data...</div>
          ) : (
            <>
              {/* Stats Row */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
                {[
                  { label: 'Total Calls', val: callStats.total_calls, color: 'text-foreground' },
                  { label: 'Failed Calls', val: callStats.failed_calls, color: 'text-rose-400' },
                  { label: 'Avg Sentiment', val: (parseFloat(callStats.avg_sentiment) || 0).toFixed(1), color: 'text-[var(--k-brand)]' },
                  { label: 'Active Agents', val: agents.length, color: 'text-foreground' }
                ].map((stat, i) => (
                  <div key={i} className="p-6 rounded-2xl border border-[var(--k-border)] bg-[var(--k-surface)] shadow-sm">
                    <div className="text-[10px] tracking-[0.2em] uppercase text-muted-foreground font-bold mb-2">{stat.label}</div>
                    <div className={`text-3xl font-bold k-heading tracking-tighter ${stat.color}`}>{stat.val}</div>
                  </div>
                ))}
              </div>

              {/* Charts Row */}
              <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
                <div className="col-span-1 lg:col-span-3 p-6 rounded-2xl border border-[var(--k-border)] bg-[var(--k-surface)]">
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

                <div className="col-span-1 lg:col-span-2 p-6 rounded-2xl border border-[var(--k-border)] bg-[var(--k-surface)]">
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
                      const sk = sentKey(log.sentiment);
                      const sent = sentimentIcons[sk] || sentimentIcons.neutral;
                      const _d = toDate(log.created_at);
                      const callDate = _d ? _d.toLocaleString('en-IN', {
                        day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit'
                      }) : 'Unknown';
                      const title = log.lead_name || log.to_number || log.from_number || 'Inbound Call';
                      const subtitle = [log.lead_company, log.lead_email].filter(Boolean).join(' · ');

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
                                  {title}
                               </span>
                               <Badge className={`bg-transparent border ${sent.color.replace('text-', 'border-')}/30 ${sent.color} text-[9px] px-1.5 py-0 uppercase font-bold`}>
                                  {sk}
                               </Badge>
                               {(() => { const ct = callType(log); return (
                                 <Badge className={`bg-transparent border ${ct.cls} text-[9px] px-1.5 py-0 font-bold`}>
                                   {ct.icon} {ct.label}
                                 </Badge>
                               ); })()}
                               {(log.actions?.length > 0) && (
                                 <span className="text-[9px] text-muted-foreground font-medium" title="Automated follow-ups">
                                   {log.actions.map(a => actionMeta[a.type]?.emoji || '•').join(' ')}
                                 </span>
                               )}
                            </div>
                            <p className="text-xs text-muted-foreground truncate max-w-2xl">{subtitle || log.summary || 'Click to view call details and transcript...'}</p>
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
    </div>
  );
}
