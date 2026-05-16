import { useState, useEffect } from "react";
import {
  Code, Copy, Check, Key, ArrowSquareOut, Eye, EyeSlash,
  Lightning, Brain, Robot, ArrowClockwise, Terminal,
  BookOpen, Cpu, Microphone, Phone
} from "@phosphor-icons/react";
import { keysAPI } from "../../lib/api";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { vscDarkPlus } from "react-syntax-highlighter/dist/esm/styles/prism";

const API_BASE_URL =
  window.location.hostname === "localhost"
    ? "http://localhost:5000"
    : window.location.origin;

const V1_BASE = `${API_BASE_URL}/api/v1`;
const BACKEND = API_BASE_URL;

const MODELS = [
  {
    id: "kautilya-daily",
    label: "Kautilya Daily",
    icon: Lightning,
    color: "var(--k-yellow)",
    tier: "Fast · Streaming",
    ctx: "128k",
    desc: "Fast general-purpose chat. Best for high-throughput apps, chatbots, and quick Q&A.",
  },
  {
    id: "kautilya-pro",
    label: "Kautilya Pro",
    icon: Brain,
    color: "var(--k-brand)",
    tier: "Reasoning · Strategic",
    ctx: "128k",
    desc: "Deep strategic reasoning with toggleable thinking. Best for analysis, research, and complex tasks.",
  },
  {
    id: "kautilya-coder",
    label: "Kautilya Coder",
    icon: Robot,
    color: "#10b981",
    tier: "Code · Frontier",
    ctx: "128k",
    desc: "Frontier code generation with extended thinking. Best for software development and architecture.",
  },
];

const EXAMPLES = {
  python: `from openai import OpenAI

client = OpenAI(
    api_key="YOUR_KEY_HERE",
    base_url="${V1_BASE}",
)

# Streaming response
stream = client.chat.completions.create(
    model="kautilya-coder",
    messages=[
        {"role": "system", "content": "You are a senior software architect."},
        {"role": "user", "content": "Build a FastAPI auth endpoint with JWT"}
    ],
    stream=True,
)

for chunk in stream:
    print(chunk.choices[0].delta.content or "", end="", flush=True)`,

  javascript: `import OpenAI from "openai";

const client = new OpenAI({
    apiKey: "YOUR_KEY_HERE",
    baseURL: "${V1_BASE}",
    dangerouslyAllowBrowser: true, // only for local dev
});

const stream = await client.chat.completions.create({
    model: "kautilya-pro",
    messages: [
        { role: "user", content: "Analyze India's fintech market in 2025" }
    ],
    stream: true,
});

for await (const chunk of stream) {
    process.stdout.write(chunk.choices[0]?.delta?.content ?? "");
}`,

  curl: `curl ${V1_BASE}/chat/completions \\
  -H "Content-Type: application/json" \\
  -H "Authorization: Bearer YOUR_KEY_HERE" \\
  -d '{
    "model": "kautilya-daily",
    "messages": [
      {"role": "user", "content": "Hello Kautilya!"}
    ],
    "stream": true
  }'`,

  cline: `// VS Code → Settings → Open settings.json
// Add under Cline (saoudrizwan.claude-dev) extension:
{
  "cline.apiProvider": "openai",
  "cline.openAiBaseUrl": "${V1_BASE}",
  "cline.openAiApiKey": "YOUR_KEY_HERE",
  "cline.openAiModelId": "kautilya-coder"
}`,

  continue: `// ~/.continue/config.json  (Continue extension)
{
  "models": [
    {
      "title": "Kautilya Coder",
      "provider": "openai",
      "model": "kautilya-coder",
      "apiKey": "YOUR_KEY_HERE",
      "apiBase": "${V1_BASE}"
    },
    {
      "title": "Kautilya Pro",
      "provider": "openai",
      "model": "kautilya-pro",
      "apiKey": "YOUR_KEY_HERE",
      "apiBase": "${V1_BASE}"
    }
  ]
}`,

  litellm: `# LiteLLM — use Kautilya models as a provider
import litellm

response = litellm.completion(
    model="openai/kautilya-pro",
    messages=[{"role": "user", "content": "Explain quantum entanglement"}],
    api_base="${V1_BASE}",
    api_key="YOUR_KEY_HERE",
    stream=True,
)

for chunk in response:
    print(chunk.choices[0].delta.content or "", end="")`,

  livekit_js: `// Step 1 — Get a LiveKit token for your voice agent
// YOUR_AGENT_ID: copy from Agent Studio → your agent → details
const resp = await fetch(
  "${BACKEND}/api/agents/YOUR_AGENT_ID/livekit-token",
  {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Authorization": "Bearer YOUR_KEY_HERE",
    },
    body: JSON.stringify({ participantName: "Priya" }),
  }
);
const { token, wsUrl } = await resp.json();

// Step 2 — Connect using the LiveKit browser SDK
// npm install @livekit/components-react livekit-client
import { Room, RoomEvent, Track } from "livekit-client";

const room = new Room({ adaptiveStream: true, dynacast: true });

room.on(RoomEvent.TrackSubscribed, (track, publication, participant) => {
  if (track.kind === Track.Kind.Audio) {
    // Attach the agent's audio to a <div> in your page
    const el = track.attach();
    document.getElementById("agent-audio").appendChild(el);
  }
});

await room.connect(wsUrl, token);
console.log("Connected to voice agent room:", room.name);

// Step 3 — Enable your microphone so the agent can hear you
await room.localParticipant.setMicrophoneEnabled(true);`,

  livekit_react: `// React component — embed a voice call with your Kautilya agent
// npm install @livekit/components-react livekit-client
import { useState } from "react";
import { LiveKitRoom, AudioConference } from "@livekit/components-react";
import "@livekit/components-styles";

const BACKEND = "${BACKEND}";
const AGENT_ID = "YOUR_AGENT_ID";   // from Agent Studio
const API_KEY  = "YOUR_KEY_HERE";   // from Developer API page

export function VoiceAgent({ userName = "User" }) {
  const [conn, setConn] = useState(null); // { token, wsUrl }

  const startCall = async () => {
    const resp = await fetch(\`\${BACKEND}/api/agents/\${AGENT_ID}/livekit-token\`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "Authorization": \`Bearer \${API_KEY}\` },
      body: JSON.stringify({ participantName: userName }),
    });
    setConn(await resp.json());
  };

  if (!conn) return (
    <button onClick={startCall}>
      Start Voice Call with Kautilya Agent
    </button>
  );

  return (
    <LiveKitRoom
      token={conn.token}
      serverUrl={conn.wsUrl}
      connect={true}
      audio={true}
      video={false}
    >
      <AudioConference />
    </LiveKitRoom>
  );
}`,
};

