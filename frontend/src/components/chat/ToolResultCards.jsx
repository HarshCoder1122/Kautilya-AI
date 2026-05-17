/**
 * Render structured tool outputs (gmail, calendar, python sandbox, search) as
 * proper UI cards instead of dumping JSON / prose into the chat bubble.
 *
 * Backend emits SSE events of shape:
 *   {"event":"tool_result","tool":"<name>","data":{...}}
 * ChatMain accumulates them into msg.toolResults; this component renders them.
 */
import { Envelope, CalendarCheck, MapPin, VideoCamera, Code, Image as ImageIcon, Terminal, MagnifyingGlass } from "@phosphor-icons/react";
import { useState } from "react";

export function ToolResultCards({ results }) {
  if (!Array.isArray(results) || results.length === 0) return null;
  return (
    <div className="space-y-3 my-3">
      {results.map((r, i) => <ToolResultCard key={i} tool={r.tool} data={r.data} />)}
    </div>
  );
}

function ToolResultCard({ tool, data }) {
  if (!data) return null;
  switch (tool) {
    case "gmail_list":   return <GmailListCard {...data} />;
    case "calendar_list": return <CalendarListCard {...data} />;
    case "python_run":   return <PythonRunCard {...data} />;
    case "search":       return <SearchCard {...data} />;
    default:             return null;
  }
}

// ============= GMAIL =============
function GmailListCard({ emails = [], query = "" }) {
  if (!emails.length) {
    return (
      <CardShell icon={Envelope} accent="rose" label="Gmail">
        <p className="text-sm text-muted-foreground">
          No emails {query ? `matching "${query}"` : "found"}.
        </p>
      </CardShell>
    );
  }
  return (
    <CardShell icon={Envelope} accent="rose" label={`Gmail · ${emails.length} message${emails.length > 1 ? "s" : ""}`}>
      <div className="divide-y divide-[var(--k-border)]/60">
        {emails.map((e, i) => (
          <div key={i} className="py-2.5 first:pt-0 last:pb-0">
            <div className="flex items-start justify-between gap-3">
              <div className="text-sm font-semibold text-foreground line-clamp-1">
                {stripEmailDecoration(e.from)}
              </div>
              <div className="text-[10px] text-muted-foreground shrink-0">{shortDate(e.date)}</div>
            </div>
            <div className="text-[13px] text-foreground/90 mt-0.5 line-clamp-1">{e.subject || "(no subject)"}</div>
            {e.snippet && (
              <div className="text-xs text-muted-foreground mt-1 line-clamp-2 leading-relaxed">{e.snippet}</div>
            )}
          </div>
        ))}
      </div>
    </CardShell>
  );
}

// ============= CALENDAR =============
function CalendarListCard({ events = [], days = 7 }) {
  if (!events.length) {
    return (
      <CardShell icon={CalendarCheck} accent="brand" label={`Calendar · next ${days} days`}>
        <p className="text-sm text-muted-foreground">No events scheduled.</p>
      </CardShell>
    );
  }
  return (
    <CardShell icon={CalendarCheck} accent="brand" label={`Calendar · ${events.length} event${events.length > 1 ? "s" : ""}`}>
      <div className="space-y-2">
        {events.map((e, i) => (
          <a
            key={i}
            href={e.htmlLink || e.hangoutLink || "#"}
            target="_blank" rel="noopener noreferrer"
            className="block p-3 rounded-lg bg-[var(--k-surface-elevated)]/40 border border-[var(--k-border)]/60 hover:border-[var(--k-brand)]/40 transition-colors"
          >
            <div className="flex items-start justify-between gap-3">
              <div className="text-sm font-semibold text-foreground line-clamp-1">{e.summary}</div>
              {e.hangoutLink && (
                <span className="inline-flex items-center gap-1 text-[10px] text-emerald-400">
                  <VideoCamera className="w-3 h-3" weight="fill" /> Meet
                </span>
              )}
            </div>
            <div className="text-xs text-muted-foreground mt-1">{formatEventTime(e.start, e.end)}</div>
            {e.location && (
              <div className="text-[11px] text-muted-foreground mt-1 flex items-center gap-1">
                <MapPin className="w-3 h-3" /> <span className="line-clamp-1">{e.location}</span>
              </div>
            )}
            {e.description && (
              <div className="text-[11px] text-muted-foreground mt-1 line-clamp-2">{e.description}</div>
            )}
          </a>
        ))}
      </div>
    </CardShell>
  );
}

