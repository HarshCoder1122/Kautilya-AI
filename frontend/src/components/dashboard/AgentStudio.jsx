import { useState, useEffect } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { Plus, PencilSimple, Trash, SpeakerHigh, Brain, Lightning, CheckCircle, Phone, X, UploadSimple, LinkSimple, FileText, ChatCircleText, Clock, Globe, CaretLeft, Microphone } from "@phosphor-icons/react";
import { LiveKitVoice } from "@/components/chat/LiveKitVoice";
import { agentsAPI, telephonyAPI, ttsAPI, integrationsAPI } from "../../lib/api";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Switch } from "@/components/ui/switch";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

const GEMINI_LIVE_VOICES = [
  { value: "Puck", label: "Puck" },
  { value: "Charon", label: "Charon" },
  { value: "Kore", label: "Kore" },
  { value: "Fenrir", label: "Fenrir" },
  { value: "Aoede", label: "Aoede" }
];

const STANDARD_VOICES = {
  revealiq: [
    { value: "revealiq:af_heart", label: "Priya (RevealIQ Hindi/English Female)" },
    { value: "revealiq:hf_alpha", label: "Aarav (RevealIQ Hindi Male)" },
    { value: "revealiq:hf_beta", label: "Ishaan (RevealIQ Hindi Male)" },
    { value: "revealiq:hm_omega", label: "Kabir (RevealIQ Hindi Male)" },
    { value: "revealiq:hm_psi", label: "Vihaan (RevealIQ Hindi Male)" },
    { value: "revealiq:af_bella", label: "Ananya (RevealIQ English Female)" },
    { value: "revealiq:af_nicole", label: "Nicole (RevealIQ English Female)" },
    { value: "revealiq:af_sky", label: "Sky (RevealIQ English Female)" },
    { value: "revealiq:am_adam", label: "Arjun (RevealIQ English Male)" },
    { value: "revealiq:am_michael", label: "Michael (RevealIQ English Male)" }
  ],
  sarvam: [
    { value: "sarvam:shubh", label: "Shubh (Sarvam Bulbul v3)" },
    { value: "sarvam:priya", label: "Priya (Sarvam Bulbul v3)" },
    { value: "sarvam:rahul", label: "Rahul (Sarvam Bulbul v3)" },
    { value: "sarvam:deepa", label: "Deepa (Sarvam Bulbul v3)" },
    { value: "sarvam:amit", label: "Amit (Sarvam Bulbul v3)" },
    { value: "sarvam:suraj", label: "Suraj (Sarvam Bulbul v3)" },
    { value: "sarvam:kiran", label: "Kiran (Sarvam Bulbul v3)" },
    { value: "sarvam:smita", label: "Smita (Sarvam Bulbul v3)" }
  ],
  elevenlabs: [
    { value: "elevenlabs:21m00Tcm4TlvDq8ikWAM", label: "Rachel (ElevenLabs Female)" },
    { value: "elevenlabs:AZnzlk1XhkUvS5ch7s7i", label: "Domi (ElevenLabs Female)" },
    { value: "elevenlabs:EXAVITQu4vr4xnSDxMaL", label: "Bella (ElevenLabs Female)" },
    { value: "elevenlabs:ErXw9S1aaH7HBy8S4H2u", label: "Antoni (ElevenLabs Male)" },
    { value: "elevenlabs:Lcf7m3M63S7G38m7V8p7", label: "Charlie (ElevenLabs Male)" },
    { value: "elevenlabs:pNInz6obpgqj9YJElM3j", label: "Adam (ElevenLabs Male)" },
    { value: "elevenlabs:IKne3meq5aSn9XLyUdCD", label: "Charlie V2 (ElevenLabs Male)" },
    { value: "elevenlabs:JBF2zCBsd21rIBHNCm1X", label: "Josh (ElevenLabs Male)" }
  ],
  cartesia: [
    { value: "cartesia:79a125e8-cd45-4c13-8a25-4eede72224e5", label: "Emma (Cartesia English Female)" },
    { value: "cartesia:a0e9987c-abaf-4752-909e-3199cd709935", label: "Jessica (Cartesia English Female)" },
    { value: "cartesia:248be419-caca-407b-83fa-ee92ae248a37", label: "Ryan (Cartesia English Male)" },
    { value: "cartesia:156fb38d-1355-4080-9286-90b56b3e945c", label: "Marcus (Cartesia English Male)" },
    { value: "cartesia:63836798-251c-435b-80a5-f85c6f376cf9", label: "Aditya (Cartesia Hindi Male)" },
    { value: "cartesia:b822d645-0d29-450e-b8d2-8b9a7c376cf9", label: "Kavya (Cartesia Hindi Female)" }
  ]
};

