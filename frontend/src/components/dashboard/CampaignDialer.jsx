import { useState, useEffect } from "react";
import { Play, Pause, Clock, CheckCircle, Plus, Lightning, Users, Trash } from "@phosphor-icons/react";
import { campaignsAPI, agentsAPI } from "../../lib/api";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Progress } from "@/components/ui/progress";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";

const statusConfig = {
  running: { icon: Play, color: 'text-[var(--k-green)]', bg: 'bg-[var(--k-green)]/10', label: 'Running' },
  scheduled: { icon: Clock, color: 'text-[var(--k-yellow)]', bg: 'bg-[var(--k-yellow)]/10', label: 'Scheduled' },
  completed: { icon: CheckCircle, color: 'text-[var(--k-brand)]', bg: 'bg-[var(--k-brand)]/10', label: 'Completed' },
  paused: { icon: Pause, color: 'text-[var(--k-yellow)]', bg: 'bg-[var(--k-yellow)]/10', label: 'Paused' },
};

export default function CampaignDialer() {
  const [campaigns, setCampaigns] = useState([]);
  const [agents, setAgents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);

  useEffect(() => {
    loadCampaigns();
    loadAgents();
  }, []);

  const loadCampaigns = async () => {
    try {
      setLoading(true);
      const data = await campaignsAPI.list();
      setCampaigns(data.campaigns || []);
    } catch (error) {
      console.error('Failed to load campaigns:', error);
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

  const handleStartCampaign = async (campaignId) => {
    try {
      await campaignsAPI.start(campaignId);
      loadCampaigns();
    } catch (error) {
      console.error('Failed to start campaign:', error);
    }
  };

  const handleStopCampaign = async (campaignId) => {
    try {
      await campaignsAPI.stop(campaignId);
      loadCampaigns();
    } catch (error) {
      console.error('Failed to stop campaign:', error);
    }
  };

  const handleDeleteCampaign = async (campaignId) => {
    if (!confirm('Are you sure you want to delete this campaign?')) return;
    try {
      await campaignsAPI.delete(campaignId);
      loadCampaigns();
    } catch (error) {
      console.error('Failed to delete campaign:', error);
    }
  };

  return (
    <div className="h-full" data-testid="campaign-dialer">
      {/* Header */}
      <div className="px-8 py-6 border-b border-[var(--k-border)]">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-medium k-heading tracking-tight text-foreground">Campaign Dialer</h1>
            <p className="text-sm text-muted-foreground mt-1">Manage outbound calling campaigns</p>
          </div>
          <Dialog open={showCreate} onOpenChange={setShowCreate}>
            <DialogTrigger asChild>
              <button
                data-testid="create-campaign-btn"
                className="flex items-center gap-2 px-4 py-2.5 rounded-md bg-[var(--k-brand)] text-white text-sm font-medium hover:bg-[var(--k-brand-hover)] transition-all duration-200 hover:-translate-y-px"
              >
                <Plus className="w-4 h-4" />
                New Campaign
              </button>
            </DialogTrigger>
            <DialogContent className="sm:max-w-[500px]">
              <DialogHeader>
                <DialogTitle className="k-heading tracking-tight">Create Campaign</DialogTitle>
              </DialogHeader>
              <CreateCampaignForm onClose={() => setShowCreate(false)} onSuccess={loadCampaigns} agents={agents} />
            </DialogContent>
          </Dialog>
        </div>
      </div>

      {/* Campaign Cards */}
      <ScrollArea className="h-[calc(100vh-120px)]">
        <div className="px-8 py-6 space-y-4">
          {loading ? (
            <div className="text-center py-8 text-sm text-muted-foreground">Loading campaigns...</div>
          ) : campaigns.length === 0 ? (
            <div className="text-center py-8 text-sm text-muted-foreground">No campaigns yet</div>
          ) : (
            campaigns.map((campaign) => {
              const status = statusConfig[campaign.status] || statusConfig.paused;
              const contactRate = campaign.total_leads > 0 ? Math.round((campaign.contacted_count / campaign.total_leads) * 100) : 0;
              const convRate = campaign.connected_count > 0 ? Math.round((campaign.converted_count / campaign.connected_count) * 100) : 0;

              return (
                <div key={campaign.camp_id} data-testid={`campaign-card-${campaign.camp_id}`} className="p-5 rounded-md border border-[var(--k-border)] bg-[var(--k-surface)] hover:bg-[var(--k-surface-elevated)] transition-all duration-200">
                  <div className="flex items-start justify-between mb-4">
                    <div>
                      <div className="flex items-center gap-2 mb-1">
                        <h3 className="text-base font-medium k-heading tracking-tight text-foreground">{campaign.name}</h3>
                        <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium ${status.color} ${status.bg}`}>
                          <status.icon className="w-3 h-3" weight="fill" />
                          {status.label}
                        </span>
                      </div>
                      <p className="text-xs text-muted-foreground">Agent: {campaign.agent_name || 'N/A'}</p>
                    </div>
                    <div className="flex items-center gap-2">
                      {campaign.status === 'running' && (
                        <button data-testid={`pause-campaign-${campaign.camp_id}`} onClick={() => handleStopCampaign(campaign.camp_id)} className="p-2 rounded-md hover:bg-accent transition-colors text-muted-foreground hover:text-[var(--k-yellow)]">
                          <Pause className="w-4 h-4" />
                        </button>
                      )}
                      {campaign.status === 'scheduled' && (
                        <button data-testid={`start-campaign-${campaign.camp_id}`} onClick={() => handleStartCampaign(campaign.camp_id)} className="p-2 rounded-md hover:bg-accent transition-colors text-muted-foreground hover:text-[var(--k-green)]">
                          <Play className="w-4 h-4" />
                        </button>
                      )}
                      <button data-testid={`delete-campaign-${campaign.camp_id}`} onClick={() => handleDeleteCampaign(campaign.camp_id)} className="p-2 rounded-md hover:bg-accent transition-colors text-muted-foreground hover:text-red-500">
                        <Trash className="w-4 h-4" />
                      </button>
                    </div>
                  </div>

                  {/* Progress */}
                  <div className="mb-4">
                    <div className="flex items-center justify-between mb-1.5">
                      <span className="text-xs text-muted-foreground">Progress</span>
                      <span className="text-xs font-medium text-foreground">{campaign.contacted_count || 0}/{campaign.total_leads || 0}</span>
                    </div>
                    <Progress value={contactRate} className="h-1.5" />
                  </div>

                  {/* Stats */}
                  <div className="grid grid-cols-4 gap-4 pt-4 border-t border-[var(--k-border)]">
                    <div>
                      <div className="text-[10px] text-muted-foreground uppercase tracking-wider">Total Leads</div>
                      <div className="text-lg font-medium text-foreground k-heading">{campaign.total_leads || 0}</div>
                    </div>
                    <div>
                      <div className="text-[10px] text-muted-foreground uppercase tracking-wider">Contacted</div>
                      <div className="text-lg font-medium text-foreground k-heading">{campaign.contacted_count || 0}</div>
                    </div>
                    <div>
                      <div className="text-[10px] text-muted-foreground uppercase tracking-wider">Connected</div>
                      <div className="text-lg font-medium text-foreground k-heading">{campaign.connected_count || 0}</div>
                    </div>
                    <div>
                      <div className="text-[10px] text-muted-foreground uppercase tracking-wider">Converted</div>
                      <div className="text-lg font-medium text-[var(--k-green)] k-heading">{campaign.converted_count || 0} <span className="text-xs font-normal text-muted-foreground">({convRate}%)</span></div>
                    </div>
                  </div>
                </div>
              );
            })
          )}
        </div>
      </ScrollArea>
    </div>
  );
}

function CreateCampaignForm({ onClose, onSuccess, agents }) {
  const [loading, setLoading] = useState(false);
  const [formData, setFormData] = useState({
    name: '',
    agent_id: '',
    schedule: 'Mon-Fri, 10AM-6PM IST',
  });
  const [file, setFile] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!formData.name || !formData.agent_id) return;

    try {
      setLoading(true);
      if (file) {
        await campaignsAPI.upload(formData.agent_id, formData.name, file);
      } else {
        await campaignsAPI.create({
          name: formData.name,
          agent_id: formData.agent_id,
          schedule: formData.schedule,
        });
      }
      onSuccess();
      onClose();
    } catch (error) {
      console.error('Failed to create campaign:', error);
      alert('Failed to create campaign. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4 py-2">
      <div>
        <label className="text-xs font-medium text-muted-foreground mb-1.5 block">Campaign Name</label>
        <input
          data-testid="new-campaign-name"
          type="text"
          placeholder="e.g., Q4 Enterprise Push"
          value={formData.name}
          onChange={(e) => setFormData({ ...formData, name: e.target.value })}
          className="w-full px-3 py-2 text-sm bg-transparent border border-[var(--k-border)] rounded-md text-foreground focus:outline-none focus:ring-1 focus:ring-[var(--k-brand)] placeholder:text-muted-foreground"
          required
        />
      </div>
      <div>
        <label className="text-xs font-medium text-muted-foreground mb-1.5 block">Assign Agent</label>
        <select
          data-testid="campaign-agent-select"
          value={formData.agent_id}
          onChange={(e) => setFormData({ ...formData, agent_id: e.target.value })}
          className="w-full px-3 py-2 text-sm bg-transparent border border-[var(--k-border)] rounded-md text-foreground focus:outline-none focus:ring-1 focus:ring-[var(--k-brand)]"
          required
        >
          <option value="">Select an agent</option>
          {agents.map((agent) => (
            <option key={agent.agent_id} value={agent.agent_id}>{agent.name}</option>
          ))}
        </select>
      </div>
      <div>
        <label className="text-xs font-medium text-muted-foreground mb-1.5 block">Upload Lead List (CSV)</label>
        <div className="border-2 border-dashed border-[var(--k-border)] rounded-md p-6 text-center hover:border-[var(--k-brand)]/30 transition-colors cursor-pointer">
          <input
            type="file"
            accept=".csv"
            onChange={(e) => setFile(e.target.files[0])}
            className="hidden"
            id="campaign-file-upload"
          />
          <label htmlFor="campaign-file-upload" className="cursor-pointer">
            <Users className="w-6 h-6 text-muted-foreground mx-auto mb-2" />
            <p className="text-xs text-muted-foreground">{file ? file.name : 'Drop CSV file or click to upload'}</p>
          </label>
        </div>
      </div>
      <div>
        <label className="text-xs font-medium text-muted-foreground mb-1.5 block">Schedule</label>
        <input
          data-testid="campaign-schedule"
          type="text"
          placeholder="Mon-Fri, 10AM-6PM IST"
          value={formData.schedule}
          onChange={(e) => setFormData({ ...formData, schedule: e.target.value })}
          className="w-full px-3 py-2 text-sm bg-transparent border border-[var(--k-border)] rounded-md text-foreground focus:outline-none focus:ring-1 focus:ring-[var(--k-brand)] placeholder:text-muted-foreground"
        />
      </div>
      <div className="flex justify-end gap-3 pt-2">
        <button
          type="button"
          onClick={onClose}
          className="px-4 py-2 text-sm text-muted-foreground hover:text-foreground transition-colors"
          disabled={loading}
        >
          Cancel
        </button>
        <button
          data-testid="launch-campaign-btn"
          type="submit"
          disabled={loading}
          className="px-4 py-2 rounded-md bg-[var(--k-brand)] text-white text-sm font-medium hover:bg-[var(--k-brand-hover)] transition-all duration-200 disabled:opacity-50"
        >
          {loading ? 'Creating...' : (
            <>
              <Lightning className="w-3.5 h-3.5 inline mr-1" />
              Launch
            </>
          )}
        </button>
      </div>
    </form>
  );
}
