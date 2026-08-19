import { useState, useEffect, useCallback } from "react";
import { X, HardDrives, File, ArrowClockwise, FileText, FolderOpen, Compass } from "@phosphor-icons/react";
import { computerAPI } from "@/lib/api";
import { BrowseCard } from "./ToolResultCards";

/**
 * Kautilya Computer — ONE persistent view for this chat session's sandbox:
 * a Files tab (backend: services/computer_service.py, tools: [FILE_WRITE:] /
 * [FILE_READ:] / [FILE_LIST:] / [RUN_PYTHON:]) and a Browser tab (backend:
 * services/browser_service.py, tools: [BROWSE:] / [BROWSE_CLICK:] /
 * [BROWSE_TYPE:]).
 *
 * The Browser tab is deliberately the ONLY place browsing shows up — earlier
 * this rendered a screenshot card in the chat transcript per action, which
 * flooded the conversation with "a picture of every next screen". Now each
 * browse/click/type just updates ONE live view here (current URL, title,
 * screenshot, links) and the chat only gets a one-line status
 * ("Browsing example.com…") in the action timeline.
 *
 * Files stay pull-based (REST) since they're not naturally "live" the same
 * way; Browser state is pushed in via the `browserState` prop, updated by
 * ChatMain on every browse-family tool_result event.
 */
export function ComputerPanel({ sessionId, onClose, refreshSignal, browserState, browseSignal }) {
  const [activeTab, setActiveTab] = useState(browserState ? "browser" : "files");
  const [files, setFiles] = useState([]);
  const [loadingFiles, setLoadingFiles] = useState(false);
  const [selected, setSelected] = useState(null);
  const [content, setContent] = useState("");
  const [loadingContent, setLoadingContent] = useState(false);
  const [error, setError] = useState("");

  const refresh = useCallback(async () => {
    if (!sessionId) return;
    setLoadingFiles(true);
    setError("");
    try {
      const res = await computerAPI.listFiles(sessionId);
      setFiles(res.files || []);
    } catch (e) {
      setError("Couldn't load the workspace.");
    } finally {
      setLoadingFiles(false);
    }
  }, [sessionId]);

  useEffect(() => { refresh(); }, [refresh, refreshSignal]);

  // A new browse/click/type result arrived — bring it to the front even if
  // the panel was already open on the Files tab.
  useEffect(() => {
    if (browseSignal) setActiveTab("browser");
  }, [browseSignal]);

  const openFile = async (path) => {
    setSelected(path);
    setLoadingContent(true);
    try {
      const res = await computerAPI.readFile(sessionId, path);
      setContent(res.content || "");
    } catch (e) {
      setContent("Couldn't read this file.");
    } finally {
      setLoadingContent(false);
    }
  };

  return (
    <div className="computer-pane flex flex-col bg-[var(--k-bg)]" data-testid="computer-pane">
      <div className="h-14 min-h-[56px] flex items-center justify-between px-4 border-b border-[var(--k-border)] bg-[var(--k-surface)]">
        <div className="flex items-center gap-3 overflow-hidden">
          <div className="w-8 h-8 rounded-lg bg-sky-400/10 flex items-center justify-center text-sky-400 flex-shrink-0">
            <HardDrives className="w-4 h-4" />
          </div>
          <span className="text-sm font-semibold truncate text-foreground leading-tight">Kautilya Computer</span>
        </div>
        <div className="flex items-center gap-1">
          {activeTab === "files" && (
            <button onClick={refresh} className="p-2 rounded-md hover:bg-accent transition-all duration-200" title="Refresh">
              <ArrowClockwise className={`w-4 h-4 text-muted-foreground ${loadingFiles ? "animate-spin" : ""}`} />
            </button>
          )}
          <div className="w-px h-4 bg-[var(--k-border)] mx-1" />
          <button onClick={onClose} className="p-2 rounded-md hover:bg-accent transition-all duration-200 group">
            <X className="w-5 h-5 text-muted-foreground group-hover:text-foreground" />
          </button>
        </div>
      </div>

      <div className="flex items-center gap-1 px-3 pt-2 border-b border-[var(--k-border)] bg-[var(--k-surface)]">
        {[
          { id: "files", label: "Files", icon: FolderOpen, count: files.length },
          { id: "browser", label: "Browser", icon: Compass, count: browserState ? 1 : 0 },
        ].map((t) => (
          <button
            key={t.id}
            onClick={() => setActiveTab(t.id)}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-t-md text-xs font-medium transition-colors ${
              activeTab === t.id
                ? "bg-[var(--k-bg)] text-foreground border-t border-x border-[var(--k-border)] -mb-px"
                : "text-muted-foreground hover:text-foreground"
            }`}
          >
            <t.icon className="w-3.5 h-3.5" />
            {t.label}
            {t.count > 0 && <span className="text-[10px] text-muted-foreground/70">({t.count})</span>}
          </button>
        ))}
      </div>

      {activeTab === "files" && (
        <div className="flex-1 min-h-0 flex overflow-hidden">
          <div className="w-[38%] min-w-[140px] max-w-[260px] border-r border-[var(--k-border)] overflow-y-auto">
            {error && <div className="p-3 text-xs text-rose-400">{error}</div>}
            {!error && !loadingFiles && files.length === 0 && (
              <div className="p-4 text-xs text-muted-foreground leading-relaxed">
                Nothing here yet. Ask Kautilya (in Code mode) to write a file and it'll show up here.
              </div>
            )}
            {files.map((f) => (
              <button
                key={f.path}
                onClick={() => openFile(f.path)}
                className={`w-full flex items-center gap-2 px-3 py-2 text-left text-xs border-b border-[var(--k-border)]/40 hover:bg-accent transition-colors ${
                  selected === f.path ? "bg-accent" : ""
                }`}
                title={f.path}
              >
                <File className="w-3.5 h-3.5 text-muted-foreground shrink-0" />
                <span className="truncate font-mono">{f.path}</span>
              </button>
            ))}
          </div>

          <div className="flex-1 min-w-0 overflow-y-auto p-4">
            {!selected && (
              <div className="h-full flex flex-col items-center justify-center text-center text-muted-foreground gap-2">
                <FileText className="w-8 h-8 opacity-40" />
                <p className="text-xs max-w-[220px]">Select a file to preview its current contents.</p>
              </div>
            )}
            {selected && (
              <>
                <div className="text-[11px] font-mono text-muted-foreground mb-2 truncate">{selected}</div>
                {loadingContent ? (
                  <div className="text-xs text-muted-foreground">Loading…</div>
                ) : (
                  <pre className="text-[12px] bg-[var(--k-surface-elevated)]/60 rounded-md p-3 w-full max-w-full overflow-x-auto border border-[var(--k-border)]/40 whitespace-pre-wrap k-mono">
                    {content}
                  </pre>
                )}
              </>
            )}
          </div>
        </div>
      )}

      {activeTab === "browser" && (
        <div className="flex-1 min-h-0 overflow-y-auto p-4">
          {!browserState && (
            <div className="h-full flex flex-col items-center justify-center text-center text-muted-foreground gap-2">
              <Compass className="w-8 h-8 opacity-40" />
              <p className="text-xs max-w-[220px]">
                Nothing browsed yet this session. Ask Kautilya to visit a specific site and this fills in live.
              </p>
            </div>
          )}
          {browserState && <BrowseCard {...browserState} />}
        </div>
      )}
    </div>
  );
}
