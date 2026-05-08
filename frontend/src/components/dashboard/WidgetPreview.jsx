import { useState, useEffect } from "react";
import { Code, Copy, CheckCircle, Eye, ChatCircleDots, PaintBrush } from "@phosphor-icons/react";
import { agentsAPI } from "@/lib/api";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Switch } from "@/components/ui/switch";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

const embedCode = `<!-- Kautilya AI Chat Widget -->
<script>
  (function() {
    var s = document.createElement('script');
    s.src = 'https://cdn.kautilya.ai/widget.js';
    s.async = true;
    s.dataset.agentId = 'agent-1';
    s.dataset.theme = 'dark';
    s.dataset.position = 'bottom-right';
    document.head.appendChild(s);
  })();
</script>`;

export default function WidgetPreview() {
  const [copied, setCopied] = useState(false);
  const [agents, setAgents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [widgetConfig, setWidgetConfig] = useState({
    theme: 'dark',
    position: 'bottom-right',
    greeting: 'Hi! How can I help you today?',
    agentId: '',
    autoOpen: false,
    showBranding: true,
  });

  useEffect(() => {
    const loadAgents = async () => {
      try {
        const data = await agentsAPI.list();
        setAgents(data.agents || []);
        if (data.agents && data.agents.length > 0) {
          setWidgetConfig(prev => ({ ...prev, agentId: data.agents[0].agent_id }));
        }
      } catch (error) {
        console.error('Failed to load agents:', error);
      } finally {
        setLoading(false);
      }
    };
    loadAgents();
  }, []);

  const handleCopy = () => {
    navigator.clipboard.writeText(embedCode);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="h-full" data-testid="widget-preview">
      <div className="px-8 py-6 border-b border-[var(--k-border)]">
        <h1 className="text-2xl font-medium k-heading tracking-tight text-foreground">Embeddable Widgets</h1>
        <p className="text-sm text-muted-foreground mt-1">Generate chat widgets for your website</p>
      </div>

      <ScrollArea className="h-[calc(100vh-120px)]">
        <div className="px-8 py-6">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
            {/* Configuration */}
            <div className="space-y-6">
              <Tabs defaultValue="config">
                <TabsList className="bg-transparent h-9 p-0 gap-4 mb-4">
                  <TabsTrigger value="config" className="bg-transparent data-[state=active]:bg-transparent data-[state=active]:shadow-none px-0 pb-2 rounded-none border-b-2 border-transparent data-[state=active]:border-[var(--k-brand)] text-xs font-medium">
                    <PaintBrush className="w-3.5 h-3.5 mr-1.5" />
                    Customize
                  </TabsTrigger>
                  <TabsTrigger value="code" className="bg-transparent data-[state=active]:bg-transparent data-[state=active]:shadow-none px-0 pb-2 rounded-none border-b-2 border-transparent data-[state=active]:border-[var(--k-brand)] text-xs font-medium">
                    <Code className="w-3.5 h-3.5 mr-1.5" />
                    Embed Code
                  </TabsTrigger>
                </TabsList>

                <TabsContent value="config" className="space-y-4">
                  <div>
                    <label className="text-xs font-medium text-muted-foreground mb-1.5 block">Assign Agent</label>
                    <select
                      data-testid="widget-agent-select"
                      value={widgetConfig.agentId}
                      onChange={(e) => setWidgetConfig(prev => ({ ...prev, agentId: e.target.value }))}
                      className="w-full px-3 py-2 text-sm bg-transparent border border-[var(--k-border)] rounded-md text-foreground focus:outline-none focus:ring-1 focus:ring-[var(--k-brand)]"
                      disabled={loading}
                    >
                      {loading ? (
                        <option>Loading agents...</option>
                      ) : agents.length === 0 ? (
                        <option>No agents available</option>
                      ) : (
                        agents.map((agent) => (
                          <option key={agent.agent_id} value={agent.agent_id}>{agent.name}</option>
                        ))
                      )}
                    </select>
                  </div>

                  <div>
                    <label className="text-xs font-medium text-muted-foreground mb-1.5 block">Greeting Message</label>
                    <input
                      data-testid="widget-greeting"
                      type="text"
                      value={widgetConfig.greeting}
                      onChange={(e) => setWidgetConfig(prev => ({ ...prev, greeting: e.target.value }))}
                      className="w-full px-3 py-2 text-sm bg-transparent border border-[var(--k-border)] rounded-md text-foreground focus:outline-none focus:ring-1 focus:ring-[var(--k-brand)]"
                    />
                  </div>

                  <div>
                    <label className="text-xs font-medium text-muted-foreground mb-1.5 block">Theme</label>
                    <div className="grid grid-cols-2 gap-2">
                      {['dark', 'light'].map(t => (
                        <button
                          key={t}
                          data-testid={`widget-theme-${t}`}
                          onClick={() => setWidgetConfig(prev => ({ ...prev, theme: t }))}
                          className={`px-3 py-2 text-sm rounded-md border transition-all capitalize ${
                            widgetConfig.theme === t
                              ? 'border-[var(--k-brand)] bg-[var(--k-brand)]/5 text-[var(--k-brand)]'
                              : 'border-[var(--k-border)] text-muted-foreground hover:text-foreground'
                          }`}
                        >
                          {t}
                        </button>
                      ))}
                    </div>
                  </div>

                  <div>
                    <label className="text-xs font-medium text-muted-foreground mb-1.5 block">Position</label>
                    <div className="grid grid-cols-2 gap-2">
                      {['bottom-right', 'bottom-left'].map(pos => (
                        <button
                          key={pos}
                          data-testid={`widget-pos-${pos}`}
                          onClick={() => setWidgetConfig(prev => ({ ...prev, position: pos }))}
                          className={`px-3 py-2 text-sm rounded-md border transition-all ${
                            widgetConfig.position === pos
                              ? 'border-[var(--k-brand)] bg-[var(--k-brand)]/5 text-[var(--k-brand)]'
                              : 'border-[var(--k-border)] text-muted-foreground hover:text-foreground'
                          }`}
                        >
                          {pos}
                        </button>
                      ))}
                    </div>
                  </div>

                  <div className="space-y-3">
                    <div className="flex items-center justify-between p-3 rounded-md border border-[var(--k-border)]">
                      <div>
                        <div className="text-sm font-medium text-foreground">Auto Open</div>
                        <div className="text-xs text-muted-foreground">Open widget automatically after 5s</div>
                      </div>
                      <Switch data-testid="widget-auto-open" checked={widgetConfig.autoOpen} onCheckedChange={(v) => setWidgetConfig(prev => ({ ...prev, autoOpen: v }))} />
                    </div>
                    <div className="flex items-center justify-between p-3 rounded-md border border-[var(--k-border)]">
                      <div>
                        <div className="text-sm font-medium text-foreground">Show Branding</div>
                        <div className="text-xs text-muted-foreground">Display "Powered by Kautilya"</div>
                      </div>
                      <Switch data-testid="widget-branding" checked={widgetConfig.showBranding} onCheckedChange={(v) => setWidgetConfig(prev => ({ ...prev, showBranding: v }))} />
                    </div>
                  </div>
                </TabsContent>

                <TabsContent value="code">
                  <div className="relative">
                    <pre className="p-4 rounded-md bg-[#1E1E1E] text-[#D4D4D4] text-xs font-mono leading-relaxed overflow-x-auto">
                      <code>{embedCode}</code>
                    </pre>
                    <button
                      data-testid="copy-embed-code"
                      onClick={handleCopy}
                      className="absolute top-3 right-3 flex items-center gap-1 px-2 py-1 rounded-md bg-white/10 hover:bg-white/20 text-white text-xs transition-colors"
                    >
                      {copied ? <CheckCircle className="w-3.5 h-3.5" /> : <Copy className="w-3.5 h-3.5" />}
                      {copied ? 'Copied!' : 'Copy'}
                    </button>
                  </div>
                </TabsContent>
              </Tabs>
            </div>

            {/* Widget Preview */}
            <div>
              <div className="text-xs font-semibold text-foreground mb-3 k-heading flex items-center gap-2">
                <Eye className="w-4 h-4 text-[var(--k-brand)]" weight="duotone" />
                Live Preview
              </div>
              <div className="relative rounded-md border border-[var(--k-border)] bg-[var(--k-surface-elevated)] h-[500px] overflow-hidden">
                {/* Mock website background */}
                <div className="p-6">
                  <div className="h-3 w-32 bg-[var(--k-border)] rounded mb-3" />
                  <div className="h-2 w-full bg-[var(--k-border)] rounded mb-2" />
                  <div className="h-2 w-3/4 bg-[var(--k-border)] rounded mb-2" />
                  <div className="h-2 w-5/6 bg-[var(--k-border)] rounded mb-6" />
                  <div className="grid grid-cols-3 gap-3">
                    {[1,2,3].map(i => (
                      <div key={i} className="h-20 bg-[var(--k-border)] rounded" />
                    ))}
                  </div>
                </div>

                {/* Widget */}
                <div className={`absolute bottom-4 ${widgetConfig.position === 'bottom-right' ? 'right-4' : 'left-4'}`}>
                  {/* Chat Popup */}
                  <div className={`mb-3 w-72 rounded-lg overflow-hidden border border-[var(--k-border)] shadow-xl ${widgetConfig.theme === 'dark' ? 'bg-[#121212]' : 'bg-white'}`} data-testid="widget-preview-popup">
                    {/* Widget Header */}
                    <div className="px-4 py-3 bg-[var(--k-brand)]">
                      <div className="flex items-center gap-2">
                        <div className="w-6 h-6 rounded-md bg-white/20 flex items-center justify-center">
                          <span className="text-white text-[10px] font-bold">K</span>
                        </div>
                        <div>
                          <div className="text-xs font-medium text-white">Kautilya AI</div>
                          <div className="text-[10px] text-white/70">Online</div>
                        </div>
                      </div>
                    </div>
                    {/* Messages */}
                    <div className="p-3 space-y-2 h-48">
                      <div className={`px-3 py-2 rounded-lg text-xs max-w-[80%] ${widgetConfig.theme === 'dark' ? 'bg-[#1A1A1A] text-white' : 'bg-gray-100 text-gray-800'}`}>
                        {widgetConfig.greeting}
                      </div>
                      <div className="flex justify-end">
                        <div className="px-3 py-2 rounded-lg text-xs bg-[var(--k-brand)] text-white max-w-[80%]">
                          I want to know about your pricing
                        </div>
                      </div>
                      <div className={`px-3 py-2 rounded-lg text-xs max-w-[80%] ${widgetConfig.theme === 'dark' ? 'bg-[#1A1A1A] text-white' : 'bg-gray-100 text-gray-800'}`}>
                        Sure! We have flexible plans starting at INR 2,999/mo. Let me share more details...
                      </div>
                    </div>
                    {/* Input */}
                    <div className={`px-3 py-2 border-t ${widgetConfig.theme === 'dark' ? 'border-white/10' : 'border-gray-200'}`}>
                      <div className={`px-3 py-2 rounded-md text-[10px] ${widgetConfig.theme === 'dark' ? 'bg-[#1A1A1A] text-white/40' : 'bg-gray-50 text-gray-400'}`}>
                        Type a message...
                      </div>
                    </div>
                    {widgetConfig.showBranding && (
                      <div className={`text-center py-1.5 text-[8px] ${widgetConfig.theme === 'dark' ? 'text-white/30' : 'text-gray-400'}`}>
                        Powered by Kautilya AI
                      </div>
                    )}
                  </div>

                  {/* FAB */}
                  <div className={`w-12 h-12 rounded-full bg-[var(--k-brand)] flex items-center justify-center shadow-lg cursor-pointer hover:scale-105 transition-transform ${widgetConfig.position === 'bottom-right' ? 'ml-auto' : ''}`}>
                    <ChatCircleDots className="w-6 h-6 text-white" weight="fill" />
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </ScrollArea>
    </div>
  );
}
