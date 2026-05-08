import { useState, useEffect } from "react";
import { Plus, Play, Pause, PencilSimple, Trash, SpeakerHigh, Brain, Lightning } from "@phosphor-icons/react";
import { agentsAPI } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Switch } from "@/components/ui/switch";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

export default function AgentStudio() {
  const [agents, setAgents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedAgent, setSelectedAgent] = useState(null);
  const [showCreate, setShowCreate] = useState(false);

  useEffect(() => {
    loadAgents();
  }, []);

  const loadAgents = async () => {
    try {
      setLoading(true);
      const data = await agentsAPI.list();
      setAgents(data.agents || []);
    } catch (error) {
      console.error('Failed to load agents:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteAgent = async (agentId) => {
    try {
      await agentsAPI.delete(agentId);
      loadAgents();
      setSelectedAgent(null);
    } catch (error) {
      console.error('Failed to delete agent:', error);
    }
  };

  return (
    <div className="h-full" data-testid="agent-studio">
      {/* Header */}
      <div className="px-8 py-6 border-b border-[var(--k-border)]">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-medium k-heading tracking-tight text-foreground">Agent Studio</h1>
            <p className="text-sm text-muted-foreground mt-1">Create and manage your AI voice & chat agents</p>
          </div>
          <Dialog open={showCreate} onOpenChange={setShowCreate}>
            <DialogTrigger asChild>
              <button
                data-testid="create-agent-btn"
                className="flex items-center gap-2 px-4 py-2.5 rounded-md bg-[var(--k-brand)] text-white text-sm font-medium hover:bg-[var(--k-brand-hover)] transition-all duration-200 hover:-translate-y-px"
              >
                <Plus className="w-4 h-4" />
                Create Agent
              </button>
            </DialogTrigger>
            <DialogContent className="sm:max-w-[600px]">
              <DialogHeader>
                <DialogTitle className="k-heading tracking-tight">Create New Agent</DialogTitle>
              </DialogHeader>
              <CreateAgentForm onClose={() => setShowCreate(false)} onSuccess={loadAgents} />
            </DialogContent>
          </Dialog>
        </div>
      </div>

      {/* Agent Grid */}
      <ScrollArea className="h-[calc(100vh-120px)]">
        <div className="px-8 py-6">
          {loading ? (
            <div className="text-center py-8 text-sm text-muted-foreground">Loading agents...</div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
              {agents.map((agent) => (
                <AgentCard
                  key={agent.agent_id}
                  agent={agent}
                  onSelect={() => setSelectedAgent(agent)}
                  onDelete={() => handleDeleteAgent(agent.agent_id)}
                />
              ))}

              {/* Empty card to create */}
              <button
                data-testid="create-agent-card"
                onClick={() => setShowCreate(true)}
                className="flex flex-col items-center justify-center p-8 rounded-md border border-dashed border-[var(--k-border)] hover:border-[var(--k-brand)]/30 hover:bg-[var(--k-brand)]/5 transition-all duration-200 min-h-[220px] group"
              >
                <div className="w-12 h-12 rounded-full border-2 border-dashed border-[var(--k-border)] group-hover:border-[var(--k-brand)]/30 flex items-center justify-center mb-3 transition-colors">
                  <Plus className="w-5 h-5 text-muted-foreground group-hover:text-[var(--k-brand)] transition-colors" />
                </div>
                <span className="text-sm font-medium text-muted-foreground group-hover:text-foreground transition-colors">Create New Agent</span>
              </button>
            </div>
          )}
        </div>
      </ScrollArea>

      {/* Agent Detail Dialog */}
      <Dialog open={!!selectedAgent} onOpenChange={() => setSelectedAgent(null)}>
        <DialogContent className="sm:max-w-[700px] max-h-[85vh] overflow-hidden">
          <DialogHeader>
            <DialogTitle className="k-heading tracking-tight">{selectedAgent?.name}</DialogTitle>
          </DialogHeader>
          {selectedAgent && <AgentDetail agent={selectedAgent} />}
        </DialogContent>
      </Dialog>
    </div>
  );
}

function AgentCard({ agent, onSelect, onDelete }) {
  const statusColor = agent.status === 'active' ? 'var(--k-green)' : 'var(--k-yellow)';

  return (
    <div
      data-testid={`agent-card-${agent.agent_id}`}
      className="p-5 rounded-md border border-[var(--k-border)] bg-[var(--k-surface)] hover:bg-[var(--k-surface-elevated)] transition-all duration-200 cursor-pointer group"
    >
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-3" onClick={onSelect}>
          <div className="w-10 h-10 rounded-md bg-[var(--k-brand)]/10 flex items-center justify-center">
            <Brain className="w-5 h-5 text-[var(--k-brand)]" weight="duotone" />
          </div>
          <div>
            <h3 className="text-sm font-medium text-foreground k-heading">{agent.name}</h3>
            <span className="text-xs text-muted-foreground">{agent.model}</span>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1.5">
            <div className="w-2 h-2 rounded-full" style={{ background: statusColor }} />
            <span className="text-[10px] uppercase tracking-wider text-muted-foreground font-medium">{agent.status}</span>
          </div>
          <button
            onClick={(e) => { e.stopPropagation(); onDelete(); }}
            className="p-1.5 rounded-md hover:bg-red-500/10 hover:text-red-500 text-muted-foreground transition-colors"
          >
            <Trash className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      <p className="text-xs text-muted-foreground mb-4 leading-relaxed line-clamp-2">{agent.system_prompt?.substring(0, 100) || 'No description'}</p>

      <div className="flex items-center justify-between pt-3 border-t border-[var(--k-border)]">
        <div className="flex items-center gap-4">
          <div>
            <div className="text-xs text-muted-foreground">Calls</div>
            <div className="text-sm font-medium text-foreground">{agent.call_count || 0}</div>
          </div>
        </div>
        <div className="flex items-center gap-1.5 px-2 py-1 rounded-md bg-accent text-xs text-muted-foreground">
          <SpeakerHigh className="w-3 h-3" />
          {agent.voice}
        </div>
      </div>
    </div>
  );
}

function AgentDetail({ agent }) {
  return (
    <ScrollArea className="max-h-[70vh]">
      <Tabs defaultValue="config" className="w-full">
        <TabsList className="bg-transparent h-9 p-0 gap-4 mb-4">
          <TabsTrigger value="config" className="bg-transparent data-[state=active]:bg-transparent data-[state=active]:shadow-none px-0 pb-2 rounded-none border-b-2 border-transparent data-[state=active]:border-[var(--k-brand)] text-xs font-medium">Configuration</TabsTrigger>
          <TabsTrigger value="voice" className="bg-transparent data-[state=active]:bg-transparent data-[state=active]:shadow-none px-0 pb-2 rounded-none border-b-2 border-transparent data-[state=active]:border-[var(--k-brand)] text-xs font-medium">Voice Settings</TabsTrigger>
        </TabsList>

        <TabsContent value="config" className="space-y-4">
          <div>
            <label className="text-xs font-medium text-muted-foreground mb-1.5 block">System Prompt</label>
            <textarea
              data-testid="agent-system-prompt"
              defaultValue={agent.system_prompt || ''}
              className="w-full h-32 p-3 text-sm bg-[var(--k-surface-elevated)] border border-[var(--k-border)] rounded-md font-mono text-foreground focus:outline-none focus:ring-1 focus:ring-[var(--k-brand)] resize-none"
            />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="text-xs font-medium text-muted-foreground mb-1.5 block">Model</label>
              <div className="px-3 py-2 text-sm border border-[var(--k-border)] rounded-md text-foreground bg-[var(--k-surface-elevated)]">{agent.model}</div>
            </div>
            <div>
              <label className="text-xs font-medium text-muted-foreground mb-1.5 block">Temperature</label>
              <div className="px-3 py-2 text-sm border border-[var(--k-border)] rounded-md text-foreground bg-[var(--k-surface-elevated)]">{agent.temperature}</div>
            </div>
          </div>
          <div className="flex items-center justify-between p-3 rounded-md border border-[var(--k-border)]">
            <div>
              <div className="text-sm font-medium text-foreground">Active</div>
              <div className="text-xs text-muted-foreground">Enable or disable this agent</div>
            </div>
            <Switch data-testid="agent-active-toggle" defaultChecked={agent.status === 'active'} />
          </div>
        </TabsContent>

        <TabsContent value="voice" className="space-y-4">
          <div>
            <label className="text-xs font-medium text-muted-foreground mb-1.5 block">Voice Model</label>
            <div className="px-3 py-2 text-sm border border-[var(--k-border)] rounded-md text-foreground bg-[var(--k-surface-elevated)]">{agent.voice}</div>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="text-xs font-medium text-muted-foreground mb-1.5 block">Language</label>
              <div className="px-3 py-2 text-sm border border-[var(--k-border)] rounded-md text-foreground bg-[var(--k-surface-elevated)]">{agent.language}</div>
            </div>
            <div>
              <label className="text-xs font-medium text-muted-foreground mb-1.5 block">Agent Type</label>
              <div className="px-3 py-2 text-sm border border-[var(--k-border)] rounded-md text-foreground bg-[var(--k-surface-elevated)]">{agent.agent_type}</div>
            </div>
          </div>
          <div className="flex items-center justify-between p-3 rounded-md border border-[var(--k-border)]">
            <div>
              <div className="text-sm font-medium text-foreground">Interruption Mode</div>
              <div className="text-xs text-muted-foreground">Allow user to interrupt the agent mid-sentence</div>
            </div>
            <Switch data-testid="interruption-toggle" defaultChecked={agent.interruption_mode === 'allow'} />
          </div>
        </TabsContent>
      </Tabs>
    </ScrollArea>
  );
}

function CreateAgentForm({ onClose, onSuccess }) {
  const [loading, setLoading] = useState(false);
  const [formData, setFormData] = useState({
    name: '',
    system_prompt: '',
    model: 'kautilya-daily',
    voice: 'shubh',
    language: 'hi-IN',
    agent_type: 'inbound',
    temperature: 0.7,
  });

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!formData.name) return;

    try {
      setLoading(true);
      await agentsAPI.create(formData);
      onSuccess();
      onClose();
    } catch (error) {
      console.error('Failed to create agent:', error);
      alert('Failed to create agent. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4 py-2">
      <div>
        <label className="text-xs font-medium text-muted-foreground mb-1.5 block">Agent Name</label>
        <input
          data-testid="new-agent-name"
          type="text"
          placeholder="e.g., Sales Closer"
          value={formData.name}
          onChange={(e) => setFormData({ ...formData, name: e.target.value })}
          className="w-full px-3 py-2 text-sm bg-transparent border border-[var(--k-border)] rounded-md text-foreground focus:outline-none focus:ring-1 focus:ring-[var(--k-brand)] placeholder:text-muted-foreground"
          required
        />
      </div>
      <div>
        <label className="text-xs font-medium text-muted-foreground mb-1.5 block">System Prompt</label>
        <textarea
          data-testid="new-agent-prompt"
          placeholder="Define the agent's behavior and personality..."
          value={formData.system_prompt}
          onChange={(e) => setFormData({ ...formData, system_prompt: e.target.value })}
          className="w-full h-24 p-3 text-sm bg-transparent border border-[var(--k-border)] rounded-md text-foreground focus:outline-none focus:ring-1 focus:ring-[var(--k-brand)] resize-none placeholder:text-muted-foreground"
          required
        />
      </div>
      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="text-xs font-medium text-muted-foreground mb-1.5 block">Model</label>
          <select
            data-testid="new-agent-model"
            value={formData.model}
            onChange={(e) => setFormData({ ...formData, model: e.target.value })}
            className="w-full px-3 py-2 text-sm bg-transparent border border-[var(--k-border)] rounded-md text-foreground focus:outline-none focus:ring-1 focus:ring-[var(--k-brand)]"
          >
            <option value="kautilya-daily">Kautilya Daily</option>
            <option value="kautilya-pro">Kautilya Pro</option>
            <option value="coder">Coder</option>
          </select>
        </div>
        <div>
          <label className="text-xs font-medium text-muted-foreground mb-1.5 block">Voice</label>
          <select
            data-testid="new-agent-voice"
            value={formData.voice}
            onChange={(e) => setFormData({ ...formData, voice: e.target.value })}
            className="w-full px-3 py-2 text-sm bg-transparent border border-[var(--k-border)] rounded-md text-foreground focus:outline-none focus:ring-1 focus:ring-[var(--k-brand)]"
          >
            <option value="shubh">Shubh (Hindi)</option>
            <option value="priya">Priya (Hindi)</option>
            <option value="rahul">Rahul (Hindi)</option>
          </select>
        </div>
      </div>
      <div className="flex justify-end gap-3 pt-2">
        <button
          data-testid="cancel-create-agent"
          type="button"
          onClick={onClose}
          className="px-4 py-2 text-sm text-muted-foreground hover:text-foreground transition-colors"
          disabled={loading}
        >
          Cancel
        </button>
        <button
          data-testid="save-agent-btn"
          type="submit"
          disabled={loading}
          className="px-4 py-2 rounded-md bg-[var(--k-brand)] text-white text-sm font-medium hover:bg-[var(--k-brand-hover)] transition-all duration-200 disabled:opacity-50"
        >
          {loading ? 'Creating...' : 'Create Agent'}
        </button>
      </div>
    </form>
  );
}
