import { useState, useRef, useEffect } from "react";
import { SidebarSimple, ArrowRight, Paperclip, Code, MagnifyingGlass, Lightning, Columns, CaretDown, X, Microphone, MicrophoneSlash, Phone, StopCircle, File, Image, Camera, HardDrive, Cpu, Brain, Diamond } from "@phosphor-icons/react";
import { ChatMessage } from "@/components/chat/ChatMessage";
import { ThinkingTokens } from "@/components/chat/ThinkingTokens";
import { LiveKitVoice } from "@/components/chat/LiveKitVoice";
import { chatAPI, getAuthHeaders, integrationsAPI } from "../../lib/api";
// ReActSteps is rendered inside ChatMessage — no need to import here
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
  DropdownMenuSeparator,
  DropdownMenuLabel,
} from "@/components/ui/dropdown-menu";
import { Switch } from "@/components/ui/switch";
import { useToast } from "@/hooks/use-toast";
import { Toaster } from "@/components/ui/toaster";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";

// Force same-origin when served from *.revealiq.in so the proxy is used (see lib/api.js).
const _hn = (typeof window !== 'undefined' ? window.location.hostname : '') || '';
const API_BASE_URL = /(^|\.)revealiq\.in$/i.test(_hn)
  ? window.location.origin
  : (process.env.REACT_APP_API_URL || (_hn === 'localhost' ? 'http://localhost:5000' : window.location.origin));

const modes = [
  { id: 'chat',     label: 'Chat',         icon: Lightning,       desc: 'General AI assistant' },
  { id: 'pro',      label: 'Pro',          icon: Diamond,         desc: 'Deep reasoning · Extended thinking' },
  { id: 'research', label: 'Deep Research',icon: MagnifyingGlass, desc: 'Web search & citations' },
  { id: 'code',     label: 'Code',         icon: Code,            desc: 'Frontier code generation' },
];

function parseAttrs(s) {
  const out = {};
  const re = /([a-zA-Z_:][\w:-]*)\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]+))/g;
  let m;
  while ((m = re.exec(s)) !== null) {
    out[m[1].toLowerCase()] = m[2] ?? m[3] ?? m[4] ?? '';
  }
  return out;
}

// Cache key for the per-session message mirror. We keep one slot per session
// in sessionStorage so unmounting (route change, tab close) doesn't blank the
// last in-progress response — remounting reads this synchronously and shows
// the user exactly what was on screen before, while history/polling catches
// up in the background.
const _streamCacheKey = (sid) => `chat:lastMessages:${sid || 'none'}`;
const _readStreamCache = (sid) => {
  if (!sid) return null;
  try {
    const raw = sessionStorage.getItem(_streamCacheKey(sid));
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed?.messages) ? parsed : null;
  } catch { return null; }
};
const _writeStreamCache = (sid, messages, streaming) => {
  if (!sid) return;
  try {
    sessionStorage.setItem(_streamCacheKey(sid), JSON.stringify({
      messages, streaming: !!streaming, ts: Date.now(),
    }));
  } catch { /* quota / private mode — soft-fail */ }
};

