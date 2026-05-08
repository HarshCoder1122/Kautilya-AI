import { useState } from "react";
import { ChatSidebar } from "@/components/chat/ChatSidebar";
import { ChatMain } from "@/components/chat/ChatMain";
import { CanvasPane } from "@/components/chat/CanvasPane";
import { ThemeToggle } from "@/components/shared/ThemeToggle";

export default function ChatPage({ theme, toggleTheme }) {
  const [selectedConversation, setSelectedConversation] = useState(null);
  const [canvasOpen, setCanvasOpen] = useState(false);
  const [canvasContent, setCanvasContent] = useState(null);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [activeMode, setActiveMode] = useState('chat'); // chat, research, code

  const handleSessionChange = (sessionId) => {
    setSelectedConversation(sessionId);
  };

  return (
    <div className="chat-layout" data-testid="chat-page">
      {!sidebarCollapsed && (
        <ChatSidebar
          selectedConversation={selectedConversation}
          onSelectConversation={setSelectedConversation}
          onCollapse={() => setSidebarCollapsed(true)}
          theme={theme}
          toggleTheme={toggleTheme}
        />
      )}
      <ChatMain
        sidebarCollapsed={sidebarCollapsed}
        onExpandSidebar={() => setSidebarCollapsed(false)}
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