export default function AgentStudio() {
  const navigate = useNavigate();
  const [agents, setAgents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [studioError, setStudioError] = useState("");

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
    } catch (error) {
      console.error('Failed to delete agent:', error);
    }
  };

  const handleEditAgent = (agent) => {
    setStudioError("");
    navigate(`/dashboard/agents/${agent.agent_id}`);
  };

  return (
    <div className="h-full flex flex-col bg-background" data-testid="agent-studio">
      {/* Header */}
      <div className="px-4 sm:px-8 py-6 border-b border-[var(--k-border)] bg-background/50 backdrop-blur-sm z-10">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl font-medium k-heading tracking-tight text-foreground">Agent Studio</h1>
            <p className="text-sm text-muted-foreground mt-1">Create and manage your AI voice & chat agents</p>
            {studioError && <p className="text-xs text-rose-400 mt-2">{studioError}</p>}
          </div>
          <Dialog open={showCreate} onOpenChange={setShowCreate}>
            <DialogTrigger asChild>
              <button
                data-testid="create-agent-btn"
                className="flex items-center justify-center gap-2 px-4 py-2.5 rounded-md bg-[var(--k-brand)] text-white text-sm font-medium hover:bg-[var(--k-brand-hover)] transition-all duration-200 hover:-translate-y-px shadow-lg shadow-[var(--k-brand)]/20 w-full sm:w-auto"
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
        <div className="px-4 sm:px-8 py-8">
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
                  onEdit={() => handleEditAgent(agent)}
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

    </div>
  );
}

