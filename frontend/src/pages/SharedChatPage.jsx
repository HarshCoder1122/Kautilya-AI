import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { chatAPI } from "../lib/api";

// Public, login-free read-only viewer for a shared chat. Anyone with the
// /share/<id> link sees the conversation snapshot — no account required.
export default function SharedChatPage() {
  const { shareId } = useParams();
  const [state, setState] = useState({ status: "loading", data: null });

  useEffect(() => {
    document.title = "Shared chat — Kautilya AI";
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

  return (
    <div className="min-h-screen bg-[#07070a] text-[#f5f5f7] font-sans flex flex-col">
      {/* Top bar */}
      <div className="border-b border-[#1f2029] px-6 py-3 flex items-center justify-between sticky top-0 bg-[#07070a]/90 backdrop-blur z-10">
        <a href="/" className="flex items-center gap-2">
          <img src="/logo.png" alt="Kautilya" className="w-7 h-7 rounded-lg" />
          <span className="text-[#FF6D3F] font-bold text-base tracking-tight">Kautilya AI</span>
        </a>
        <a
          href="/"
          className="text-xs font-semibold px-3 py-1.5 rounded-lg bg-[#FF6D3F] text-white hover:opacity-90 transition-opacity"
        >
          Try Kautilya free
        </a>
      </div>

      <div className="flex-1 w-full max-w-3xl mx-auto px-4 py-8">
        {state.status === "loading" && (
          <div className="flex flex-col items-center justify-center h-[60vh] text-gray-500">
            <div className="w-10 h-10 border-2 border-indigo-500/20 border-t-indigo-500 rounded-full animate-spin mb-3" />
            <div className="text-xs tracking-widest uppercase">Loading shared chat</div>
          </div>
        )}

        {(state.status === "not_found" || state.status === "revoked" || state.status === "error") && (
          <div className="flex flex-col items-center justify-center h-[60vh] text-center px-6">
            <div className="text-4xl mb-4">{state.status === "revoked" ? "🔒" : "🔍"}</div>
            <h1 className="text-xl font-bold text-white mb-2">
              {state.status === "revoked" ? "This link was disabled" : state.status === "not_found" ? "Chat not found" : "Couldn't load this chat"}
            </h1>
            <p className="text-sm text-gray-500 max-w-sm">
              {state.status === "revoked"
                ? "The person who shared this chat turned the link off."
                : state.status === "not_found"
                ? "This shared link is invalid or has been removed."
                : "Something went wrong fetching this conversation. Please try again later."}
            </p>
            <a href="/" className="mt-6 text-xs font-semibold px-4 py-2 rounded-lg bg-[#FF6D3F] text-white">
              Go to Kautilya AI
            </a>
          </div>
        )}

        {state.status === "ok" && (
          <>
            <div className="mb-8">
              <h1 className="text-2xl font-bold text-white tracking-tight mb-1">{state.data.title || "Shared chat"}</h1>
              <p className="text-xs text-gray-500">
                {state.data.shared_by ? `Shared by ${state.data.shared_by}` : "Shared conversation"}
                {state.data.message_count ? ` · ${state.data.message_count} messages` : ""}
                {" · read-only"}
              </p>
            </div>

            <div className="space-y-5">
              {(state.data.messages || []).map((m, i) => (
                <Bubble key={i} role={m.role} content={m.content} />
              ))}
            </div>

            <div className="mt-12 pt-6 border-t border-[#1f2029] text-center">
              <p className="text-xs text-gray-600 mb-3">This conversation was created with Kautilya AI.</p>
              <a href="/" className="text-xs font-semibold px-4 py-2 rounded-lg bg-[#FF6D3F] text-white">
                Start your own chat — free
              </a>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

function Bubble({ role, content }) {
  const isUser = role === "user";
  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div className={`max-w-[85%] ${isUser ? "items-end" : "items-start"} flex flex-col`}>
        <div className="text-[10px] uppercase tracking-wider text-gray-600 mb-1 px-1">
          {isUser ? "You" : "Kautilya"}
        </div>
        <div
          className={`rounded-2xl px-4 py-3 text-sm leading-relaxed ${
            isUser
              ? "bg-indigo-600 text-white"
              : "bg-[#0f0f15] border border-[#1f2029] text-gray-200"
          }`}
        >
          {isUser ? (
            <div className="whitespace-pre-wrap break-words">{content}</div>
          ) : (
            <div className="prose prose-invert prose-sm max-w-none break-words prose-pre:bg-[#07070a] prose-pre:border prose-pre:border-[#1f2029]">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{String(content || "")}</ReactMarkdown>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
