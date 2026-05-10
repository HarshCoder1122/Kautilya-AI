import { useState } from "react";
import { ChatSidebar } from "@/components/chat/ChatSidebar";
import { ChatMain } from "@/components/chat/ChatMain";
import { CanvasPane } from "@/components/chat/CanvasPane";
import { ThemeToggle } from "@/components/shared/ThemeToggle";

export default function ChatPage({ theme, toggleTheme, user }) {
  const [selectedConversation, setSelectedConversation] = useState(null);
  const [canvasOpen, setCanvasOpen] = useState(false);
  const [canvasContent, setCanvasContent] = useState(null);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);
  const [activeMode, setActiveMode] = useState('chat'); // chat, research, code

  const handleSessionChange = (sessionId) => {
    setSelectedConversation(sessionId);
  };

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
      />
      <ChatMain
        sidebarCollapsed={sidebarCollapsed}
        onExpandSidebar={() => setSidebarCollapsed(false)}
        onOpenMobileSidebar={() => setMobileSidebarOpen(true)}
        canvasOpen={canvasOpen}
        onToggleCanvas={() => setCanvasOpen(!canvasOpen)}
        onOpenCanvas={(content) => { setCanvasContent(content); setCanvasOpen(true); }}
        activeMode={activeMode}
        onSetMode={setActiveMode}
        theme={theme}
        toggleTheme={toggleTheme}
        sessionId={selectedConversation}
        onSessionChange={handleSessionChange}
      />
      {canvasOpen && (
        <CanvasPane
          content={canvasContent}
          onClose={() => setCanvasOpen(false)}
          activeMode={activeMode}
        />
      )}
    </div>
  );
}