// ============= PYTHON SANDBOX =============
function PythonRunCard({ code = "", stdout = "", stderr = "", images = [], ok = true }) {
  const [showCode, setShowCode] = useState(false);
  return (
    <CardShell icon={Terminal} accent={ok ? "sky" : "rose"} label={`Python · ${ok ? "ran successfully" : "error"}`}>
      <button
        onClick={() => setShowCode(s => !s)}
        className="text-[11px] text-[var(--k-brand)] hover:underline mb-2"
      >
        {showCode ? "Hide code" : "Show code"}
      </button>
      {showCode && (
        <pre className="text-[11px] bg-[var(--k-surface-elevated)] rounded-md p-3 overflow-x-auto border border-[var(--k-border)]/60 mb-3">
          <code className="k-mono whitespace-pre">{code}</code>
        </pre>
      )}
      {images.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-2 mb-3">
          {images.map((src, i) => (
            <a key={i} href={src} target="_blank" rel="noopener noreferrer">
              <img src={src} alt={`chart ${i + 1}`} className="w-full rounded-md border border-[var(--k-border)]/60" />
            </a>
          ))}
        </div>
      )}
      {stdout && (
        <div>
          <div className="text-[10px] uppercase tracking-wider text-muted-foreground mb-1">stdout</div>
          <pre className="text-[12px] bg-[var(--k-surface-elevated)]/60 rounded-md p-2.5 overflow-x-auto border border-[var(--k-border)]/40 whitespace-pre-wrap k-mono max-h-[260px] overflow-y-auto">{stdout}</pre>
        </div>
      )}
      {stderr && !ok && (
        <div className="mt-2">
          <div className="text-[10px] uppercase tracking-wider text-rose-400 mb-1">error</div>
          <pre className="text-[12px] bg-rose-500/5 rounded-md p-2.5 overflow-x-auto border border-rose-500/20 whitespace-pre-wrap text-rose-300 k-mono max-h-[200px] overflow-y-auto">{stderr}</pre>
        </div>
      )}
    </CardShell>
  );
}

// ============= SEARCH =============
function SearchCard({ results = [], query = "" }) {
  if (!results.length) return null;
  return (
    <CardShell icon={MagnifyingGlass} accent="violet" label={`Search · "${query}"`}>
      <div className="space-y-2">
        {results.slice(0, 6).map((r, i) => (
          <a key={i} href={r.url} target="_blank" rel="noopener noreferrer"
             className="block p-2 rounded-lg hover:bg-[var(--k-surface-elevated)]/40 transition-colors">
            <div className="text-sm font-medium text-foreground line-clamp-1">{r.title}</div>
            <div className="text-[10px] text-muted-foreground">{r.site || hostFromUrl(r.url)}</div>
            {r.snippet && <div className="text-xs text-muted-foreground mt-1 line-clamp-2">{r.snippet}</div>}
          </a>
        ))}
      </div>
    </CardShell>
  );
}

// ============= CARD SHELL =============
function CardShell({ icon: Icon, accent = "brand", label, children }) {
  const accents = {
    rose: "text-rose-400",
    brand: "text-[var(--k-brand)]",
    sky: "text-sky-400",
    violet: "text-violet-400",
  };
  return (
    <div className="rounded-xl border border-[var(--k-border)] bg-[var(--k-surface)] p-4">
      <div className="flex items-center gap-2 mb-2">
        <Icon weight="duotone" className={`w-4 h-4 ${accents[accent]}`} />
        <span className="text-[11px] font-semibold uppercase tracking-widest text-muted-foreground">{label}</span>
      </div>
      {children}
    </div>
  );
}

// ============= HELPERS =============
function stripEmailDecoration(from) {
  if (!from) return "";
  // "Name <email@x>" → "Name"; otherwise show email
  const m = from.match(/^\s*"?([^"<]+?)"?\s*<.+>/);
  return m ? m[1].trim() : from;
}
function shortDate(d) {
  if (!d) return "";
  try {
    const date = new Date(d);
    if (isNaN(date)) return d;
    const now = new Date();
    const sameDay = date.toDateString() === now.toDateString();
    if (sameDay) return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    return date.toLocaleDateString([], { month: "short", day: "numeric" });
  } catch { return d; }
}
function formatEventTime(start, end) {
  try {
    if (!start) return "";
    const s = new Date(start);
    if (isNaN(s)) return start;
    const dateStr = s.toLocaleDateString([], { weekday: "short", month: "short", day: "numeric" });
    const startTime = s.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    if (end) {
      const e = new Date(end);
      if (!isNaN(e)) {
        const endTime = e.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
        return `${dateStr} · ${startTime} – ${endTime}`;
      }
    }
    return `${dateStr} · ${startTime}`;
  } catch { return start; }
}
function hostFromUrl(url) {
  try { return new URL(url).hostname.replace("www.", ""); } catch { return ""; }
}