export function ChatMain({ sidebarCollapsed, onExpandSidebar, onOpenMobileSidebar, canvasOpen, onToggleCanvas, onOpenCanvas, activeMode, onSetMode, theme, toggleTheme, sessionId, onSessionChange, onNewSession, onStreamComplete }) {
  // Restore previous in-progress messages synchronously so a remount (after
  // navigating to dashboard / switching tabs) never shows a blank screen.
  const [messages, setMessages] = useState(() => _readStreamCache(sessionId)?.messages || []);
  const [inputValue, setInputValue] = useState("");
  const [selectedFiles, setSelectedFiles] = useState([]);
  const [isThinking, setIsThinking] = useState(false);
  const [isStreaming, setIsStreaming] = useState(false);
  const [isRecording, setIsRecording] = useState(false);
  const [isTranscribing, setIsTranscribing] = useState(false);
  const [isLiveVoice, setIsLiveVoice] = useState(false);
  const [staleTimeout, setStaleTimeout] = useState(false); // true when thinking >90s with no response
  const fileInputRef = useRef(null);
  const imageInputRef = useRef(null);
  const cameraInputRef = useRef(null);
  const inputRef = useRef(null);
  const [maxThinking, setMaxThinking] = useState(false);
  const [showMcpDialog, setShowMcpDialog] = useState(false);
  const [mcpSearch, setMcpSearch] = useState("");
  const [mcpStatus, setMcpStatus] = useState(null);
  const [loadingMcp, setLoadingMcp] = useState(false);
  const { toast } = useToast();
  const messagesEndRef = useRef(null);
  const mediaRecorderRef = useRef(null);
  const audioChunksRef = useRef([]);
  // Track sessions we just created so we don't reload empty history
  const pendingSessionRef = useRef(null);
  // Track whether we left mid-stream (user navigated away during generation)
  const leftMidStreamRef = useRef(false);
  const staleTimerRef = useRef(null);
  const abortControllerRef = useRef(null);

  // Auto-scroll: instant during streaming (smooth would jitter as tokens arrive
  // faster than the animation finishes), smooth only on quiescent updates.
  // Skip entirely if the user has scrolled up to read backscroll.
  const stickToBottomRef = useRef(true);
  useEffect(() => {
    const el = messagesEndRef.current;
    if (!el) return;
    const scroller = el.parentElement;
    if (scroller) {
      const distance = scroller.scrollHeight - scroller.scrollTop - scroller.clientHeight;
      if (distance > 120) {
        stickToBottomRef.current = false;
        return;
      }
      stickToBottomRef.current = true;
    }
    el.scrollIntoView({ behavior: isStreaming ? "auto" : "smooth", block: "end" });
  }, [messages, isThinking, isStreaming]);

  // Reload history when user returns to the tab after leaving mid-stream
  useEffect(() => {
    const handleVisibility = () => {
      if (document.visibilityState === 'visible' && leftMidStreamRef.current && sessionId) {
        leftMidStreamRef.current = false;
        // Small delay to let the backend thread finish saving
        setTimeout(() => loadHistory(sessionId), 1200);
      }
      if (document.visibilityState === 'hidden') {
        // Record we left the tab
        leftMidStreamRef.current = isStreaming || isThinking;
      }
    };
    document.addEventListener('visibilitychange', handleVisibility);
    return () => document.removeEventListener('visibilitychange', handleVisibility);
  }, [sessionId, isStreaming, isThinking]);

  // Fetch MCP status when the dialog opens
  useEffect(() => {
    if (!showMcpDialog) return;

    const fetchMcpStatus = async () => {
      setLoadingMcp(true);
      try {
        const data = await integrationsAPI.getMcpStatus();
        setMcpStatus(data);
      } catch (err) {
        console.error("Failed to load MCP status:", err);
        toast({
          variant: "destructive",
          title: "Failed to load MCP Status",
          description: err.message || "An error occurred while fetching MCP servers."
        });
      } finally {
        setLoadingMcp(false);
      }
    };

    fetchMcpStatus();
  }, [showMcpDialog, toast]);

  // Load history when sessionId changes
  useEffect(() => {
    if (!sessionId) {
      setMessages([]);
      return;
    }
    // Skip loading history for sessions we just created (they're empty on backend)
    if (pendingSessionRef.current === sessionId) {
      pendingSessionRef.current = null;
      return;
    }
    // If we just hydrated from the sessionStorage cache for this session and
    // it was mid-stream, kick off polling immediately so the UI keeps growing
    // without waiting on a full history fetch (avoids a flash of "Thinking…"
    // over a stale placeholder).
    const cached = _readStreamCache(sessionId);
    if (cached?.streaming) {
      setIsStreaming(true);
      pollStreamingMessage(sessionId);
    }
    loadHistory(sessionId);
  }, [sessionId]);

  // Mirror messages to sessionStorage so unmount/remount restores the exact
  // last-rendered state. Only writes while streaming or right after — idle
  // sessions don't need the churn.
  useEffect(() => {
    if (!sessionId) return;
    if (!isStreaming && !isThinking) {
      // Final snapshot once the stream settles, then stop mirroring.
      _writeStreamCache(sessionId, messages, false);
      return;
    }
    _writeStreamCache(sessionId, messages, true);
  }, [sessionId, messages, isStreaming, isThinking]);

  // Stale-response detector: if thinking with no first chunk for 90s, surface a recovery button
  useEffect(() => {
    if (isThinking && !isStreaming) {
      staleTimerRef.current = setTimeout(() => {
        setIsThinking(false);
        setStaleTimeout(true);
      }, 90000);
    } else {
      clearTimeout(staleTimerRef.current);
      if (!isThinking) setStaleTimeout(false);
    }
    return () => clearTimeout(staleTimerRef.current);
  }, [isThinking, isStreaming]);

  // Hydrate a Firestore-saved message back into the live message shape used
  // by ChatMessage. Tool-result cards / ReAct steps / citations are stored
  // as JSON strings on the backend so they survive serialization — we
  // re-parse them here so they render exactly like they did during streaming.
  const hydrateHistoryMessage = (m) => {
    const safeParse = (v) => {
      if (v == null) return v;
      if (typeof v !== 'string') return v;
      try { return JSON.parse(v); } catch (e) { return v; }
    };
    const toolResults = safeParse(m.tool_results);
    const reactStepsRaw = safeParse(m.react_steps);
    const citations = safeParse(m.citations);
    const artifact = safeParse(m.artifact);
    return {
      ...m,
      id: m.id || `msg-${Math.random()}`,
      timestamp: m.timestamp || new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      toolResults: Array.isArray(toolResults) ? toolResults : undefined,
      reactSteps: Array.isArray(reactStepsRaw) ? reactStepsRaw : undefined,
      citations: Array.isArray(citations) ? citations : undefined,
      agentType: m.agent_type || m.agentType,
      hasArtifact: !!artifact,
      artifactType: artifact?.type,
      artifactTitle: artifact?.title,
    };
  };

  const loadHistory = async (sid) => {
    try {
      setIsThinking(true);
      const data = await chatAPI.getConversation(sid);
      if (data && data.messages && data.messages.length > 0) {
        setMessages(data.messages.map(m => hydrateHistoryMessage(m)));
        // If the server is still generating the last assistant message
        // (user closed/reloaded the app mid-stream), poll for live updates
        // until the streaming flag flips off. Keep "thinking" UI active so
        // the user always sees a live indicator — never a dead screen.
        if (data.streaming) {
          setIsStreaming(true);          // shows the bottom "streaming" pulse
          pollStreamingMessage(sid);
          return;                          // skip the finally setIsThinking(false)
        }
      }
    } catch (error) {
      console.error('Failed to load conversation history:', error);
    } finally {
      setIsThinking(false);
    }
  };

  // Poll Firestore-backed history for in-progress generation. Stops as soon
  // as the backend flips `streaming` to false (or after 5 min of no growth).
  const pollStreamingMessage = async (sid) => {
    let lastLen = 0;
    let stableTicks = 0;
    setIsStreaming(true);
    // Tight 1.2s polling — partial Firestore writes land every 1.5s
    for (let i = 0; i < 250; i++) { // 250 * 1.2s = 5 min hard cap
      await new Promise(r => setTimeout(r, 1200));
      try {
        const data = await chatAPI.getConversation(sid);
        if (!data || !data.messages) continue;
        setMessages(data.messages.map(m => hydrateHistoryMessage(m)));
        const lastMsg = data.messages[data.messages.length - 1];
        const lastContent = typeof lastMsg?.content === 'string' ? lastMsg.content : '';
        // Keep thinking bubble visible while server has nothing to show yet
        // (deep-search spends 10-60s searching before first token).
        if (lastContent.length === 0) setIsThinking(true);
        else setIsThinking(false);
        if (!data.streaming) break;          // Backend finished
        if (lastContent.length === lastLen) {
          stableTicks++;
          if (stableTicks >= 50) break;       // 1 min with no growth — stop
        } else {
          stableTicks = 0;
          lastLen = lastContent.length;
        }
      } catch (e) {
        // soft-fail: keep polling
      }
    }
    setIsStreaming(false);
    setIsThinking(false);
  };

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

  // Voice recording
  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      audioChunksRef.current = [];
      const mediaRecorder = new MediaRecorder(stream, { mimeType: 'audio/webm' });
      mediaRecorderRef.current = mediaRecorder;

      mediaRecorder.ondataavailable = (e) => {
        if (e.data.size > 0) audioChunksRef.current.push(e.data);
      };

      mediaRecorder.onstop = async () => {
        stream.getTracks().forEach(t => t.stop());
        const blob = new Blob(audioChunksRef.current, { type: 'audio/webm' });
        if (blob.size < 500) return; // Too short
        setIsTranscribing(true);
        try {
          const formData = new FormData();
          formData.append('audio', blob, 'recording.webm');
          const resp = await fetch(`${API_BASE_URL}/api/voice/transcribe`, {
            method: 'POST',
            headers: getAuthHeaders(),
            body: formData,
          });
          if (resp.ok) {
            const data = await resp.json();
            if (data.text) {
              setInputValue(prev => prev ? `${prev} ${data.text}` : data.text);
              inputRef.current?.focus();
            }
          }
        } catch (err) {
          console.error('Transcription failed:', err);
        } finally {
          setIsTranscribing(false);
        }
      };

      mediaRecorder.start();
      setIsRecording(true);
    } catch (err) {
      console.error('Microphone access denied:', err);
      alert('Microphone access is required for voice input.');
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      mediaRecorderRef.current.stop();
    }
    setIsRecording(false);
  };

  const toggleRecording = () => {
    if (isRecording) {
      stopRecording();
    } else {
      startRecording();
    }
  };

  const handleStopGeneration = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    setIsStreaming(false);
    setIsThinking(false);
  };

  const handleSend = async () => {
    if (!inputValue.trim() && selectedFiles.length === 0) return;
    if (isStreaming) return;

    // Materialize image previews so they survive in the message bubble after send
    const fileMetas = await Promise.all(selectedFiles.map(async (f) => {
      const meta = { name: f.name, type: f.type, size: f.size };
      if (f.type && f.type.startsWith('image/') && f.size < 4 * 1024 * 1024) {
        try {
          meta.previewUrl = await new Promise((resolve, reject) => {
            const r = new FileReader();
            r.onload = () => resolve(r.result);
            r.onerror = reject;
            r.readAsDataURL(f);
          });
        } catch { /* skip preview if read fails */ }
      }
      return meta;
    }));

    const userMsg = {
      id: `msg-${Date.now()}`,
      role: 'user',
      content: inputValue,
      files: fileMetas,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    };
    setMessages(prev => [...prev, userMsg]);

    const currentFiles = [...selectedFiles];
    const currentInput = inputValue;
    setInputValue('');
    setSelectedFiles([]);
    setIsThinking(true);

    // Create new session if needed — mark it as pending so useEffect won't reload empty history
    const currentSessionId = sessionId || `session-${Date.now()}`;
    const isNewSession = !sessionId;
    if (isNewSession && onSessionChange) {
      pendingSessionRef.current = currentSessionId;
      onSessionChange(currentSessionId);
      // Optimistically add to sidebar so it shows up immediately (Claude-like UX)
      if (onNewSession) {
        onNewSession({
          id: currentSessionId,
          title: currentInput.slice(0, 40) || 'New Chat',
          preview: currentInput.slice(0, 80),
        });
      }
    }

    try {
      const model = activeMode === 'code' ? 'coder' : activeMode === 'pro' ? 'pro' : 'auto';
      abortControllerRef.current = new AbortController();

      const response = activeMode === 'research'
        ? await chatAPI.streamResearch(currentInput, currentSessionId, { signal: abortControllerRef.current.signal })
        : await chatAPI.streamMessage(currentInput, currentSessionId, model, currentFiles, {
          // Only respect the user's explicit "Max Thinking" toggle. Code
          // mode used to force this true, but Qwen3-Coder is NOT a
          // reasoning model — forcing max_thinking made the backend
          // allocate a 12k-token reasoning budget that Qwen3-Coder didn't
          // use and that NVIDIA deducted from output. Net effect: 12k
          // fewer tokens for actual code → mid-file cutoffs.
          maxThinking: maxThinking,
          signal: abortControllerRef.current.signal,
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

      // Keep "Analyzing your request..." banner visible until the first
      // actual content/thinking chunk arrives — otherwise the indicator
      // disappears the instant headers are received (a few seconds before
      // NVIDIA daily model emits its first token), leaving a dead screen.
      setIsStreaming(true);
      setStaleTimeout(false);
      leftMidStreamRef.current = true; // Mark in-progress so tab-return triggers reload
      let firstChunkSeen = false;
      const markFirstChunk = () => {
        if (firstChunkSeen) return;
        firstChunkSeen = true;
      };

      setIsThinking(false);
      const aiMsg = {
        id: `msg-ai-${Date.now()}`,
        role: 'assistant',
        content: '',
        thinking: '',
        thinkingDone: false,
        streaming: true,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        agentType: activeMode === 'research' ? 'researcher' : activeMode === 'code' ? 'coder' : null,
      };
      setMessages(prev => [...prev, aiMsg]);

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let fullContent = '';
      let buffer = '';
      let researchSources = [];
      let canvasOpened = false;

      // Render each network chunk directly — fastest possible perceived
      // response. Earlier we tried a rAF typewriter to even out burst
      // arrivals, but it added enough lag to make snappy responses feel
      // sluggish. Trust the upstream pacing and just paint as it arrives.
      const updateAssistant = (patch) => {
        setMessages(prev => prev.map(msg => (
          msg.id === aiMsg.id ? { ...msg, ...patch } : msg
        )));
      };

      const updateContent = () => {
        const visible = fullContent;
        // Multi-file workspace: detect either <file>...</file> blocks OR the
        // common "**filename.ext**\n```lang\n...\n```" pattern that
        // Claude/Emergent-style coder responses emit. We require 2+ filename
        // headers OR any explicit <file> tag so single code snippets still
        // render as a normal artifact rather than a multi-file project.
        const hasFileTags = /<file[\s>]/i.test(fullContent);
        const filenameHeaderRe = /(^|\n)[ \t]*(?:\*\*|`|#{1,6}\s+|(?:[Ff]ile|[Ff]ilename|[Pp]ath)\s*[:=]\s*)?[\w./@-]+\.(?:jsx|tsx|js|ts|html|css|py|json|md|vue|svelte|go|rs|java|cpp|c|h|sh|yml|yaml|toml|env)(?:\*\*|`)?[ \t]*\n[ \t]*```/g;
        const headerHits = (fullContent.match(filenameHeaderRe) || []).length;
        if (hasFileTags || headerHits >= 2) {
          // Visible body uses the typewriter-smoothed slice; the canvas/
          // artifact gets fullContent so file tree is always current.
          const cleanContent = visible.replace(/<file[\s\S]*?<\/file>/gi, '').replace(/<file[\s\S]*/gi, '').trim();
          updateAssistant({
            content: cleanContent || 'Here are the project files:',
            thinkingDone: true,
            isSynthesizing: false,
            hasArtifact: true,
            artifactType: 'multifile',
            artifactTitle: 'Project Files',
            artifactCode: fullContent,
          });
          if (onOpenCanvas) {
            if (!canvasOpened) canvasOpened = true;
            onOpenCanvas({ type: 'multifile', code: fullContent, title: 'Project Files', messageId: aiMsg.id });
          }
          return;
        }

        const tagMatch = fullContent.match(/<artifact(\s+[^>]+)?>/i);
        let artifactData = null;
        if (tagMatch) {
          const openTag = tagMatch[0];
          const attrs = parseAttrs(tagMatch[1] || '');
          const startIndex = tagMatch.index + openTag.length;
          const closeIndex = fullContent.indexOf('</artifact>', startIndex);
          const code = closeIndex >= 0
            ? fullContent.slice(startIndex, closeIndex)
            : fullContent.slice(startIndex);

          artifactData = {
            type: attrs.type || 'document',
            title: attrs.title || 'Analysis',
            filename: attrs.filename || '',
            subtype: attrs.subtype || '',
            code: code.trim(),
            isClosed: closeIndex >= 0
          };
        }

        const cleanContent = visible
          .replace(/<artifact[\s\S]*?<\/artifact>/gi, '')
          .replace(/<artifact[\s\S]*/gi, '')
          .trim();

        updateAssistant({
          content: cleanContent || (artifactData ? 'Here is the generated artifact:' : ''),
          thinkingDone: true,
          isSynthesizing: false,
          artifactType: artifactData?.type,
          artifactTitle: artifactData?.title,
          artifactFilename: artifactData?.filename,
          artifactSubtype: artifactData?.subtype,
          artifactCode: artifactData?.code,
          hasArtifact: !!artifactData,
        });

        // Open or update canvas in real-time
        if (artifactData && onOpenCanvas) {
          onOpenCanvas({
            type: artifactData.type,
            code: artifactData.code,
            title: artifactData.title,
            filename: artifactData.filename,
            subtype: artifactData.subtype,
            messageId: aiMsg.id,
          });
          canvasOpened = true;
        }
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
                if (parsed.message) {
                  markFirstChunk();
                  updateAssistant({ thinking: parsed.message, thinkingDone: false });
                } else {
                  updateAssistant({ thinkingDone: true });
                }
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
              // ReAct step events
              if (parsed.event === 'react_action') {
                setMessages(prev => prev.map(msg => {
                  if (msg.id !== aiMsg.id) return msg;
                  const steps = [...(msg.reactSteps || [])];
                  const existing = steps.findIndex(s => s.id === parsed.id);
                  const step = { id: parsed.id, tool: parsed.tool, input: parsed.input, status: parsed.status };
                  if (existing >= 0) steps[existing] = step;
                  else steps.push(step);
                  return { ...msg, reactSteps: steps, isSynthesizing: false };
                }));
                continue;
              }
              if (parsed.event === 'react_action_done') {
                setMessages(prev => prev.map(msg => {
                  if (msg.id !== aiMsg.id) return msg;
                  const steps = (msg.reactSteps || []).map(s =>
                    s.id === parsed.id
                      ? { ...s, status: parsed.status, preview: parsed.preview, sources: parsed.sources }
                      : s
                  );
                  return { ...msg, reactSteps: steps };
                }));
                continue;
              }
              if (parsed.event === 'react_synthesizing') {
                updateAssistant({ isSynthesizing: true });
                continue;
              }
              // Structured tool output (gmail list, calendar, python sandbox, etc.)
              if (parsed.event === 'tool_result') {
                setMessages(prev => prev.map(msg => {
                  if (msg.id !== aiMsg.id) return msg;
                  const toolResults = [...(msg.toolResults || [])];
                  toolResults.push({ tool: parsed.tool, data: parsed.data });
                  return { ...msg, toolResults };
                }));
                continue;
              }
              if (parsed.event === 'artifact') {
                // Research finished — open canvas with the accumulated content
                if (!canvasOpened && onOpenCanvas && fullContent) {
                  canvasOpened = true;
                  updateAssistant({
                    hasArtifact: true,
                    artifactType: parsed.artifactType || 'document',
                    artifactTitle: parsed.artifactTitle || 'Deep Research',
                    artifactCode: fullContent,
                  });
                  onOpenCanvas({
                    type: parsed.artifactType || 'document',
                    code: fullContent,
                    title: parsed.artifactTitle || 'Deep Research',
                  });
                }
                continue;
              }
              if (parsed.thinking) {
                markFirstChunk();
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
                markFirstChunk();
                fullContent += parsed.chunk;
                updateContent();
              }
            } catch (e) {
              // Non-JSON raw chunk
              if (data && data !== '[DONE]') {
                markFirstChunk();
                fullContent += data;
                updateContent();
              }
            }
          }
        }
      }

      // Flush remaining buffer
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

      updateAssistant({ streaming: false });
      setIsStreaming(false);
      leftMidStreamRef.current = false; // Stream completed normally — no reload needed
      // Refresh sidebar so the AI-generated title replaces the optimistic preview.
      if (onStreamComplete) {
        setTimeout(() => onStreamComplete(), 800);
      }
    } catch (error) {
      updateAssistant({ streaming: false });
      if (error.name === 'AbortError') {
        console.log('Stream aborted by user');
        setIsThinking(false);
        setIsStreaming(false);
        leftMidStreamRef.current = false;
        return;
      }

      console.error('Failed to send message:', error);
      setIsThinking(false);
      setIsStreaming(false);
      leftMidStreamRef.current = false;

      const errorMsg = {
        id: `msg-err-${Date.now()}`,
        role: 'assistant',
        content: `Sorry, there was an error: ${error.message || 'Please try again.'}`,
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
          {/* Mobile Menu Button */}
          <button
            data-testid="mobile-menu-btn"
            onClick={onOpenMobileSidebar}
            className="md:hidden p-1.5 rounded-md hover:bg-accent transition-colors duration-200"
          >
            <SidebarSimple className="w-5 h-5 text-muted-foreground" />
          </button>

          {sidebarCollapsed && (
            <button
              data-testid="expand-sidebar-btn"
              onClick={onExpandSidebar}
              className="hidden md:block p-1.5 rounded-md hover:bg-accent transition-colors duration-200 mr-1"
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

        <div className="flex items-center gap-1.5">
          {/* Voice input (mic → transcribe) */}
          <button
            data-testid="voice-mode-btn"
            onClick={toggleRecording}
            disabled={isTranscribing}
            title={isRecording ? 'Stop recording' : 'Voice input'}
            className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-md text-xs font-medium transition-all duration-200 ${isRecording
                ? 'bg-rose-500/15 text-rose-400 animate-pulse'
                : isTranscribing
                  ? 'bg-accent text-muted-foreground'
                  : 'hover:bg-accent text-muted-foreground'
              }`}
          >
            {isRecording
              ? <MicrophoneSlash className="w-3.5 h-3.5" weight="fill" />
              : <Microphone className="w-3.5 h-3.5" weight="duotone" />}
            <span className="hidden sm:inline">{isRecording ? 'Stop' : isTranscribing ? '…' : 'Voice'}</span>
          </button>

          {/* Kautilya Live — full-duplex voice agent */}
          <button
            data-testid="live-voice-btn"
            onClick={() => setIsLiveVoice(true)}
            title="Kautilya Live — speak with AI agent"
            className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-md text-xs font-medium hover:bg-accent text-muted-foreground transition-all duration-200"
          >
            <Phone className="w-3.5 h-3.5" weight="duotone" />
            <span className="hidden sm:inline">Live</span>
          </button>

          <button
            data-testid="toggle-canvas-btn"
            onClick={onToggleCanvas}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-all duration-200 ${canvasOpen
                ? 'bg-[var(--k-brand)] text-white'
                : 'hover:bg-accent text-muted-foreground'
              }`}
          >
            <Columns className="w-3.5 h-3.5" weight="duotone" />
            <span>Canvas</span>
          </button>
        </div>
      </div>

      {/* LiveKit full-duplex voice overlay */}
      {isLiveVoice && (
        <LiveKitVoice onClose={() => setIsLiveVoice(false)} />
      )}

      {/* Messages Area */}
      <ScrollArea className="flex-1">
        <div className="max-w-3xl mx-auto px-4 py-6 space-y-6">
          {messages.length === 0 && !isThinking && (
            <div className="flex flex-col items-center justify-center h-[60vh] animate-fade-up px-4 text-center">
              <div className="flex items-center justify-center mb-6">
                <img src="/logo.png" alt="Kautilya Logo" className="w-14 h-14 rounded-xl" />
              </div>
              <h2 className="text-2xl font-medium k-heading tracking-tight text-foreground mb-2">
                How can I help you today?
              </h2>
              <p className="text-sm text-muted-foreground mb-8">
                Research, analyze data, generate reports, or write code
              </p>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 max-w-md w-full px-2">
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

          {messages.map((msg, index) => (
            <ChatMessage
              key={msg.id}
              message={msg}
              onRegenerate={async (failedMsg) => {
                const userMsgIndex = messages.findIndex(m => m.id === failedMsg.id) - 1;
                if (userMsgIndex >= 0) {
                  const userMsg = messages[userMsgIndex];
                  setMessages(prev => prev.filter(m => m.id !== failedMsg.id && m.id !== userMsg.id));
                  let userText = '';
                  if (typeof userMsg.content === 'string') {
                    userText = userMsg.content;
                  } else if (Array.isArray(userMsg.content)) {
                    userText = userMsg.content
                      .filter(part => part && part.type === 'text')
                      .map(part => part.text || '')
                      .join('\n');
                  }
                  setInputValue(userText);
                  setTimeout(() => handleSend(), 50);
                }
              }}
              onOpenArtifact={(artifactOverride) => onOpenCanvas(artifactOverride || {
                type: msg.artifactType,
                code: msg.artifactCode || "",
                title: msg.artifactTitle || 'AI Analysis',
                filename: msg.artifactFilename || "",
                subtype: msg.artifactSubtype || "",
                messageId: msg.id,
              })}
            />
          ))}

          {isThinking && messages[messages.length - 1]?.role !== 'assistant' && (
            <ThinkingTokens
              text="Reading your question... Drafting response... Analyzing context... Routing to the right agent..."
            />
          )}

          {staleTimeout && (
            <div className="flex items-start gap-3 animate-fade-up">
              <div className="w-8 h-8 rounded-full bg-[var(--k-brand)]/10 flex items-center justify-center flex-shrink-0 mt-0.5">
                <span className="text-[var(--k-brand)] text-xs font-bold k-heading">K</span>
              </div>
              <div className="flex-1 max-w-2xl bg-[var(--k-surface)] border border-[var(--k-border)] rounded-xl px-4 py-3 text-sm text-muted-foreground">
                <p className="mb-2">The model is still processing your request in the background. This can happen when the server is busy or starting up.</p>
                <button
                  onClick={() => { setStaleTimeout(false); loadHistory(sessionId); }}
                  className="px-3 py-1.5 rounded-md bg-[var(--k-brand)] text-white text-xs font-semibold hover:opacity-90 transition-opacity"
                >
                  Check for response
                </button>
              </div>
            </div>
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
              {selectedFiles.map((file, i) => {
                const isImage = file.type && file.type.startsWith('image/');
                const sizeKb = Math.round(file.size / 1024);
                return (
                  <div
                    key={i}
                    className="group relative flex items-center gap-2 px-2 py-1 bg-accent/50 rounded-lg border border-[var(--k-border)] text-[11px]"
                  >
                    {isImage ? (
                      <img
                        src={URL.createObjectURL(file)}
                        alt={file.name}
                        className="w-10 h-10 rounded-md object-cover border border-[var(--k-border)]"
                        onLoad={(e) => URL.revokeObjectURL(e.currentTarget.src)}
                      />
                    ) : (
                      <Paperclip className="w-3.5 h-3.5 text-muted-foreground" />
                    )}
                    <div className="flex flex-col">
                      <span className="max-w-[140px] truncate text-foreground">{file.name}</span>
                      <span className="text-[10px] text-muted-foreground">
                        {sizeKb < 1024 ? `${sizeKb} KB` : `${(sizeKb / 1024).toFixed(1)} MB`}
                      </span>
                    </div>
                    <button
                      onClick={() => removeFile(i)}
                      className="p-1 rounded hover:bg-rose-500/20 hover:text-rose-400 transition-colors"
                      title="Remove"
                    >
                      <X className="w-3 h-3" />
                    </button>
                  </div>
                );
              })}
            </div>
          )}

          {/* Recording indicator */}
          {isRecording && (
            <div className="flex items-center gap-2 mb-2 px-3 py-1.5 rounded-md bg-rose-500/10 border border-rose-500/20 text-xs text-rose-400">
              <div className="w-2 h-2 rounded-full bg-rose-500 animate-pulse" />
              <span>Recording… click Stop Voice to finish</span>
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
            <input
              type="file"
              ref={imageInputRef}
              onChange={handleFileSelect}
              accept="image/*"
              multiple
              className="hidden"
            />
            <input
              type="file"
              ref={cameraInputRef}
              onChange={handleFileSelect}
              accept="image/*"
              capture="environment"
              className="hidden"
            />
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <button
                  data-testid="attach-file-btn"
                  className="p-3 text-muted-foreground hover:text-foreground transition-colors focus:outline-none"
                  title="Upload & Tools"
                >
                  <Paperclip className="w-4 h-4" />
                </button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="start" side="top" className="w-64 bg-[var(--k-surface)] border border-[var(--k-border)] rounded-xl shadow-xl p-1.5 z-[110]">
                <DropdownMenuLabel className="text-[10px] uppercase font-bold tracking-wider text-muted-foreground/70 px-2.5 py-1">
                  Upload Options
                </DropdownMenuLabel>
                <DropdownMenuItem
                  onClick={() => fileInputRef.current?.click()}
                  className="flex items-center gap-2.5 px-2.5 py-2 text-sm rounded-lg cursor-pointer hover:bg-accent text-foreground transition-colors duration-150"
                >
                  <File className="w-4 h-4 text-sky-400" weight="duotone" />
                  <span>Files</span>
                </DropdownMenuItem>
                <DropdownMenuItem
                  onClick={() => imageInputRef.current?.click()}
                  className="flex items-center gap-2.5 px-2.5 py-2 text-sm rounded-lg cursor-pointer hover:bg-accent text-foreground transition-colors duration-150"
                >
                  <Image className="w-4 h-4 text-emerald-400" weight="duotone" />
                  <span>Images</span>
                </DropdownMenuItem>
                <DropdownMenuItem
                  onClick={() => cameraInputRef.current?.click()}
                  className="flex items-center gap-2.5 px-2.5 py-2 text-sm rounded-lg cursor-pointer hover:bg-accent text-foreground transition-colors duration-150"
                >
                  <Camera className="w-4 h-4 text-rose-400" weight="duotone" />
                  <span>Camera</span>
                </DropdownMenuItem>
                <DropdownMenuItem
                  onClick={() => toast({
                    title: "Google Drive Placeholder",
                    description: "Drive integration completed. Placeholder successfully mounted.",
                  })}
                  className="flex items-center gap-2.5 px-2.5 py-2 text-sm rounded-lg cursor-pointer hover:bg-accent text-foreground transition-colors duration-150"
                >
                  <HardDrive className="w-4 h-4 text-amber-400" weight="duotone" />
                  <span>Drive</span>
                </DropdownMenuItem>

                <DropdownMenuSeparator className="border-t border-[var(--k-border)] my-1" />

                <DropdownMenuLabel className="text-[10px] uppercase font-bold tracking-wider text-muted-foreground/70 px-2.5 py-1">
                  Tools & Capabilities
                </DropdownMenuLabel>
                <DropdownMenuItem
                  onSelect={() => setShowMcpDialog(true)}
                  className="flex items-center gap-2.5 px-2.5 py-2 text-sm rounded-lg cursor-pointer hover:bg-accent text-foreground transition-colors duration-150"
                >
                  <Cpu className="w-4 h-4 text-indigo-400" weight="duotone" />
                  <span>MCP Servers</span>
                </DropdownMenuItem>

                <DropdownMenuSeparator className="border-t border-[var(--k-border)] my-1" />

                <DropdownMenuItem
                  onSelect={(e) => e.preventDefault()}
                  className="flex items-center justify-between gap-2.5 px-2.5 py-2 text-sm rounded-lg text-foreground focus:bg-transparent"
                >
                  <div className="flex items-center gap-2.5">
                    <Brain className={`w-4 h-4 transition-colors ${maxThinking ? 'text-purple-400' : 'text-muted-foreground'}`} weight={maxThinking ? "fill" : "duotone"} />
                    <div className="flex flex-col">
                      <span className="font-medium text-xs">Max Thinking</span>
                      <span className="text-[9px] text-muted-foreground">High reasoning mode</span>
                    </div>
                  </div>
                  <Switch
                    checked={maxThinking}
                    onCheckedChange={setMaxThinking}
                    className="scale-90 data-[state=checked]:bg-purple-600"
                  />
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
            <textarea
              ref={inputRef}
              data-testid="chat-input"
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={
                isRecording ? 'Recording voice...'
                  : activeMode === 'research'
                    ? 'Ask a research question...'
                    : activeMode === 'code'
                      ? 'Describe what you want to analyze...'
                      : 'Message Kautilya...'
              }
              rows={1}
              disabled={isRecording}
              className="flex-1 py-3 px-1 bg-transparent resize-none focus:outline-none text-sm text-foreground placeholder:text-muted-foreground max-h-32 disabled:opacity-60"
              style={{ minHeight: '44px' }}
            />
            {(isThinking || isStreaming) ? (
              <button
                data-testid="stop-generation-btn"
                onClick={handleStopGeneration}
                className="p-3 text-rose-500 hover:text-rose-400 transition-colors"
                title="Stop generation"
              >
                <StopCircle className="w-5 h-5" weight="fill" />
              </button>
            ) : (
              <button
                data-testid="send-message-btn"
                onClick={handleSend}
                disabled={(!inputValue.trim() && selectedFiles.length === 0) || isRecording}
                className={`p-3 transition-colors ${inputValue.trim() && !isRecording
                    ? 'text-[var(--k-brand)] hover:text-[var(--k-brand-hover)]'
                    : 'text-muted-foreground/40'
                  }`}
              >
                <ArrowRight className="w-5 h-5" weight="bold" />
              </button>
            )}
          </div>
          <div className="flex items-center justify-between mt-2 px-1">
            <div className="flex items-center gap-3">
              {modes.map(mode => (
                <button
                  key={mode.id}
                  data-testid={`quick-mode-${mode.id}`}
                  onClick={() => onSetMode(mode.id)}
                  className={`flex items-center gap-1 text-[11px] transition-colors ${activeMode === mode.id
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
      <Dialog open={showMcpDialog} onOpenChange={setShowMcpDialog}>
        <DialogContent className="sm:max-w-[700px] max-h-[85vh] flex flex-col p-6 overflow-hidden bg-[var(--k-surface-elevated)] border-[var(--k-border)] rounded-xl shadow-2xl">
          <DialogHeader className="pb-4 border-b border-[var(--k-border)]">
            <DialogTitle className="text-xl font-semibold tracking-tight text-foreground flex items-center gap-2">
              <Cpu className="w-5 h-5 text-indigo-400" weight="duotone" />
              Model Context Protocol (MCP) Servers
            </DialogTitle>
            <DialogDescription className="text-xs text-muted-foreground mt-1">
              Active and available MCP servers providing external tools, context, and integrations to Kautilya AI.
            </DialogDescription>
          </DialogHeader>

          {loadingMcp && !mcpStatus ? (
            <div className="flex-1 flex flex-col items-center justify-center py-12 gap-3">
              <div className="w-8 h-8 rounded-full border-2 border-[var(--k-brand)] border-t-transparent animate-spin" />
              <span className="text-xs text-muted-foreground">Querying MCP server status...</span>
            </div>
          ) : !mcpStatus ? (
            <div className="flex-1 flex flex-col items-center justify-center py-12 gap-3">
              <span className="text-xs text-rose-400">Failed to load MCP server configuration.</span>
              <button
                onClick={async () => {
                  setLoadingMcp(true);
                  try {
                    const data = await integrationsAPI.getMcpStatus();
                    setMcpStatus(data);
                  } catch (err) {
                    console.error("Failed to load MCP status:", err);
                  } finally {
                    setLoadingMcp(false);
                  }
                }}
                className="px-3 py-1.5 rounded-lg bg-[var(--k-brand)] hover:bg-[var(--k-brand-hover)] text-xs text-white transition-colors"
              >
                Retry
              </button>
            </div>
          ) : (() => {
            const servers = mcpStatus?.servers || [];

            // Group by category
            const categoriesMap = {};
            servers.forEach(s => {
              const catName = s.category || "Other";
              if (!categoriesMap[catName]) {
                categoriesMap[catName] = [];
              }
              categoriesMap[catName].push(s);
            });

            const groupedCategories = Object.keys(categoriesMap).map(catName => ({
              category: catName,
              servers: categoriesMap[catName]
            }));

            const total = servers.length;
            const q = mcpSearch.trim().toLowerCase();
            const filtered = groupedCategories
              .map(cat => ({
                ...cat,
                servers: q
                  ? cat.servers.filter(s =>
                    s.name.toLowerCase().includes(q) ||
                    (s.description || "").toLowerCase().includes(q) ||
                    s.tools.some(t => t.name.toLowerCase().includes(q) || t.underlying.toLowerCase().includes(q))
                  )
                  : cat.servers,
              }))
              .filter(cat => cat.servers.length > 0);

            return (
              <>
                <div className="px-1 pb-3 flex items-center gap-3 border-b border-[var(--k-border)]/50">
                  <div className="relative flex-1">
                    <input
                      type="text"
                      value={mcpSearch}
                      onChange={(e) => setMcpSearch(e.target.value)}
                      placeholder="Search MCP servers, tools, or capabilities..."
                      className="w-full pl-3 pr-3 py-2 text-xs bg-[var(--k-surface)] border border-[var(--k-border)] rounded-lg text-foreground focus:outline-none focus:ring-1 focus:ring-[var(--k-brand)] placeholder:text-muted-foreground"
                    />
                  </div>
                  <span className="text-[10px] text-muted-foreground whitespace-nowrap">
                    {q ? `${filtered.reduce((s, c) => s + c.servers.length, 0)} match` : `${total} servers`}
                  </span>
                </div>

                <div className="flex-1 mt-3 pr-2 overflow-y-auto min-h-0 max-h-[60vh] scrollbar-thin scrollbar-thumb-muted-foreground/30">
                  <div className="space-y-6">
                    {filtered.length === 0 && (
                      <div className="text-center py-12 text-xs text-muted-foreground">
                        No MCP servers found for "{mcpSearch}".
                      </div>
                    )}
                    {filtered.map(cat => (
                      <div key={cat.category}>
                        <div className="text-[10px] uppercase font-bold tracking-[0.18em] text-muted-foreground/70 mb-3 px-1">
                          {cat.category} <span className="text-muted-foreground/40 normal-case font-medium">· {cat.servers.length}</span>
                        </div>
                        <div className="space-y-3">
                          {cat.servers.map(server => {
                            const state = server.state || 'disabled';
                            const isActive = state === 'active';
                            const isError = state === 'error';
                            const isMissingEnv = state === 'missing_env';

                            let pillStyle = "text-muted-foreground bg-muted border-[var(--k-border)]";
                            let pillText = "Disabled";
                            let hasDot = false;

                            if (isActive) {
                              pillStyle = "text-emerald-400 bg-emerald-400/10 border-emerald-400/20";
                              pillText = "Active";
                              hasDot = true;
                            } else if (isError) {
                              pillStyle = "text-rose-400 bg-rose-400/10 border-rose-400/20";
                              pillText = "Error";
                              hasDot = true;
                            } else if (isMissingEnv) {
                              pillStyle = "text-amber-400 bg-amber-400/10 border-amber-400/20";
                              pillText = "Missing Env";
                              hasDot = true;
                            }

                            return (
                              <div
                                key={server.name}
                                className={`p-4 rounded-xl border transition-all duration-200 ${isActive
                                    ? 'border-[var(--k-border)] bg-[var(--k-surface)] hover:bg-[var(--k-surface-elevated)]'
                                    : 'border-[var(--k-border)] bg-[var(--k-surface)]/60 hover:bg-[var(--k-surface)] opacity-85 hover:opacity-100'
                                  }`}
                              >
                                <div className="flex items-start justify-between mb-2 gap-3">
                                  <div className="min-w-0">
                                    <div className="flex items-center gap-2 flex-wrap">
                                      <span className={`font-semibold text-sm ${isActive ? 'text-foreground' : 'text-foreground/90'}`}>
                                        {server.name}
                                      </span>
                                      <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[9px] font-medium border ${pillStyle}`}>
                                        {hasDot && (
                                          <span className={`w-1.5 h-1.5 rounded-full ${isActive ? 'bg-emerald-400 animate-pulse' :
                                              isError ? 'bg-rose-500' : 'bg-amber-400'
                                            }`} />
                                        )}
                                        {pillText}
                                      </span>
                                    </div>
                                    <p className={`text-xs mt-1 ${isActive ? 'text-muted-foreground' : 'text-muted-foreground/80'}`}>
                                      {server.description}
                                    </p>

                                    {isError && server.error && (
                                      <div className="mt-2 text-[10px] font-mono text-rose-400 bg-rose-950/20 border border-rose-900/30 rounded p-1.5 max-h-20 overflow-y-auto">
                                        Error: {server.error}
                                      </div>
                                    )}

                                    {isMissingEnv && server.env_required && (
                                      <div className="mt-2 text-[10px] text-amber-300">
                                        Required keys: {server.env_required.join(', ')}
                                      </div>
                                    )}
                                  </div>
                                </div>

                                {server.tools && server.tools.length > 0 && (
                                  <div className={`mt-3 pt-3 border-t ${isActive ? 'border-[var(--k-border)]/50' : 'border-[var(--k-border)]/30'}`}>
                                    <span className={`text-[10px] uppercase font-bold tracking-wider block mb-2 ${isActive ? 'text-muted-foreground/80' : 'text-muted-foreground/60'}`}>
                                      Exposed Tools ({server.tools.length})
                                    </span>
                                    <div className="flex flex-wrap gap-1.5">
                                      {server.tools.map(t => (
                                        <code
                                          key={t.name}
                                          title={`Underlying: ${t.underlying}`}
                                          className={`text-[10px] font-mono px-2 py-0.5 rounded ${isActive
                                              ? 'bg-muted border border-[var(--k-border)]/50 text-indigo-300'
                                              : 'bg-muted/30 border border-[var(--k-border)]/20 text-muted-foreground'
                                            }`}
                                        >
                                          {t.name}
                                        </code>
                                      ))}
                                    </div>
                                  </div>
                                )}
                              </div>
                            );
                          })}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </>
            );
          })()}
        </DialogContent>
      </Dialog>
      <Toaster />
    </div>
  );
}
