import { useState, useEffect, useMemo, useRef } from "react";
import ReactMarkdown from 'react-markdown';
import JSZip from 'jszip';
import { X, Code, ChartBar, FileText, Copy, Download, ArrowsOutSimple, Check, FolderOpen, Eye, File, ArrowSquareOut, Archive } from "@phosphor-icons/react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ScrollArea } from "@/components/ui/scroll-area";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell, Area, AreaChart } from "recharts";
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';

/** Parse <file name="..." language="...">...</file> blocks from model output */
function parseFileBlocks(code) {
  if (!code) return [];
  const regex = /<file\s+name="([^"]+)"(?:\s+language="([^"]+)")?>([\s\S]*?)<\/file>/g;
  const files = [];
  let m;
  while ((m = regex.exec(code)) !== null) {
    files.push({ name: m[1], language: m[2] || inferLang(m[1]), content: m[3].trim() });
  }
  return files;
}

function inferLang(filename) {
  const ext = filename.split('.').pop().toLowerCase();
  const map = { js: 'javascript', jsx: 'javascript', ts: 'typescript', tsx: 'typescript',
    py: 'python', html: 'html', css: 'css', json: 'json', md: 'markdown',
    txt: 'text', sh: 'bash', yml: 'yaml', yaml: 'yaml' };
  return map[ext] || 'text';
}

function buildHtmlPreview(files) {
  // Prefer index.html; fall back to any .html file.
  const html = files.find(f => f.name === 'index.html')
            || files.find(f => f.name.toLowerCase().endsWith('.html'));
  if (!html) return null;
  let src = html.content;

  // Escape regex metachars in filenames before building patterns.
  const escapeRe = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

  // Inline CSS files: match <link href="name"> with or without ./ prefix.
  files.filter(f => f.language === 'css' || f.name.toLowerCase().endsWith('.css')).forEach(f => {
    const n = escapeRe(f.name);
    const re = new RegExp(`<link[^>]*href=["'](?:\\./)?${n}["'][^>]*/?>`, 'gi');
    src = src.replace(re, `<style data-file="${f.name}">\n${f.content}\n</style>`);
  });

  // Inline JS files: match <script src="name"></script> with or without ./ prefix.
  files.filter(f => (f.language === 'javascript' || f.name.toLowerCase().endsWith('.js')) && !f.name.endsWith('.jsx')).forEach(f => {
    const n = escapeRe(f.name);
    const re = new RegExp(`<script[^>]*src=["'](?:\\./)?${n}["'][^>]*></script>`, 'gi');
    src = src.replace(re, `<script data-file="${f.name}">\n${f.content}\n</script>`);
  });

  // If model emitted index.html with NO <head> wrapping, give it a basic shell
  // so styles + viewport meta work even when AI forgets them.
  if (!/<html[\s>]/i.test(src)) {
    src = `<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Preview</title></head><body>${src}</body></html>`;
  }
  return src;
}

