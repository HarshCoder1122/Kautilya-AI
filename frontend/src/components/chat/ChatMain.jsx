import { useState, useRef, useEffect } from "react";
import { SidebarSimple, ArrowRight, Paperclip, Code, MagnifyingGlass, Lightning, Columns, CaretDown, X } from "@phosphor-icons/react";
import { ChatMessage } from "@/components/chat/ChatMessage";
import { ThinkingTokens } from "@/components/chat/ThinkingTokens";
import { chatAPI } from "../../lib/api";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

const modes = [
  { id: 'chat', label: 'Chat', icon: Lightning, desc: 'General AI assistant' },
  { id: 'research', label: 'Deep Research', icon: MagnifyingGlass, desc: 'Web search & citations' },
  { id: 'code', label: 'Code Interpreter', icon: Code, desc: 'Execute & analyze code' },
];

export function ChatMain({ sidebarCollapsed, onExpandSidebar, canvasOpen, onToggleCanvas, onOpenCanvas, activeMode, onSetMode, theme, toggleTheme, sessionId, onSessionChange }) {
  const [messages, setMessages] = useState([]);
  const [inputValue, setInputValue] = useState("");
  const [selectedFiles, setSelectedFiles] = useState([]);
  const [isThinking, setIsThinking] = useState(false);
  const [isStreaming, setIsStreaming] = useState(false);
  const fileInputRef = useRef(null);
  const inputRef = useRef(null);
  const messagesEndRef = useRef(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, isThinking, isStreaming]);

  const parseSSELines = (buffer) => {
    const lines = buffer.split(/\r?\n/);
    return {
      completeLines: lines.slice(0, -1),
      remainder: lines[lines.length - 1] || "",
    };
  };

  const handleFileSelect = (e) => {
    const files = Array.from(e.target.files);
    setSelectedFiles(prev => [...prev, ...files]);
  };

  const removeFile = (index) => {
    setSelectedFiles(prev => prev.filter((_, i) => i !== index));
  };

  const handleSend = async () => {
    if (!inputValue.trim() && selectedFiles.length === 0) return;
    
    const userMsg = {
      id: `msg-${Date.now()}`,
      role: 'user',
      content: inputValue,
      files: selectedFiles.map(f => ({ name: f.name, type: f.type })),
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    };
    setMessages(prev => [...prev, userMsg]);
    
    const currentFiles = [...selectedFiles];
    setInputValue('');
    setSelectedFiles([]);
    setIsThinking(true);

    try {
      // chat -> backend auto router, code -> DeepSeek via NVIDIA,
      // research -> dedicated SerpAPI-backed research endpoint.
      const model = activeMode === 'code' ? 'coder' : 'auto';
      
      // Create new session if needed
      const currentSessionId = sessionId || `session-${Date.now()}`;
      if (!sessionId && onSessionChange) {
        onSessionChange(currentSessionId);
      }

      const response = activeMode === 'research'
        ? await chatAPI.streamResearch(inputValue)
        : await chatAPI.streamMessage(inputValue, currentSessionId, model, currentFiles, {
            maxThinking: activeMode === 'code',
          });

      if (!response.ok || !response.body) {
        let detail = '';
        try {
          const payload = await response.json();
          detail = payload.error || payload.message || '';
        } catch (e) {
          detail = response.statusText;
        }
        throw new Error(detail || `Request failed (${response.status})`);
      }
      
      setIsThinking(false);
      setIsStreaming(true);
      
      const aiMsg = {
        id: `msg-${Date.now() + 1}`,
        role: 'assistant',
        content: '',
        thinking: '',
        thinkingDone: false,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        agentType: activeMode === 'research' ? 'researcher' : activeMode === 'code' ? 'coder' : null,
      };
      setMessages(prev => [...prev, aiMsg]);

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let fullContent = '';
      let buffer = '';
      let researchSources = [];

      const updateAssistant = (patch) => {
        setMessages(prev => prev.map(msg => (
          msg.id === aiMsg.id ? { ...msg, ...patch } : msg
        )));
      };

      const updateContent = () => {
        const artifactMatch = fullContent.match(/<artifact\s+type="([^"]+)"(?:\s+title="([^"]+)")?>([\s\S]*?)<\/artifact>/);
        const artifactData = artifactMatch ? {
          type: artifactMatch[1],
          title: artifactMatch[2] || 'Analysis',
          code: artifactMatch[3].trim()
        } : null;

        updateAssistant({
          content: fullContent.replace(/<artifact[\s\S]*?<\/artifact>/g, '').trim(),
          thinkingDone: true,
          artifactType: artifactData?.type,
          artifactTitle: artifactData?.title,
          artifactCode: artifactData?.code,
          hasArtifact: !!artifactData,
        });
      };

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        
        buffer += decoder.decode(value, { stream: true });
        const parsedBuffer = parseSSELines(buffer);
        buffer = parsedBuffer.remainder;
        
        for (const line of parsedBuffer.completeLines) {
          if (line.startsWith('data: ')) {
            const data = line.slice(6);
            if (data === '[DONE]') {
              setIsStreaming(false);
              break;
            }
            
            try {
              const parsed = JSON.parse(data);
              if (parsed.event === 'agent') {
                updateAssistant({ agentType: parsed.agent || aiMsg.agentType });
                continue;
              }
              if (parsed.event === 'query') {
                updateAssistant({ thinking: `Searching: ${(parsed.queries || []).join(' | ')}`, thinkingDone: false });
                continue;
              }
              if (parsed.event === 'status') {
                updateAssistant({ thinking: parsed.message, thinkingDone: false });
                continue;
              }
              if (parsed.event === 'sources') {
                researchSources = (parsed.sources || []).map((source, index) => ({
                  id: index + 1,
                  title: source.title || source.site || source.url,
                  url: source.url,
                  source: source.site || '',
                }));
                updateAssistant({ citations: researchSources, thinkingDone: true });
                continue;
              }
              if (parsed.event === 'done') {
                updateAssistant({ thinkingDone: true });
                continue;
              }
              if (parsed.thinking) {
                setMessages(prev => prev.map(msg => (
                  msg.id === aiMsg.id
                    ? { ...msg, thinking: `${msg.thinking || ''}${parsed.thinking}`, thinkingDone: false }
                    : msg
                )));
                continue;
              }
              if (parsed.thinking_done) {
                updateAssistant({ thinkingDone: true });
                continue;
              }
              if (parsed.chunk) {
                fullContent += parsed.chunk;
                updateContent();
              }
            } catch (e) {
              // Handle non-JSON chunks or incomplete JSON
              fullContent += data;
              updateContent();
            }
          }
        }
      }

      if (buffer.startsWith('data: ')) {
        const data = buffer.slice(6);
        if (data && data !== '[DONE]') {
          try {
            const parsed = JSON.parse(data);
            if (parsed.chunk) {
              fullContent += parsed.chunk;
              updateContent();
            }
          } catch (e) {
            fullContent += data;
            updateContent();
          }
        }
      }

      setIsStreaming(false);
    } catch (error) {
      console.error('Failed to send message:', error);
      setIsThinking(false);
      setIsStreaming(false);
      
      const errorMsg = {
        id: `msg-${Date.now() + 1}`,
        role: 'assistant',
        content: 'Sorry, there was an error processing your request. Please try again.',
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      };
      setMessages(prev => [...prev, errorMsg]);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const currentMode = modes.find(m => m.id === activeMode);

  return (
    <div className="chat-main" data-testid="chat-main">
      {/* Top Bar */}
      <div className="h-12 min-h-[48px] flex items-center justify-between px-4 border-b border-[var(--k-border)]">
        <div className="flex items-center gap-2">
          {sidebarCollapsed && (
            <button
              data-testid="expand-sidebar-btn"
              onClick={onExpandSidebar}
              className="p-1.5 rounded-md hover:bg-accent transition-colors duration-200 mr-1"
            >
              <SidebarSimple className="w-4 h-4 text-muted-foreground" />
            </button>
          )}

          {/* Mode Selector */}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button data-testid="mode-selector-btn" className="flex items-center gap-2 px-3 py-1.5 rounded-md hover:bg-accent transition-colors duration-200 text-sm font-medium text-foreground">
                {currentMode && <currentMode.icon className="w-4 h-4 text-[var(--k-brand)]" weight="duotone" />}
                <span>{currentMode?.label}</span>
                <CaretDown className="w-3 h-3 text-muted-foreground" />
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="start" className="w-56">
              {modes.map(mode => (
                <DropdownMenuItem
                  key={mode.id}
                  data-testid={`mode-${mode.id}`}
                  onClick={() => onSetMode(mode.id)}
                  className="flex items-center gap-3 py-2"
                >
                  <mode.icon className={`w-4 h-4 ${activeMode === mode.id ? 'text-[var(--k-brand)]' : 'text-muted-foreground'}`} weight="duotone" />
                  <div>
                    <div className="text-sm font-medium">{mode.label}</div>
                    <div className="text-xs text-muted-foreground">{mode.desc}</div>
                  </div>
                </DropdownMenuItem>
              ))}
            </DropdownMenuContent>
          </DropdownMenu>
        </div>

        <div className="flex items-center gap-2">
          <button
            data-testid="toggle-canvas-btn"
            onClick={onToggleCanvas}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-all duration-200 ${
              canvasOpen
                ? 'bg-[var(--k-brand)] text-white'
                : 'hover:bg-accent text-muted-foreground'
            }`}
          >
            <Columns className="w-3.5 h-3.5" weight="duotone" />
            <span>Canvas</span>
          </button>
        </div>
      </div>

      {/* Messages Area */}
      <ScrollArea className="flex-1">
        <div className="max-w-3xl mx-auto px-4 py-6 space-y-6">
          {messages.length === 0 && (
            <div className="flex flex-col items-center justify-center h-[60vh] animate-fade-up">
              <div className="w-14 h-14 rounded-xl bg-[var(--k-brand)] flex items-center justify-center mb-6">
                <span className="text-white text-xl font-bold k-heading">K</span>
              </div>
              <h2 className="text-2xl font-medium k-heading tracking-tight text-foreground mb-2">
                How can I help you today?
              </h2>
              <p className="text-sm text-muted-foreground mb-8">
                Research, analyze data, generate reports, or write code
              </p>
              <div className="grid grid-cols-2 gap-3 max-w-md">
                {[
                  'Analyze my Q3 sales data',
                  'Research Indian fintech market',
                  'Generate a sales proposal',
                  'Create a revenue forecast',
                ].map((suggestion, i) => (
                  <button
                    key={i}
                    data-testid={`suggestion-${i}`}
                    onClick={() => { setInputValue(suggestion); inputRef.current?.focus(); }}
                    className="text-left px-4 py-3 rounded-md border border-[var(--k-border)] hover:bg-accent transition-all duration-200 text-xs text-muted-foreground hover:text-foreground"
                  >
                    {suggestion}
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map((msg) => (
            <ChatMessage
              key={msg.id}
              message={msg}
              onOpenArtifact={() => onOpenCanvas({
                type: msg.artifactType,
                code: msg.artifactCode || "",
                title: msg.role === 'assistant' ? 'AI Analysis' : undefined,
              })}
            />
          ))}

          {isThinking && (
            <ThinkingTokens
              text="Analyzing your request... Routing to specialized agent... Gathering context..."
            />
          )}

          <div ref={messagesEndRef} />
        </div>
      </ScrollArea>

      {/* Input Area */}
      <div className="border-t border-[var(--k-border)] p-4">
        <div className="max-w-3xl mx-auto">
          {/* Selected Files Preview */}
          {selectedFiles.length > 0 && (
            <div className="flex flex-wrap gap-2 mb-3">
              {selectedFiles.map((file, i) => (
                <div key={i} className="flex items-center gap-2 px-2 py-1 bg-accent/50 rounded-md border border-[var(--k-border)] text-[10px]">
                  <Paperclip className="w-3 h-3" />
                  <span className="max-w-[100px] truncate">{file.name}</span>
                  <button onClick={() => removeFile(i)} className="p-0.5 hover:text-red-400">
                    <X className="w-2.5 h-2.5" />
                  </button>
                </div>
              ))}
            </div>
          )}

          <div className="relative flex items-end border border-[var(--k-border)] rounded-lg bg-[var(--k-surface)] focus-within:ring-1 focus-within:ring-[var(--k-brand)] transition-all duration-200">
            <input
              type="file"
              ref={fileInputRef}
              onChange={handleFileSelect}
              multiple
              className="hidden"
            />
            <button
              data-testid="attach-file-btn"
              onClick={() => fileInputRef.current?.click()}
              className="p-3 text-muted-foreground hover:text-foreground transition-colors"
            >
              <Paperclip className="w-4 h-4" />
            </button>
            <textarea
              ref={inputRef}
              data-testid="chat-input"
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={
                activeMode === 'research'
                  ? 'Ask a research question...'
                  : activeMode === 'code'
                  ? 'Describe what you want to analyze...'
                  : 'Message Kautilya...'
              }
              rows={1}
              className="flex-1 py-3 px-1 bg-transparent resize-none focus:outline-none text-sm text-foreground placeholder:text-muted-foreground max-h-32"
              style={{ minHeight: '44px' }}
            />
            <button
              data-testid="send-message-btn"
              onClick={handleSend}
              disabled={!inputValue.trim() || isThinking}
              className={`p-3 transition-colors ${
                inputValue.trim()
                  ? 'text-[var(--k-brand)] hover:text-[var(--k-brand-hover)]'
                  : 'text-muted-foreground/40'
              }`}
            >
              <ArrowRight className="w-5 h-5" weight="bold" />
            </button>
          </div>
          <div className="flex items-center justify-between mt-2 px-1">
            <div className="flex items-center gap-3">
              {modes.map(mode => (
                <button
                  key={mode.id}
                  data-testid={`quick-mode-${mode.id}`}
                  onClick={() => onSetMode(mode.id)}
                  className={`flex items-center gap-1 text-[11px] transition-colors ${
                    activeMode === mode.id
                      ? 'text-[var(--k-brand)] font-medium'
                      : 'text-muted-foreground hover:text-foreground'
                  }`}
                >
                  <mode.icon className="w-3 h-3" weight="duotone" />
                  {mode.label}
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
