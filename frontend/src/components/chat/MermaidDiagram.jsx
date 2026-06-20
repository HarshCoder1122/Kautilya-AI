import React, { useEffect, useRef, useState, useCallback } from "react";
import { TreeStructure, Copy, Check, Download, ArrowsOutSimple, X, Plus, Minus, ArrowCounterClockwise, Code as CodeIcon } from "@phosphor-icons/react";

/* ──────────────────────────────────────────────────────────────────────────
 * Inline diagram artifacts — Claude-style. A ```mermaid fenced block in an
 * assistant message renders as a live, theme-matched SVG right inside the chat
 * bubble (not the separate Canvas pane). A ```svg block renders sanitised in a
 * locked sandbox iframe. Both support copy-source, download (SVG/PNG) and an
 * expand-to-zoom overlay.
 *
 * Mermaid is loaded lazily (dynamic import → its own webpack chunk) so the
 * ~500KB library never weighs on the initial bundle for the common case of a
 * message with no diagram.
 * ────────────────────────────────────────────────────────────────────────── */

let _mermaidPromise = null;
function loadMermaid() {
  if (!_mermaidPromise) {
    _mermaidPromise = import("mermaid").then((m) => m.default || m);
  }
  return _mermaidPromise;
}

let _renderSeq = 0;

/** Read the active theme's brand/surface colors so diagrams match light/dark. */
function readPalette() {
  let dark = true;
  try {
    const el = document.documentElement;
    if (el.classList.contains("dark")) dark = true;
    else if (el.classList.contains("light")) dark = false;
    else dark = !window.matchMedia || window.matchMedia("(prefers-color-scheme: dark)").matches;
  } catch { /* default dark */ }

  let brand = "#0052FF";
  try {
    const cs = getComputedStyle(document.documentElement);
    brand = (cs.getPropertyValue("--k-brand") || "").trim() || brand;
  } catch { /* keep default */ }

  if (dark) {
    return {
      key: "dark|" + brand,
      themeVariables: {
        fontFamily: 'ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, sans-serif',
        fontSize: "14px",
        background: "transparent",
        primaryColor: "#17191f",
        primaryTextColor: "#E5E7EB",
        primaryBorderColor: brand,
        secondaryColor: "#1f2230",
        tertiaryColor: "#14161b",
        lineColor: "#6B7280",
        textColor: "#D1D5DB",
        mainBkg: "#17191f",
        nodeBorder: brand,
        clusterBkg: "rgba(255,255,255,0.03)",
        clusterBorder: "rgba(255,255,255,0.12)",
        noteBkgColor: "#1f2230",
        noteTextColor: "#E5E7EB",
        actorBkg: "#17191f",
        actorBorder: brand,
        labelBoxBkgColor: "#17191f",
      },
    };
  }
  return {
    key: "light|" + brand,
    themeVariables: {
      fontFamily: 'ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, sans-serif',
      fontSize: "14px",
      background: "transparent",
      primaryColor: "#FFFFFF",
      primaryTextColor: "#111827",
      primaryBorderColor: brand,
      secondaryColor: "#F3F4F6",
      tertiaryColor: "#FAFAFA",
      lineColor: "#9CA3AF",
      textColor: "#1F2937",
      mainBkg: "#FFFFFF",
      nodeBorder: brand,
      noteBkgColor: "#FEF3C7",
      noteTextColor: "#111827",
    },
  };
}