// Full-page wrapper rendered at /dashboard/agents/:agentId
export function AgentDetailPage() {
  const { agentId } = useParams();
  const navigate = useNavigate();
  const [agent, setAgent] = useState(null);
  const [error, setError] = useState("");

  const fetchAgent = async () => {
    try {
      setError("");
      const data = await agentsAPI.get(agentId);
      setAgent(data);
    } catch (e) {
      setError(e.response?.data?.error || e.message || "Failed to load agent");
    }
  };

  useEffect(() => { fetchAgent(); /* eslint-disable-next-line */ }, [agentId]);

  if (error) {
    return (
      <div className="h-full flex flex-col items-center justify-center text-center p-8">
        <p className="text-sm text-rose-400 mb-4">{error}</p>
        <button onClick={() => navigate('/dashboard')} className="px-4 py-2 rounded-md bg-accent text-sm">Back to Agents</button>
      </div>
    );
  }
  if (!agent) {
    return <div className="h-full flex items-center justify-center text-sm text-muted-foreground">Loading agent…</div>;
  }

  return (
    <div className="h-full flex flex-col bg-background">
      <div className="px-6 py-3 border-b border-[var(--k-border)] flex items-center gap-3">
        <button
          onClick={() => navigate('/dashboard')}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-md hover:bg-accent text-sm text-muted-foreground hover:text-foreground transition-colors"
        >
          <CaretLeft className="w-4 h-4" /> Agents
        </button>
        <span className="text-sm text-muted-foreground">/</span>
        <span className="text-sm font-medium text-foreground">{agent.name}</span>
      </div>
      <div className="flex-1 min-h-0 overflow-hidden">
        <AgentDetail
          agent={agent}
          onClose={() => navigate('/dashboard')}
          onUpdate={fetchAgent}
        />
      </div>
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
  const [webCallOpen, setWebCallOpen] = useState(false);
  const [isPreviewing, setIsPreviewing] = useState(false);
  const [testNumber, setTestNumber] = useState("");
  const [editedAgent, setEditedAgent] = useState({ ...agent });
  const [activeTab, setActiveTab] = useState("config");
  const [kbFiles, setKbFiles] = useState([]);
  const [kbUrl, setKbUrl] = useState("");
  const [kbLoading, setKbLoading] = useState(false);
  const [crawlMaxPages, setCrawlMaxPages] = useState(50);
  const [logs, setLogs] = useState([]);
  const [logsLoading, setLogsLoading] = useState(false);
  const [testMessages, setTestMessages] = useState([]);
  const [testInput, setTestInput] = useState("");
  const [isChatTesting, setIsChatTesting] = useState(false);
  const [testNotice, setTestNotice] = useState("");
  const [integrationsStatus, setIntegrationsStatus] = useState({
    hubspot: false,
    zoho: false,
    google_calendar: false,
    gmail: false,
    whatsapp: false,
    slack: false
  });

  // Per-agent integration allow-list. Undefined = enabled (default-on), so
  // existing agents keep working; toggling a switch off opts that agent out.
  const integrationOn = (key) => editedAgent.integrations?.[key] !== false;
  const toggleIntegration = (key, val) => setEditedAgent({
    ...editedAgent,
    integrations: { ...(editedAgent.integrations || {}), [key]: val },
  });

	  useEffect(() => {
	    if (activeTab === "knowledge") loadKnowledge();
	    if (activeTab === "logs") loadLogs();
	    if (activeTab === "tools") loadIntegrations();
	    // The loaders are local actions; re-run only when the selected tab/agent changes.
	    // eslint-disable-next-line react-hooks/exhaustive-deps
	  }, [activeTab, agent.agent_id]);

  const loadIntegrations = async () => {
    try {
      const data = await integrationsAPI.list();
      const statusMap = {
        hubspot: false,
        zoho: false,
        google_calendar: false,
        gmail: false,
        whatsapp: false,
        slack: false
      };
      if (data && data.integrations) {
        data.integrations.forEach(item => {
          if (item.id in statusMap) {
            statusMap[item.id] = !!item.connected;
          }
        });
      }
      setIntegrationsStatus(statusMap);
    } catch (err) {
      console.error("Failed to load integrations status:", err);
    }
  };

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
    if (!testNumber) return alert("Enter a phone number to test (e.g. +919876543210)");
    try {
      setIsTesting(true);
      const result = await telephonyAPI.outbound({ to: testNumber, agent_id: agent.agent_id });
      // Surface remaining free quota so the user knows when PRO kicks in.
      const left = result?.calls_remaining;
      const remainingMsg = (left != null)
        ? `\n\nYou have ${left} free test call${left === 1 ? '' : 's'} left.`
        : '';
      alert(`✅ Call initiated to ${testNumber}!\nCall ID: ${result?.call_id || 'pending'}${remainingMsg}`);
    } catch (error) {
      const status = error.response?.status;
      const data = error.response?.data || {};
      // Free-call quota exhausted → PRO upsell.
      if (status === 402 || data.code === 'upgrade_required') {
        const go = window.confirm(
          `${data.message || "You've used all your free test calls. Upgrade to PRO for unlimited outbound mobile calling."}\n\nGo to Billing to upgrade now?`
        );
        if (go) window.location.href = '/dashboard/billing';
        return;
      }
      const msg = data.error || error.message || 'Call failed';
      if (msg.includes('telephony') || msg.includes('provider') || msg.includes('config') || msg.includes('Vobiz') || msg.includes('Exotel')) {
        alert(`📞 Telephony not configured.\n\nTo enable calls:\n1. Go to Dashboard → Settings → Telephony\n2. Add your Exotel or Vobiz credentials\n3. Then retry the call.\n\nError: ${msg}`);
      } else {
        alert(`Call failed: ${msg}`);
      }
    } finally {
      setIsTesting(false);
    }
  };

  const handleVoicePreview = async () => {
    try {
      setIsPreviewing(true);
      const voiceStr = editedAgent.voice || 'sarvam:shubh';
      let provider = 'sarvam';
      let voiceId = voiceStr;
      if (voiceStr.includes(':')) {
        const parts = voiceStr.split(':');
        provider = parts[0];
        voiceId = parts[1];
      }
      
      const audioBlob = await agentsAPI.previewVoice({
        voice: voiceId,
        provider: provider,
        text: editedAgent.welcome_message || 'Namaste! This is a preview of how my voice will sound on the call.',
      });
      const audio = new Audio(URL.createObjectURL(audioBlob));
      const playPromise = audio.play();
      if (playPromise !== undefined) {
        playPromise.catch(error => {
          console.warn("[AgentStudio] Audio play interrupted or blocked:", error);
        });
      }
    } catch (error) {
      console.error('Voice preview failed:', error);
      alert(error.response?.data?.error || 'Voice preview failed');
    } finally {
      setIsPreviewing(false);
    }
  };

  const loadKnowledge = async () => {
    try {
      setKbLoading(true);
      const data = await agentsAPI.getKB(agent.agent_id);
      setKbFiles(data.knowledge_base || []);
    } catch (error) {
      console.error('Failed to load knowledge:', error);
    } finally {
      setKbLoading(false);
    }
  };

  const handleKbUpload = async (event) => {
    const files = Array.from(event.target.files || []);
    if (!files.length) return;
    try {
      setKbLoading(true);
      await agentsAPI.uploadKB(agent.agent_id, files);
      event.target.value = "";
      await loadKnowledge();
    } catch (error) {
      alert(error.response?.data?.error || 'Upload failed');
    } finally {
      setKbLoading(false);
    }
  };

  const handleAddKbUrl = async () => {
    if (!kbUrl.trim()) return;
    try {
      setKbLoading(true);
      await agentsAPI.addKBUrl(agent.agent_id, kbUrl.trim());
      setKbUrl("");
      await loadKnowledge();
    } catch (error) {
      alert(error.response?.data?.error || 'Website indexing failed');
    } finally {
      setKbLoading(false);
    }
  };

  const handleCrawlSite = async () => {
    const url = kbUrl.trim();
    if (!url) return;
    if (!confirm(`Crawl up to ${crawlMaxPages} pages from ${url}? This may take a few minutes.`)) return;
    try {
      setKbLoading(true);
      const result = await agentsAPI.crawlKBSite(agent.agent_id, url, crawlMaxPages);
      setKbUrl("");
      alert(`✅ Crawled ${result.pages_added}/${result.pages_attempted} pages (${result.errors} errors).`);
      await loadKnowledge();
    } catch (error) {
      alert(error.response?.data?.error || 'Crawl failed');
    } finally {
      setKbLoading(false);
    }
  };

  const handleDeleteKb = async (fileId) => {
    if (!confirm("Delete this knowledge file?")) return;
    try {
      await agentsAPI.deleteKBFile(agent.agent_id, fileId);
      setKbFiles(prev => prev.filter(file => file.id !== fileId));
    } catch (error) {
      alert(error.response?.data?.error || 'Delete failed');
    }
  };

  const loadLogs = async () => {
    try {
      setLogsLoading(true);
      const data = await agentsAPI.getLogs(agent.agent_id);
      setLogs(data.logs || []);
    } catch (error) {
      console.error('Failed to load logs:', error);
      setLogs([]);
    } finally {
      setLogsLoading(false);
    }
  };

  const handleChatTest = async () => {
    const text = testInput.trim();
    if (!text || isChatTesting) return;
    const nextMessages = [...testMessages, { role: 'user', content: text }];
    const assistantMsg = { role: 'assistant', content: '' };
    setTestMessages([...nextMessages, assistantMsg]);
    setTestInput("");
    setIsChatTesting(true);
    try {
      const response = await agentsAPI.chat(agent.agent_id, nextMessages.slice(-10));
      if (!response.ok || !response.body) throw new Error(response.statusText || 'Agent chat failed');
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let answer = "";
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split(/\r?\n/);
        buffer = lines.pop() || "";
        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          const raw = line.slice(6).trim();
          if (!raw || raw === '[DONE]') continue;
          try {
            const parsed = JSON.parse(raw);
            const chunk = parsed.content || parsed.chunk || "";
            if (chunk) {
              answer += chunk;
              setTestMessages(prev => prev.map((msg, index) => (
                index === prev.length - 1 ? { ...msg, content: answer } : msg
              )));
            }
          } catch (e) {
            answer += raw;
          }
        }
      }
      setTestNotice("Text test saved to recent logs.");
    } catch (error) {
      setTestMessages(prev => prev.map((msg, index) => (
        index === prev.length - 1 ? { ...msg, content: `Error: ${error.message}` } : msg
      )));
    } finally {
      setIsChatTesting(false);
    }
  };

  return (
    <div className="flex flex-col" style={{height: '100%', minHeight: 0}}>
      <div className="px-6 py-4 border-b border-[var(--k-border)] flex items-center justify-between bg-[var(--k-surface-elevated)] flex-shrink-0">
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

      <ScrollArea className="flex-1 overflow-auto" style={{minHeight: 0}}>
        <div className="p-6">
        <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
          <TabsList className="bg-accent/50 h-auto p-1 mb-6 rounded-lg w-full max-w-2xl flex flex-wrap gap-1">
            <TabsTrigger value="config" className="flex-1 rounded-md text-xs font-semibold py-1.5 data-[state=active]:bg-background data-[state=active]:text-[var(--k-brand)]">Instruction</TabsTrigger>
            <TabsTrigger value="voice" className="flex-1 rounded-md text-xs font-semibold py-1.5 data-[state=active]:bg-background data-[state=active]:text-[var(--k-brand)]">Voice & LLM</TabsTrigger>
            <TabsTrigger value="knowledge" className="flex-1 rounded-md text-xs font-semibold py-1.5 data-[state=active]:bg-background data-[state=active]:text-[var(--k-brand)]">Knowledge</TabsTrigger>
            <TabsTrigger value="tools" className="flex-1 rounded-md text-xs font-semibold py-1.5 data-[state=active]:bg-background data-[state=active]:text-[var(--k-brand)]">Tools</TabsTrigger>
            <TabsTrigger value="test" className="flex-1 rounded-md text-xs font-semibold py-1.5 data-[state=active]:bg-background data-[state=active]:text-[var(--k-brand)]">Live Test</TabsTrigger>
            <TabsTrigger value="logs" className="flex-1 rounded-md text-xs font-semibold py-1.5 data-[state=active]:bg-background data-[state=active]:text-[var(--k-brand)]">Logs</TabsTrigger>
          </TabsList>

          <TabsContent value="config" className="space-y-6 animate-fade-up">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="space-y-2">
                <label className="text-xs font-bold uppercase tracking-widest text-muted-foreground">Agent Name</label>
                <input
                  value={editedAgent.name || ''}
                  onChange={(e) => setEditedAgent({ ...editedAgent, name: e.target.value })}
                  className="w-full px-3 py-2.5 text-sm bg-[var(--k-surface-elevated)] border border-[var(--k-border)] rounded-lg text-foreground focus:outline-none"
                />
              </div>
              <div className="space-y-2">
                <label className="text-xs font-bold uppercase tracking-widest text-muted-foreground">Welcome Message</label>
                <input
                  value={editedAgent.welcome_message || ''}
                  onChange={(e) => setEditedAgent({ ...editedAgent, welcome_message: e.target.value })}
                  className="w-full px-3 py-2.5 text-sm bg-[var(--k-surface-elevated)] border border-[var(--k-border)] rounded-lg text-foreground focus:outline-none"
                />
              </div>
            </div>
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
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
              <div className="space-y-2">
                <label className="text-xs font-bold uppercase tracking-widest text-muted-foreground">Voice Engine</label>
                <select
                  value={editedAgent.voice}
                  onChange={(e) => setEditedAgent({ ...editedAgent, voice: e.target.value })}
                  className="w-full px-3 py-2.5 text-sm bg-[var(--k-surface-elevated)] border border-[var(--k-border)] rounded-lg text-foreground focus:outline-none"
                >
                  {editedAgent.model === "gemini-live" ? (
                    GEMINI_LIVE_VOICES.map((v) => (
                      <option key={v.value} value={v.value}>{v.label}</option>
                    ))
                  ) : (
                    <>
                      <optgroup label="RevealIQ (Premium Indian Voices)">
                        {STANDARD_VOICES.revealiq.map((v) => (
                          <option key={v.value} value={v.value}>{v.label}</option>
                        ))}
                      </optgroup>
                      <optgroup label="Sarvam Bulbul v3 Voices">
                        {STANDARD_VOICES.sarvam.map((v) => (
                          <option key={v.value} value={v.value}>{v.label}</option>
                        ))}
                      </optgroup>
                      <optgroup label="ElevenLabs Voices">
                        {STANDARD_VOICES.elevenlabs.map((v) => (
                          <option key={v.value} value={v.value}>{v.label}</option>
                        ))}
                      </optgroup>
                      <optgroup label="Cartesia Voices">
                        {STANDARD_VOICES.cartesia.map((v) => (
                          <option key={v.value} value={v.value}>{v.label}</option>
                        ))}
                      </optgroup>
                    </>
                  )}
                </select>
                {editedAgent.model !== "gemini-live" && (
                  <button
                    type="button"
                    onClick={handleVoicePreview}
                    disabled={isPreviewing}
                    className="mt-2 flex items-center gap-2 px-3 py-2 rounded-lg border border-[var(--k-border)] hover:bg-accent text-xs text-foreground disabled:opacity-50"
                  >
                    <SpeakerHigh className="w-3.5 h-3.5" />
                    {isPreviewing ? 'Previewing...' : 'Preview Voice'}
                  </button>
                )}
              </div>
              <div className="space-y-2">
                <label className="text-xs font-bold uppercase tracking-widest text-muted-foreground">Language</label>
                <div className="px-3 py-2.5 text-sm bg-accent/10 border border-[var(--k-border)] rounded-lg text-muted-foreground flex items-center gap-2">
                   <span className="text-lg">🇮🇳</span> Hindi (India)
                </div>
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
              <div className="space-y-2">
                <label className="text-xs font-bold uppercase tracking-widest text-muted-foreground">LLM Back-end</label>
                <select
                  value={editedAgent.model}
                  onChange={(e) => {
                    const newModel = e.target.value;
                    const isGeminiLive = newModel === "gemini-live";
                    const currentVoice = editedAgent.voice;
                    let nextVoice = currentVoice;
                    if (isGeminiLive) {
                      if (!GEMINI_LIVE_VOICES.some(v => v.value === currentVoice)) {
                        nextVoice = "Puck";
                      }
                    } else {
                      if (GEMINI_LIVE_VOICES.some(v => v.value === currentVoice)) {
                        nextVoice = "sarvam:shubh";
                      }
                    }
                    setEditedAgent({ ...editedAgent, model: newModel, voice: nextVoice });
                  }}
                  className="w-full px-3 py-2.5 text-sm bg-[var(--k-surface-elevated)] border border-[var(--k-border)] rounded-lg text-foreground focus:outline-none"
                >
                  <option value="kautilya-fast">Kautilya Fast (Ultra-low latency)</option>
                  <option value="kautilya-daily">Kautilya Daily (Fast · General)</option>
                  <option value="kautilya-pro">Kautilya Pro (Deep Reasoning)</option>
                  <option value="coder">Kautilya Coder (Code Heavy)</option>
                  <option value="gemini-live">Gemini Live (Multimodal)</option>
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

          <TabsContent value="knowledge" className="space-y-6 animate-fade-up">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <label className="relative p-6 rounded-xl border border-dashed border-[var(--k-border)] hover:border-[var(--k-brand)]/40 bg-accent/10 cursor-pointer text-center">
                <input
                  type="file"
                  multiple
                  accept=".pdf,.txt,.docx"
                  onChange={handleKbUpload}
                  disabled={kbLoading}
                  className="absolute inset-0 opacity-0 cursor-pointer"
                />
                <UploadSimple className="w-8 h-8 mx-auto mb-3 text-[var(--k-brand)]" />
                <div className="text-sm font-bold text-foreground">{kbLoading ? 'Processing...' : 'Upload Documents'}</div>
                <div className="text-xs text-muted-foreground mt-1">PDF, TXT, DOCX knowledge files</div>
              </label>
              <div className="p-6 rounded-xl border border-[var(--k-border)] bg-accent/10">
                <Globe className="w-8 h-8 mb-3 text-[var(--k-brand)]" />
                <div className="text-sm font-bold text-foreground mb-1">Index Website</div>
                <div className="text-[10px] text-muted-foreground mb-3">Single page or full-site crawl (up to 50 pages, same domain)</div>
                <div className="flex gap-2 mb-2">
                  <input
                    value={kbUrl}
                    onChange={(e) => setKbUrl(e.target.value)}
                    onKeyDown={(e) => { if (e.key === 'Enter') handleAddKbUrl(); }}
                    placeholder="https://example.com/docs"
                    className="flex-1 px-3 py-2 text-xs bg-background border border-[var(--k-border)] rounded-lg text-foreground"
                  />
                  <button
                    onClick={handleAddKbUrl}
                    disabled={kbLoading || !kbUrl.trim()}
                    className="px-3 py-2 rounded-lg bg-accent text-foreground text-xs font-bold disabled:opacity-50 border border-[var(--k-border)]"
                    title="Index just this URL"
                  >
                    +1 Page
                  </button>
                </div>
                <div className="flex gap-2 items-center">
                  <label className="text-[10px] text-muted-foreground">Crawl up to</label>
                  <input
                    type="number"
                    min={1}
                    max={50}
                    value={crawlMaxPages}
                    onChange={(e) => setCrawlMaxPages(Math.min(50, Math.max(1, parseInt(e.target.value) || 1)))}
                    className="w-14 px-2 py-1 text-xs bg-background border border-[var(--k-border)] rounded-md text-foreground"
                  />
                  <label className="text-[10px] text-muted-foreground flex-1">pages from this URL</label>
                  <button
                    onClick={handleCrawlSite}
                    disabled={kbLoading || !kbUrl.trim()}
                    className="px-3 py-2 rounded-lg bg-[var(--k-brand)] text-white text-xs font-bold disabled:opacity-50"
                    title="BFS crawl same-domain links"
                  >
                    {kbLoading ? 'Crawling…' : 'Crawl Site'}
                  </button>
                </div>
              </div>
            </div>

            <div className="space-y-3">
              <div className="text-xs font-bold uppercase tracking-widest text-muted-foreground">Current Knowledge</div>
              {kbFiles.length === 0 ? (
                <div className="p-8 rounded-xl border border-dashed border-[var(--k-border)] text-center text-sm text-muted-foreground">
                  No knowledge files added yet.
                </div>
              ) : (
                kbFiles.map(file => (
                  <div key={file.id} className="flex items-center gap-3 p-3 rounded-xl border border-[var(--k-border)] bg-accent/10">
                    <FileText className="w-5 h-5 text-[var(--k-brand)]" />
                    <div className="flex-1 min-w-0">
                      <div className="text-sm text-foreground truncate">{file.name}</div>
                      <div className="text-[10px] text-muted-foreground">{Math.round((file.size || 0) / 1024)} KB</div>
                    </div>
                    <button
                      onClick={() => handleDeleteKb(file.id)}
                      className="p-2 rounded-md hover:bg-rose-500/10 text-muted-foreground hover:text-rose-400"
                    >
                      <Trash className="w-4 h-4" />
                    </button>
                  </div>
                ))
              )}
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
             {/* Web Call (Browser) — no phone number needed, talks to the agent via LiveKit */}
             <div className="p-6 rounded-2xl border border-emerald-500/20 bg-emerald-500/5">
                <div className="flex items-center gap-3 mb-4">
                  <div className="w-10 h-10 rounded-full bg-emerald-500/20 flex items-center justify-center">
                    <Microphone className="w-5 h-5 text-emerald-400" weight="duotone" />
                  </div>
                  <div>
                    <h4 className="text-sm font-bold text-foreground">Web Call (Browser)</h4>
                    <p className="text-xs text-muted-foreground">Talk to this agent live from your browser — no phone needed.</p>
                  </div>
                </div>
                <button
                  onClick={() => setWebCallOpen(true)}
                  className="flex items-center gap-2 px-6 py-3 rounded-xl bg-emerald-500 text-white text-sm font-bold hover:bg-emerald-600 transition-all shadow-lg shadow-emerald-500/20"
                >
                  <Microphone className="w-4 h-4" /> Start Web Call
                </button>
             </div>
             {webCallOpen && (
                <div className="fixed inset-0 z-50 bg-black/80 flex items-center justify-center p-4" onClick={() => setWebCallOpen(false)}>
                  <div onClick={(e) => e.stopPropagation()} className="w-full max-w-md">
                    <LiveKitVoice agentId={agent.agent_id} onClose={() => setWebCallOpen(false)} />
                  </div>
                </div>
             )}
             <div className="p-6 rounded-2xl border border-[var(--k-border)] bg-accent/10">
                <div className="flex items-center gap-3 mb-4">
                  <div className="w-10 h-10 rounded-full bg-emerald-500/10 flex items-center justify-center">
                    <ChatCircleText className="w-5 h-5 text-emerald-400" weight="duotone" />
                  </div>
                  <div>
                    <h4 className="text-sm font-bold text-foreground">Text Chat Test</h4>
                    <p className="text-xs text-muted-foreground">Check prompt, model routing, and knowledge-base answers.</p>
                  </div>
                </div>
                <div className="h-56 overflow-y-auto rounded-xl border border-[var(--k-border)] bg-background/60 p-3 space-y-3">
                  {testMessages.length === 0 ? (
                    <div className="h-full flex items-center justify-center text-xs text-muted-foreground">Start a test conversation.</div>
                  ) : (
                    testMessages.map((msg, index) => (
                      <div key={index} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                        <div className={`max-w-[82%] px-3 py-2 rounded-xl text-xs whitespace-pre-wrap ${msg.role === 'user' ? 'bg-[var(--k-brand)] text-white' : 'bg-accent text-foreground'}`}>
                          {msg.content || (isChatTesting && index === testMessages.length - 1 ? 'Thinking...' : '')}
                        </div>
                      </div>
                    ))
                  )}
                </div>
                <div className="flex gap-2 mt-3">
                  <input
                    value={testInput}
                    onChange={(e) => setTestInput(e.target.value)}
                    onKeyDown={(e) => { if (e.key === 'Enter') handleChatTest(); }}
                    placeholder="Type a test message..."
                    disabled={isChatTesting}
                    className="flex-1 px-4 py-3 text-sm bg-background border border-[var(--k-border)] rounded-xl text-foreground"
                  />
                  <button
                    onClick={handleChatTest}
                    disabled={isChatTesting || !testInput.trim()}
                    className="px-5 py-3 rounded-xl bg-[var(--k-brand)] text-white text-sm font-bold disabled:opacity-50"
                  >
                    Send
                  </button>
                </div>
                {testNotice && <p className="mt-2 text-[10px] text-emerald-400">{testNotice}</p>}
             </div>
          </TabsContent>

          <TabsContent value="tools" className="space-y-6 animate-fade-up">
            <div className="p-4 rounded-xl border border-[var(--k-border)] bg-accent/5">
              <h4 className="text-sm font-semibold text-foreground mb-1">Integration Capabilities</h4>
              <p className="text-xs text-muted-foreground">
                Toggle which connected tools <span className="font-semibold text-foreground">this agent</span> is allowed to use after a call.
                Switch one off and this agent will skip it (other agents are unaffected). Tools you haven't connected won't run regardless.
              </p>
            </div>
            
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold uppercase tracking-widest text-muted-foreground">Available Integration Tools</span>
                <button
                  onClick={() => navigate('/dashboard/integrations')}
                  className="text-xs font-bold text-[var(--k-brand)] hover:underline"
                >
                  Manage Integrations →
                </button>
              </div>
              
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                {[
                  { key: 'crm', title: 'CRM Leads Sync', connected: integrationsStatus.hubspot || integrationsStatus.zoho,
                    desc: 'Queries client details in HubSpot or Zoho during the call and logs an interaction note afterwards.',
                    connect: 'Connect HubSpot/Zoho CRM' },
                  { key: 'google_calendar', title: 'Google Calendar', connected: integrationsStatus.google_calendar,
                    desc: 'Books follow-up meetings and sends clash-free calendar invites directly to callers.',
                    connect: 'Connect Google Calendar' },
                  { key: 'gmail', title: 'Email Follow-ups', connected: integrationsStatus.gmail,
                    desc: 'Auto-sends a follow-up email to the lead from your own connected Gmail after the call.',
                    connect: 'Connect Gmail' },
                  { key: 'whatsapp', title: 'WhatsApp Reporting', connected: integrationsStatus.whatsapp,
                    desc: 'Sends post-call summaries and booking confirmations using WhatsApp Business templates.',
                    connect: 'Connect WhatsApp API' },
                  { key: 'slack', title: 'Slack Alerts', connected: integrationsStatus.slack,
                    desc: 'Posts call outcomes to your Slack channel for urgent human handoffs and alerts.',
                    connect: 'Connect Slack webhook' },
                ].map((it) => {
                  const on = integrationOn(it.key);
                  return (
                    <div key={it.key} className={`p-4 rounded-xl border bg-[var(--k-surface)] flex flex-col justify-between h-40 transition-opacity ${on ? 'border-[var(--k-border)]' : 'border-[var(--k-border)] opacity-60'}`}>
                      <div>
                        <div className="flex items-center justify-between mb-2 gap-2">
                          <span className="text-xs font-bold text-foreground">{it.title}</span>
                          <div className="flex items-center gap-2 flex-shrink-0">
                            <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                              it.connected
                                ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                                : 'bg-zinc-500/10 text-zinc-400 border border-zinc-500/20'
                            }`}>
                              {it.connected ? 'Connected' : 'Not connected'}
                            </span>
                            <Switch checked={on} onCheckedChange={(v) => toggleIntegration(it.key, v)} />
                          </div>
                        </div>
                        <p className="text-[11px] text-muted-foreground leading-relaxed">{it.desc}</p>
                      </div>
                      {!it.connected ? (
                        <button onClick={() => navigate('/dashboard/integrations')} className="text-[10px] font-bold text-[var(--k-brand)] hover:underline text-left">{it.connect}</button>
                      ) : (
                        <span className={`text-[10px] font-medium ${on ? 'text-emerald-400' : 'text-muted-foreground'}`}>
                          {on ? 'This agent will use it' : 'Disabled for this agent'}
                        </span>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          </TabsContent>

          <TabsContent value="logs" className="space-y-4 animate-fade-up">
            {logsLoading ? (
              <div className="p-8 text-center text-sm text-muted-foreground">Loading recent activity...</div>
            ) : logs.length === 0 ? (
              <div className="p-8 rounded-xl border border-dashed border-[var(--k-border)] text-center text-sm text-muted-foreground">No logs yet.</div>
            ) : (
              logs.map((log, index) => (
                <div key={log.id || index} className="p-4 rounded-xl border border-[var(--k-border)] bg-accent/10">
                  <div className="flex items-start gap-3">
                    <Clock className="w-4 h-4 mt-0.5 text-[var(--k-brand)]" />
                    <div className="flex-1 min-w-0">
                      <div className="text-sm font-medium text-foreground">{log.summary || log.analysis || 'Agent activity completed.'}</div>
                      <div className="mt-1 flex flex-wrap gap-2 text-[10px] text-muted-foreground">
                        <span>{log.channel || log.type || 'activity'}</span>
                        <span>{log.model || editedAgent.model}</span>
                        <span>{log.status || 'completed'}</span>
                      </div>
                    </div>
                  </div>
                </div>
              ))
            )}
          </TabsContent>
        </Tabs>
        </div>
      </ScrollArea>

      <div className="px-6 py-4 border-t border-[var(--k-border)] bg-[var(--k-surface-elevated)] flex justify-end gap-3 flex-shrink-0">
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
    voice: 'sarvam:shubh',
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
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div className="space-y-1.5">
          <label className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground">Brain Model</label>
          <select
            data-testid="new-agent-model"
            value={formData.model}
            onChange={(e) => {
              const newModel = e.target.value;
              const isGeminiLive = newModel === "gemini-live";
              const currentVoice = formData.voice;
              let nextVoice = currentVoice;
              if (isGeminiLive) {
                if (!GEMINI_LIVE_VOICES.some(v => v.value === currentVoice)) {
                  nextVoice = "Puck";
                }
              } else {
                if (GEMINI_LIVE_VOICES.some(v => v.value === currentVoice)) {
                  nextVoice = "sarvam:shubh";
                }
              }
              setFormData({ ...formData, model: newModel, voice: nextVoice });
            }}
            className="w-full px-4 py-3 text-sm bg-accent/20 border border-[var(--k-border)] rounded-xl text-foreground"
          >
            <option value="kautilya-fast">Fast (Ultra-low latency)</option>
            <option value="kautilya-daily">Daily (Fast · General)</option>
            <option value="kautilya-pro">Pro (Deep Reasoning)</option>
            <option value="coder">Coder (Code Heavy)</option>
            <option value="gemini-live">Gemini Live (Multimodal)</option>
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
            {formData.model === "gemini-live" ? (
              GEMINI_LIVE_VOICES.map((v) => (
                <option key={v.value} value={v.value}>{v.label}</option>
              ))
            ) : (
              <>
                <optgroup label="RevealIQ (Premium Indian Voices)">
                  {STANDARD_VOICES.revealiq.map((v) => (
                    <option key={v.value} value={v.value}>{v.label}</option>
                  ))}
                </optgroup>
                <optgroup label="Sarvam Bulbul v3 Voices">
                  {STANDARD_VOICES.sarvam.map((v) => (
                    <option key={v.value} value={v.value}>{v.label}</option>
                  ))}
                </optgroup>
                <optgroup label="ElevenLabs Voices">
                  {STANDARD_VOICES.elevenlabs.map((v) => (
                    <option key={v.value} value={v.value}>{v.label}</option>
                  ))}
                </optgroup>
                <optgroup label="Cartesia Voices">
                  {STANDARD_VOICES.cartesia.map((v) => (
                    <option key={v.value} value={v.value}>{v.label}</option>
                  ))}
                </optgroup>
              </>
            )}
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
