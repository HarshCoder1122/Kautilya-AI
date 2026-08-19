import { useState, useEffect, useCallback, useRef } from "react";
import { ChatSidebar } from "@/components/chat/ChatSidebar";
import { ChatMain } from "@/components/chat/ChatMain";
import { CanvasPane } from "@/components/chat/CanvasPane";
import { ComputerPanel } from "@/components/chat/ComputerPanel";
import { OnboardingModal } from "@/components/shared/OnboardingModal";
import { chatAPI } from "../lib/api";

// Local mirror of the first page of chat history so the sidebar paints
// instantly on open (no spinner), while the DB load refreshes it to the latest
// in the background. Keyed per user; capped so we never blow the quota.
const _histKey = (uid) => `kchat:history:${uid || 'anon'}`;
const _readHistoryCache = (uid) => {
  try {
    const raw = localStorage.getItem(_histKey(uid));
    if (!raw) return null;
    const arr = JSON.parse(raw);
    return Array.isArray(arr) && arr.length ? arr : null;
  } catch { return null; }
};
const _writeHistoryCache = (uid, chats) => {
  try { localStorage.setItem(_histKey(uid), JSON.stringify((chats || []).slice(0, 100))); }
  catch { /* quota / private mode — soft-fail */ }
};

export default function ChatPage({ theme, toggleTheme, user }) {
  const _cachedHistory = _readHistoryCache(user?.uid);
  const [selectedConversation, setSelectedConversation] = useState(null);
  const [canvasOpen, setCanvasOpen] = useState(false);
  const [canvasContent, setCanvasContent] = useState(null);
  const [computerOpen, setComputerOpen] = useState(false);
  const [computerRefreshSignal, setComputerRefreshSignal] = useState(0);
  // Auto-open the Computer panel at most once per session so it doesn't keep
  // popping back after the user explicitly closes it (shared by both the
  // Files and Browser tabs — either activity can trigger the first open).
  const computerAutoOpenedRef = useRef(new Set());
  // Latest live-browsed page (url/title/screenshot/links) — a single object,
  // not a history list, since the Browser tab shows ONE persistent "current
  // screen" rather than a card per action.
  const [browserState, setBrowserState] = useState(null);
  const [browseSignal, setBrowseSignal] = useState(0);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);
  const [activeMode, setActiveMode] = useState('pro'); // Pro selected by default on open
  const [conversations, setConversations] = useState(_cachedHistory || []);
  // Skip the spinner if we already have a cached list to show instantly.
  const [convoLoading, setConvoLoading] = useState(!_cachedHistory);
  // Pagination cursor for "load older chats". null once there are no more.
  const [historyCursor, setHistoryCursor] = useState(null);
  const [loadingMore, setLoadingMore] = useState(false);
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

  // Canvas and Computer share the same side-panel slot — opening one closes
  // the other rather than trying to fit both side by side.
  const handleToggleComputer = useCallback(() => {
    setComputerOpen(open => {
      if (!open) setCanvasOpen(false);
      return !open;
    });
  }, []);

  const handleComputerActivity = useCallback(() => {
    if (selectedConversation && computerAutoOpenedRef.current.has(selectedConversation)) return;
    if (selectedConversation) computerAutoOpenedRef.current.add(selectedConversation);
    setCanvasOpen(false);
    setComputerOpen(true);
  }, [selectedConversation]);

  // Every browse/click/type result updates the SAME live view (not a new
  // card) — the panel switches to its Browser tab on every call (see
  // ComputerPanel's browseSignal effect), but only force-OPENS the panel
  // the first time this session, same as file activity.
  const handleBrowseUpdate = useCallback((data) => {
    setBrowserState(data);
    setBrowseSignal(v => v + 1);
    if (selectedConversation && computerAutoOpenedRef.current.has(selectedConversation)) return;
    if (selectedConversation) computerAutoOpenedRef.current.add(selectedConversation);
    setCanvasOpen(false);
    setComputerOpen(true);
  }, [selectedConversation]);

  // Switching chats shouldn't keep showing a PREVIOUS conversation's browsed
  // page.
  useEffect(() => { setBrowserState(null); }, [selectedConversation]);

  const refreshSessions = useCallback(async () => {
    try {
      const data = await chatAPI.getHistory();
      setConversations(data.chats || []);
      setHistoryCursor(data.next_before || null);
      _writeHistoryCache(user?.uid, data.chats || []); // refresh the local mirror
    } catch (e) {
      console.error('Failed to load conversations:', e);
    } finally {
      setConvoLoading(false);
    }
  }, [user?.uid]);

  const handleStreamComplete = useCallback(() => {
    refreshSessions();
    setComputerRefreshSignal(v => v + 1);
  }, [refreshSessions]);

  // Append the next page of older chats (dedup by session id).
  const loadMoreSessions = useCallback(async () => {
    if (!historyCursor || loadingMore) return;
    setLoadingMore(true);
    try {
      const data = await chatAPI.getHistory({ before: historyCursor });
      setConversations(prev => {
        const seen = new Set(prev.map(c => c.session_id || c.id));
        const older = (data.chats || []).filter(c => !seen.has(c.session_id || c.id));
        return [...prev, ...older];
      });
      setHistoryCursor(data.next_before || null);
    } catch (e) {
      console.error('Failed to load older conversations:', e);
    } finally {
      setLoadingMore(false);
    }
  }, [historyCursor, loadingMore]);

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
        onLoadMore={loadMoreSessions}
        hasMore={!!historyCursor}
        loadingMore={loadingMore}
      />
      <ChatMain
        sidebarCollapsed={sidebarCollapsed}
        onExpandSidebar={() => setSidebarCollapsed(false)}
        onOpenMobileSidebar={() => setMobileSidebarOpen(true)}
        canvasOpen={canvasOpen}
        onToggleCanvas={() => { if (canvasOpen) handleCloseCanvas(); else { setComputerOpen(false); setCanvasOpen(true); } }}
        onOpenCanvas={handleOpenCanvas}
        computerOpen={computerOpen}
        onToggleComputer={handleToggleComputer}
        onComputerActivity={handleComputerActivity}
        onBrowseUpdate={handleBrowseUpdate}
        activeMode={activeMode}
        onSetMode={setActiveMode}
        theme={theme}
        toggleTheme={toggleTheme}
        sessionId={selectedConversation}
        onSessionChange={setSelectedConversation}
        onNewSession={addOptimisticSession}
        onStreamComplete={handleStreamComplete}
      />
      {canvasOpen && (
        <CanvasPane
          content={canvasContent}
          onClose={handleCloseCanvas}
          activeMode={activeMode}
        />
      )}
      {computerOpen && (
        <ComputerPanel
          sessionId={selectedConversation}
          onClose={() => setComputerOpen(false)}
          refreshSignal={computerRefreshSignal}
          browserState={browserState}
          browseSignal={browseSignal}
        />
      )}
      <OnboardingModal user={user} />
    </div>
  );
}
