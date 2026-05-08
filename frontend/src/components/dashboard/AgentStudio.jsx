import { useState, useEffect } from "react";
import { Plus, Play, Pause, PencilSimple, Trash, SpeakerHigh, Brain, Lightning, CheckCircle, Phone, X } from "@phosphor-icons/react";
import { agentsAPI, telephonyAPI } from "@/lib/api";
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
    if (!confirm("Are you sure you want to delete this agent?")) return;
    try {
      await agentsAPI.delete(agentId);
      loadAgents();
      setSelectedAgent(null);
    } catch (error) {
      console.error('Failed to delete agent:', error);
    }
  };

  return (
    <div className="h-full flex flex-col bg-background" data-testid="agent-studio">
      {/* Header */}
      <div className="px-8 py-6 border-b border-[var(--k-border)] bg-background/50 backdrop-blur-sm z-10">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-medium k-heading tracking-tight text-foreground">Agent Studio</h1>
            <p className="text-sm text-muted-foreground mt-1">Create and manage your AI voice & chat agents</p>
          </div>
          <Dialog open={showCreate} onOpenChange={setShowCreate}>
            <DialogTrigger asChild>
              <button
                data-testid="create-agent-btn"
                className="flex items-center gap-2 px-4 py-2.5 rounded-md bg-[var(--k-brand)] text-white text-sm font-medium hover:bg-[var(--k-brand-hover)] transition-all duration-200 hover:-translate-y-px shadow-lg shadow-[var(--k-brand)]/20"
              >
                <Plus className="w-4 h-4" />
                Create Agent
              </button>
            </DialogTrigger>
            <DialogContent className="sm:max-w-[600px] bg-[var(--k-surface)] border-[var(--k-border)]">
              <DialogHeader>
                <DialogTitle className="k-heading tracking-tight">Create New Agent</DialogTitle>
              </DialogHeader>
              <CreateAgentForm onClose={() => setShowCreate(false)} onSuccess={loadAgents} />
            </DialogContent>
          </Dialog>
        </div>
      </div>

      {/* Agent Grid */}
      <ScrollArea className="flex-1">
        <div className="px-8 py-8">
          {loading ? (
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
               {[1,2,3].map(i => (
                 <div key={i} className="h-[220px] rounded-xl border border-[var(--k-border)] bg-muted/5 animate-pulse" />
               ))}
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
              {agents.map((agent) => (
                <AgentCard
                  key={agent.agent_id}
                  agent={agent}
                  onEdit={() => setSelectedAgent(agent)}
                  onDelete={() => handleDeleteAgent(agent.agent_id)}
                />
              ))}

              {/* Empty card to create */}
              <button
                data-testid="create-agent-card"
                onClick={() => setShowCreate(true)}
                className="flex flex-col items-center justify-center p-8 rounded-xl border border-dashed border-[var(--k-border)] hover:border-[var(--k-brand)]/30 hover:bg-[var(--k-brand)]/5 transition-all duration-300 min-h-[220px] group bg-background/50"
              >
                <div className="w-12 h-12 rounded-full border-2 border-dashed border-[var(--k-border)] group-hover:border-[var(--k-brand)]/30 flex items-center justify-center mb-4 transition-all group-hover:scale-110">
                  <Plus className="w-5 h-5 text-muted-foreground group-hover:text-[var(--k-brand)] transition-colors" />
                </div>
                <span className="text-sm font-medium text-muted-foreground group-hover:text-foreground transition-colors">Deploy New Agent</span>
              </button>
            </div>
          )}
        </div>
      </ScrollArea>

      {/* Agent Edit/Detail Dialog */}
      <Dialog open={!!selectedAgent} onOpenChange={() => setSelectedAgent(null)}>
        <DialogContent className="sm:max-w-[750px] max-h-[90vh] p-0 overflow-hidden bg-[var(--k-surface)] border-[var(--k-border)] shadow-2xl">
          {selectedAgent && (
            <AgentDetail 
              agent={selectedAgent} 
              onClose={() => setSelectedAgent(null)} 
              onUpdate={loadAgents} 
            />
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}

function AgentCard({ agent, onEdit, onDelete }) {
  const statusColor = agent.status === 'active' ? 'var(--k-green)' : 'var(--k-yellow)';

  return (
    <div
      data-testid={`agent-card-${agent.agent_id}`}
      className="group relative p-6 rounded-xl border border-[var(--k-border)] bg-[var(--k-surface)] hover:bg-[var(--k-surface-elevated)] transition-all duration-300 hover:shadow-xl hover:shadow-[var(--k-brand)]/5 hover:-translate-y-1"
    >
      <div className="flex items-start justify-between mb-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-[var(--k-brand)]/10 flex items-center justify-center group-hover:scale-110 transition-transform">
            <Brain className="w-6 h-6 text-[var(--k-brand)]" weight="duotone" />
          </div>
          <div>
            <h3 className="text-sm font-bold text-foreground k-heading tracking-tight">{agent.name}</h3>
            <span className="text-[10px] uppercase tracking-widest text-muted-foreground font-semibold">{agent.model}</span>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Badge className={`bg-transparent border ${agent.status === 'active' ? 'border-[var(--k-green)]/30 text-[var(--k-green)]' : 'border-[var(--k-yellow)]/30 text-[var(--k-yellow)]'} text-[10px] px-1.5 py-0`}>
             {agent.status}
          </Badge>
        </div>
      </div>

      <p className="text-xs text-muted-foreground mb-6 leading-relaxed line-clamp-3 min-h-[4.5em]">
        {agent.system_prompt || 'No instruction set for this agent.'}
      </p>

      <div className="flex items-center justify-between pt-4 border-t border-[var(--k-border)]">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1.5 px-2 py-1 rounded-md bg-accent/50 text-[10px] font-bold text-muted-foreground uppercase">
            <SpeakerHigh className="w-3.5 h-3.5" />
            {agent.voice}
          </div>
        </div>
        <div className="flex items-center gap-1">
          <button
            onClick={onEdit}
            className="p-2 rounded-md hover:bg-[var(--k-brand)]/10 text-muted-foreground hover:text-[var(--k-brand)] transition-all"
            title="Edit Agent"
          >
            <PencilSimple className="w-4 h-4" />
          </button>
          <button
            onClick={onDelete}
            className="p-2 rounded-md hover:bg-rose-500/10 text-muted-foreground hover:text-rose-400 transition-all"
            title="Delete Agent"
          >
            <Trash className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  );
}

function AgentDetail({ agent, onClose, onUpdate }) {
  const [isSaving, setIsSaving] = useState(false);
  const [isTesting, setIsTesting] = useState(false);
  const [testNumber, setTestNumber] = useState("");
  const [editedAgent, setEditedAgent] = useState({ ...agent });
  const [activeTab, setActiveTab] = useState("config");

  const handleSave = async () => {
    try {
      setIsSaving(true);
      await agentsAPI.update(agent.agent_id, editedAgent);
      onUpdate();
      onClose();
    } catch (error) {
      console.error('Update failed:', error);
      alert('Failed to save changes');
    } finally {
      setIsSaving(false);
    }
  };

  const handleTestCall = async () => {
    if (!testNumber) return alert("Enter a phone number to test");
    try {
      setIsTesting(true);
      await telephonyAPI.outbound({
        to: testNumber,
        agent_id: agent.agent_id
      });
      alert(`Test call initiated to ${testNumber}!`);
    } catch (error) {
      console.error('Test call failed:', error);
      alert('Failed to initiate test call');
    } finally {
      setIsTesting(false);
    }
  };

  return (
    <div className="flex flex-col h-full">
      <div className="px-6 py-4 border-b border-[var(--k-border)] flex items-center justify-between bg-[var(--k-surface-elevated)]">
         <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-[var(--k-brand)] flex items-center justify-center text-white">
               <Brain className="w-5 h-5" weight="bold" />
            </div>
            <div>
              <h3 className="text-base font-bold text-foreground k-heading">{agent.name}</h3>
              <span className="text-[10px] text-muted-foreground uppercase tracking-widest">{agent.agent_id}</span>
            </div>
         </div>
         <button onClick={onClose} className="p-1.5 rounded-full hover:bg-accent text-muted-foreground transition-colors">
            <X className="w-4 h-4" />
         </button>
      </div>

      <ScrollArea className="flex-1 p-6">
        <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
          <TabsList className="bg-accent/50 h-10 p-1 mb-6 rounded-lg w-full max-w-sm">
            <TabsTrigger value="config" className="flex-1 rounded-md text-xs font-semibold data-[state=active]:bg-background data-[state=active]:text-[var(--k-brand)]">Instruction</TabsTrigger>
            <TabsTrigger value="voice" className="flex-1 rounded-md text-xs font-semibold data-[state=active]:bg-background data-[state=active]:text-[var(--k-brand)]">Voice & LLM</TabsTrigger>
            <TabsTrigger value="test" className="flex-1 rounded-md text-xs font-semibold data-[state=active]:bg-background data-[state=active]:text-[var(--k-brand)]">Live Test</TabsTrigger>
          </TabsList>

          <TabsContent value="config" className="space-y-6 animate-fade-up">
            <div className="space-y-2">
              <label className="text-xs font-bold uppercase tracking-widest text-muted-foreground flex items-center justify-between">
                 <span>Agent Personality & Role</span>
                 <Badge className="bg-[var(--k-brand)]/10 text-[var(--k-brand)] border-none">System Prompt</Badge>
              </label>
              <textarea
                value={editedAgent.system_prompt}
                onChange={(e) => setEditedAgent({ ...editedAgent, system_prompt: e.target.value })}
                className="w-full h-48 p-4 text-sm bg-accent/20 border border-[var(--k-border)] rounded-xl font-mono text-foreground focus:outline-none focus:ring-1 focus:ring-[var(--k-brand)] resize-none transition-all"
                placeholder="Ex: You are a friendly sales assistant for Kautilya AI. Your goal is to..."
              />
            </div>
            
            <div className="flex items-center justify-between p-4 rounded-xl border border-[var(--k-border)] bg-accent/10">
              <div>
                <div className="text-sm font-bold text-foreground">Operational Status</div>
                <div className="text-xs text-muted-foreground">Active agents can handle real-time calls</div>
              </div>
              <Switch 
                checked={editedAgent.status === 'active'} 
                onCheckedChange={(val) => setEditedAgent({ ...editedAgent, status: val ? 'active' : 'inactive' })} 
              />
            </div>
          </TabsContent>

          <TabsContent value="voice" className="space-y-6 animate-fade-up">
            <div className="grid grid-cols-2 gap-6">
              <div className="space-y-2">
                <label className="text-xs font-bold uppercase tracking-widest text-muted-foreground">Voice Engine</label>
                <select
                  value={editedAgent.voice}
                  onChange={(e) => setEditedAgent({ ...editedAgent, voice: e.target.value })}
                  className="w-full px-3 py-2.5 text-sm bg-accent/20 border border-[var(--k-border)] rounded-lg text-foreground focus:outline-none"
                >
                  <option value="shubh">Shubh (Indian Male)</option>
                  <option value="priya">Priya (Indian Female)</option>
                  <option value="rahul">Rahul (Deep Voice)</option>
                </select>
              </div>
              <div className="space-y-2">
                <label className="text-xs font-bold uppercase tracking-widest text-muted-foreground">Language</label>
                <div className="px-3 py-2.5 text-sm bg-accent/10 border border-[var(--k-border)] rounded-lg text-muted-foreground flex items-center gap-2">
                   <span className="text-lg">🇮🇳</span> Hindi (India)
                </div>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-6">
              <div className="space-y-2">
                <label className="text-xs font-bold uppercase tracking-widest text-muted-foreground">LLM Back-end</label>
                <select
                  value={editedAgent.model}
                  onChange={(e) => setEditedAgent({ ...editedAgent, model: e.target.value })}
                  className="w-full px-3 py-2.5 text-sm bg-accent/20 border border-[var(--k-border)] rounded-lg text-foreground focus:outline-none"
                >
                  <option value="kautilya-daily">Kautilya Daily (Llama 3.3)</option>
                  <option value="kautilya-pro">Kautilya Pro (Nemotron-3)</option>
                  <option value="coder">DeepSeek-V4 (Logic Heavy)</option>
                </select>
              </div>
              <div className="space-y-2">
                <label className="text-xs font-bold uppercase tracking-widest text-muted-foreground">Creativity (Temp)</label>
                <input 
                  type="range" min="0" max="1" step="0.1" 
                  value={editedAgent.temperature} 
                  onChange={(e) => setEditedAgent({...editedAgent, temperature: parseFloat(e.target.value)})}
                  className="w-full mt-2 accent-[var(--k-brand)]"
                />
                <div className="flex justify-between text-[10px] text-muted-foreground font-mono">
                  <span>Deterministic</span>
                  <span>{editedAgent.temperature}</span>
                  <span>Creative</span>
                </div>
              </div>
            </div>
          </TabsContent>

          <TabsContent value="test" className="space-y-6 animate-fade-up">
             <div className="p-6 rounded-2xl border border-[var(--k-brand)]/20 bg-[var(--k-brand)]/5">
                <div className="flex items-center gap-3 mb-4">
                  <div className="w-10 h-10 rounded-full bg-[var(--k-brand)]/20 flex items-center justify-center">
                    <Lightning className="w-5 h-5 text-[var(--k-brand)]" weight="duotone" />
                  </div>
                  <div>
                    <h4 className="text-sm font-bold text-foreground">Instant Telephony Test</h4>
                    <p className="text-xs text-muted-foreground">Call your number to talk with this agent live.</p>
                  </div>
                </div>

                <div className="flex gap-3">
                  <input
                    type="tel"
                    placeholder="Enter your number (with +91)"
                    value={testNumber}
                    onChange={(e) => setTestNumber(e.target.value)}
                    className="flex-1 px-4 py-3 text-sm bg-background border border-[var(--k-border)] rounded-xl text-foreground focus:ring-1 focus:ring-[var(--k-brand)]"
                  />
                  <button
                    onClick={handleTestCall}
                    disabled={isTesting || !testNumber}
                    className="flex items-center gap-2 px-6 py-3 rounded-xl bg-[var(--k-brand)] text-white text-sm font-bold hover:bg-[var(--k-brand-hover)] transition-all shadow-lg shadow-[var(--k-brand)]/20 disabled:opacity-50"
                  >
                    {isTesting ? <Lightning className="w-4 h-4 animate-spin" /> : <Phone className="w-4 h-4" />}
                    {isTesting ? 'Calling...' : 'Call Me'}
                  </button>
                </div>
                <p className="mt-4 text-[10px] text-muted-foreground flex items-center gap-1.5">
                   <Lightning className="w-3 h-3 text-[var(--k-brand)]" />
                   Uses master SIP credentials for instantaneous routing.
                </p>
             </div>
          </TabsContent>
        </Tabs>
      </ScrollArea>

      <div className="px-6 py-4 border-t border-[var(--k-border)] bg-[var(--k-surface-elevated)] flex justify-end gap-3">
        <button
          onClick={onClose}
          className="px-6 py-2 text-sm font-medium text-muted-foreground hover:text-foreground transition-colors"
        >
          Discard
        </button>
        <button
          onClick={handleSave}
          disabled={isSaving}
          className="flex items-center gap-2 px-8 py-2 rounded-lg bg-[var(--k-brand)] text-white text-sm font-bold hover:bg-[var(--k-brand-hover)] transition-all shadow-lg shadow-[var(--k-brand)]/20 disabled:opacity-50"
        >
          {isSaving ? 'Saving...' : 'Save Changes'}
          {!isSaving && <CheckCircle className="w-4 h-4" />}
        </button>
      </div>
    </div>
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
      alert('Failed to create agent');
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4 py-4">
      <div className="space-y-1.5">
        <label className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground">Agent Display Name</label>
        <input
          data-testid="new-agent-name"
          type="text"
          placeholder="e.g., Sales Closer"
          value={formData.name}
          onChange={(e) => setFormData({ ...formData, name: e.target.value })}
          className="w-full px-4 py-3 text-sm bg-accent/20 border border-[var(--k-border)] rounded-xl text-foreground focus:ring-1 focus:ring-[var(--k-brand)]"
          required
        />
      </div>
      <div className="space-y-1.5">
        <label className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground">Core Instructions</label>
        <textarea
          data-testid="new-agent-prompt"
          placeholder="Describe how the agent should behave..."
          value={formData.system_prompt}
          onChange={(e) => setFormData({ ...formData, system_prompt: e.target.value })}
          className="w-full h-32 p-4 text-sm bg-accent/20 border border-[var(--k-border)] rounded-xl text-foreground focus:ring-1 focus:ring-[var(--k-brand)] resize-none"
          required
        />
      </div>
      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-1.5">
          <label className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground">Brain Model</label>
          <select
            data-testid="new-agent-model"
            value={formData.model}
            onChange={(e) => setFormData({ ...formData, model: e.target.value })}
            className="w-full px-4 py-3 text-sm bg-accent/20 border border-[var(--k-border)] rounded-xl text-foreground"
          >
            <option value="kautilya-daily">Daily (Llama 3.3)</option>
            <option value="kautilya-pro">Pro (Nemotron-3)</option>
            <option value="coder">Coder (DeepSeek)</option>
          </select>
        </div>
        <div className="space-y-1.5">
          <label className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground">Voice Accent</label>
          <select
            data-testid="new-agent-voice"
            value={formData.voice}
            onChange={(e) => setFormData({ ...formData, voice: e.target.value })}
            className="w-full px-4 py-3 text-sm bg-accent/20 border border-[var(--k-border)] rounded-xl text-foreground"
          >
            <option value="shubh">Shubh (Hindi)</option>
            <option value="priya">Priya (Hindi)</option>
            <option value="rahul">Rahul (Deep)</option>
          </select>
        </div>
      </div>
      <div className="flex justify-end gap-3 pt-6">
        <button
          data-testid="cancel-create-agent"
          type="button"
          onClick={onClose}
          className="px-6 py-2 text-sm font-medium text-muted-foreground"
          disabled={loading}
        >
          Cancel
        </button>
        <button
          data-testid="save-agent-btn"
          type="submit"
          disabled={loading}
          className="px-8 py-2 rounded-lg bg-[var(--k-brand)] text-white text-sm font-bold hover:bg-[var(--k-brand-hover)] shadow-lg shadow-[var(--k-brand)]/20"
        >
          {loading ? 'Deploying...' : 'Deploy Agent'}
        </button>
      </div>
    </form>
  );
}