function CopyButton({ text, size = "sm" }) {
  const [copied, setCopied] = useState(false);
  const handle = () => {
    navigator.clipboard.writeText(text).catch(() => {});
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };
  return (
    <button
      onClick={handle}
      className={`flex items-center gap-1 px-2 py-1 rounded transition-all ${
        size === "xs"
          ? "text-[10px]"
          : "text-xs"
      } ${
        copied
          ? "bg-green-500/10 text-green-400"
          : "bg-accent hover:bg-[var(--k-border)] text-muted-foreground hover:text-foreground"
      }`}
    >
      {copied ? <Check className="w-3 h-3" /> : <Copy className="w-3 h-3" />}
      {copied ? "Copied" : "Copy"}
    </button>
  );
}

function CodeBlock({ code, language }) {
  return (
    <div className="relative rounded-lg overflow-hidden border border-[var(--k-border)]">
      <div className="flex items-center justify-between px-4 py-2 bg-[#1a1d23] border-b border-[var(--k-border)]">
        <span className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground">
          {language}
        </span>
        <CopyButton text={code} size="xs" />
      </div>
      <SyntaxHighlighter
        language={language === "curl" ? "bash" : language === "cline" || language === "continue" ? "json" : language}
        style={vscDarkPlus}
        customStyle={{ margin: 0, padding: "1rem", fontSize: "12px", background: "#0d1117" }}
      >
        {code}
      </SyntaxHighlighter>
    </div>
  );
}

