import { useState } from "react";
import { Plus, MagnifyingGlass, ChatCircleDots, SidebarSimple, Brain, Code, ChartBar, SignOut, UserCircle } from "@phosphor-icons/react";
import { ThemeToggle } from "@/components/shared/ThemeToggle";
import { logout } from "../../lib/firebase";
import { ScrollArea } from "@/components/ui/scroll-area";
import { useNavigate } from "react-router-dom";

const agentIcons = {
  researcher: <Brain className="w-3 h-3" />,
  coder: <Code className="w-3 h-3" />,
  sales: <ChartBar className="w-3 h-3" />,
  daily: <ChartBar className="w-3 h-3" />,
};

const agentColors = {
  researcher: 'text-blue-400',
  coder: 'text-emerald-400',
  sales: 'text-amber-400',
  daily: 'text-purple-400',
};

export function ChatSidebar({ selectedConversation, onSelectConversation, onCollapse, theme, toggleTheme, user, isOpen, onClose, conversations = [], loading = false, onRefresh, onLoadMore, hasMore = false, loadingMore = false }) {
  const [searchQuery, setSearchQuery] = useState('');
  const navigate = useNavigate();

  const filtered = conversations.filter(c =>
    (c.title || c.preview || 'Untitled').toLowerCase().includes(searchQuery.toLowerCase())
  );

  const handleNewChat = () => {
    onSelectConversation(null);
    if (onClose) onClose();
  };

  return (
    <>
      <div className={`sidebar-overlay ${isOpen ? 'active' : ''}`} onClick={onClose} />
      <div className={`chat-sidebar ${isOpen ? 'open' : ''}`} data-testid="chat-sidebar">
        {/* Header */}
        <div className="p-4 flex items-center justify-between border-b border-[var(--k-border)]">
          <div className="flex items-center gap-2">
            <img src="/logo.png" alt="Kautilya Logo" className="w-7 h-7 object-contain" />
            <span className="text-sm font-semibold k-heading tracking-tight text-foreground">Kautilya AI</span>
          </div>
          <div className="flex items-center gap-1">
            <ThemeToggle theme={theme} toggleTheme={toggleTheme} />
            <button
              data-testid="collapse-sidebar-btn"
              onClick={onCollapse}
              className="p-2 rounded-md hover:bg-accent transition-colors duration-200"
            >
              <SidebarSimple className="w-4 h-4 text-muted-foreground" />
            </button>
          </div>
        </div>

        {/* New Chat */}
        <div className="p-3">
          <button
            data-testid="new-chat-btn"
            onClick={handleNewChat}
            className="w-full flex items-center gap-2 px-3 py-2.5 rounded-md border border-[var(--k-border)] hover:bg-accent transition-all duration-200 text-sm text-foreground"
          >
            <Plus className="w-4 h-4" />
            <span>New Chat</span>
          </button>
        </div>

        {/* Search */}
        <div className="px-3 pb-2">
          <div className="relative">
            <MagnifyingGlass className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-muted-foreground" />
            <input
              data-testid="search-conversations-input"
              type="text"
              placeholder="Search conversations..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-9 pr-3 py-2 text-xs bg-transparent border border-[var(--k-border)] rounded-md focus:outline-none focus:ring-1 focus:ring-[var(--k-brand)] text-foreground placeholder:text-muted-foreground"
            />
          </div>
        </div>

        {/* Conversations */}
        <ScrollArea className="flex-1">
          <div className="px-2 py-1">
            <span className="px-2 text-[10px] tracking-[0.2em] uppercase font-semibold text-muted-foreground">Recent</span>
          </div>
          <div className="px-2 space-y-0.5">
            {loading ? (
              <div className="px-3 py-4 text-xs text-muted-foreground">Loading conversations...</div>
            ) : filtered.length === 0 ? (
              <div className="px-3 py-4 text-xs text-muted-foreground">No conversations yet</div>
            ) : (
              filtered.map((conv) => {
                const agentType = conv.model || 'daily';
                return (
                  <button
                    key={conv.session_id || conv.id}
                    data-testid={`conversation-${conv.session_id || conv.id}`}
                    onClick={() => {
                      onSelectConversation(conv.session_id || conv.id);
                      if (onClose) onClose();
                    }}
                    className={`w-full text-left px-3 py-2.5 rounded-md transition-all duration-200 group ${
                      selectedConversation === (conv.session_id || conv.id)
                        ? 'bg-accent'
                        : 'hover:bg-accent/50'
                    }`}
                  >
                    <div className="flex items-center gap-2 mb-0.5">
                      <span className={`${agentColors[agentType] || agentColors.daily}`}>
                        {agentIcons[agentType] || agentIcons.daily}
                      </span>
                      <span className="text-sm font-medium text-foreground truncate">
                        {conv.title || conv.preview || 'Untitled'}
                      </span>
                    </div>
                    <p className="text-xs text-muted-foreground truncate pl-5">{conv.preview || conv.lastMessage || 'No message'}</p>
                    <span className="text-[10px] text-muted-foreground/60 pl-5">
                      {conv.last_updated ? new Date(conv.last_updated).toLocaleString() : conv.timestamp}
                    </span>
                  </button>
                );
              })
            )}

            {/* Load older chats — pages back through the full history so chats
                beyond the first page aren't lost. Hidden while searching. */}
            {!loading && hasMore && !searchQuery && (
              <button
                data-testid="load-older-chats-btn"
                onClick={onLoadMore}
                disabled={loadingMore}
                className="w-full mt-1 px-3 py-2 rounded-md text-xs font-medium text-muted-foreground hover:bg-accent/50 transition-colors disabled:opacity-50"
              >
                {loadingMore ? 'Loading…' : 'Load older chats'}
              </button>
            )}
          </div>
        </ScrollArea>

        {/* Footer */}
        <div className="p-3 border-t border-[var(--k-border)] space-y-1">
          <button
            data-testid="go-to-dashboard-btn"
            onClick={() => navigate('/dashboard')}
            className="w-full flex items-center gap-2 px-3 py-2 rounded-md hover:bg-accent transition-colors duration-200 text-sm text-muted-foreground"
          >
            <ChartBar className="w-4 h-4" />
            <span>Dashboard</span>
          </button>
          
          <div className="pt-2 px-1">
            <div className="flex items-center justify-between p-2 rounded-lg bg-white/5 border border-white/5">
              <div className="flex items-center gap-2 overflow-hidden">
                {user?.photoURL ? (
                  <img src={user.photoURL} alt="" className="w-7 h-7 rounded-full" />
                ) : (
                  <UserCircle className="w-7 h-7 text-muted-foreground" />
                )}
                <div className="overflow-hidden">
                  <div className="text-xs font-medium truncate text-foreground">{user?.displayName || 'User'}</div>
                  <div className="text-[10px] truncate text-muted-foreground">{user?.email}</div>
                </div>
              </div>
              <button
                onClick={() => logout()}
                className="p-1.5 rounded-md hover:bg-rose-500/10 text-muted-foreground hover:text-rose-400 transition-colors"
                title="Sign Out"
              >
                <SignOut className="w-4 h-4" />
              </button>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