function downloadFile(filename, content) {
  const blob = new Blob([content], { type: 'text/plain' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a'); a.href = url; a.download = filename; a.click();
  URL.revokeObjectURL(url);
}

/** Download every file as a single ZIP. Preserves directory structure (a/b/c.js). */
async function downloadFilesAsZip(files, zipName) {
  const zip = new JSZip();
  for (const f of files) {
    if (f && f.name) zip.file(f.name, f.content || '');
  }
  const blob = await zip.generateAsync({ type: 'blob', compression: 'DEFLATE', compressionOptions: { level: 6 } });
  const safe = (zipName || 'kautilya-project').replace(/[^a-z0-9-_]/gi, '-').toLowerCase();
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `${safe}.zip`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

/** Open the preview in a new browser tab (works as fullscreen). */
function openPreviewInNewTab(htmlString) {
  if (!htmlString) return;
  const blob = new Blob([htmlString], { type: 'text/html' });
  const url = URL.createObjectURL(blob);
  window.open(url, '_blank', 'noopener,noreferrer');
  // Note: do not revoke immediately — the new tab needs the URL.
  setTimeout(() => URL.revokeObjectURL(url), 60_000);
}

/** Strip backend tags + research sources blob so the canvas shows clean prose. */
function cleanDocumentContent(raw) {
  if (!raw) return { body: '', sources: [] };
  let text = String(raw)
    .replace(/<think>[\s\S]*?<\/think>/g, '')
    .replace(/<artifact[\s\S]*?<\/artifact>/g, '')
    .replace(/<file\s+name="[^"]+"[\s\S]*?<\/file>/g, '')
    .trim();

  let sources = [];
  const sIdx = text.indexOf('__sources__:');
  if (sIdx >= 0) {
    const after = text.slice(sIdx + '__sources__:'.length).trim();
    try { sources = JSON.parse(after); } catch { sources = []; }
    text = text.slice(0, sIdx).trim();
  }
  return { body: text, sources };
}

/** Custom ReactMarkdown components for document-style rendering. */
const DOC_COMPONENTS = {
  h1: ({ children }) => <h1 className="k-heading text-3xl md:text-4xl font-bold mb-6 mt-2 text-foreground tracking-tight">{children}</h1>,
  h2: ({ children }) => <h2 className="k-heading text-2xl font-semibold mb-4 mt-10 text-foreground border-b border-[var(--k-border)] pb-2">{children}</h2>,
  h3: ({ children }) => <h3 className="k-heading text-xl font-semibold mb-3 mt-8 text-foreground">{children}</h3>,
  h4: ({ children }) => <h4 className="k-heading text-lg font-semibold mb-2 mt-6 text-foreground">{children}</h4>,
  p: ({ children }) => <p className="text-base leading-[1.85] mb-4 text-foreground/90">{children}</p>,
  ul: ({ children }) => <ul className="list-disc pl-6 mb-4 space-y-1.5 text-foreground/90">{children}</ul>,
  ol: ({ children }) => <ol className="list-decimal pl-6 mb-4 space-y-1.5 text-foreground/90">{children}</ol>,
  li: ({ children }) => <li className="leading-[1.7]">{children}</li>,
  blockquote: ({ children }) => <blockquote className="border-l-4 border-[var(--k-brand)] pl-4 italic my-6 text-foreground/80">{children}</blockquote>,
  a: ({ href, children }) => <a href={href} target="_blank" rel="noopener noreferrer" className="text-[var(--k-brand)] underline underline-offset-2 hover:opacity-80 break-all">{children}</a>,
  table: ({ children }) => <div className="overflow-x-auto my-6"><table className="min-w-full border border-[var(--k-border)] rounded-md text-sm">{children}</table></div>,
  thead: ({ children }) => <thead className="bg-[var(--k-surface)]">{children}</thead>,
  th: ({ children }) => <th className="px-4 py-2 text-left font-semibold border-b border-[var(--k-border)]">{children}</th>,
  td: ({ children }) => <td className="px-4 py-2 border-b border-[var(--k-border)]">{children}</td>,
  code: ({ inline, children }) => inline
    ? <code className="bg-accent/50 px-1.5 py-0.5 rounded text-[0.85em] font-mono">{children}</code>
    : <pre className="bg-[var(--k-surface)] border border-[var(--k-border)] rounded-md p-4 overflow-x-auto my-4 text-sm font-mono"><code>{children}</code></pre>,
  hr: () => <hr className="my-8 border-[var(--k-border)]" />,
  strong: ({ children }) => <strong className="font-semibold text-foreground">{children}</strong>,
};

function MultiFileWorkspace({ files, title }) {
  const [activeFile, setActiveFile] = useState(files[0]?.name || '');
  const [viewMode, setViewMode] = useState('code'); // 'code' | 'preview'
  const [copied, setCopied] = useState(false);
  const [zipping, setZipping] = useState(false);
  const [fullscreen, setFullscreen] = useState(false);

  const currentFile = files.find(f => f.name === activeFile) || files[0];
  const htmlPreview = useMemo(() => buildHtmlPreview(files), [files]);

  const handleCopy = () => {
    if (currentFile) {
      navigator.clipboard.writeText(currentFile.content).catch(() => {});
      setCopied(true); setTimeout(() => setCopied(false), 2000);
    }
  };

  const handleDownloadZip = async () => {
    if (zipping || !files.length) return;
    setZipping(true);
    try {
      await downloadFilesAsZip(files, title);
    } catch (e) {
      console.error('[Zip] failed:', e);
    } finally {
      setZipping(false);
    }
  };

  // ESC closes fullscreen preview
  useEffect(() => {
    if (!fullscreen) return;
    const onKey = (e) => { if (e.key === 'Escape') setFullscreen(false); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [fullscreen]);

  return (
    <div className="flex flex-col h-full">
      {/* Toolbar */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-[var(--k-border)] bg-[var(--k-surface)] flex-shrink-0">
        <div className="flex items-center gap-1 min-w-0">
          <FolderOpen className="w-4 h-4 text-[var(--k-brand)] shrink-0" />
          <span className="text-xs font-bold text-foreground ml-1 truncate max-w-[160px]">{title}</span>
          <span className="text-[10px] text-muted-foreground ml-2 shrink-0">{files.length} file{files.length !== 1 ? 's' : ''}</span>
        </div>
        <div className="flex items-center gap-1">
          {htmlPreview && (
            <>
              <button
                onClick={() => setViewMode(v => v === 'preview' ? 'code' : 'preview')}
                className={`flex items-center gap-1 px-2 py-1 rounded text-[10px] font-bold transition-all ${viewMode === 'preview' ? 'bg-[var(--k-brand)] text-white' : 'bg-accent text-muted-foreground hover:text-foreground'}`}
                title={viewMode === 'preview' ? 'Show code' : 'Show preview'}
              >
                <Eye className="w-3 h-3" />{viewMode === 'preview' ? 'Code' : 'Preview'}
              </button>
              {viewMode === 'preview' && (
                <>
                  <button
                    onClick={() => setFullscreen(true)}
                    className="p-1.5 rounded hover:bg-accent"
                    title="Fullscreen preview"
                  >
                    <ArrowsOutSimple className="w-3.5 h-3.5 text-muted-foreground" />
                  </button>
                  <button
                    onClick={() => openPreviewInNewTab(htmlPreview)}
                    className="p-1.5 rounded hover:bg-accent"
                    title="Open preview in new tab"
                  >
                    <ArrowSquareOut className="w-3.5 h-3.5 text-muted-foreground" />
                  </button>
                </>
              )}
            </>
          )}
          <button onClick={handleCopy} className="p-1.5 rounded hover:bg-accent" title="Copy current file">
            {copied ? <Check className="w-3.5 h-3.5 text-green-400" /> : <Copy className="w-3.5 h-3.5 text-muted-foreground" />}
          </button>
          <button onClick={() => currentFile && downloadFile(currentFile.name, currentFile.content)} className="p-1.5 rounded hover:bg-accent" title="Download current file">
            <Download className="w-3.5 h-3.5 text-muted-foreground" />
          </button>
          <button
            onClick={handleDownloadZip}
            disabled={zipping}
            className="flex items-center gap-1 px-2 py-1 rounded bg-[var(--k-brand)]/10 hover:bg-[var(--k-brand)]/20 text-[var(--k-brand)] text-[10px] font-bold transition-all disabled:opacity-50"
            title="Download all files as ZIP"
          >
            <Archive className="w-3 h-3" />
            {zipping ? '...' : 'ZIP'}
          </button>
        </div>
      </div>

      <div className="flex flex-1 min-h-0">
        {/* File tree */}
        <div className="w-44 border-r border-[var(--k-border)] bg-[var(--k-surface)] flex-shrink-0 overflow-y-auto">
          {files.map(f => (
            <button
              key={f.name}
              onClick={() => { setActiveFile(f.name); setViewMode('code'); }}
              className={`w-full flex items-center gap-2 px-3 py-2 text-left text-xs transition-all ${
                activeFile === f.name
                  ? 'bg-[var(--k-brand)]/10 text-[var(--k-brand)] font-semibold border-r-2 border-[var(--k-brand)]'
                  : 'text-muted-foreground hover:bg-accent hover:text-foreground'
              }`}
            >
              <File className="w-3 h-3 flex-shrink-0" />
              <span className="truncate">{f.name}</span>
            </button>
          ))}
        </div>

        {/* Editor / Preview */}
        <div className="flex-1 min-w-0 overflow-hidden">
          {viewMode === 'preview' && htmlPreview ? (
            <iframe
              srcDoc={htmlPreview}
              sandbox="allow-scripts allow-same-origin allow-forms allow-popups allow-modals"
              className="w-full h-full border-none bg-white"
              title="Live Preview"
            />
          ) : currentFile ? (
            <ScrollArea className="h-full">
              <SyntaxHighlighter
                language={currentFile.language || 'text'}
                style={vscDarkPlus}
                customStyle={{ margin: 0, borderRadius: 0, fontSize: '12px', minHeight: '100%', background: 'var(--k-bg)' }}
                showLineNumbers
              >
                {currentFile.content}
              </SyntaxHighlighter>
            </ScrollArea>
          ) : null}
        </div>
      </div>

      {/* Fullscreen preview overlay */}
      {fullscreen && htmlPreview && (
        <div className="fixed inset-0 z-[100] bg-black/95 flex flex-col">
          <div className="h-12 flex items-center justify-between px-4 border-b border-white/10 bg-[var(--k-surface)]">
            <div className="flex items-center gap-2">
              <Eye className="w-4 h-4 text-[var(--k-brand)]" />
              <span className="text-sm font-bold text-foreground truncate max-w-[60vw]">{title} — Live Preview</span>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={() => openPreviewInNewTab(htmlPreview)}
                className="flex items-center gap-1 px-3 py-1.5 rounded bg-accent text-foreground hover:bg-accent/80 text-xs font-semibold"
                title="Open in new tab"
              >
                <ArrowSquareOut className="w-3.5 h-3.5" />
                New Tab
              </button>
              <button
                onClick={() => setFullscreen(false)}
                className="p-2 rounded hover:bg-accent text-muted-foreground hover:text-foreground"
                title="Close (Esc)"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          </div>
          <iframe
            srcDoc={htmlPreview}
            sandbox="allow-scripts allow-same-origin allow-forms allow-popups allow-modals"
            className="flex-1 w-full border-none bg-white"
            title="Fullscreen Preview"
          />
        </div>
      )}
    </div>
  );
}

export function CanvasPane({ content, onClose, activeMode }) {
  const getInitialTab = (c) => {
    if (c?.type === 'code') return 'code';
    if (c?.type === 'document') return 'document';
    if (c?.type === 'dashboard') return 'dashboard';
    return 'document';
  };

  const [activeTab, setActiveTab] = useState(getInitialTab(content));
  const [copied, setCopied] = useState(false);

  // Parse multi-file blocks from content
  const fileBlocks = useMemo(() => parseFileBlocks(content?.code), [content?.code]);
  const isMultiFile = fileBlocks.length > 0;

  // Sync tab when content changes (new artifact opened)
  useEffect(() => {
    setActiveTab(getInitialTab(content));
  }, [content?.type, content?.title]);

  const handleCopy = () => {
    if (content?.code) {
      navigator.clipboard.writeText(content.code).catch(() => {});
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const handleDownload = () => {
    if (!content?.code) return;
    const ext = activeTab === 'code' ? (content.language || 'txt') : 'md';
    const filename = `${(content.title || 'kautilya-artifact').replace(/[^a-z0-9]/gi, '-').toLowerCase()}.${ext}`;
    const blob = new Blob([content.code], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  };

  const getDynamicData = () => {
    if (!content?.code) return null;
    try {
      if (content.code.trim().startsWith('{') || content.code.trim().startsWith('[')) {
        return JSON.parse(content.code);
      }
    } catch (e) {
      return null;
    }
    return null;
  };

  const dynamicData = getDynamicData();
  const kpis = dynamicData?.kpis || [];
  const revenueData = dynamicData?.revenue || [];
  const salesByRegion = dynamicData?.salesByRegion || [];
  const funnelData = dynamicData?.conversionFunnel || [];

  return (
    <div className="canvas-pane flex flex-col bg-[var(--k-bg)]" data-testid="canvas-pane">
      {/* Header */}
      <div className="h-14 min-h-[56px] flex items-center justify-between px-4 border-b border-[var(--k-border)] bg-[var(--k-surface)]">
        <div className="flex items-center gap-3 overflow-hidden">
          <div className="w-8 h-8 rounded-lg bg-[var(--k-brand)]/10 flex items-center justify-center text-[var(--k-brand)] flex-shrink-0">
            {isMultiFile ? <FolderOpen className="w-4 h-4" /> : activeTab === 'code' ? <Code className="w-4 h-4" /> : activeTab === 'dashboard' ? <ChartBar className="w-4 h-4" /> : <FileText className="w-4 h-4" />}
          </div>
          <div className="flex flex-col overflow-hidden">
            <span className="text-sm font-semibold truncate text-foreground leading-tight">
              {content?.title || 'Canvas'}
            </span>
            <span className="text-[10px] text-muted-foreground uppercase tracking-widest font-bold">
              {isMultiFile ? `${fileBlocks.length} Files` : `${activeTab} View`}
            </span>
          </div>
        </div>
        <div className="flex items-center gap-1">
          <button
            onClick={handleCopy}
            className="p-2 rounded-md hover:bg-accent transition-all duration-200"
            title="Copy content"
          >
            {copied ? <Check className="w-4 h-4 text-[var(--k-green)]" /> : <Copy className="w-4 h-4 text-muted-foreground" />}
          </button>
          <button
            onClick={handleDownload}
            className="p-2 rounded-md hover:bg-accent transition-all duration-200"
            title="Download"
          >
            <Download className="w-4 h-4 text-muted-foreground" />
          </button>
          <div className="w-px h-4 bg-[var(--k-border)] mx-1" />
          <button onClick={onClose} className="p-2 rounded-md hover:bg-accent transition-all duration-200 group">
            <X className="w-5 h-5 text-muted-foreground group-hover:text-foreground" />
          </button>
        </div>
      </div>

      {isMultiFile ? (
        <div className="flex-1 min-h-0">
          <MultiFileWorkspace files={fileBlocks} title={content?.title || 'Project'} />
        </div>
      ) : (
      <Tabs value={activeTab} onValueChange={setActiveTab} className="flex-1 flex flex-col overflow-hidden">
        <div className="px-4 bg-[var(--k-surface)] border-b border-[var(--k-border)]">
          <TabsList className="bg-transparent h-10 p-0 gap-6">
            {['document', 'code', 'dashboard', 'preview'].map((tab) => (
              <TabsTrigger
                key={tab}
                value={tab}
                className="bg-transparent data-[state=active]:bg-transparent data-[state=active]:shadow-none data-[state=active]:text-[var(--k-brand)] text-muted-foreground px-0 pb-3 rounded-none border-b-2 border-transparent data-[state=active]:border-[var(--k-brand)] text-[11px] font-bold uppercase tracking-wider transition-all"
              >
                {tab}
              </TabsTrigger>
            ))}
          </TabsList>
        </div>

        <TabsContent value="document" className="flex-1 overflow-hidden m-0">
          <ScrollArea className="h-full bg-[#fcfcfc] dark:bg-[#0f1115]">
            <div className="min-h-full p-6 md:p-12 max-w-4xl mx-auto">
              <div className="bg-white dark:bg-[#16181d] shadow-[0_0_50px_rgba(0,0,0,0.04)] dark:shadow-none border border-[var(--k-border)] rounded-lg p-8 md:p-14 min-h-[800px]">
                {/* Document Title Bar */}
                <div className="mb-10">
                  <div className="w-12 h-1 bg-[var(--k-brand)] mb-4" />
                  <div className="text-[10px] uppercase tracking-[0.25em] text-muted-foreground font-bold mb-1">Kautilya Document</div>
                  <h1 className="k-heading text-2xl md:text-3xl font-bold text-foreground">{content?.title || 'Untitled Document'}</h1>
                </div>

                {(() => {
                  const { body, sources } = cleanDocumentContent(content?.code);
                  if (!body) {
                    return (
                      <div className="flex flex-col items-center justify-center py-20 text-center text-muted-foreground">
                        <FileText className="w-12 h-12 mb-4 opacity-10" />
                        <p>No document content generated yet.</p>
                        <p className="text-xs mt-2 opacity-60">Use Deep Research or ask Kautilya to write a document.</p>
                      </div>
                    );
                  }
                  return (
                    <>
                      <div className="font-sans">
                        <ReactMarkdown components={DOC_COMPONENTS}>{body}</ReactMarkdown>
                      </div>
                      {sources?.length > 0 && (
                        <div className="mt-12 pt-6 border-t border-[var(--k-border)]">
                          <div className="text-[10px] uppercase tracking-[0.25em] text-muted-foreground font-bold mb-4">Sources</div>
                          <ol className="space-y-2 text-sm">
                            {sources.map((s, i) => (
                              <li key={i} className="flex items-start gap-3">
                                <span className="text-[var(--k-brand)] font-bold min-w-[24px]">[{i + 1}]</span>
                                <a href={s.url} target="_blank" rel="noopener noreferrer" className="text-[var(--k-brand)] underline underline-offset-2 hover:opacity-80 break-all">
                                  {s.title || s.url}
                                </a>
                              </li>
                            ))}
                          </ol>
                        </div>
                      )}
                    </>
                  );
                })()}

                {/* Footer */}
                <div className="mt-20 pt-8 border-t border-[var(--k-border)] flex justify-between items-center text-[10px] uppercase tracking-widest text-muted-foreground font-bold">
                  <span>Kautilya AI · Deep Research</span>
                  <span>Confidential</span>
                </div>
              </div>
            </div>
          </ScrollArea>
        </TabsContent>

        <TabsContent value="code" className="flex-1 overflow-hidden m-0">
          <div className="h-full bg-[#1e1e1e]">
            <SyntaxHighlighter
              language={content?.language || 'javascript'}
              style={vscDarkPlus}
              customStyle={{
                margin: 0,
                padding: '1.5rem',
                fontSize: '0.85rem',
                height: '100%',
                background: 'transparent',
              }}
              showLineNumbers
            >
              {content?.code || "// No code available"}
            </SyntaxHighlighter>
          </div>
        </TabsContent>

        <TabsContent value="dashboard" className="flex-1 overflow-hidden m-0">
          <ScrollArea className="h-full">
            <div className="p-6 space-y-6">
              {(!kpis || kpis.length === 0) && (!revenueData || revenueData.length === 0) ? (
                <div className="flex flex-col items-center justify-center py-20 text-center">
                  <div className="w-16 h-16 rounded-full bg-accent/50 flex items-center justify-center mb-6">
                    <ChartBar className="w-8 h-8 text-muted-foreground/30" />
                  </div>
                  <h3 className="text-lg font-semibold mb-2">No Visual Data</h3>
                  <p className="text-sm text-muted-foreground max-w-[280px]">Ask Kautilya to analyze data or generate a report to see visualizations here.</p>
                </div>
              ) : (
                <>
                  {kpis.length > 0 && (
                    <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
                      {kpis.map((kpi, i) => (
                        <div key={i} className="p-4 rounded-xl border border-[var(--k-border)] bg-[var(--k-surface)] shadow-sm hover:shadow-md transition-shadow">
                          <div className="text-[10px] tracking-[0.15em] uppercase text-muted-foreground font-bold mb-2">{kpi.label}</div>
                          <div className="text-2xl font-bold tracking-tight text-foreground">{kpi.value}</div>
                          {kpi.change && (
                            <div className={`text-xs font-bold mt-2 flex items-center gap-1 ${kpi.positive ? 'text-[var(--k-green)]' : 'text-rose-500'}`}>
                              <span className="px-1.5 py-0.5 rounded bg-current/10">{kpi.change}</span>
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  )}

                  {revenueData.length > 0 && (
                    <div className="p-6 rounded-xl border border-[var(--k-border)] bg-[var(--k-surface)] shadow-sm">
                      <div className="text-sm font-bold text-foreground mb-6 flex items-center gap-2">
                        <div className="w-1.5 h-1.5 rounded-full bg-[var(--k-brand)]" />
                        Performance Trend
                      </div>
                      <ResponsiveContainer width="100%" height={250}>
                        <AreaChart data={revenueData}>
                          <defs>
                            <linearGradient id="colorRevenue" x1="0" y1="0" x2="0" y2="1">
                              <stop offset="5%" stopColor="var(--k-brand)" stopOpacity={0.2}/>
                              <stop offset="95%" stopColor="var(--k-brand)" stopOpacity={0}/>
                            </linearGradient>
                          </defs>
                          <CartesianGrid strokeDasharray="3 3" stroke="var(--k-border)" vertical={false} />
                          <XAxis dataKey="label" tick={{ fontSize: 10, fill: 'var(--k-text-secondary)', fontWeight: 600 }} axisLine={false} tickLine={false} />
                          <YAxis tick={{ fontSize: 10, fill: 'var(--k-text-secondary)', fontWeight: 600 }} axisLine={false} tickLine={false} />
                          <Tooltip
                            contentStyle={{ background: 'var(--k-surface)', border: '1px solid var(--k-border)', borderRadius: '12px', fontSize: '12px', fontWeight: 600, boxShadow: '0 10px 15px -3px rgba(0,0,0,0.1)' }}
                            cursor={{ stroke: 'var(--k-brand)', strokeWidth: 1 }}
                          />
                          <Area type="monotone" dataKey="value" stroke="var(--k-brand)" strokeWidth={3} fill="url(#colorRevenue)" />
                        </AreaChart>
                      </ResponsiveContainer>
                    </div>
                  )}

                  {salesByRegion.length > 0 && (
                    <div className="p-6 rounded-xl border border-[var(--k-border)] bg-[var(--k-surface)] shadow-sm">
                      <div className="text-sm font-bold text-foreground mb-6 flex items-center gap-2">
                        <div className="w-1.5 h-1.5 rounded-full bg-[var(--k-yellow)]" />
                        Regional Distribution
                      </div>
                      <ResponsiveContainer width="100%" height={250}>
                        <BarChart data={salesByRegion}>
                          <CartesianGrid strokeDasharray="3 3" stroke="var(--k-border)" vertical={false} />
                          <XAxis dataKey="name" tick={{ fontSize: 10, fill: 'var(--k-text-secondary)', fontWeight: 600 }} axisLine={false} tickLine={false} />
                          <YAxis tick={{ fontSize: 10, fill: 'var(--k-text-secondary)', fontWeight: 600 }} axisLine={false} tickLine={false} />
                          <Tooltip contentStyle={{ background: 'var(--k-surface)', border: '1px solid var(--k-border)', borderRadius: '12px', fontSize: '12px', fontWeight: 600 }} />
                          <Bar dataKey="value" radius={[6, 6, 0, 0]}>
                            {salesByRegion.map((entry, index) => (
                              <Cell key={index} fill={entry.fill || "var(--k-brand)"} />
                            ))}
                          </Bar>
                        </BarChart>
                      </ResponsiveContainer>
                    </div>
                  )}
                </>
              )}
            </div>
          </ScrollArea>
        </TabsContent>

        <TabsContent value="preview" className="flex-1 overflow-hidden m-0 bg-white">
          {content?.code?.includes('<!DOCTYPE html>') || content?.code?.includes('<html') ? (
            <iframe
              srcDoc={content.code}
              title="Preview"
              className="w-full h-full border-none"
              sandbox="allow-scripts"
            />
          ) : (
            <div className="flex flex-col items-center justify-center h-full text-center p-10 bg-[var(--k-bg)]">
              <ArrowsOutSimple className="w-16 h-16 text-muted-foreground/10 mb-6" />
              <h3 className="text-lg font-semibold mb-2">No Preview Available</h3>
              <p className="text-sm text-muted-foreground max-w-[280px]">Standard code snippets cannot be previewed. Generate HTML/CSS to enable the live preview.</p>
            </div>
          )}
        </TabsContent>
      </Tabs>
      )}
    </div>
  );
}
