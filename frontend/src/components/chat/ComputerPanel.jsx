import { useState, useEffect, useCallback } from "react";
import { X, HardDrives, File, ArrowClockwise, FileText } from "@phosphor-icons/react";
import { computerAPI } from "@/lib/api";

/**
 * Kautilya Computer — a browser for this chat session's persistent sandbox
 * workspace (backend: services/computer_service.py, tools: [FILE_WRITE:] /
 * [FILE_READ:] / [FILE_LIST:] / [RUN_PYTHON:]).
 *
 * Pull-based by design: it fetches the file list/content over REST
 * (GET /api/computer/files, /api/computer/file) rather than parsing the SSE
 * stream — the same files are already visible inline as ToolResultCards
 * (FileWriteCard/FileReadCard/FileListCard) as the agent works; this panel
 * is a persistent, whole-session view on top of that, refreshed whenever a
 * turn finishes (`refreshSignal` bumps on stream completion).
 */
export function ComputerPanel({ sessionId, onClose, refreshSignal }) {
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
          <div className="flex flex-col overflow-hidden">
            <span className="text-sm font-semibold truncate text-foreground leading-tight">Kautilya Computer</span>
            <span className="text-[10px] text-muted-foreground uppercase tracking-widest font-bold">
              {files.length} file{files.length === 1 ? "" : "s"} · this session
            </span>
          </div>
        </div>
        <div className="flex items-center gap-1">
          <button onClick={refresh} className="p-2 rounded-md hover:bg-accent transition-all duration-200" title="Refresh">
            <ArrowClockwise className={`w-4 h-4 text-muted-foreground ${loadingFiles ? "animate-spin" : ""}`} />
          </button>
          <div className="w-px h-4 bg-[var(--k-border)] mx-1" />
          <button onClick={onClose} className="p-2 rounded-md hover:bg-accent transition-all duration-200 group">
            <X className="w-5 h-5 text-muted-foreground group-hover:text-foreground" />
          </button>
        </div>
      </div>

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
    </div>
  );
}
