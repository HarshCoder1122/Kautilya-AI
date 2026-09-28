import { extractArtifact } from "./artifacts";

// Turn a persisted history message (snake_case fields, JSON-string side-data)
// into the exact shape <ChatMessage> renders during live streaming — so old
// chats AND shared chats show identical mermaid, images, code, tool cards,
// citations, artifacts and reasoning. Shared by ChatMain (history reload) and
// the public SharedChatPage so the two can never drift.
export function hydrateHistoryMessage(m) {
  const safeParse = (v) => {
    if (v == null) return v;
    if (typeof v !== 'string') return v;
    try { return JSON.parse(v); } catch (e) { return v; }
  };
  const toolResults = safeParse(m.tool_results);
  const reactStepsRaw = safeParse(m.react_steps);
  const citations = safeParse(m.citations);
  const artifact = safeParse(m.artifact);

  const rawContent = typeof m.content === 'string' ? m.content : '';
  let art = extractArtifact(rawContent);
  if (!art.hasArtifact && artifact) {
    art = {
      hasArtifact: true,
      artifactType: artifact.type || 'document',
      artifactTitle: artifact.title || 'Document',
      artifactCode: rawContent,
      cleanContent: rawContent,
    };
  }

  return {
    ...m,
    id: m.id || `msg-${Math.random()}`,
    content: (typeof m.content === 'string' && art.hasArtifact) ? art.cleanContent : m.content,
    timestamp: m.timestamp || new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    toolResults: Array.isArray(toolResults) ? toolResults : undefined,
    reactSteps: Array.isArray(reactStepsRaw) ? reactStepsRaw : undefined,
    citations: Array.isArray(citations) ? citations : undefined,
    agentType: m.agent_type || m.agentType,
    hasArtifact: art.hasArtifact,
    artifactType: art.artifactType,
    artifactTitle: art.artifactTitle,
    artifactCode: art.artifactCode,
    artifactFilename: art.artifactFilename,
    artifactSubtype: art.artifactSubtype,
    artifactLanguage: art.artifactLanguage,
    thinking: m.thinking || undefined,
    thinkingDone: !!m.thinking,
  };
}