/** Pull intrinsic dimensions out of an SVG string (for PNG raster sizing). */
function svgDimensions(svgString) {
  let w = 0, h = 0;
  const vb = svgString.match(/viewBox=["']\s*([\d.eE+-]+)\s+([\d.eE+-]+)\s+([\d.eE+-]+)\s+([\d.eE+-]+)\s*["']/);
  if (vb) { w = parseFloat(vb[3]); h = parseFloat(vb[4]); }
  const wm = svgString.match(/\bwidth=["']\s*([\d.]+)(px)?\s*["']/);
  const hm = svgString.match(/\bheight=["']\s*([\d.]+)(px)?\s*["']/);
  if (wm) w = parseFloat(wm[1]) || w;
  if (hm) h = parseFloat(hm[1]) || h;
  if (!w || !h) { w = 1200; h = 800; }
  return { w, h };
}

function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function downloadSvg(svgString, title) {
  const safe = (title || "diagram").replace(/[^a-z0-9-_]+/gi, "-").toLowerCase();
  downloadBlob(new Blob([svgString], { type: "image/svg+xml;charset=utf-8" }), `${safe}.svg`);
}

/** Rasterise an SVG string to a PNG blob at `scale`× for crisp downloads. */
function svgToPng(svgString, scale = 2, bg = null) {
  return new Promise((resolve, reject) => {
    const { w, h } = svgDimensions(svgString);
    const blob = new Blob([svgString], { type: "image/svg+xml;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const img = new Image();
    img.onload = () => {
      try {
        const canvas = document.createElement("canvas");
        canvas.width = Math.max(1, Math.round(w * scale));
        canvas.height = Math.max(1, Math.round(h * scale));
        const ctx = canvas.getContext("2d");
        if (bg) { ctx.fillStyle = bg; ctx.fillRect(0, 0, canvas.width, canvas.height); }
        ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
        URL.revokeObjectURL(url);
        canvas.toBlob((b) => (b ? resolve(b) : reject(new Error("toBlob returned null"))), "image/png");
      } catch (e) {
        URL.revokeObjectURL(url);
        reject(e);
      }
    };
    img.onerror = (e) => { URL.revokeObjectURL(url); reject(e); };
    img.src = url;
  });
}

/* ── Zoom / pan overlay shared by both diagram kinds ───────────────────────── */
function ZoomOverlay({ title, children, onClose, onCopy, copied, onDownloadSvg, onDownloadPng }) {
  const [scale, setScale] = useState(1);
  const [pos, setPos] = useState({ x: 0, y: 0 });
  const drag = useRef(null);

  useEffect(() => {
    const onKey = (e) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const zoom = (delta) => setScale((s) => Math.min(6, Math.max(0.3, +(s + delta).toFixed(2))));
  const reset = () => { setScale(1); setPos({ x: 0, y: 0 }); };

  const onWheel = (e) => {
    e.preventDefault();
    setScale((s) => Math.min(6, Math.max(0.3, +(s - e.deltaY * 0.0015).toFixed(3))));
  };
  const onPointerDown = (e) => { drag.current = { x: e.clientX - pos.x, y: e.clientY - pos.y }; };
  const onPointerMove = (e) => {
    if (!drag.current) return;
    setPos({ x: e.clientX - drag.current.x, y: e.clientY - drag.current.y });
  };
  const onPointerUp = () => { drag.current = null; };

  return (
    <div className="fixed inset-0 z-[120] bg-black/90 backdrop-blur-sm flex flex-col" data-testid="diagram-zoom">
      <div className="h-12 flex items-center justify-between px-4 border-b border-white/10 bg-[var(--k-surface)] shrink-0">
        <div className="flex items-center gap-2 min-w-0">
          <TreeStructure className="w-4 h-4 text-[var(--k-brand)] shrink-0" weight="duotone" />
          <span className="text-sm font-bold text-foreground truncate max-w-[40vw]">{title}</span>
        </div>
        <div className="flex items-center gap-1">
          <button onClick={() => zoom(-0.25)} className="p-2 rounded hover:bg-accent text-muted-foreground hover:text-foreground" title="Zoom out"><Minus className="w-4 h-4" /></button>
          <span className="text-[11px] font-mono text-muted-foreground w-12 text-center tabular-nums">{Math.round(scale * 100)}%</span>
          <button onClick={() => zoom(0.25)} className="p-2 rounded hover:bg-accent text-muted-foreground hover:text-foreground" title="Zoom in"><Plus className="w-4 h-4" /></button>
          <button onClick={reset} className="p-2 rounded hover:bg-accent text-muted-foreground hover:text-foreground" title="Reset view"><ArrowCounterClockwise className="w-4 h-4" /></button>
          <div className="w-px h-4 bg-white/10 mx-1" />
          {onCopy && (
            <button onClick={onCopy} className="p-2 rounded hover:bg-accent text-muted-foreground hover:text-foreground" title="Copy source">
              {copied ? <Check className="w-4 h-4 text-emerald-400" /> : <Copy className="w-4 h-4" />}
            </button>
          )}
          {onDownloadSvg && (
            <button onClick={onDownloadSvg} className="px-2.5 py-1.5 rounded hover:bg-accent text-muted-foreground hover:text-foreground text-xs font-semibold" title="Download SVG">SVG</button>
          )}
          {onDownloadPng && (
            <button onClick={onDownloadPng} className="px-2.5 py-1.5 rounded hover:bg-accent text-muted-foreground hover:text-foreground text-xs font-semibold" title="Download PNG">PNG</button>
          )}
          <button onClick={onClose} className="p-2 rounded hover:bg-accent text-muted-foreground hover:text-foreground" title="Close (Esc)"><X className="w-5 h-5" /></button>
        </div>
      </div>
      <div
        className="flex-1 overflow-hidden flex items-center justify-center cursor-grab active:cursor-grabbing"
        onWheel={onWheel}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerLeave={onPointerUp}
      >
        <div style={{ transform: `translate(${pos.x}px, ${pos.y}px) scale(${scale})`, transition: drag.current ? "none" : "transform 0.08s ease-out" }}>
          {children}
        </div>
      </div>
    </div>
  );
}

/* ── Mermaid block ─────────────────────────────────────────────────────────── */
export function MermaidDiagram({ code, streaming = false, title = "Diagram" }) {
  const [svg, setSvg] = useState("");
  const [status, setStatus] = useState("loading"); // loading | ok | error
  const [copied, setCopied] = useState(false);
  const [zoom, setZoom] = useState(false);
  const lastGoodRef = useRef("");
  const paletteKeyRef = useRef(readPalette().key);

  const source = (code || "").trim();

  useEffect(() => {
    let cancelled = false;
    if (!source) { setStatus("loading"); return; }

    const timer = setTimeout(async () => {
      try {
        const mermaid = await loadMermaid();
        const palette = readPalette();
        paletteKeyRef.current = palette.key;
        mermaid.initialize({
          startOnLoad: false,
          securityLevel: "strict", // sanitises labels — model output is untrusted
          theme: "base",
          themeVariables: palette.themeVariables,
          flowchart: { curve: "basis", htmlLabels: false, useMaxWidth: true },
          sequence: { useMaxWidth: true },
          gantt: { useMaxWidth: true },
        });

        // Validate first so partial/streaming syntax doesn't inject error SVGs.
        let valid = false;
        try { valid = await mermaid.parse(source, { suppressErrors: true }); }
        catch { valid = false; }
        if (cancelled) return;
        if (!valid) { setStatus(lastGoodRef.current ? "ok" : "error"); return; }

        const { svg: out } = await mermaid.render(`kmd-${++_renderSeq}`, source);
        if (cancelled) return;
        lastGoodRef.current = out;
        setSvg(out);
        setStatus("ok");
      } catch {
        if (!cancelled) setStatus(lastGoodRef.current ? "ok" : "error");
      }
    }, streaming ? 400 : 120);

    return () => { cancelled = true; clearTimeout(timer); };
  }, [source, streaming]);

  const handleCopy = useCallback(() => {
    navigator.clipboard.writeText(source).catch(() => {});
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }, [source]);

  const handleDownloadSvg = useCallback(() => {
    const out = lastGoodRef.current || svg;
    if (out) downloadSvg(out, title);
  }, [svg, title]);

  const handleDownloadPng = useCallback(async () => {
    const out = lastGoodRef.current || svg;
    if (!out) return;
    try {
      const blob = await svgToPng(out, 2, readPalette().key.startsWith("dark") ? "#0A0A0A" : "#FFFFFF");
      downloadBlob(blob, `${(title || "diagram").replace(/[^a-z0-9-_]+/gi, "-").toLowerCase()}.png`);
    } catch {
      handleDownloadSvg();
    }
  }, [svg, title, handleDownloadSvg]);

  const showSvg = status === "ok" && (svg || lastGoodRef.current);

  return (
    <div className="my-4 rounded-xl overflow-hidden border border-[var(--k-border)] bg-black/20 dark:bg-black/30 w-full max-w-full min-w-0" data-testid="mermaid-diagram">
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2 bg-gradient-to-r from-[var(--k-brand)]/10 via-transparent to-transparent border-b border-white/5">
        <div className="flex items-center gap-2 min-w-0">
          <TreeStructure className="w-4 h-4 text-[var(--k-brand)] shrink-0" weight="duotone" />
          <span className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground">Diagram</span>
          {streaming && status !== "ok" && (
            <span className="text-[10px] text-muted-foreground/60 italic">· rendering…</span>
          )}
        </div>
        {showSvg && (
          <div className="flex items-center gap-1 shrink-0">
            <button onClick={handleCopy} className="p-1.5 rounded hover:bg-white/10 text-muted-foreground hover:text-foreground transition-all" title="Copy diagram source">
              {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
            </button>
            <button onClick={handleDownloadPng} className="p-1.5 rounded hover:bg-white/10 text-muted-foreground hover:text-foreground transition-all" title="Download PNG">
              <Download className="w-3.5 h-3.5" />
            </button>
            <button onClick={() => setZoom(true)} className="p-1.5 rounded hover:bg-white/10 text-muted-foreground hover:text-foreground transition-all" title="Expand & zoom">
              <ArrowsOutSimple className="w-3.5 h-3.5" />
            </button>
          </div>
        )}
      </div>

      {/* Body */}
      <div className="p-4 overflow-x-auto flex justify-center bg-[var(--k-bg)]/40">
        {showSvg ? (
          <div
            className="k-mermaid w-full flex justify-center [&_svg]:max-w-full [&_svg]:h-auto cursor-zoom-in"
            onClick={() => setZoom(true)}
            // eslint-disable-next-line react/no-danger
            dangerouslySetInnerHTML={{ __html: lastGoodRef.current || svg }}
          />
        ) : status === "error" ? (
          <div className="w-full">
            <div className="text-[11px] text-amber-400/80 mb-2 flex items-center gap-1.5">
              <CodeIcon className="w-3.5 h-3.5" /> Couldn't render this diagram — showing source.
            </div>
            <pre className="text-xs font-mono text-foreground/70 whitespace-pre-wrap break-words overflow-x-auto">{source}</pre>
          </div>
        ) : (
          <div className="flex items-center gap-2 py-6 text-xs text-muted-foreground/70 italic">
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-[var(--k-brand)] opacity-60" />
              <span className="relative inline-flex rounded-full h-2 w-2 bg-[var(--k-brand)]" />
            </span>
            Drawing diagram…
          </div>
        )}
      </div>

      {zoom && showSvg && (
        <ZoomOverlay
          title={title}
          onClose={() => setZoom(false)}
          onCopy={handleCopy}
          copied={copied}
          onDownloadSvg={handleDownloadSvg}
          onDownloadPng={handleDownloadPng}
        >
          <div
            className="k-mermaid bg-transparent [&_svg]:h-auto"
            // eslint-disable-next-line react/no-danger
            dangerouslySetInnerHTML={{ __html: lastGoodRef.current || svg }}
          />
        </ZoomOverlay>
      )}
    </div>
  );
}

/* ── Raw SVG block (sandboxed) ─────────────────────────────────────────────── */
export function SvgBlock({ code, title = "Vector graphic" }) {
  const [copied, setCopied] = useState(false);
  const [zoom, setZoom] = useState(false);
  const source = (code || "").trim();

  // Lock the SVG inside a script-less sandbox iframe — model-authored SVG can
  // carry <script>/onload; sandbox="" gives it a unique origin with no script
  // execution, so it renders but can't run anything.
  const doc = `<!doctype html><html><head><meta charset="utf-8"><style>html,body{margin:0;padding:0;background:transparent;display:flex;align-items:center;justify-content:center;min-height:100%}svg{max-width:100%;height:auto}</style></head><body>${source}</body></html>`;

  const handleCopy = () => {
    navigator.clipboard.writeText(source).catch(() => {});
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };
  const handleDownloadSvg = () => downloadSvg(source, title);
  const handleDownloadPng = async () => {
    try {
      const blob = await svgToPng(source, 2);
      downloadBlob(blob, `${(title || "graphic").replace(/[^a-z0-9-_]+/gi, "-").toLowerCase()}.png`);
    } catch {
      handleDownloadSvg();
    }
  };

  if (!source.includes("<svg")) {
    return <pre className="my-2 p-3 bg-accent/20 rounded-lg overflow-x-auto text-xs font-mono whitespace-pre-wrap break-words">{source}</pre>;
  }

  // Size the frame to the illustration's own aspect ratio so custom SVG art
  // renders edge-to-edge (like Claude) instead of inside a fixed box.
  const { w, h } = svgDimensions(source);
  const aspect = Math.max(0.3, Math.min(4, w / h));

  return (
    <div className="my-4 rounded-xl overflow-hidden border border-[var(--k-border)] bg-black/20 dark:bg-black/30 w-full max-w-full min-w-0" data-testid="svg-block">
      <div className="flex items-center justify-between px-3 py-2 bg-gradient-to-r from-[var(--k-brand)]/10 via-transparent to-transparent border-b border-white/5">
        <div className="flex items-center gap-2 min-w-0">
          <TreeStructure className="w-4 h-4 text-[var(--k-brand)] shrink-0" weight="duotone" />
          <span className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground">SVG</span>
        </div>
        <div className="flex items-center gap-1 shrink-0">
          <button onClick={handleCopy} className="p-1.5 rounded hover:bg-white/10 text-muted-foreground hover:text-foreground transition-all" title="Copy SVG source">
            {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
          </button>
          <button onClick={handleDownloadPng} className="p-1.5 rounded hover:bg-white/10 text-muted-foreground hover:text-foreground transition-all" title="Download PNG">
            <Download className="w-3.5 h-3.5" />
          </button>
          <button onClick={() => setZoom(true)} className="p-1.5 rounded hover:bg-white/10 text-muted-foreground hover:text-foreground transition-all" title="Expand">
            <ArrowsOutSimple className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>
      <div className="bg-[var(--k-bg)]/40 p-2 flex justify-center">
        <iframe
          srcDoc={doc}
          sandbox=""
          title={title}
          className="w-full border-none"
          style={{ aspectRatio: String(aspect), maxHeight: "70vh", background: "transparent" }}
        />
      </div>

      {zoom && (
        <ZoomOverlay
          title={title}
          onClose={() => setZoom(false)}
          onCopy={handleCopy}
          copied={copied}
          onDownloadSvg={handleDownloadSvg}
          onDownloadPng={handleDownloadPng}
        >
          <iframe srcDoc={doc} sandbox="" title={`${title} (expanded)`} style={{ width: "80vw", height: "80vh", border: "none", background: "transparent" }} />
        </ZoomOverlay>
      )}
    </div>
  );
}
