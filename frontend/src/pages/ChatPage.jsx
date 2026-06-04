import { useState, useEffect, useCallback, useRef } from "react";
import { ChatSidebar } from "@/components/chat/ChatSidebar";
import { ChatMain } from "@/components/chat/ChatMain";
import { CanvasPane } from "@/components/chat/CanvasPane";
import { OnboardingModal } from "@/components/shared/OnboardingModal";
import { chatAPI } from "../lib/api";

export default function ChatPage({ theme, toggleTheme, user }) {
  const [selectedConversation, setSelectedConversation] = useState(null);
  const [canvasOpen, setCanvasOpen] = useState(false);
  const [canvasContent, setCanvasContent] = useState(null);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);
  const [activeMode, setActiveMode] = useState('chat');
  const [conversations, setConversations] = useState([]);
  const [convoLoading, setConvoLoading] = useState(true);
  // Track artifacts the user explicitly closed so the live stream doesn't keep
  // re-opening the canvas on every chunk. Keyed by messageId.
  const closedArtifactsRef = useRef(new Set());

  // opts.auto = true  → streaming update: refresh canvas content, but do NOT
  //                     re-open if the user already closed it for this message.
  // opts.auto = false → explicit user action (artifact button): always open and
  //                     clear any prior "closed" mark.
  const handleOpenCanvas = useCallback((content, opts = {}) => {
    setCanvasContent(content);
    const mid = content?.messageId;
    if (opts.auto) {
      if (mid && closedArtifactsRef.current.has(mid)) return; // stay closed
      setCanvasOpen(true);
    } else {
      if (mid) closedArtifactsRef.current.delete(mid);
      setCanvasOpen(true);
    }
  }, []);

  const handleCloseCanvas = useCallback(() => {
    setCanvasOpen(false);
    setCanvasContent(prev => {
      if (prev?.messageId) closedArtifactsRef.current.add(prev.messageId);
      return prev;
    });
  }, []);

  const refreshSessions = useCallback(async () => {
    try {
      const data = await chatAPI.getHistory();
      setConversations(data.chats || []);
    } catch (e) {
      console.error('Failed to load conversations:', e);
    } finally {
      setConvoLoading(false);
    }
  }, []);

  useEffect(() => { refreshSessions(); }, [refreshSessions]);

  // Optimistically add a new session to the top of the sidebar.
  const addOptimisticSession = useCallback((sess) => {
    setConversations(prev => {
      if (prev.some(c => (c.id || c.session_id) === sess.id)) return prev;
      return [{
        id: sess.id,
        session_id: sess.id,
        title: sess.title || 'New Chat',
        preview: sess.preview || '',
        last_updated: Date.now() / 1000,
        _optimistic: true,
      }, ...prev];
    });
  }, []);

  return (
    <div className={`chat-layout ${sidebarCollapsed ? 'sidebar-collapsed' : ''}`} data-testid="chat-page">
      <ChatSidebar
        selectedConversation={selectedConversation}
        onSelectConversation={setSelectedConversation}
        onCollapse={() => setSidebarCollapsed(true)}
        theme={theme}
        toggleTheme={toggleTheme}
        user={user}
        isOpen={mobileSidebarOpen}
        onClose={() => setMobileSidebarOpen(false)}
        conversations={conversations}
        loading={convoLoading}
        onRefresh={refreshSessions}
      />
      <ChatMain
        sidebarCollapsed={sidebarCollapsed}
        onExpandSidebar={() => setSidebarCollapsed(false)}
        onOpenMobileSidebar={() => setMobileSidebarOpen(true)}
        canvasOpen={canvasOpen}
        onToggleCanvas={() => { if (canvasOpen) handleCloseCanvas(); else setCanvasOpen(true); }}
        onOpenCanvas={handleOpenCanvas}
        activeMode={activeMode}
        onSetMode={setActiveMode}
        theme={theme}
        toggleTheme={toggleTheme}
        sessionId={selectedConversation}
        onSessionChange={setSelectedConversation}
        onNewSession={addOptimisticSession}
        onStreamComplete={refreshSessions}
      />
      {canvasOpen && (
        <CanvasPane
          content={canvasContent}
          onClose={handleCloseCanvas}
          activeMode={activeMode}
        />
      )}
      <OnboardingModal user={user} />
    </div>
  );
}
