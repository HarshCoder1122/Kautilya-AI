import { useState, useEffect, useMemo, useRef } from "react";
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import JSZip from 'jszip';
import { X, Code, ChartBar, FileText, Copy, Download, ArrowsOutSimple, Check, FolderOpen, Eye, File, ArrowSquareOut, Archive, CaretUp, CaretDown, MagnifyingGlass, Table } from "@phosphor-icons/react";
import { Tabs, TabsContent } from "@/components/ui/tabs";
import { ScrollArea } from "@/components/ui/scroll-area";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell, Area, AreaChart } from "recharts";
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { coderProjectsAPI, artifactsAPI } from '@/lib/api';

/** Parse `<file ...>...</file>` blocks from model output.
 *
 * Tolerates the variations the model emits in practice:
 *   - attribute can be `name=`, `path=`, or `filename=`
 *   - quotes can be "double", 'single', or unquoted
 *   - optional `language=`
 *   - body may be wrapped in ```fenced``` code blocks (we strip the fence)
 *   - `</file>` may be on the same line as the closing fence
 */
function parseFileBlocks(code) {
  if (!code) return [];
  const files = [];
  const seen = new Set();

  const pushFile = (name, body, langHint) => {
    if (!name) return;
    const cleanName = name.trim().replace(/^["'`]|["'`]$/g, '');
    if (!cleanName || seen.has(cleanName)) return;
    seen.add(cleanName);
    files.push({
      name: cleanName,
      language: langHint || inferLang(cleanName),
      content: (body || '').replace(/^\n+|\n+$/g, ''),
    });
  };

  // 1) Explicit <file name="..." language="..."> blocks
  const re = /<file\s+([^>]+?)>([\s\S]*?)<\/file>/gi;
  let m;
  while ((m = re.exec(code)) !== null) {
    const attrs = parseAttrs(m[1]);
    const filename = attrs.name || attrs.path || attrs.filename || attrs.file;
    if (!filename) continue;
    let body = m[2];
    body = body.replace(/^\s*```[a-zA-Z0-9_+-]*\s*\n/, '').replace(/\n\s*```\s*$/, '');
    pushFile(filename, body, attrs.language || attrs.lang);
  }

  // 1.5) Handle unclosed <file ...> tag at the end of streaming code
  const lastOpenIndex = code.toLowerCase().lastIndexOf('<file');
  const lastCloseIndex = code.toLowerCase().lastIndexOf('</file>');
  if (lastOpenIndex > lastCloseIndex) {
    const unclosedPart = code.slice(lastOpenIndex);
    const tagMatch = unclosedPart.match(/<file\s+([^>]+?)>/i);
    if (tagMatch) {
      const openTag = tagMatch[0];
      const attrs = parseAttrs(tagMatch[1]);
      const filename = attrs.name || attrs.path || attrs.filename || attrs.file;
      if (filename) {
        let body = unclosedPart.slice(tagMatch.index + openTag.length);
        body = body.replace(/^\s*```[a-zA-Z0-9_+-]*\s*\n/, '');
        body = body.replace(/\n\s*```\s*$/, '');
        pushFile(filename, body, attrs.language || attrs.lang);
      }
    }
  }

  // 2) Claude/Emergent-style: a filename header immediately followed by a
  //    fenced code block. We accept several common header forms so projects
  //    parse cleanly even when the model forgets <file> tags.
  //
  //    Recognized headers (each on its own line, with code fence right after):
  //      **path/file.tsx**
  //      ### path/file.tsx
  //      ## path/file.tsx
  //      `path/file.tsx`
  //      File: path/file.tsx
  //      path/file.tsx
  //
  //    Also recognizes ```filename.tsx as the language label.
  const FILENAME_HINT = /^[\w./@-]+\.[a-zA-Z0-9]{1,6}$/;
  const headerRe = /^[ \t]*(?:\*\*|`|#{1,6}\s+|(?:[Ff]ile|[Ff]ilename|[Pp]ath)\s*[:=]\s*)?([\w./@-]+\.[a-zA-Z0-9]{1,6})(?:\*\*|`)?[ \t]*$/;
  // Tokenize on fenced blocks so we can pair "preceding header" → "fence".
  const fenceRe = /```([a-zA-Z0-9_+./@-]*)\s*\n([\s\S]*?)```/g;
  let fm;
  while ((fm = fenceRe.exec(code)) !== null) {
    const lang = (fm[1] || '').trim();
    const body = fm[2] || '';
    const startIdx = fm.index;

    // Skip if this fence sits INSIDE a <file>...</file> we already handled.
    const tail = code.slice(0, startIdx);
    const lastOpen = tail.lastIndexOf('<file');
    const lastClose = tail.lastIndexOf('</file>');
    if (lastOpen > lastClose) continue;

    // Case A: language label is itself a filename → use it.
    if (FILENAME_HINT.test(lang)) {
      pushFile(lang, body);
      continue;
    }

    // Case B: look at the up-to-3 non-empty lines preceding the fence for a
    // filename header.
    const beforeText = tail.slice(Math.max(0, tail.length - 400));
    const beforeLines = beforeText.split('\n').filter(l => l.trim().length).slice(-3).reverse();
    let foundName = null;
    for (const line of beforeLines) {
      const h = line.match(headerRe);
      if (h && FILENAME_HINT.test(h[1])) { foundName = h[1]; break; }
      // First non-empty line that ISN'T a filename header breaks the search
      // (we only want IMMEDIATELY-preceding filename labels).
      if (line.trim().length > 0 && !/^[\*#`>\-\s]*$/.test(line)) break;
    }
    if (foundName) {
      pushFile(foundName, body, lang || undefined);
      continue;
    }

    // Case C: leading comment naming the file: // File: x.tsx  or  # path/y.py
    const firstLine = body.split('\n', 1)[0] || '';
    const commentMatch = firstLine.match(/^[ \t]*(?:\/\/|#|--|;)\s*(?:[Ff]ile\s*[:=]\s*)?([\w./@-]+\.[a-zA-Z0-9]{1,6})\s*$/);
    if (commentMatch && FILENAME_HINT.test(commentMatch[1])) {
      const stripped = body.split('\n').slice(1).join('\n');
      pushFile(commentMatch[1], stripped, lang || undefined);
      continue;
    }
  }

  return files;
}

/** Tiny attribute parser for the `<file ...>` open tag. */
function parseAttrs(s) {
  const out = {};
  const re = /([a-zA-Z_:][\w:-]*)\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]+))/g;
  let m;
  while ((m = re.exec(s)) !== null) {
    out[m[1].toLowerCase()] = m[2] ?? m[3] ?? m[4] ?? '';
  }
  return out;
}

function inferLang(filename) {
  const ext = filename.split('.').pop().toLowerCase();
  const map = { js: 'javascript', jsx: 'javascript', ts: 'typescript', tsx: 'typescript',
    py: 'python', html: 'html', css: 'css', json: 'json', md: 'markdown',
    txt: 'text', sh: 'bash', yml: 'yaml', yaml: 'yaml' };
  return map[ext] || 'text';
}

/** Wrap a single code-snippet artifact into a one-element files array so it can
 *  flow through MultiFileWorkspace — which gives it the live preview toggle,
 *  fullscreen, open-in-new-tab, copy and download controls for free. The name
 *  is chosen so the preview builders detect an entrypoint (index.html for HTML,
 *  App.jsx/App.tsx for React) and render it instead of showing "no preview". */
function syntheticFilesFromCode(content) {
  const code = content?.code || '';
  const lang = (content?.language || '').toLowerCase();
  const looksHtml = /<!doctype html>|<html[\s>]/i.test(code);
  const looksJsx = /<[A-Za-z][^>]*>/.test(code) &&
                   /\b(import|export|function|const)\b/.test(code) &&
                   /return\s*\(?\s*</.test(code);
  let name;
  if (looksHtml || lang === 'html') name = 'index.html';
  else if (lang === 'tsx') name = 'App.tsx';
  else if (lang === 'jsx' || ((lang === 'javascript' || lang === 'js' || !lang) && looksJsx)) name = 'App.jsx';
  else if (lang === 'css') name = 'styles.css';
  else if (lang === 'json') name = 'data.json';
  else if (lang === 'python' || lang === 'py') name = 'main.py';
  else if (lang === 'typescript' || lang === 'ts') name = 'index.ts';
  else if (lang === 'javascript' || lang === 'js') name = 'index.js';
  else name = 'snippet.' + (lang ? lang.replace(/[^a-z0-9]/g, '') : 'txt');
  return [{ name, language: lang || inferLang(name), content: code }];
}

// Google-Fonts link the previews share (Inter + Plus Jakarta Sans).
const PREVIEW_FONTS_LINK =
  '<link rel="preconnect" href="https://fonts.googleapis.com">' +
  '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>' +
  '<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap" rel="stylesheet">';

/** Make an HTML document preview render the way the model intended: ensure
 *  Tailwind + web fonts are present. We only inject Tailwind when the markup
 *  clearly uses utility classes but forgot the CDN (so we never double-load a
 *  framework the author already included). Fonts are added when absent. */
function injectPreviewAssets(src) {
  if (!src) return src;
  const hasTailwind = /cdn\.tailwindcss\.com|tailwindcss/i.test(src);
  const hasFonts = /fonts\.googleapis\.com/i.test(src);
  const usesTwClasses = /class=["'][^"']*\b(flex|grid|hidden|rounded|shadow|gap-\d|p-\d|px-\d|py-\d|m-\d|mx-|my-|text-(?:xs|sm|base|lg|xl|\d)|bg-[a-z]|border|w-\d|h-\d|items-|justify-)/i.test(src);

  let head = '';
  if (!hasTailwind && usesTwClasses) head += '<script src="https://cdn.tailwindcss.com"></script>';
  if (!hasFonts) {
    head += PREVIEW_FONTS_LINK;
    // Only set a default font when the author didn't pick one themselves.
    if (!/font-family/i.test(src)) {
      head += "<style>:root{font-family:Inter,'Plus Jakarta Sans',system-ui,-apple-system,sans-serif}</style>";
    }
  }
  if (!head) return src;

  if (/<head[^>]*>/i.test(src)) return src.replace(/<head[^>]*>/i, (m) => m + head);
  if (/<html[^>]*>/i.test(src)) return src.replace(/<html[^>]*>/i, (m) => m + '<head>' + head + '</head>');
  return head + src;
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
  return injectPreviewAssets(src);
}

/** Build a self-contained HTML page that mounts a React/JSX/TSX project in
 *  the iframe using Babel standalone for in-browser transpile. Recognizes
 *  common entrypoints (App.jsx, App.tsx, src/App.tsx, index.tsx, main.tsx)
 *  and loads sibling modules via an in-memory import map so `import X from
 *  './Other'` works without a bundler. CSS files are inlined as <style>.
 */
function buildReactPreview(files) {
  if (!files || !files.length) return null;
  const isReactFile = (f) => /\.(jsx|tsx)$/i.test(f.name);
  const reactFiles = files.filter(isReactFile);
  if (!reactFiles.length) return null;

  // Pick an entry: App.tsx/jsx → src/App.tsx → main/index.tsx → first React file
  const byName = (n) => reactFiles.find(f => f.name.replace(/^\.\//, '') === n);
  const entry =
       byName('App.tsx') || byName('App.jsx')
    || byName('src/App.tsx') || byName('src/App.jsx')
    || byName('index.tsx') || byName('index.jsx')
    || byName('main.tsx') || byName('main.jsx')
    || byName('src/index.tsx') || byName('src/main.tsx')
    || reactFiles[0];

  if (!entry) return null;

  // All inlined CSS
  const cssFiles = files.filter(f => /\.css$/i.test(f.name));
  const cssCombined = cssFiles.map(f => `/* ${f.name} */\n${f.content}`).join('\n\n');

  // Build module registry: { "./Foo": "...code...", "./components/Bar": "..." }
  // Strip extensions on keys so import paths resolve regardless of extension.
  const moduleMap = {};
  for (const f of reactFiles) {
    const noExt = f.name.replace(/\.(jsx|tsx|js|ts)$/i, '');
    moduleMap[`./${noExt}`] = f.content;
    moduleMap[`./${f.name}`] = f.content;
    // Also expose without leading './'
    moduleMap[noExt] = f.content;
    moduleMap[f.name] = f.content;
  }

  // Strip TypeScript-only constructs that Babel preset-typescript handles —
  // we already include preset-typescript, so this is just a safety net for
  // `import type` lines that cause issues with the loader.
  // (Babel handles the rest.)

  const moduleMapJson = JSON.stringify(moduleMap);
  const entryName = entry.name;

  return `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>React Preview</title>
<script src="https://cdn.tailwindcss.com"></script>
<script>window.tailwind=window.tailwind||{};window.tailwind.config={theme:{extend:{fontFamily:{sans:['Inter','Plus Jakarta Sans','ui-sans-serif','system-ui','sans-serif'],display:['Plus Jakarta Sans','Inter','sans-serif']}}}};</script>
${PREVIEW_FONTS_LINK}
<script crossorigin src="https://unpkg.com/react@18/umd/react.development.js"></script>
<script crossorigin src="https://unpkg.com/react-dom@18/umd/react-dom.development.js"></script>
<script src="https://unpkg.com/@babel/standalone@7.24.7/babel.min.js"></script>
<style>
  html,body,#root{margin:0;padding:0;min-height:100vh;font-family:Inter,'Plus Jakarta Sans',-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;}
  #__preview_error{position:fixed;inset:0;background:#1e1e22;color:#ff8a8a;padding:24px;font:13px/1.55 ui-monospace,SFMono-Regular,Menlo,monospace;white-space:pre-wrap;overflow:auto;display:none;z-index:9999;}
${cssCombined}
</style>
</head>
<body>
<div id="root"></div>
<pre id="__preview_error"></pre>
<script>
  window.process = window.process || { env: { NODE_ENV: 'development' } };
  const __MODULES__ = ${moduleMapJson};
  const __CACHE__ = {};

  function showError(err) {
    const box = document.getElementById('__preview_error');
    box.textContent = (err && (err.stack || err.message)) || String(err);
    box.style.display = 'block';
    console.error(err);
  }
  window.addEventListener('error', e => showError(e.error || e.message));
  window.addEventListener('unhandledrejection', e => showError(e.reason));

  function resolve(spec, fromKey) {
    // Strip ./ and extension to match registry keys
    let k = spec.replace(/^\\.\\//, '');
    if (__MODULES__[spec] != null) return spec;
    if (__MODULES__['./' + k] != null) return './' + k;
    if (__MODULES__[k] != null) return k;
    const stripped = k.replace(/\\.(jsx|tsx|js|ts)$/i, '');
    if (__MODULES__['./' + stripped] != null) return './' + stripped;
    if (__MODULES__[stripped] != null) return stripped;
    return null;
  }

  function externalModule(spec) {
    if (spec === 'react') return React;
    if (spec === 'react-dom') return ReactDOM;
    if (spec === 'react-dom/client') return ReactDOM;
    return null;
  }

  function load(spec) {
    if (__CACHE__[spec]) return __CACHE__[spec].exports;
    const src = __MODULES__[spec];
    if (src == null) throw new Error('Module not found: ' + spec);

    let transformed;
    try {
      transformed = Babel.transform(src, {
        presets: [
          ['env', { modules: 'commonjs', targets: { esmodules: true } }],
          'react',
          ['typescript', { allExtensions: true, isTSX: true, allowDeclareFields: true }]
        ],
        filename: spec
      }).code;
    } catch (e) {
      throw new Error('Compile failed in ' + spec + ':\\n' + (e.message || e));
    }

    const module = { exports: {} };
    __CACHE__[spec] = module;
    const require = (req) => {
      const ext = externalModule(req);
      if (ext) return ext;
      const resolved = resolve(req, spec);
      if (resolved == null) throw new Error('Cannot resolve "' + req + '" from ' + spec);
      return load(resolved);
    };
    try {
      new Function('require', 'module', 'exports', transformed)(require, module, module.exports);
    } catch (e) {
      throw new Error('Runtime error in ' + spec + ':\\n' + (e.stack || e.message || e));
    }
    return module.exports;
  }

  try {
    const entryKey = resolve(${JSON.stringify(entryName)}, null) || ${JSON.stringify(entryName)};
    const mod = load(entryKey);
    const Component = mod && (mod.default || mod.App || mod);
    const container = document.getElementById('root');
    if (typeof Component === 'function' || (Component && Component.$$typeof)) {
      const root = ReactDOM.createRoot(container);
      root.render(React.createElement(Component));
    } else if (mod && mod.default && typeof mod.default === 'object') {
      // Module just exported elements
      const root = ReactDOM.createRoot(container);
      root.render(mod.default);
    } else {
      // Side-effect entry (e.g. main.tsx already calls createRoot)
      // Nothing to do — the entry already rendered itself.
    }
  } catch (e) {
    showError(e);
  }
</script>
</body>
</html>`;
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
    .replace(/<file\s+[^>]*?>[\s\S]*?<\/file>/gi, '')
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
  a: ({ href, children }) => {
    // Normalize scheme-less hrefs (e.g. "youtube.com/abc") so the browser
    // doesn't treat them as paths relative to ai.revealiq.in.
    let safe = (href || '').trim();
    if (safe && !/^(https?:|ftp:|mailto:|tel:|sms:|#|\/)/i.test(safe)) {
      if (safe.startsWith('//')) safe = 'https:' + safe;
      else if (/^[a-z0-9.-]+\.[a-z]{2,}(\/|$)/i.test(safe)) safe = 'https://' + safe;
    }
    return <a href={safe || '#'} target="_blank" rel="noopener noreferrer" className="text-[var(--k-brand)] underline underline-offset-2 hover:opacity-80 break-all">{children}</a>;
  },
  table: ({ children }) => <div className="overflow-x-auto my-4 sm:my-6 max-w-full -mx-0"><table className="min-w-full border border-[var(--k-border)] rounded-md text-sm">{children}</table></div>,
  thead: ({ children }) => <thead className="bg-[var(--k-surface)]">{children}</thead>,
  th: ({ children }) => <th className="px-4 py-2 text-left font-semibold border-b border-[var(--k-border)]">{children}</th>,
  td: ({ children }) => <td className="px-4 py-2 border-b border-[var(--k-border)]">{children}</td>,
  code: ({ inline, children }) => inline
    ? <code className="bg-accent/50 px-1.5 py-0.5 rounded text-[0.85em] font-mono break-all">{children}</code>
    : <pre className="bg-[var(--k-surface)] border border-[var(--k-border)] rounded-md p-3 sm:p-4 overflow-x-auto my-4 text-sm font-mono max-w-full"><code className="whitespace-pre">{children}</code></pre>,
  hr: () => <hr className="my-8 border-[var(--k-border)]" />,
  strong: ({ children }) => <strong className="font-semibold text-foreground">{children}</strong>,
};

function isNumericColumn(rows, colIndex) {
  if (!rows || rows.length === 0) return false;
  const checkCount = Math.min(rows.length, 10);
  let numericCount = 0;
  for (let i = 0; i < checkCount; i++) {
    const val = String(rows[i][colIndex] ?? '').trim();
    if (!val) continue; // Skip empty
    const clean = val.replace(/[$,%]/g, '');
    if (!isNaN(Number(clean)) || /^-?\d+(\.\d+)?$/.test(clean)) {
      numericCount++;
    }
  }
  return numericCount > 0 && numericCount >= (checkCount / 2);
}

function parseSpreadsheetCode(code) {
  if (!code) return [];
  let trimmed = code.trim();

  // Strip code block wrappers if any (e.g. ```json ... ``` or ```csv ... ```)
  trimmed = trimmed.replace(/^```[a-zA-Z0-9_+-]*\s*\n/, '').replace(/\n\s*```\s*$/, '').trim();

  if (trimmed.startsWith('{') || trimmed.startsWith('[')) {
    try {
      const data = JSON.parse(trimmed);
      if (data && Array.isArray(data.sheets)) {
        return data.sheets.map(sheet => ({
          name: sheet.name || 'Sheet',
          headers: Array.isArray(sheet.header) ? sheet.header : (Array.isArray(sheet.headers) ? sheet.headers : []),
          rows: Array.isArray(sheet.rows) ? sheet.rows : [],
        }));
      }
      if (Array.isArray(data)) {
        if (data.length === 0) return [];
        const headers = Object.keys(data[0] || {});
        const rows = data.map(item => headers.map(h => item[h]));
        return [{
          name: 'Sheet 1',
          headers,
          rows,
        }];
      }
      if (data && (Array.isArray(data.header) || Array.isArray(data.headers)) && Array.isArray(data.rows)) {
        const headers = Array.isArray(data.header) ? data.header : data.headers;
        return [{
          name: 'Sheet 1',
          headers,
          rows: data.rows,
        }];
      }
    } catch (e) {
      console.warn("JSON sheet parsing failed, falling back to markdown/csv", e);
    }
  }

  // Check if it's a markdown table
  const lines = trimmed.split('\n').map(line => line.trim()).filter(line => line.length > 0);
  const pipeLines = lines.filter(line => line.startsWith('|'));
  if (pipeLines.length >= 2) {
    const parseRow = (line) => line.split('|').map(cell => cell.trim()).filter((_, idx, arr) => idx > 0 && idx < arr.length - 1);
    const headers = parseRow(pipeLines[0]);
    const startIdx = pipeLines[1].replace(/[\s|:-]/g, '') === '' ? 2 : 1;
    const rows = pipeLines.slice(startIdx).map(line => parseRow(line));
    return [{
      name: 'Table',
      headers,
      rows,
    }];
  }

  // Check if it's comma/semicolon/tab separated (CSV-like)
  if (lines.length > 0) {
    const firstLine = lines[0];
    let delimiter = ',';
    if (firstLine.includes('\t')) delimiter = '\t';
    else if (firstLine.includes(';')) delimiter = ';';

    const parseCSVLine = (line) => {
      const result = [];
      let current = '';
      let inQuotes = false;
      for (let i = 0; i < line.length; i++) {
        const char = line[i];
        if (char === '"' || char === "'") {
          inQuotes = !inQuotes;
        } else if (char === delimiter && !inQuotes) {
          result.push(current.trim());
          current = '';
        } else {
          current += char;
        }
      }
      result.push(current.trim());
      return result;
    };

    const headers = parseCSVLine(lines[0]);
    const rows = lines.slice(1).map(line => parseCSVLine(line));
    return [{
      name: 'CSV Sheet',
      headers,
      rows,
    }];
  }

  return [];
}

function SpreadsheetView({ code }) {
  const sheets = useMemo(() => parseSpreadsheetCode(code), [code]);
  const [selectedSheetIndex, setSelectedSheetIndex] = useState(0);
  const [searchTerm, setSearchTerm] = useState("");
  const [sortState, setSortState] = useState({ colIndex: null, direction: null });

  useEffect(() => {
    setSelectedSheetIndex(0);
    setSearchTerm("");
    setSortState({ colIndex: null, direction: null });
  }, [code]);

  const currentSheet = sheets[selectedSheetIndex] || sheets[0];

  const handleSort = (colIndex) => {
    setSortState(prev => {
      if (prev.colIndex === colIndex) {
        if (prev.direction === 'asc') return { colIndex, direction: 'desc' };
        if (prev.direction === 'desc') return { colIndex: null, direction: null };
      }
      return { colIndex, direction: 'asc' };
    });
  };

  const filteredRows = useMemo(() => {
    if (!currentSheet || !currentSheet.rows) return [];
    if (!searchTerm.trim()) return currentSheet.rows;
    const lower = searchTerm.toLowerCase();
    return currentSheet.rows.filter(row =>
      row.some(cell => String(cell ?? '').toLowerCase().includes(lower))
    );
  }, [currentSheet, searchTerm]);

  const sortedRows = useMemo(() => {
    if (sortState.colIndex === null || !sortState.direction) return filteredRows;
    return [...filteredRows].sort((a, b) => {
      let valA = String(a[sortState.colIndex] ?? '').trim();
      let valB = String(b[sortState.colIndex] ?? '').trim();

      const cleanA = valA.replace(/[$,%]/g, '');
      const cleanB = valB.replace(/[$,%]/g, '');
      const numA = Number(cleanA);
      const numB = Number(cleanB);

      if (!isNaN(numA) && !isNaN(numB)) {
        return sortState.direction === 'asc' ? numA - numB : numB - numA;
      }

      return sortState.direction === 'asc'
        ? valA.localeCompare(valB, undefined, { numeric: true, sensitivity: 'base' })
        : valB.localeCompare(valA, undefined, { numeric: true, sensitivity: 'base' });
    });
  }, [filteredRows, sortState]);

  const numericColumns = useMemo(() => {
    if (!currentSheet || !currentSheet.headers || !currentSheet.rows) return {};
    const cols = {};
    currentSheet.headers.forEach((_, idx) => {
      cols[idx] = isNumericColumn(currentSheet.rows, idx);
    });
    return cols;
  }, [currentSheet]);

  if (!sheets || sheets.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-center p-10 bg-[var(--k-bg)]">
        <Table className="w-16 h-16 text-muted-foreground/15 mb-6" />
        <h3 className="text-lg font-semibold mb-2">No Spreadsheet Data</h3>
        <p className="text-sm text-muted-foreground max-w-[280px]">
          The spreadsheet content could not be parsed. Make sure it is formatted as JSON sheets or a markdown table.
        </p>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full bg-[var(--k-bg)] min-h-0">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-4 border-b border-[var(--k-border)] bg-[var(--k-surface)] flex-shrink-0">
        <div className="flex items-center gap-2">
          <div className="relative flex-1 sm:w-64">
            <span className="absolute inset-y-0 left-3 flex items-center pointer-events-none text-muted-foreground">
              <MagnifyingGlass className="w-4 h-4" />
            </span>
            <input
              type="text"
              placeholder="Search spreadsheet..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full pl-9 pr-4 py-1.5 text-xs rounded-lg border border-[var(--k-border)] bg-[var(--k-bg)] text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-[var(--k-brand)] focus:border-[var(--k-brand)]"
            />
          </div>
          {searchTerm && (
            <button
              onClick={() => setSearchTerm("")}
              className="text-xs text-[var(--k-brand)] hover:underline"
            >
              Clear
            </button>
          )}
        </div>
        <div className="text-xs text-muted-foreground font-medium">
          Showing {sortedRows.length} of {currentSheet.rows?.length || 0} rows
        </div>
      </div>

      {sheets.length > 1 && (
        <div className="flex border-b border-[var(--k-border)] bg-[var(--k-surface)] overflow-x-auto select-none flex-shrink-0">
          {sheets.map((sheet, index) => (
            <button
              key={index}
              onClick={() => {
                setSelectedSheetIndex(index);
                setSortState({ colIndex: null, direction: null });
              }}
              className={`px-4 py-2 text-xs font-bold border-b-2 transition-all ${
                selectedSheetIndex === index
                  ? 'border-[var(--k-brand)] text-[var(--k-brand)] bg-[var(--k-brand)]/5'
                  : 'border-transparent text-muted-foreground hover:bg-accent hover:text-foreground'
              }`}
            >
              {sheet.name}
            </button>
          ))}
        </div>
      )}

      <div className="flex-1 overflow-auto min-h-0">
        <table className="w-full border-collapse text-left text-xs select-text">
          <thead className="sticky top-0 bg-[var(--k-surface)] border-b border-[var(--k-border)] z-10">
            <tr>
              {currentSheet.headers.map((header, idx) => {
                const isNumeric = numericColumns[idx];
                const isSorted = sortState.colIndex === idx;
                return (
                  <th
                    key={idx}
                    onClick={() => handleSort(idx)}
                    className={`px-4 py-3 font-semibold text-foreground border-r border-[var(--k-border)] hover:bg-accent/60 cursor-pointer select-none transition-colors ${
                      isNumeric ? 'text-right' : ''
                    }`}
                  >
                    <div className={`flex items-center gap-1.5 justify-between ${isNumeric ? 'flex-row-reverse' : ''}`}>
                      <span className="truncate">{header}</span>
                      <span className="flex-shrink-0 text-muted-foreground/60">
                        {isSorted ? (
                          sortState.direction === 'asc' ? <CaretUp className="w-3.5 h-3.5 text-[var(--k-brand)]" /> : <CaretDown className="w-3.5 h-3.5 text-[var(--k-brand)]" />
                        ) : (
                          <div className="w-3.5 h-3.5 opacity-0 group-hover:opacity-100" />
                        )}
                      </span>
                    </div>
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody className="divide-y divide-[var(--k-border)] bg-[var(--k-bg)]">
            {sortedRows.length === 0 ? (
              <tr>
                <td colSpan={currentSheet.headers.length} className="px-4 py-8 text-center text-muted-foreground italic">
                  No matching records found.
                </td>
              </tr>
            ) : (
              sortedRows.map((row, rowIdx) => (
                <tr key={rowIdx} className="hover:bg-accent/30 transition-colors odd:bg-[var(--k-surface)]/20">
                  {currentSheet.headers.map((_, colIdx) => {
                    const isNumeric = numericColumns[colIdx];
                    const val = row[colIdx];
                    return (
                      <td
                        key={colIdx}
                        className={`px-4 py-2 border-r border-[var(--k-border)] text-foreground/90 max-w-xs truncate ${
                          isNumeric ? 'text-right font-mono' : ''
                        }`}
                        title={String(val ?? '')}
                      >
                        {val === null || val === undefined ? '' : String(val)}
                      </td>
                    );
                  })}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function MultiFileWorkspace({ files, title }) {
  const [activeFile, setActiveFile] = useState(files[0]?.name || '');
  const [viewMode, setViewMode] = useState('code'); // 'code' | 'preview'
  const [copied, setCopied] = useState(false);
  const [zipping, setZipping] = useState(false);
  const [fullscreen, setFullscreen] = useState(false);

  const currentFile = files.find(f => f.name === activeFile) || files[0];
  const htmlPreview = useMemo(() => buildHtmlPreview(files), [files]);
  const reactPreview = useMemo(() => buildReactPreview(files), [files]);
  // Pick whichever preview is available — HTML wins when both, since the
  // model usually emits a dedicated index.html for plain web projects.
  const previewSrc = htmlPreview || reactPreview;
  const previewKind = htmlPreview ? 'html' : (reactPreview ? 'react' : null);

  // Default to the live preview the first time one becomes available — the
  // whole point of the canvas is to SHOW the built UI, not its source.
  const autoPreviewed = useRef(false);
  useEffect(() => {
    if (previewSrc && !autoPreviewed.current) {
      autoPreviewed.current = true;
      setViewMode('preview');
    }
  }, [previewSrc]);

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
          {previewSrc && (
            <>
              <button
                onClick={() => setViewMode(v => v === 'preview' ? 'code' : 'preview')}
                className={`flex items-center gap-1 px-2 py-1 rounded text-[10px] font-bold transition-all ${viewMode === 'preview' ? 'bg-[var(--k-brand)] text-white' : 'bg-accent text-muted-foreground hover:text-foreground'}`}
                title={viewMode === 'preview' ? 'Show code' : `Live ${previewKind === 'react' ? 'React' : 'HTML'} preview`}
              >
                <Eye className="w-3 h-3" />{viewMode === 'preview' ? 'Code' : (previewKind === 'react' ? 'React' : 'Preview')}
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
                    onClick={() => openPreviewInNewTab(previewSrc)}
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
        {/* File tree — only when there's more than one file. */}
        {files.length > 1 && (
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
        )}

        {/* Editor / Preview */}
        <div className="flex-1 min-w-0 overflow-hidden">
          {viewMode === 'preview' && previewSrc ? (
            <iframe
              srcDoc={previewSrc}
              sandbox="allow-scripts allow-forms allow-popups allow-modals"
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
      {fullscreen && previewSrc && (
        <div className="fixed inset-0 z-[100] bg-black/95 flex flex-col">
          <div className="h-12 flex items-center justify-between px-4 border-b border-white/10 bg-[var(--k-surface)]">
            <div className="flex items-center gap-2">
              <Eye className="w-4 h-4 text-[var(--k-brand)]" />
              <span className="text-sm font-bold text-foreground truncate max-w-[60vw]">{title} — Live {previewKind === 'react' ? 'React' : 'HTML'} Preview</span>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={() => openPreviewInNewTab(previewSrc)}
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
            srcDoc={previewSrc}
            sandbox="allow-scripts allow-forms allow-popups allow-modals"
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
    if (c?.type === 'excel' || c?.type === 'spreadsheet' || c?.type === 'csv') return 'spreadsheet';
    if (c?.type === 'code') return 'code';
    if (c?.type === 'document') return 'document';
    if (c?.type === 'dashboard') return 'dashboard';
    return 'document';
  };

  const [activeTab, setActiveTab] = useState(getInitialTab(content));
  const [copied, setCopied] = useState(false);
  const [restoredFiles, setRestoredFiles] = useState(null);

  // Parse multi-file blocks from content
  const parsedBlocks = useMemo(() => parseFileBlocks(content?.code), [content?.code]);
  // Prefer Firestore-restored files when message text doesn't parse to as
  // many files — this is the "never lose your project" guarantee.
  const fileBlocks = useMemo(() => {
    if (restoredFiles && restoredFiles.length > parsedBlocks.length) return restoredFiles;
    return parsedBlocks;
  }, [parsedBlocks, restoredFiles]);
  const isMultiFile = fileBlocks.length > 0;

  // A single code snippet (type === 'code', no <file> blocks) is wrapped into a
  // one-file workspace so it gets the SAME live preview + fullscreen + new-tab +
  // copy + download controls as a full project — and nothing else clutters it.
  const singleCodeFiles = useMemo(() => {
    if (isMultiFile || content?.type !== 'code' || !content?.code) return null;
    return syntheticFilesFromCode(content);
  }, [isMultiFile, content?.type, content?.code, content?.language]);

  // Auto-save coder projects to Firestore (keyed by message_id) so files
  // survive across page reloads even if the underlying message text is
  // trimmed/edited.
  useEffect(() => {
    if (!isMultiFile || !content?.messageId || parsedBlocks.length === 0) return;
    const uid = (() => {
      try { return JSON.parse(localStorage.getItem('user') || '{}')?.uid || ''; }
      catch { return ''; }
    })();
    if (!uid) return;
    const handle = setTimeout(() => {
      coderProjectsAPI.save({
        uid,
        message_id: content.messageId,
        title: content.title || 'Untitled Project',
        files: parsedBlocks.map(f => ({ name: f.name, language: f.language, content: f.content })),
      }).catch((e) => console.warn('[CoderProject] save failed:', e?.message || e));
    }, 800);
    return () => clearTimeout(handle);
  }, [isMultiFile, parsedBlocks, content?.messageId, content?.title]);

  // Auto-restore from Firestore when message text parses to nothing (older
  // chats reopened after a reload).
  useEffect(() => {
    if (!content?.messageId || parsedBlocks.length > 0) return;
    const uid = (() => {
      try { return JSON.parse(localStorage.getItem('user') || '{}')?.uid || ''; }
      catch { return ''; }
    })();
    if (!uid) return;
    let cancelled = false;
    coderProjectsAPI.load(content.messageId, uid)
      .then((res) => {
        if (cancelled) return;
        if (res?.found && Array.isArray(res.files) && res.files.length) {
          setRestoredFiles(res.files);
        }
      })
      .catch((e) => console.warn('[CoderProject] load failed:', e?.message || e));
    return () => { cancelled = true; };
  }, [content?.messageId, parsedBlocks.length]);

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

  const handleDownload = async (kindOverride) => {
    if (!content?.code) return;
    // Default download for a DOCUMENT artifact is a real PDF — not raw .md.
    // (The doc tab also has explicit PDF/DOCX buttons.) Spreadsheets/CSV keep
    // their native formats; the raw code view downloads as source.
    const kind = (typeof kindOverride === 'string' ? kindOverride : null) ||
                 ((content?.type === 'excel' || content?.type === 'spreadsheet') ? 'excel' :
                  content?.type === 'csv' ? 'csv' :
                  activeTab === 'code' ? 'code' : 'pdf');

    if (['excel', 'csv', 'pdf', 'docx'].includes(kind)) {
      // For document exports, strip backend tags (<think>/<artifact>) and the
      // __sources__ blob, and fold any sources into a readable bibliography so
      // the PDF/DOCX matches the on-screen document and is self-contained.
      let payload = content.code;
      if (kind === 'pdf' || kind === 'docx') {
        const { body, sources } = cleanDocumentContent(content.code);
        payload = body || content.code;
        if (sources?.length && !/\n#+\s*sources/i.test(payload)) {
          payload += '\n\n## Sources\n' + sources
            .map((s, i) => `${i + 1}. ${s.title || s.url} — ${s.url}`)
            .join('\n');
        }
      }
      try {
        const blob = await artifactsAPI.create({
          kind,
          content: payload,
          title: content.title || 'Kautilya Export',
          filename: content.filename
        });
        
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        const ext = kind === 'excel' ? 'xlsx' : kind;
        // Force the export kind's extension. The model's artifact `filename`
        // often carries a wrong extension (e.g. .md), which would otherwise
        // save a real DOCX/PDF/XLSX blob under that wrong name.
        const base = (content.filename || content.title || 'kautilya-export')
          .replace(/\.[a-z0-9]+$/i, '')
          .replace(/[^a-z0-9._-]+/gi, '-');
        a.download = `${base}.${ext}`;
        a.click();
        URL.revokeObjectURL(url);
      } catch (err) {
        console.error("Failed to download binary artifact:", err);
        const ext = kind === 'excel' ? 'json' : (kind === 'csv' ? 'csv' : 'md');
        const filename = content.filename || `${(content.title || 'kautilya-artifact').replace(/[^a-z0-9]/gi, '-').toLowerCase()}.${ext}`;
        const blob = new Blob([content.code], { type: 'text/plain' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        a.click();
        URL.revokeObjectURL(url);
      }
    } else {
      const ext = activeTab === 'code' ? (content.language || 'txt') : 'md';
      const filename = content.filename || `${(content.title || 'kautilya-artifact').replace(/[^a-z0-9]/gi, '-').toLowerCase()}.${ext}`;
      const blob = new Blob([content.code], { type: 'text/plain' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      a.click();
      URL.revokeObjectURL(url);
    }
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

  // Canvas shows ONLY the view that matches what was actually made — no empty
  // "document / dashboard / preview" tabs hanging around to confuse the user.
  // (code artifacts are handled separately via singleCodeFiles → workspace.)
  const docView = (content?.type === 'excel' || content?.type === 'spreadsheet' || content?.type === 'csv')
    ? 'spreadsheet'
    : content?.type === 'dashboard' ? 'dashboard' : 'document';

  return (
    <div className="canvas-pane flex flex-col bg-[var(--k-bg)]" data-testid="canvas-pane">
      {/* Header */}
      <div className="h-14 min-h-[56px] flex items-center justify-between px-4 border-b border-[var(--k-border)] bg-[var(--k-surface)]">
        <div className="flex items-center gap-3 overflow-hidden">
          <div className="w-8 h-8 rounded-lg bg-[var(--k-brand)]/10 flex items-center justify-center text-[var(--k-brand)] flex-shrink-0">
            {isMultiFile ? <FolderOpen className="w-4 h-4" /> : singleCodeFiles ? <Code className="w-4 h-4" /> : docView === 'dashboard' ? <ChartBar className="w-4 h-4" /> : docView === 'spreadsheet' ? <Table className="w-4 h-4" /> : <FileText className="w-4 h-4" />}
          </div>
          <div className="flex flex-col overflow-hidden">
            <span className="text-sm font-semibold truncate text-foreground leading-tight">
              {content?.title || 'Canvas'}
            </span>
            <span className="text-[10px] text-muted-foreground uppercase tracking-widest font-bold">
              {isMultiFile ? `${fileBlocks.length} Files` : singleCodeFiles ? `${content?.language || 'Code'} · Code` : `${docView} View`}
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
      ) : singleCodeFiles ? (
        <div className="flex-1 min-h-0">
          <MultiFileWorkspace files={singleCodeFiles} title={content?.title || 'Code'} />
        </div>
      ) : (
      <Tabs value={docView} className="flex-1 flex flex-col overflow-hidden">
        <TabsContent value="spreadsheet" className="flex-1 overflow-hidden m-0">
          <SpreadsheetView code={content?.code} />
        </TabsContent>

        <TabsContent value="document" className="flex-1 overflow-hidden m-0">
          <ScrollArea className="h-full bg-[#fcfcfc] dark:bg-[#0f1115]">
            <div className="min-h-full p-6 md:p-12 max-w-4xl mx-auto">
              <div className="bg-white dark:bg-[#16181d] shadow-[0_0_50px_rgba(0,0,0,0.04)] dark:shadow-none border border-[var(--k-border)] rounded-lg p-4 sm:p-8 md:p-14 min-h-[800px] overflow-hidden w-full">
                {/* Document Title Bar */}
                <div className="mb-6 sm:mb-10 flex flex-col gap-4 border-b border-[var(--k-border)] pb-4 sm:pb-6">
                  <div>
                    <div className="w-12 h-1 bg-[var(--k-brand)] mb-4" />
                    <div className="text-[10px] uppercase tracking-[0.25em] text-muted-foreground font-bold mb-1">Kautilya Document</div>
                    <h1 className="k-heading text-2xl md:text-3xl font-bold text-foreground">{content?.title || 'Untitled Document'}</h1>
                  </div>
                  <div className="flex gap-2">
                    <button
                      onClick={() => handleDownload('pdf')}
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-[var(--k-border)] bg-[var(--k-surface)] hover:bg-accent text-xs font-semibold text-muted-foreground hover:text-foreground transition-all"
                      title="Download PDF"
                    >
                      <FileText className="w-3.5 h-3.5 text-rose-500" />
                      <span>PDF</span>
                    </button>
                    <button
                      onClick={() => handleDownload('docx')}
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-[var(--k-border)] bg-[var(--k-surface)] hover:bg-accent text-xs font-semibold text-muted-foreground hover:text-foreground transition-all"
                      title="Download Word Document"
                    >
                      <FileText className="w-3.5 h-3.5 text-blue-500" />
                      <span>DOCX</span>
                    </button>
                  </div>
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
                        <ReactMarkdown components={DOC_COMPONENTS} remarkPlugins={[remarkGfm]}>{body}</ReactMarkdown>
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
      </Tabs>
      )}
    </div>
  );
}
