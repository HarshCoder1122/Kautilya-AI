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

  useEffect(() => {
    if (sessionId) {
      loadHistory(sessionId);
    } else {
      setMessages([]);
    }
  }, [sessionId]);

  const loadHistory = async (sid) => {
    try {
      setIsThinking(true);
      const data = await chatAPI.getConversation(sid);
      if (data && data.messages) {
        setMessages(data.messages.map(m => ({
          ...m,
          id: m.id || `msg-${Math.random()}`,
          timestamp: m.timestamp || new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        })));
      }
    } catch (error) {
      console.error('Failed to load conversation history:', error);
    } finally {
      setIsThinking(false);
    }
  };

  const handleFileSelect = (e) => {
    const files = Array.from(e.target.files);
    setSelectedFiles(prev => [...prev, ...files]);
  };

  const removeFile = (index) => {
    setSelectedFiles(prev => prev.filter((_, i) => i !== index));
  };

  const handleSend = async (overrideValue = null) => {
    const text = overrideValue !== null ? overrideValue : inputValue;
    if (!text.trim() && selectedFiles.length === 0) return;
    
    const userMsg = {
      id: `msg-${Date.now()}`,
      role: 'user',
      content: text,
      files: selectedFiles.map(f => ({ name: f.name, type: f.type })),
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    };
    
    if (overrideValue === null) {
      setMessages(prev => [...prev, userMsg]);
      setInputValue('');
    }
    
    const currentFiles = [...selectedFiles];
    setSelectedFiles([]);
    setIsThinking(true);

    try {
      const model = activeMode === 'code' ? 'coder' : 'auto';
      const currentSessionId = sessionId || `session-${Date.now()}`;
      if (!sessionId && onSessionChange) onSessionChange(currentSessionId);

      const response = await chatAPI.streamMessage(text, currentSessionId, model, currentFiles);
      if (!response.ok || !response.body) throw new Error("Connection failed");

      setIsThinking(false);
      setIsStreaming(true);
      
      const aiMsgId = `msg-${Date.now() + 1}`;
      setMessages(prev => [...prev, {
        id: aiMsgId,
        role: 'assistant',
        content: '',
        thinking: 'Initializing strategic intelligence protocol...',
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      }]);

      const updateAssistant = (patch) => {
        setMessages(prev => prev.map(m => m.id === aiMsgId ? { ...m, ...patch } : m));
      };

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let fullContent = '';
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split(/\r?\n/);
        buffer = lines.pop() || "";
        
        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          const data = line.slice(6).trim();
          if (data === '[DONE]') break;
          try {
            const parsed = JSON.parse(data);
            if (parsed.thinking) {
              updateAssistant({ thinking: (fullContent ? '' : parsed.thinking) });
            } else if (parsed.chunk) {
              fullContent += parsed.chunk;
              updateAssistant({ content: fullContent, thinking: '' });
            }
          } catch (e) {
            fullContent += data;
            updateAssistant({ content: fullContent, thinking: '' });
          }
        }
      }
      setIsStreaming(false);
    } catch (error) {
      console.error('Send error:', error);
      setIsThinking(false);
      setIsStreaming(false);
    }
  };

  const handleRegenerate = (msg) => {
    const lastUserMsg = [...messages].reverse().find(m => m.role === 'user');
    if (lastUserMsg) {
      setMessages(prev => prev.filter(m => m.id !== msg.id));
      handleSend(lastUserMsg.content);
    }
  };

  const currentMode = modes.find(m => m.id === activeMode);

  return (
    <div className="flex flex-col h-full bg-background" data-testid="chat-main">
      <div className="h-12 min-h-[48px] flex items-center justify-between px-4 border-b border-[var(--k-border)]">
        <div className="flex items-center gap-2">
          {sidebarCollapsed && (
            <button onClick={onExpandSidebar} className="p-1.5 rounded-md hover:bg-accent"><SidebarSimple className="w-4 h-4" /></button>
          )}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button className="flex items-center gap-2 px-3 py-1.5 rounded-md hover:bg-accent text-sm font-medium">
                {currentMode && <currentMode.icon className="w-4 h-4 text-[var(--k-brand)]" weight="duotone" />}
                <span>{currentMode?.label}</span>
                <CaretDown className="w-3 h-3 text-muted-foreground" />
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="start" className="w-56">
              {modes.map(mode => (
                <DropdownMenuItem key={mode.id} onClick={() => onSetMode(mode.id)} className="flex items-center gap-3 py-2">
                  <mode.icon className="w-4 h-4" weight="duotone" />
                  <div><div className="text-sm font-medium">{mode.label}</div><div className="text-xs text-muted-foreground">{mode.desc}</div></div>
                </DropdownMenuItem>
              ))}
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
        <button onClick={onToggleCanvas} className={`px-3 py-1.5 rounded-md text-xs font-medium ${canvasOpen ? 'bg-[var(--k-brand)] text-white' : 'hover:bg-accent'}`}>
          <Columns className="w-3.5 h-3.5 mr-1 inline" /> Canvas
        </button>
      </div>

      <ScrollArea className="flex-1">
        <div className="max-w-3xl mx-auto px-4 py-6 space-y-6">
          {messages.length === 0 && (
            <div className="flex flex-col items-center justify-center h-[60vh]">
              <div className="w-14 h-14 rounded-xl bg-[var(--k-brand)] flex items-center justify-center mb-6 text-white text-xl font-bold">K</div>
              <h2 className="text-2xl font-medium k-heading">How can I help you today?</h2>
            </div>
          )}
          {messages.map((msg) => (
            <ChatMessage
              key={msg.id}
              message={msg}
              onRegenerate={handleRegenerate}
              onOpenArtifact={() => onOpenCanvas({ type: msg.artifactType, code: msg.artifactCode, title: 'AI Analysis' })}
            />
          ))}
          {isThinking && <ThinkingTokens text="Analyzing context... Preparing response..." />}
          <div ref={messagesEndRef} />
        </div>
      </ScrollArea>

      <div className="p-4 border-t border-[var(--k-border)]">
        <div className="max-w-3xl mx-auto">
          <div className="relative flex items-end border border-[var(--k-border)] rounded-lg bg-[var(--k-surface)] focus-within:ring-1 focus-within:ring-[var(--k-brand)]">
            <input type="file" ref={fileInputRef} onChange={handleFileSelect} multiple className="hidden" />
            <button onClick={() => fileInputRef.current?.click()} className="p-3 text-muted-foreground hover:text-foreground"><Paperclip className="w-4 h-4" /></button>
            <textarea
              ref={inputRef}
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && (e.preventDefault(), handleSend())}
              placeholder="Message Kautilya..."
              rows={1}
              className="flex-1 py-3 px-1 bg-transparent resize-none focus:outline-none text-sm max-h-32"
            />
            <button onClick={() => handleSend()} disabled={!inputValue.trim() || isThinking} className="p-3 text-[var(--k-brand)]"><ArrowRight className="w-5 h-5" weight="bold" /></button>
          </div>
        </div>
      </div>
    </div>
  );
}