export default function DeveloperAPI() {
  const [activeKey, setActiveKey] = useState(null);
  const [keyVisible, setKeyVisible] = useState(false);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [toast, setToast] = useState(null);

  useEffect(() => {
    loadKey();
  }, []);

  const loadKey = async () => {
    try {
      setLoading(true);
      const data = await keysAPI.list();
      setActiveKey(data.active_key || null);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  const handleGenerate = async () => {
    try {
      setGenerating(true);
      await keysAPI.create({ name: "Developer Key" });
      await loadKey();
      setKeyVisible(true);
      showToast("New API key generated!");
    } catch (e) {
      showToast("Failed to generate key");
    } finally {
      setGenerating(false);
    }
  };

  const showToast = (msg) => {
    setToast(msg);
    setTimeout(() => setToast(null), 3000);
  };

  const maskedKey = activeKey
    ? activeKey.slice(0, 10) + "•".repeat(Math.max(0, activeKey.length - 14)) + activeKey.slice(-4)
    : null;

  const displayedKey = keyVisible ? activeKey : maskedKey;

  const examplesWithKey = Object.fromEntries(
    Object.entries(EXAMPLES).map(([k, v]) => [
      k,
      activeKey ? v.replace(/YOUR_KEY_HERE/g, activeKey) : v,
    ])
  );

  return (
    <div className="h-full flex flex-col" data-testid="developer-api">
      {/* Toast */}
      {toast && (
        <div className="fixed top-4 right-4 z-50 px-4 py-2.5 rounded-lg bg-[var(--k-brand)] text-white text-sm font-medium shadow-xl animate-fade-in flex items-center gap-2">
          <Check className="w-4 h-4" />
          {toast}
        </div>
      )}

      <ScrollArea className="flex-1">
        <div className="max-w-4xl mx-auto px-8 py-8 space-y-8">

          {/* Page Header */}
          <div>
            <div className="flex items-center gap-3 mb-3">
              <div className="w-10 h-10 rounded-xl bg-[var(--k-brand)] flex items-center justify-center">
                <Terminal className="w-5 h-5 text-white" weight="bold" />
              </div>
              <div>
                <h1 className="text-2xl font-medium k-heading tracking-tight text-foreground">Developer API</h1>
                <p className="text-sm text-muted-foreground">OpenAI-compatible access to Kautilya models</p>
              </div>
            </div>
            <div className="flex items-center gap-2 mt-2">
              <span className="px-2 py-0.5 rounded-full bg-green-500/10 text-green-400 text-[10px] font-bold uppercase tracking-wider border border-green-500/20">
                Live
              </span>
              <span className="text-xs text-muted-foreground">
                Drop-in replacement for OpenAI SDK — change base URL and model name, nothing else.
              </span>
            </div>
          </div>

          {/* API Key Card */}
          <div className="p-6 rounded-xl border border-[var(--k-border)] bg-[var(--k-surface)] space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Key className="w-4 h-4 text-[var(--k-brand)]" />
                <span className="text-sm font-semibold text-foreground">Your API Key</span>
              </div>
              {activeKey && (
                <button
                  onClick={() => setKeyVisible(v => !v)}
                  className="flex items-center gap-1 text-[11px] text-muted-foreground hover:text-foreground transition-colors"
                >
                  {keyVisible ? <EyeSlash className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
                  {keyVisible ? "Hide" : "Reveal"}
                </button>
              )}
            </div>

            {loading ? (
              <div className="h-10 bg-accent rounded-lg animate-pulse" />
            ) : activeKey ? (
              <div className="flex items-center gap-2">
                <div className="flex-1 px-4 py-2.5 bg-[#0d1117] border border-[var(--k-border)] rounded-lg font-mono text-sm text-foreground overflow-x-auto whitespace-nowrap">
                  {displayedKey}
                </div>
                <button
                  onClick={() => { navigator.clipboard.writeText(activeKey).catch(() => {}); showToast("API key copied!"); }}
                  className="flex items-center gap-1.5 px-3 py-2.5 rounded-lg bg-[var(--k-brand)]/10 text-[var(--k-brand)] hover:bg-[var(--k-brand)]/20 transition-colors text-xs font-semibold whitespace-nowrap"
                >
                  <Copy className="w-3.5 h-3.5" />
                  Copy Key
                </button>
                <button
                  onClick={handleGenerate}
                  disabled={generating}
                  className="p-2.5 rounded-lg border border-[var(--k-border)] hover:bg-accent transition-colors text-muted-foreground hover:text-foreground"
                  title="Regenerate key"
                >
                  <ArrowClockwise className={`w-3.5 h-3.5 ${generating ? "animate-spin" : ""}`} />
                </button>
              </div>
            ) : (
              <div className="flex flex-col items-center gap-3 py-4 border border-dashed border-[var(--k-border)] rounded-lg">
                <p className="text-sm text-muted-foreground">No API key yet. Generate one to get started.</p>
                <button
                  onClick={handleGenerate}
                  disabled={generating}
                  className="flex items-center gap-2 px-4 py-2 rounded-lg bg-[var(--k-brand)] text-white text-sm font-semibold hover:opacity-90 transition-opacity disabled:opacity-50"
                >
                  <Key className="w-4 h-4" />
                  {generating ? "Generating…" : "Generate API Key"}
                </button>
              </div>
            )}

            <p className="text-[11px] text-muted-foreground">
              Keep your key secret. Use it as the API key when initializing the OpenAI SDK.
            </p>
          </div>

          {/* Base URL */}
          <div className="p-5 rounded-xl border border-[var(--k-border)] bg-[var(--k-surface)] space-y-3">
            <div className="flex items-center gap-2">
              <Cpu className="w-4 h-4 text-[var(--k-brand)]" />
              <span className="text-sm font-semibold text-foreground">Base URL</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="flex-1 px-4 py-2.5 bg-[#0d1117] border border-[var(--k-border)] rounded-lg font-mono text-sm text-[var(--k-brand)] overflow-x-auto whitespace-nowrap">
                {V1_BASE}
              </div>
              <CopyButton text={V1_BASE} />
            </div>
            <p className="text-[11px] text-muted-foreground">
              Pass this as <code className="bg-accent px-1 py-0.5 rounded text-foreground">base_url</code> (Python) or <code className="bg-accent px-1 py-0.5 rounded text-foreground">baseURL</code> (JS) when initialising the OpenAI SDK.
            </p>
          </div>

          {/* Models */}
          <div className="space-y-3">
            <div className="flex items-center gap-2">
              <BookOpen className="w-4 h-4 text-[var(--k-brand)]" />
              <span className="text-sm font-semibold text-foreground">Available Models</span>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {MODELS.map(m => (
                <div key={m.id} className="p-4 rounded-xl border border-[var(--k-border)] bg-[var(--k-surface)] hover:border-[var(--k-brand)]/30 transition-colors group">
                  <div className="flex items-center justify-between mb-3">
                    <div className="w-8 h-8 rounded-lg flex items-center justify-center" style={{ background: `${m.color}15` }}>
                      <m.icon className="w-4 h-4" style={{ color: m.color }} weight="duotone" />
                    </div>
                    <button
                      onClick={() => { navigator.clipboard.writeText(m.id).catch(() => {}); showToast(`Copied "${m.id}"`); }}
                      className="opacity-0 group-hover:opacity-100 transition-opacity p-1 rounded hover:bg-accent"
                      title="Copy model ID"
                    >
                      <Copy className="w-3 h-3 text-muted-foreground" />
                    </button>
                  </div>
                  <div className="font-mono text-xs font-bold text-foreground mb-1">{m.id}</div>
                  <div className="text-[10px] text-muted-foreground mb-2">{m.tier} · {m.ctx} context</div>
                  <div className="text-[11px] text-muted-foreground leading-relaxed">{m.desc}</div>
                </div>
              ))}
            </div>
          </div>

          {/* Code Examples */}
          <div className="space-y-3">
            <div className="flex items-center gap-2">
              <Code className="w-4 h-4 text-[var(--k-brand)]" />
              <span className="text-sm font-semibold text-foreground">Integration Examples</span>
            </div>

            <Tabs defaultValue="python">
              <TabsList className="bg-[var(--k-surface)] border border-[var(--k-border)] h-9 p-1 gap-1 flex-wrap">
                {[
                  { id: "python", label: "Python" },
                  { id: "javascript", label: "Node.js" },
                  { id: "curl", label: "cURL" },
                  { id: "cline", label: "Cline (VS Code)" },
                  { id: "continue", label: "Continue" },
                  { id: "litellm", label: "LiteLLM" },
                ].map(t => (
                  <TabsTrigger
                    key={t.id}
                    value={t.id}
                    className="text-[10px] font-bold uppercase tracking-wider px-2.5 data-[state=active]:bg-[var(--k-brand)] data-[state=active]:text-white rounded"
                  >
                    {t.label}
                  </TabsTrigger>
                ))}
              </TabsList>

              <div className="mt-3">
                <TabsContent value="python" className="m-0">
                  <CodeBlock code={examplesWithKey.python} language="python" />
                </TabsContent>
                <TabsContent value="javascript" className="m-0">
                  <CodeBlock code={examplesWithKey.javascript} language="javascript" />
                </TabsContent>
                <TabsContent value="curl" className="m-0">
                  <CodeBlock code={examplesWithKey.curl} language="curl" />
                </TabsContent>
                <TabsContent value="cline" className="m-0">
                  <CodeBlock code={examplesWithKey.cline} language="cline" />
                  <p className="text-[11px] text-muted-foreground mt-2">
                    Install the <strong>Cline</strong> extension in VS Code, then add the above to your <code className="bg-accent px-1 py-0.5 rounded">settings.json</code>.
                  </p>
                </TabsContent>
                <TabsContent value="continue" className="m-0">
                  <CodeBlock code={examplesWithKey.continue} language="continue" />
                  <p className="text-[11px] text-muted-foreground mt-2">
                    Install the <strong>Continue</strong> extension, open <code className="bg-accent px-1 py-0.5 rounded">~/.continue/config.json</code> and add the above model entries.
                  </p>
                </TabsContent>
                <TabsContent value="litellm" className="m-0">
                  <CodeBlock code={examplesWithKey.litellm} language="python" />
                  <p className="text-[11px] text-muted-foreground mt-2">
                    Install with <code className="bg-accent px-1 py-0.5 rounded">pip install litellm</code>. Use the <code className="bg-accent px-1 py-0.5 rounded">openai/</code> prefix with the Kautilya model name.
                  </p>
                </TabsContent>
              </div>
            </Tabs>
          </div>

          {/* Quick Reference */}
          <div className="p-5 rounded-xl border border-[var(--k-border)] bg-[var(--k-surface)] space-y-3">
            <span className="text-sm font-semibold text-foreground">Quick Reference</span>
            <div className="grid grid-cols-2 gap-3 text-xs">
              {[
                { label: "Endpoint", value: `${V1_BASE}/chat/completions` },
                { label: "Models list", value: `${V1_BASE}/models` },
                { label: "Auth header", value: "Authorization: Bearer <key>" },
                { label: "Streaming", value: 'Set "stream": true' },
              ].map(r => (
                <div key={r.label} className="flex flex-col gap-0.5">
                  <span className="text-[10px] uppercase tracking-widest text-muted-foreground font-semibold">{r.label}</span>
                  <div className="flex items-center gap-1">
                    <span className="font-mono text-foreground break-all">{r.value}</span>
                    <button onClick={() => { navigator.clipboard.writeText(r.value).catch(() => {}); showToast("Copied!"); }} className="flex-shrink-0 p-0.5 hover:text-[var(--k-brand)] text-muted-foreground transition-colors">
                      <Copy className="w-2.5 h-2.5" />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Voice Agents (LiveKit) */}
          <div className="space-y-3">
            <div className="flex items-center gap-2">
              <Microphone className="w-4 h-4 text-[var(--k-brand)]" />
              <span className="text-sm font-semibold text-foreground">Kautilya Voice Agents</span>
              <span className="px-2 py-0.5 rounded-full bg-green-500/10 text-green-400 text-[10px] font-bold uppercase tracking-wider border border-green-500/20 ml-1">LiveKit</span>
            </div>

            {/* How it works steps */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              {[
                { n: "1", title: "Build your agent", body: "Go to Agent Studio → Create Agent. Configure the system prompt, voice, language, and model. Copy the Agent ID from the agent details." },
                { n: "2", title: "Get a token", body: "Call POST /api/agents/{agent_id}/livekit-token with your API key. Returns a LiveKit JWT token and WebSocket URL." },
                { n: "3", title: "Connect & talk", body: "Use the LiveKit JS/React SDK to join the room. Enable your mic. The Kautilya agent will hear you and respond in real-time audio." },
              ].map(s => (
                <div key={s.n} className="p-4 rounded-xl border border-[var(--k-border)] bg-[var(--k-surface)]">
                  <div className="w-6 h-6 rounded-full bg-[var(--k-brand)]/10 text-[var(--k-brand)] text-xs font-bold flex items-center justify-center mb-2">{s.n}</div>
                  <div className="text-xs font-semibold text-foreground mb-1">{s.title}</div>
                  <div className="text-[11px] text-muted-foreground leading-relaxed">{s.body}</div>
                </div>
              ))}
            </div>

            {/* Token endpoint reference */}
            <div className="p-4 rounded-xl bg-[#0d1117] border border-[var(--k-border)]">
              <div className="flex items-center justify-between mb-1">
                <span className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground">Token endpoint</span>
                <CopyButton text={`POST ${BACKEND}/api/agents/{agent_id}/livekit-token`} size="xs" />
              </div>
              <code className="font-mono text-xs text-[var(--k-brand)]">
                POST {BACKEND}/api/agents/<span className="text-yellow-400">{"{agent_id}"}</span>/livekit-token
              </code>
              <div className="mt-2 text-[11px] text-muted-foreground">
                Header: <code className="bg-accent px-1 rounded">Authorization: Bearer YOUR_KEY</code>
                &nbsp;·&nbsp;
                Body: <code className="bg-accent px-1 rounded">{`{ "participantName": "User" }`}</code>
              </div>
            </div>

            <Tabs defaultValue="livekit_js">
              <TabsList className="bg-[var(--k-surface)] border border-[var(--k-border)] h-9 p-1 gap-1">
                {[
                  { id: "livekit_js", label: "JS / Node" },
                  { id: "livekit_react", label: "React Component" },
                ].map(t => (
                  <TabsTrigger key={t.id} value={t.id} className="text-[10px] font-bold uppercase tracking-wider px-2.5 data-[state=active]:bg-[var(--k-brand)] data-[state=active]:text-white rounded">
                    {t.label}
                  </TabsTrigger>
                ))}
              </TabsList>
              <div className="mt-3">
                <TabsContent value="livekit_js" className="m-0">
                  <CodeBlock code={examplesWithKey.livekit_js} language="javascript" />
                </TabsContent>
                <TabsContent value="livekit_react" className="m-0">
                  <CodeBlock code={examplesWithKey.livekit_react} language="javascript" />
                  <p className="text-[11px] text-muted-foreground mt-2">
                    Install: <code className="bg-accent px-1 py-0.5 rounded">npm install @livekit/components-react livekit-client @livekit/components-styles</code>
                  </p>
                </TabsContent>
              </div>
            </Tabs>
          </div>

          {/* Compatibility note */}
          <div className="flex items-start gap-3 p-4 rounded-xl bg-[var(--k-brand)]/5 border border-[var(--k-brand)]/15">
            <ArrowSquareOut className="w-4 h-4 text-[var(--k-brand)] flex-shrink-0 mt-0.5" />
            <div className="text-xs text-muted-foreground leading-relaxed space-y-1">
              <p>
                <strong className="text-foreground">Chat API</strong> — fully OpenAI-compatible. Works with Claude Code CLI, Cursor, Cline, Continue, LiteLLM, LangChain, LlamaIndex, and the official OpenAI Python/JS SDKs.
                Install with <code className="bg-accent px-1 py-0.5 rounded">pip install openai</code> or <code className="bg-accent px-1 py-0.5 rounded">npm install openai</code>.
              </p>
              <p>
                <strong className="text-foreground">Voice API</strong> — powered by LiveKit. Install <code className="bg-accent px-1 py-0.5 rounded">@livekit/components-react</code> and use the token endpoint above to embed real-time voice agents in any web or mobile app.
              </p>
              <p className="text-[10px] mt-1 opacity-70">
                Platform: <strong className="text-foreground">ai.revealiq.in</strong> · API Base: <code className="bg-accent px-1 rounded">{V1_BASE}</code>
              </p>
            </div>
          </div>

        </div>
      </ScrollArea>
    </div>
  );
}
