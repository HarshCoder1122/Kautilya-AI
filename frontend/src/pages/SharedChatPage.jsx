import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { ChatMessage } from "@/components/chat/ChatMessage";
import { CanvasPane } from "@/components/chat/CanvasPane";
import { hydrateHistoryMessage } from "../lib/hydrateMessage";
import { chatAPI } from "../lib/api";

// Brand blue for the shared-page chrome (replaces the app's orange header here).
const BLUE = "#2563EB";

// Public, login-free read-only viewer for a shared chat. Renders with the SAME
// <ChatMessage> the in-app chat uses, so mermaid diagrams, images, code blocks,
// tables, tool cards, citations and artifacts all look identical.
export default function SharedChatPage() {
  const { shareId } = useParams();
  const [state, setState] = useState({ status: "loading", data: null });
  const [artifact, setArtifact] = useState(null);

  useEffect(() => {
    document.title = "Shared chat — Kautilya AI";
    document.documentElement.classList.add("dark");
    let cancelled = false;
    (async () => {
      try {
        const data = await chatAPI.getShared(shareId);
        if (!cancelled) setState({ status: "ok", data });
        if (!cancelled && data?.title) document.title = `${data.title} — Kautilya AI`;
      } catch (e) {
        const code = e?.status === 404 ? "not_found" : e?.status === 410 ? "revoked" : "error";
        if (!cancelled) setState({ status: code, data: null });
      }
    })();
    return () => { cancelled = true; };
  }, [shareId]);

  const messages = (state.data?.messages || []).map(hydrateHistoryMessage);

  return (
    <div className="min-h-screen flex flex-col bg-background text-foreground">
      {/* Top bar (blue) */}
      <div className="border-b border-[var(--k-border)] px-4 sm:px-6 py-3 flex items-center justify-between sticky top-0 bg-background/90 backdrop-blur z-20">
        <a href="/" className="flex items-center gap-2">
          <img src="/logo.png" alt="Kautilya" className="w-7 h-7 rounded-lg object-contain" />
          <span className="font-bold text-base tracking-tight" style={{ color: BLUE }}>Kautilya AI</span>
        </a>
        <a
          href="/"
          className="text-xs font-semibold px-3 py-1.5 rounded-lg text-white hover:opacity-90 transition-opacity"
          style={{ backgroundColor: BLUE }}
        >
          Try Kautilya free
        </a>
      </div>

      <div className="flex-1 overflow-y-auto">
        <div className="max-w-3xl mx-auto px-4 py-6">
          {state.status === "loading" && (
            <div className="flex flex-col items-center justify-center h-[60vh] text-muted-foreground">
              <div className="w-10 h-10 border-2 rounded-full animate-spin mb-3"
                   style={{ borderColor: `${BLUE}33`, borderTopColor: BLUE }} />
              <div className="text-xs tracking-widest uppercase">Loading shared chat</div>
            </div>
          )}

          {(state.status === "not_found" || state.status === "revoked" || state.status === "error") && (
            <div className="flex flex-col items-center justify-center h-[60vh] text-center px-6">
              <div className="text-4xl mb-4">{state.status === "revoked" ? "🔒" : "🔍"}</div>
              <h1 className="text-xl font-bold mb-2">
                {state.status === "revoked" ? "This link was disabled" : state.status === "not_found" ? "Chat not found" : "Couldn't load this chat"}
              </h1>
              <p className="text-sm text-muted-foreground max-w-sm">
                {state.status === "revoked"
                  ? "The person who shared this chat turned the link off."
                  : state.status === "not_found"
                  ? "This shared link is invalid or has been removed."
                  : "Something went wrong fetching this conversation. Please try again later."}
              </p>
              <a href="/" className="mt-6 text-xs font-semibold px-4 py-2 rounded-lg text-white" style={{ backgroundColor: BLUE }}>
                Go to Kautilya AI
              </a>
            </div>
          )}

          {state.status === "ok" && (
            <>
              <div className="mb-6 pb-4 border-b border-[var(--k-border)]">
                <h1 className="text-2xl font-bold tracking-tight mb-1 k-heading">{state.data.title || "Shared chat"}</h1>
                <p className="text-xs text-muted-foreground">
                  {state.data.shared_by ? `Shared by ${state.data.shared_by}` : "Shared conversation"}
                  {state.data.message_count ? ` · ${state.data.message_count} messages` : ""}
                  {" · read-only"}
                </p>
              </div>

              <div className="space-y-6">
                {messages.map((m) => (
                  <ChatMessage
                    key={m.id}
                    message={m}
                    onRegenerate={() => {}}
                    onOpenArtifact={(override) => setArtifact(override || {
                      type: m.artifactType,
                      code: m.artifactCode || "",
                      title: m.artifactTitle || "AI Analysis",
                      filename: m.artifactFilename || "",
                      subtype: m.artifactSubtype || "",
                      messageId: m.id,
                    })}
                  />
                ))}
              </div>

              <div className="mt-12 pt-6 border-t border-[var(--k-border)] text-center">
                <p className="text-xs text-muted-foreground mb-3">This conversation was created with Kautilya AI.</p>
                <a href="/" className="text-xs font-semibold px-4 py-2 rounded-lg text-white" style={{ backgroundColor: BLUE }}>
                  Start your own chat — free
                </a>
              </div>
            </>
          )}
        </div>
      </div>

      {/* Artifact / canvas overlay — opens like the in-app canvas */}
      {artifact && (
        <div className="fixed inset-0 sm:inset-y-0 sm:left-auto sm:right-0 sm:w-[60%] z-50 bg-background border-l border-[var(--k-border)] shadow-2xl">
          <CanvasPane content={artifact} onClose={() => setArtifact(null)} activeMode="chat" />
        </div>
      )}
    </div>
  );
}
