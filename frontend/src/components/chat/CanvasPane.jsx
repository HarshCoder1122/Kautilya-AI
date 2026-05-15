import { useState, useEffect, useMemo } from "react";
import ReactMarkdown from 'react-markdown';
import { X, Code, ChartBar, FileText, Copy, Download, ArrowsOutSimple, Check, FolderOpen, Eye, File } from "@phosphor-icons/react";
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
  const html = files.find(f => f.name.endsWith('.html') || f.name === 'index.html');
  if (!html) return null;
  let src = html.content;
  // Inline CSS files referenced by filename
  files.filter(f => f.language === 'css').forEach(f => {
    src = src.replace(
      new RegExp(`<link[^>]*href=["']${f.name}["'][^>]*>`, 'gi'),
      `<style>${f.content}</style>`
    );
  });
  // Inline JS files referenced by filename
  files.filter(f => f.language === 'javascript' && !f.name.endsWith('.jsx')).forEach(f => {
    src = src.replace(
      new RegExp(`<script[^>]*src=["']${f.name}["'][^>]*></script>`, 'gi'),
      `<script>${f.content}</script>`
    );
  });
  return src;
}

function downloadFile(filename, content) {
  const blob = new Blob([content], { type: 'text/plain' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a'); a.href = url; a.download = filename; a.click();
  URL.revokeObjectURL(url);
}

function MultiFileWorkspace({ files, title }) {
  const [activeFile, setActiveFile] = useState(files[0]?.name || '');
  const [viewMode, setViewMode] = useState('code'); // 'code' | 'preview'
  const [copied, setCopied] = useState(false);

  const currentFile = files.find(f => f.name === activeFile) || files[0];
  const htmlPreview = useMemo(() => buildHtmlPreview(files), [files]);

  const handleCopy = () => {
    if (currentFile) {
      navigator.clipboard.writeText(currentFile.content).catch(() => {});
      setCopied(true); setTimeout(() => setCopied(false), 2000);
    }
  };

  return (
    <div className="flex flex-col h-full">
      {/* Toolbar */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-[var(--k-border)] bg-[var(--k-surface)] flex-shrink-0">
        <div className="flex items-center gap-1">
          <FolderOpen className="w-4 h-4 text-[var(--k-brand)]" />
          <span className="text-xs font-bold text-foreground ml-1 truncate max-w-[160px]">{title}</span>
          <span className="text-[10px] text-muted-foreground ml-2">{files.length} file{files.length !== 1 ? 's' : ''}</span>
        </div>
        <div className="flex items-center gap-1">
          {htmlPreview && (
            <button
              onClick={() => setViewMode(v => v === 'preview' ? 'code' : 'preview')}
              className={`flex items-center gap-1 px-2 py-1 rounded text-[10px] font-bold transition-all ${viewMode === 'preview' ? 'bg-[var(--k-brand)] text-white' : 'bg-accent text-muted-foreground hover:text-foreground'}`}
            >
              <Eye className="w-3 h-3" />{viewMode === 'preview' ? 'Code' : 'Preview'}
            </button>
          )}
          <button onClick={handleCopy} className="p-1.5 rounded hover:bg-accent" title="Copy file">
            {copied ? <Check className="w-3.5 h-3.5 text-green-400" /> : <Copy className="w-3.5 h-3.5 text-muted-foreground" />}
          </button>
          <button onClick={() => currentFile && downloadFile(currentFile.name, currentFile.content)} className="p-1.5 rounded hover:bg-accent" title="Download file">
            <Download className="w-3.5 h-3.5 text-muted-foreground" />
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
              sandbox="allow-scripts"
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
            <div className="min-h-full p-8 md:p-16 max-w-4xl mx-auto">
              <div className="bg-white dark:bg-[#1a1d23] shadow-[0_0_50px_rgba(0,0,0,0.05)] dark:shadow-none border border-[var(--k-border)] rounded-sm p-10 md:p-20 min-h-[1100px]">
                {/* Document Header Decoration */}
                <div className="w-12 h-1 bg-[var(--k-brand)] mb-12" />

                <div className="prose prose-sm md:prose-base dark:prose-invert max-w-none font-sans text-[#2c3e50] dark:text-[#e1e1e1] leading-[1.8]">
                  {content?.code ? (
                    <ReactMarkdown>{content.code}</ReactMarkdown>
                  ) : (
                    <div className="flex flex-col items-center justify-center py-20 text-center text-muted-foreground">
                      <FileText className="w-12 h-12 mb-4 opacity-10" />
                      <p>No document content generated yet.</p>
                      <p className="text-xs mt-2 opacity-60">Use Deep Research or ask Kautilya to write a document.</p>
                    </div>
                  )}
                </div>

                {/* Document Footer Decoration */}
                <div className="mt-20 pt-8 border-t border-[var(--k-border)] flex justify-between items-center text-[10px] uppercase tracking-widest text-muted-foreground font-bold">
                  <span>Kautilya Deep Research Intelligence</span>
                  <span>Confidential / Internal</span>
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
