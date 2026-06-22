import { useState, useEffect } from "react";
import { MagnifyingGlass, FunnelSimple, Export, Phone, EnvelopeSimple, ArrowUp, ArrowDown, Trash } from "@phosphor-icons/react";
import { leadsAPI, telephonyAPI } from "../../lib/api";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Badge } from "@/components/ui/badge";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

const statusColors = {
  hot: { bg: 'bg-red-500/10', text: 'text-red-400', dot: 'bg-red-400' },
  warm: { bg: 'bg-amber-500/10', text: 'text-amber-400', dot: 'bg-amber-400' },
  cold: { bg: 'bg-blue-500/10', text: 'text-blue-400', dot: 'bg-blue-400' },
  new: { bg: 'bg-green-500/10', text: 'text-green-400', dot: 'bg-green-400' },
};

export default function LeadManagement() {
  const [search, setSearch] = useState('');
  const [filterStatus, setFilterStatus] = useState('all');
  const [sortField, setSortField] = useState('created_at');
  const [sortDir, setSortDir] = useState('desc');
  const [leads, setLeads] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadLeads();
  }, []);

  const loadLeads = async () => {
    try {
      setLoading(true);
      const data = await leadsAPI.list();
      setLeads(data.leads || []);
    } catch (error) {
      console.error('Failed to load leads:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteLead = async (leadId) => {
    if (!confirm('Are you sure you want to delete this lead?')) return;
    try {
      await leadsAPI.delete(leadId);
      loadLeads();
    } catch (error) {
      console.error('Failed to delete lead:', error);
      alert('Failed to delete lead');
    }
  };

  const handleUpdateStatus = async (leadId, status) => {
    try {
      await leadsAPI.update(leadId, { status });
      loadLeads();
    } catch (error) {
      console.error('Failed to update lead:', error);
    }
  };

  const [callingId, setCallingId] = useState(null);
  const handleCallLead = async (lead) => {
    const number = lead.phone;
    if (!number || number === 'N/A') {
      return alert('This lead has no phone number to call.');
    }
    if (!lead.agent_id) {
      return alert('No agent is linked to this lead, so it can\'t be auto-dialed. Open Agent Studio to call manually.');
    }
    try {
      setCallingId(lead.id);
      const res = await telephonyAPI.outbound({ agent_id: lead.agent_id, to_number: number });
      alert(`📞 Calling ${number}…\nCall ID: ${res?.call_id || 'pending'}`);
    } catch (error) {
      const data = error.response?.data || {};
      if (error.response?.status === 402 || data.code === 'upgrade_required') {
        if (window.confirm(`${data.message || 'Free call limit reached.'}\n\nGo to Billing to upgrade?`)) {
          window.location.href = '/dashboard/billing';
        }
        return;
      }
      alert(`Call failed: ${data.error || error.message || 'Unknown error'}`);
    } finally {
      setCallingId(null);
    }
  };

  const handleEmailLead = (lead) => {
    if (!lead.email) return alert('This lead has no email address.');
    const subject = encodeURIComponent('Following up on our call');
    const body = encodeURIComponent(
      `Hi ${lead.name || 'there'},\n\n${lead.message || 'Thanks for your time on the call.'}\n\n`
    );
    window.location.href = `mailto:${lead.email}?subject=${subject}&body=${body}`;
  };

  const filteredLeads = leads
    .filter(l => {
      if (filterStatus !== 'all' && l.status !== filterStatus) return false;
      if (search && !l.name?.toLowerCase().includes(search.toLowerCase()) && !l.company?.toLowerCase().includes(search.toLowerCase())) return false;
      return true;
    })
    .sort((a, b) => {
      const val = sortDir === 'asc' ? 1 : -1;
      return (a[sortField] > b[sortField] ? 1 : -1) * val;
    });

  return (
    <div className="h-full" data-testid="lead-management">
      {/* Header */}
      <div className="px-4 sm:px-8 py-6 border-b border-[var(--k-border)]">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl font-medium k-heading tracking-tight text-foreground">Lead Management</h1>
            <p className="text-sm text-muted-foreground mt-1">{leads.length} total leads tracked</p>
          </div>
          <button
            data-testid="export-leads-btn"
            className="flex items-center justify-center gap-2 px-4 py-2 rounded-md border border-[var(--k-border)] text-sm text-muted-foreground hover:text-foreground hover:bg-accent transition-all duration-200 w-full sm:w-auto"
          >
            <Export className="w-4 h-4" />
            Export
          </button>
        </div>
      </div>

      {/* Filters */}
      <div className="px-4 sm:px-8 py-4 flex flex-col md:flex-row md:items-center gap-4 border-b border-[var(--k-border)]">
        <div className="relative w-full md:max-w-sm">
          <MagnifyingGlass className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
          <input
            data-testid="lead-search-input"
            type="text"
            placeholder="Search leads..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-10 pr-4 py-2 text-sm bg-transparent border border-[var(--k-border)] rounded-md focus:outline-none focus:ring-1 focus:ring-[var(--k-brand)] text-foreground placeholder:text-muted-foreground"
          />
        </div>

        <div className="flex flex-wrap items-center gap-2 w-full md:w-auto">
          {['all', 'new', 'hot', 'warm', 'cold'].map((status) => (
            <button
              key={status}
              data-testid={`filter-${status}`}
              onClick={() => setFilterStatus(status)}
              className={`flex-1 sm:flex-none text-center px-3 py-1.5 text-xs font-medium rounded-md transition-all duration-200 capitalize ${
                filterStatus === status
                  ? 'bg-[var(--k-brand)] text-white'
                  : 'border border-[var(--k-border)] text-muted-foreground hover:text-foreground hover:bg-accent'
              }`}
            >
              {status}
            </button>
          ))}
        </div>
      </div>

      {/* Table */}
      <ScrollArea className="h-[calc(100vh-200px)]">
        <div className="px-4 sm:px-8 py-4">
          {loading ? (
            <div className="text-center py-8 text-sm text-muted-foreground">Loading leads...</div>
          ) : leads.length === 0 ? (
            <div className="text-center py-8 text-sm text-muted-foreground">No leads yet</div>
          ) : (
            <div className="overflow-x-auto w-full border border-[var(--k-border)] rounded-lg bg-[var(--k-surface)]">
              <table className="w-full min-w-[800px]" data-testid="leads-table">
                <thead>
                  <tr className="border-b border-[var(--k-border)] bg-muted/30">
                    <th className="text-left px-4 py-3 text-[10px] tracking-[0.15em] uppercase font-semibold text-muted-foreground">Contact</th>
                    <th className="text-left px-4 py-3 text-[10px] tracking-[0.15em] uppercase font-semibold text-muted-foreground">Company</th>
                    <th className="text-left px-4 py-3 text-[10px] tracking-[0.15em] uppercase font-semibold text-muted-foreground">
                      <button onClick={() => { setSortField('created_at'); setSortDir(d => d === 'asc' ? 'desc' : 'asc'); }} className="flex items-center gap-1 hover:text-foreground transition-colors">
                        Date {sortField === 'created_at' && (sortDir === 'asc' ? <ArrowUp className="w-3 h-3" /> : <ArrowDown className="w-3 h-3" />)}
                      </button>
                    </th>
                    <th className="text-left px-4 py-3 text-[10px] tracking-[0.15em] uppercase font-semibold text-muted-foreground">Status</th>
                    <th className="text-left px-4 py-3 text-[10px] tracking-[0.15em] uppercase font-semibold text-muted-foreground">Source</th>
                    <th className="text-left px-4 py-3 text-[10px] tracking-[0.15em] uppercase font-semibold text-muted-foreground">Phone</th>
                    <th className="text-right px-4 py-3 text-[10px] tracking-[0.15em] uppercase font-semibold text-muted-foreground">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredLeads.map((lead) => {
                    const sc = statusColors[lead.status] || statusColors.new;
                    const createdAt = lead.created_at ? new Date(lead.created_at).toLocaleDateString() : 'N/A';
                    return (
                      <tr key={lead.id} data-testid={`lead-row-${lead.id}`} className="border-b border-[var(--k-border)] hover:bg-accent/30 transition-colors last:border-none">
                        <td className="px-4 py-3">
                          <div className="text-sm font-medium text-foreground">{lead.name || 'Unknown'}</div>
                          <div className="text-xs text-muted-foreground">{lead.email || 'No email'}</div>
                        </td>
                        <td className="px-4 py-3 text-sm text-foreground">{lead.company || 'N/A'}</td>
                        <td className="px-4 py-3 text-xs text-muted-foreground">{createdAt}</td>
                        <td className="px-4 py-3">
                          <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[10px] font-medium uppercase tracking-wider ${sc.bg} ${sc.text}`}>
                            <span className={`w-1.5 h-1.5 rounded-full ${sc.dot}`} />
                            {lead.status || 'new'}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-xs text-muted-foreground">{lead.source || 'Direct'}</td>
                        <td className="px-4 py-3 text-sm text-foreground">{lead.phone || 'N/A'}</td>
                        <td className="px-4 py-3">
                          <div className="flex items-center justify-end gap-1">
                            <button data-testid={`call-lead-${lead.id}`} onClick={() => handleCallLead(lead)} disabled={callingId === lead.id} className="p-1.5 rounded-md hover:bg-[var(--k-green)]/10 text-muted-foreground hover:text-[var(--k-green)] transition-colors disabled:opacity-40" title="Call">
                              <Phone className={`w-3.5 h-3.5 ${callingId === lead.id ? 'animate-pulse' : ''}`} />
                            </button>
                            <button data-testid={`email-lead-${lead.id}`} onClick={() => handleEmailLead(lead)} className="p-1.5 rounded-md hover:bg-[var(--k-brand)]/10 text-muted-foreground hover:text-[var(--k-brand)] transition-colors" title="Email">
                              <EnvelopeSimple className="w-3.5 h-3.5" />
                            </button>
                            <button data-testid={`delete-lead-${lead.id}`} onClick={() => handleDeleteLead(lead.id)} className="p-1.5 rounded-md hover:bg-red-500/10 text-muted-foreground hover:text-red-500 transition-colors" title="Delete">
                              <Trash className="w-3.5 h-3.5" />
                            </button>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </ScrollArea>
    </div>
  );
}
