// Deck renderer — turns a Presentation-skill deck spec (JSON) into a single,
// self-contained, gorgeous HTML slideshow. The SAME html is used for the live
// canvas preview (iframe srcDoc), the "Present" fullscreen window, and the
// standalone .html download — so what you see is exactly what you ship. The
// backend (artifact_service.generate_pptx / generate_deck_pdf) renders the same
// spec to PowerPoint / PDF, so every export stays on-theme.
//
// FIT MODEL: slides are laid out on a FIXED 1280×720 (16:9) / 960×720 (4:3)
// canvas in px, then the whole deck is uniformly scaled (transform: scale) to
// fit its container. This is how Keynote / reveal.js guarantee that content
// never clips and that every screen size shows an identical, perfectly-fit
// slide — replacing the old viewport-relative sizing that overflowed.
//
// Theme ids here MUST match backend _DECK_THEMES and skills_spec.DECK_THEME_IDS.

export const THEMES = {
  midnight: {
    name: "Midnight", dark: true,
    bg: "#0b1020", surface: "#141a2e", accent: "#7c83ff", accent2: "#22d3ee",
    text: "#f8fafc", muted: "#9aa6c4",
    mesh: ["#1e2a6b", "#0b1020", "#0a3550"],
    head: "'Plus Jakarta Sans', sans-serif", body: "'Inter', sans-serif",
  },
  aurora: {
    name: "Aurora", dark: true,
    bg: "#150f2c", surface: "#221645", accent: "#f472b6", accent2: "#a78bfa",
    text: "#fdf4ff", muted: "#cabdf0",
    mesh: ["#5b21b6", "#150f2c", "#9d174d"],
    head: "'Plus Jakarta Sans', sans-serif", body: "'Inter', sans-serif",
  },
  noir: {
    name: "Noir", dark: true,
    bg: "#0b0b0c", surface: "#191919", accent: "#f5f5f5", accent2: "#9ca3af",
    text: "#f7f7f7", muted: "#a3a3a3",
    mesh: ["#2a2a2c", "#0b0b0c", "#1a1a1c"],
    head: "'Space Grotesk', sans-serif", body: "'Inter', sans-serif",
  },
  sunset: {
    name: "Sunset", dark: true,
    bg: "#1a100f", surface: "#2c1a16", accent: "#fb7185", accent2: "#fbbf24",
    text: "#fff7ed", muted: "#fcc89b",
    mesh: ["#9a3412", "#1a100f", "#9f1239"],
    head: "'Plus Jakarta Sans', sans-serif", body: "'Inter', sans-serif",
  },
  emerald: {
    name: "Emerald", dark: true,
    bg: "#04302c", surface: "#0a443e", accent: "#34d399", accent2: "#5eead4",
    text: "#ecfdf5", muted: "#86efc5",
    mesh: ["#065f46", "#04302c", "#0f766e"],
    head: "'Plus Jakarta Sans', sans-serif", body: "'Inter', sans-serif",
  },
  ivory: {
    name: "Ivory", dark: false,
    bg: "#f7f5f0", surface: "#ffffff", accent: "#1a1a1a", accent2: "#b45309",
    text: "#1c1917", muted: "#6b6256",
    mesh: ["#efe9dc", "#fbfaf6", "#fdebc8"],
    head: "'Fraunces', serif", body: "'Inter', sans-serif",
  },
  royal: {
    name: "Royal", dark: true,
    bg: "#1c1840", surface: "#2a235e", accent: "#c4b5fd", accent2: "#fcd34d",
    text: "#f5f3ff", muted: "#b3a8e6",
    mesh: ["#3730a3", "#1c1840", "#4f46e5"],
    head: "'Fraunces', serif", body: "'Inter', sans-serif",
  },
};

export const THEME_IDS = Object.keys(THEMES);

// Hard ceiling on slides — the user configures the count, but a deck stays a
// visual aid (matches DECK_MAX_SLIDES in backend/services/artifact_service.py).
export const DECK_MAX_SLIDES = 20;

/** Tolerant parse of a deck artifact body → spec object (or null). */
export function parseDeck(code) {
  if (!code) return null;
  if (typeof code === "object") return code.slides ? code : null;
  let s = String(code).trim().replace(/^```[a-zA-Z]*\s*/, "").replace(/\s*```$/, "");
  let data;
  try {
    data = JSON.parse(s);
  } catch {
    const a = s.indexOf("{"), b = s.lastIndexOf("}");
    if (a < 0 || b <= a) return null;
    try { data = JSON.parse(s.slice(a, b + 1)); } catch { return null; }
  }
  if (!data || typeof data !== "object" || !Array.isArray(data.slides) || !data.slides.length) return null;
  return data;
}

const esc = (v) =>
  String(v == null ? "" : v)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");

const slug = (v) => esc(v).replace(/&quot;/g, '"');

// Inline SVG icon set (stroke, currentColor) so `feature` cards look designed
// — no icon-font dependency, works in the standalone HTML download too.
const ICONS = {
  bolt: '<path d="M13 2 3 14h9l-1 8 10-12h-9l1-8z"/>',
  chart: '<path d="M3 3v18h18"/><path d="M7 14l3-3 3 3 4-5"/>',
  shield: '<path d="M12 3l8 3v5c0 5-3.5 8-8 10-4.5-2-8-5-8-10V6l8-3z"/>',
  star: '<path d="M12 3l2.9 6 6.6.9-4.8 4.6 1.2 6.5L12 18l-5.9 3 1.2-6.5L2.5 9.9 9.1 9 12 3z"/>',
  rocket: '<path d="M5 16c-1.5 1.3-2 5-2 5s3.7-.5 5-2"/><path d="M12 15l-3-3c1-4 4-8 11-9 0 7-5 10-9 11z"/><circle cx="14.5" cy="9.5" r="1.4"/>',
  check: '<path d="M4 12l5 5L20 6"/>',
  gear: '<circle cx="12" cy="12" r="3.2"/><path d="M19 12a7 7 0 0 0-.1-1.4l2-1.5-2-3.4-2.3 1a7 7 0 0 0-2.4-1.4L13.8 2h-3.6l-.4 2.3a7 7 0 0 0-2.4 1.4l-2.3-1-2 3.4 2 1.5A7 7 0 0 0 5 12c0 .5 0 1 .1 1.4l-2 1.5 2 3.4 2.3-1a7 7 0 0 0 2.4 1.4l.4 2.3h3.6l.4-2.3a7 7 0 0 0 2.4-1.4l2.3 1 2-3.4-2-1.5z"/>',
  globe: '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c2.5 3 2.5 15 0 18M12 3c-2.5 3-2.5 15 0 18"/>',
  chat: '<path d="M21 12a8 8 0 0 1-11.5 7.2L3 21l1.8-6.5A8 8 0 1 1 21 12z"/>',
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  users: '<circle cx="9" cy="8" r="3.4"/><path d="M2 20c0-3.5 3-6 7-6s7 2.5 7 6"/><path d="M16 5a3.4 3.4 0 0 1 0 6.4M22 20c0-2.4-1.5-4.4-4-5.2"/>',
  target: '<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><circle cx="12" cy="12" r="1.4"/>',
  spark: '<path d="M12 3v6M12 15v6M3 12h6M15 12h6"/><path d="M12 8.5l1.3 2.2 2.2 1.3-2.2 1.3L12 15.5l-1.3-2.2L8.5 12l2.2-1.3z"/>',
  lock: '<rect x="5" y="11" width="14" height="9" rx="2"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/>',
  lightbulb: '<path d="M9 18h6M10 22h4"/><path d="M12 2a7 7 0 0 0-4 12.7c.6.5 1 1.3 1 2.1h6c0-.8.4-1.6 1-2.1A7 7 0 0 0 12 2z"/>',
  dollar: '<path d="M12 2v20"/><path d="M17 6c0-2-2-3-5-3s-5 1-5 3.5S9 10 12 10s5 1 5 3.5S15 17 12 17s-5-1-5-3"/>',
  phone: '<path d="M5 3h3l2 5-2.5 1.5a12 12 0 0 0 6 6L17 13l5 2v3a2 2 0 0 1-2 2A17 17 0 0 1 3 5a2 2 0 0 1 2-2z"/>',
  mail: '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="M3 7l9 6 9-6"/>',
  trophy: '<path d="M8 4h8v4a4 4 0 0 1-8 0V4z"/><path d="M8 6H5a2 2 0 0 0 0 4h1M16 6h3a2 2 0 0 1 0 4h-1M10 14h4v3h-4zM8 20h8"/>',
};
const ICON_ALIAS = {
  zap: 'bolt', lightning: 'bolt', power: 'bolt', graph: 'chart', analytics: 'chart', data: 'chart',
  security: 'shield', secure: 'shield', launch: 'rocket', growth: 'rocket', done: 'check', success: 'check',
  settings: 'gear', config: 'gear', automation: 'gear', world: 'globe', global: 'globe', message: 'chat',
  support: 'chat', voice: 'chat', time: 'clock', speed: 'clock', team: 'users', people: 'users',
  customer: 'users', goal: 'target', precision: 'target', idea: 'lightbulb', innovation: 'lightbulb',
  money: 'dollar', revenue: 'dollar', price: 'dollar', roi: 'dollar', call: 'phone', email: 'mail',
  award: 'trophy', win: 'trophy', quality: 'trophy', ai: 'spark', magic: 'spark',
};
function iconSvg(name) {
  let k = String(name || '').toLowerCase().trim();
  k = ICONS[k] ? k : (ICON_ALIAS[k] || 'spark');
  return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">${ICONS[k] || ICONS.spark}</svg>`;
}

// Resolve a slide's `image` into a real, reliable URL. A full http(s) URL is
// used as-is; ANYTHING ELSE is treated as a visual description and rendered to
// an AI-GENERATED image (Gamma-style) — so the model never has to know real
// photo IDs (which it hallucinates → broken images). Deterministic seed keeps
// the same description → same image across preview + export.
function imageUrl(v) {
  const s = String(v || '').trim();
  if (!s) return '';
  if (/^https?:\/\//i.test(s)) return s;
  let seed = 0;
  for (let i = 0; i < s.length; i++) seed = ((seed << 5) - seed + s.charCodeAt(i)) | 0;
  return `https://image.pollinations.ai/prompt/${encodeURIComponent(s)}?width=1280&height=768&nologo=true&seed=${Math.abs(seed)}`;
}

// ── Per-layout slide markup ────────────────────────────────────────────────
function renderSlide(slide, i) {
  const L = String(slide.layout || "bullets").toLowerCase();
  const title = slug(slide.title || "");
  const sub = slug(slide.subtitle || "");

  // Auto-tighten when there's a lot of content so nothing clips on the fixed
  // canvas (the `dense` class drops font sizes a notch in CSS).
  const bulletCount = (slide.bullets || []).length;
  const dense = bulletCount >= 6 ? " dense" : "";

  const bullets = (arr, max) =>
    (arr || []).slice(0, max).map((b, j) =>
      `<li style="--d:${0.1 + j * 0.06}s"><span class="dot"></span><span>${slug(b)}</span></li>`).join("");

  if (L === "cover" || L === "closing" || L === "section") {
    const isSection = L === "section";
    const eyebrow = slug(slide.eyebrow || slide.index || "");
    const heroText = isSection
      ? `<div class="sec-index" style="--d:.05s">${slug(slide.index || String(i).padStart(2, "0"))}</div>
         <h1 class="hero-title" style="--d:.18s">${title}</h1>
         ${sub ? `<p class="hero-sub" style="--d:.3s">${sub}</p>` : ""}`
      : `${eyebrow ? `<div class="eyebrow" style="--d:.05s">${eyebrow}</div>` : ""}
         <div class="accent-bar" style="--d:.1s"></div>
         <h1 class="hero-title" style="--d:.18s">${title || "Untitled"}</h1>
         ${sub ? `<p class="hero-sub" style="--d:.3s">${sub}</p>` : ""}
         ${slide.footer ? `<div class="hero-foot" style="--d:.42s">${slug(slide.footer)}</div>` : ""}`;
    // Hero IMAGE → editorial split (text left on gradient, full-bleed image right).
    if (slide.image) {
      return `<div class="cover-grid">
        <div class="hero on-grid">${heroText}</div>
        <div class="cover-img" style="--d:.12s"><img loading="lazy" src="${esc(imageUrl(slide.image))}" alt=""/></div>
      </div>`;
    }
    // No image → richer decorative hero (rings + glow already in the deck bg).
    return `<div class="hero-deco" aria-hidden="true"><span class="ring"></span><span class="ring r2"></span></div>
      <div class="hero${isSection ? " section" : ""}">${heroText}</div>`;
  }

  const header = `<header class="s-head">
      <div class="s-bar"></div>
      <div class="s-head-text">
        ${sub ? `<div class="s-kicker">${sub}</div>` : ""}
        <h2 class="s-title">${title}</h2>
      </div>
    </header>`;

  if (L === "two-column") {
    const cols = (slide.columns || []).slice(0, 3);
    const cl = cols.map((c, j) =>
      `<div class="col glass" style="--d:${0.15 + j * 0.1}s">
        <h3>${slug(c.heading || "")}</h3>
        <ul class="blist">${bullets(c.bullets, 6)}</ul>
      </div>`).join("");
    return `${header}<div class="body cols cols-${Math.max(cols.length, 1)}">${cl}</div>`;
  }
  if (L === "stats") {
    const st = (slide.stats || []).slice(0, 4);
    const cards = st.map((s, j) =>
      `<div class="stat glass" style="--d:${0.15 + j * 0.1}s">
        <div class="stat-v">${slug(s.value || "")}</div>
        <div class="stat-l">${slug(s.label || "")}</div>
      </div>`).join("");
    return `${header}<div class="body stats stats-${Math.max(st.length, 1)}">${cards}</div>`;
  }
  if (L === "timeline") {
    const items = (slide.items || []).slice(0, 6).map((it, j) =>
      `<li class="tl-item" style="--d:${0.13 + j * 0.08}s">
        <div class="tl-node"></div>
        <div class="tl-time">${slug(it.time || "")}</div>
        <div class="tl-text">${slug(it.text || "")}</div>
      </li>`).join("");
    return `${header}<div class="body"><ul class="timeline">${items}</ul></div>`;
  }
  if (L === "quote") {
    return `<div class="quote-wrap">
      <div class="qmark" style="--d:.05s">&ldquo;</div>
      <blockquote class="quote" style="--d:.18s">${slug(slide.quote || "")}</blockquote>
      ${slide.author ? `<div class="qauthor" style="--d:.32s">— ${slug(slide.author)}</div>` : ""}
    </div>`;
  }
  if (L === "image") {
    const img = slide.image
      ? `<div class="img-frame glass" style="--d:.15s"><img loading="lazy" src="${esc(imageUrl(slide.image))}" alt="${title}"/></div>`
      : `<div class="img-frame glass placeholder" style="--d:.15s"></div>`;
    const side = (slide.bullets && slide.bullets.length)
      ? `<div class="img-side"><ul class="blist">${bullets(slide.bullets, 6)}</ul></div>` : "";
    return `${header}<div class="body image-layout ${side ? "split" : "full"}">
      ${img}${side}
    </div>${slide.caption ? `<div class="caption">${slug(slide.caption)}</div>` : ""}`;
  }
  if (L === "feature" || L === "features" || L === "icons" || L === "cards") {
    const items = (slide.features || slide.items || slide.cards || []).slice(0, 4);
    const cards = items.map((f, j) =>
      `<div class="feat glass" style="--d:${0.14 + j * 0.09}s">
        <div class="feat-ico">${iconSvg(f.icon)}</div>
        <h4>${slug(f.title || "")}</h4>
        ${f.text ? `<p>${slug(f.text)}</p>` : ""}
      </div>`).join("");
    return `${header}<div class="body feats feats-${Math.max(Math.min(items.length, 4), 1)}">${cards}</div>`;
  }
  if (L === "process" || L === "steps") {
    const steps = (slide.steps || []).slice(0, 5);
    const parts = [];
    steps.forEach((st, j) => {
      parts.push(`<div class="proc-card glass" style="--d:${0.15 + j * 0.1}s">
        <div class="proc-num">${j + 1}</div>
        <h4>${slug(st.title || "")}</h4>
        <p>${slug(st.text || "")}</p>
      </div>`);
      if (j < steps.length - 1) parts.push(`<div class="proc-arrow" style="--d:${0.2 + j * 0.1}s">&rarr;</div>`);
    });
    return `${header}<div class="body proc">${parts.join("")}</div>`;
  }
  if (L === "chart" || L === "bar" || L === "bars") {
    const ch = slide.chart || slide;
    const rows = (ch.data || ch.bars || []).slice(0, 7);
    const max = Math.max(1, ...rows.map((d) => Number(d.value) || 0));
    const bars = rows.map((d, j) => {
      const h = Math.round(((Number(d.value) || 0) / max) * 72) + 4;
      return `<div class="bar-col" style="--d:${0.12 + j * 0.08}s">
        <div class="bar-val">${slug(d.value)}</div>
        <div class="bar" style="height:${h}%"></div>
        <div class="bar-lbl">${slug(d.label || "")}</div>
      </div>`;
    }).join("");
    return `${header}<div class="body chart"><div class="bars">${bars}</div></div>`;
  }

  // default: bullets
  const list = bulletCount
    ? `<ul class="blist big${dense}">${bullets(slide.bullets, 8)}</ul>`
    : slide.note ? `<p class="s-note">${slug(slide.note)}</p>` : "";
  return `${header}<div class="body bullets-layout">${list}</div>`;
}

/**
 * Render the full deck as a standalone HTML document string.
 * @param {object} spec   deck spec ({title, theme, depth, aspect, slides})
 * @param {object} opts   { theme, depth } overrides (canvas theme switcher)
 */
export function renderDeckHTML(spec, opts = {}) {
  const data = parseDeck(spec) || { slides: [] };
  const themeId = THEMES[opts.theme] ? opts.theme : (THEMES[data.theme] ? data.theme : "midnight");
  const t = THEMES[themeId];
  const depth = (opts.depth || data.depth || "3d") === "flat" ? "flat" : "3d";
  const is43 = data.aspect === "4:3";
  const BW = is43 ? 960 : 1280, BH = 720;

  const slides = (data.slides || []).slice(0, DECK_MAX_SLIDES).map((s, i) => {
    const L = String(s.layout || "bullets").toLowerCase();
    const centered = ["cover", "closing", "section", "quote"].includes(L);
    return `<section class="slide${centered ? " center" : ""}" data-layout="${esc(L)}" aria-label="Slide ${i + 1}">
      <div class="slide-inner">${renderSlide(s, i + 1)}</div>
    </section>`;
  }).join("\n");

  // soft, NotebookLM-grade ambient: layered glows + faint grain (no harsh blobs)
  const grain = "data:image/svg+xml;base64," + btoa(
    `<svg xmlns='http://www.w3.org/2000/svg' width='160' height='160'><filter id='n'><feTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='2'/></filter><rect width='100%' height='100%' filter='url(%23n)' opacity='${t.dark ? 0.5 : 0.35}'/></svg>`
      .replace(/%23/g, "#")
  );

  return `<!doctype html><html lang="en"><head>
<meta charset="utf-8"/><meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>${slug(data.title || "Presentation")}</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Plus+Jakarta+Sans:wght@500;600;700;800&family=Space+Grotesk:wght@500;600;700&family=Fraunces:opsz,wght@9..144,500;9..144,600;9..144,700&display=swap" rel="stylesheet">
<style>
  :root{
    --bg:${t.bg};--surface:${t.surface};--accent:${t.accent};--accent2:${t.accent2};
    --text:${t.text};--muted:${t.muted};--head:${t.head};--body:${t.body};
  }
  *{box-sizing:border-box;margin:0;padding:0}
  html,body{height:100%}
  body{background:${t.dark ? "#08080b" : "#e9e6df"};color:var(--text);font-family:var(--body);overflow:hidden;-webkit-font-smoothing:antialiased}
  .viewport{position:fixed;inset:0;overflow:hidden;display:flex;align-items:center;justify-content:center}
  /* Fixed-size design canvas, scaled to fit via JS. Everything inside is px. */
  .deck{position:absolute;left:50%;top:50%;width:${BW}px;height:${BH}px;transform-origin:center center;
    border-radius:16px;overflow:hidden;isolation:isolate;
    box-shadow:0 40px 120px -30px rgba(0,0,0,.65);
    background:
      radial-gradient(70% 60% at 12% 4%, ${t.mesh[0]} 0%, transparent 60%),
      radial-gradient(70% 70% at 100% 102%, ${t.mesh[2]} 0%, transparent 60%),
      linear-gradient(155deg, ${t.bg} 0%, ${t.surface} 165%);}
  /* Ambient glows — soft, editorial, gently floating */
  .ambient{position:absolute;inset:0;z-index:0;pointer-events:none;overflow:hidden}
  .glow{position:absolute;border-radius:50%;filter:blur(72px);opacity:${t.dark ? ".5" : ".42"};mix-blend-mode:${t.dark ? "screen" : "multiply"};will-change:transform}
  .glow.g1{width:620px;height:620px;left:-150px;top:-190px;background:radial-gradient(circle,var(--accent),transparent 70%);animation:float1 22s ease-in-out infinite}
  .glow.g2{width:720px;height:720px;right:-200px;bottom:-240px;background:radial-gradient(circle,var(--accent2),transparent 70%);animation:float2 27s ease-in-out infinite}
  .glow.g3{width:420px;height:420px;left:42%;top:34%;background:radial-gradient(circle,${t.mesh[0]},transparent 68%);opacity:${t.dark ? ".4" : ".3"};animation:float3 30s ease-in-out infinite}
  @keyframes float1{0%,100%{transform:translate(0,0)}50%{transform:translate(40px,32px)}}
  @keyframes float2{0%,100%{transform:translate(0,0)}50%{transform:translate(-36px,-28px)}}
  @keyframes float3{0%,100%{transform:translate(0,0) scale(1)}50%{transform:translate(24px,-30px) scale(1.08)}}
  .grain{position:absolute;inset:0;z-index:6;pointer-events:none;opacity:${t.dark ? ".05" : ".04"};
    background-image:url("${grain}");background-size:240px}
  .vignette{position:absolute;inset:0;z-index:5;pointer-events:none;box-shadow:inset 0 0 200px ${t.dark ? "rgba(0,0,0,.5)" : "rgba(120,110,90,.12)"}}

  .slide{position:absolute;inset:0;padding:56px 72px;display:flex;flex-direction:column;justify-content:center;z-index:1;
    opacity:0;visibility:hidden;transform:translateY(26px) scale(.992);
    transition:opacity .5s ease, transform .6s cubic-bezier(.16,.84,.3,1), visibility .6s;
    ${depth === "3d" ? "perspective:1700px;" : ""}}
  .slide.center{justify-content:center}
  .slide.active{opacity:1;visibility:visible;transform:none;z-index:3}
  .slide-inner{width:100%;height:100%;display:flex;flex-direction:column;justify-content:center;overflow:hidden;
    ${depth === "3d" ? "transform-style:preserve-3d;" : ""}}
  .slide.active [style*="--d"]{animation:rise .65s both;animation-delay:var(--d)}
  @keyframes rise{from{opacity:0;transform:translateY(18px)}to{opacity:1;transform:none}}
  ${depth === "3d" ? `.slide.active .glass,.slide.active .img-frame{transform:translateZ(26px)}
  .slide.active .s-head{transform:translateZ(40px)} .slide.active .hero-title{transform:translateZ(54px)}` : ""}

  /* Hero / cover / closing / section */
  .hero{max-width:80%}
  .eyebrow{font-family:var(--head);font-weight:700;letter-spacing:.24em;text-transform:uppercase;font-size:15px;color:var(--accent2);margin-bottom:22px}
  .sec-index{font-family:var(--head);font-weight:800;font-size:84px;line-height:1;-webkit-text-stroke:2px var(--accent2);color:transparent;margin-bottom:6px}
  .accent-bar{width:72px;height:7px;border-radius:7px;background:linear-gradient(90deg,var(--accent),var(--accent2));margin-bottom:24px}
  .hero-title{font-family:var(--head);font-weight:800;line-height:1.03;letter-spacing:-.02em;font-size:66px;
    background:linear-gradient(180deg,var(--text) 35%, ${t.dark ? "var(--muted)" : "var(--accent2)"});-webkit-background-clip:text;background-clip:text;-webkit-text-fill-color:transparent}
  .section .hero-title{font-size:54px}
  .hero-sub{margin-top:18px;font-size:25px;color:var(--muted);max-width:24ch;line-height:1.45}
  .hero-foot{margin-top:42px;font-size:16px;color:var(--muted);letter-spacing:.04em}
  /* Hero image split (editorial cover) */
  .cover-grid{display:grid;grid-template-columns:1.05fr .95fr;gap:50px;height:100%;align-items:center}
  .cover-grid .hero{max-width:none}
  .cover-img{position:relative;height:calc(100% + 112px);margin:-56px -72px -56px 0;overflow:hidden;
    background:linear-gradient(135deg, ${t.surface}, ${t.mesh[0]})}
  .cover-img img{width:100%;height:100%;object-fit:cover}
  .cover-img::before{content:"";position:absolute;inset:0;z-index:1;
    background:linear-gradient(90deg, ${t.bg} 0%, ${t.bg}cc 14%, transparent 40%)}
  .cover-img::after{content:"";position:absolute;inset:0;z-index:1;box-shadow:inset 0 0 120px ${t.dark ? "rgba(0,0,0,.5)" : "rgba(0,0,0,.12)"}}
  /* Decorative rings for image-less hero */
  .hero-deco{position:absolute;inset:0;z-index:0;pointer-events:none;overflow:hidden}
  .hero-deco .ring{position:absolute;right:-130px;top:-150px;width:540px;height:540px;border-radius:50%;border:1.5px solid ${t.dark ? "rgba(255,255,255,.07)" : "rgba(28,25,23,.07)"}}
  .hero-deco .ring.r2{right:-30px;top:-30px;width:360px;height:360px;border-color:${t.accent}33}
  /* Feature / icon cards */
  .feats{display:grid;gap:20px;align-content:center}
  .feats-1{grid-template-columns:1fr}.feats-2{grid-template-columns:1fr 1fr}.feats-3{grid-template-columns:repeat(3,1fr)}.feats-4{grid-template-columns:1fr 1fr}
  .feat{padding:26px 24px;display:flex;flex-direction:column;gap:13px}
  .feat-ico{width:54px;height:54px;border-radius:15px;display:flex;align-items:center;justify-content:center;color:var(--accent);
    background:${t.dark ? "rgba(255,255,255,.06)" : "rgba(28,25,23,.05)"};border:1px solid ${t.accent}40}
  .feat-ico svg{width:28px;height:28px}
  .feat h4{font-family:var(--head);font-weight:700;font-size:22px;line-height:1.2}
  .feat p{font-size:16px;color:var(--muted);line-height:1.4}

  /* Content header + body region (body gets the leftover height, no overflow) */
  .s-head{display:flex;align-items:flex-start;gap:18px;flex:none;margin-bottom:30px}
  .s-bar{flex:none;width:10px;height:44px;border-radius:6px;background:linear-gradient(180deg,var(--accent),var(--accent2));margin-top:4px}
  .s-head-text{min-width:0}
  .s-kicker{font-family:var(--head);font-weight:700;letter-spacing:.18em;text-transform:uppercase;font-size:13px;color:var(--accent2);margin-bottom:6px}
  .s-title{font-family:var(--head);font-weight:800;letter-spacing:-.015em;line-height:1.06;font-size:40px}
  .body{flex:1;min-height:0;display:flex;flex-direction:column;justify-content:center;overflow:hidden}

  .glass{background:${t.dark ? "rgba(255,255,255,.055)" : "rgba(28,25,23,.04)"};
    border:1px solid ${t.dark ? "rgba(255,255,255,.1)" : "rgba(28,25,23,.09)"};
    border-radius:18px;backdrop-filter:blur(8px);
    box-shadow:0 22px 50px -26px ${t.dark ? "rgba(0,0,0,.7)" : "rgba(0,0,0,.16)"}, inset 0 1px 0 ${t.dark ? "rgba(255,255,255,.07)" : "rgba(255,255,255,.7)"}}

  /* Bullets */
  .blist{list-style:none;display:flex;flex-direction:column;gap:16px}
  .blist.big{gap:18px}.blist.big.dense{gap:13px}
  .blist li{display:flex;align-items:flex-start;gap:14px;font-size:23px;line-height:1.4;color:var(--text)}
  .blist.big li{font-size:25px}.blist.big.dense li{font-size:21px}
  .blist .dot{flex:none;width:11px;height:11px;margin-top:9px;border-radius:50%;
    background:linear-gradient(135deg,var(--accent),var(--accent2));box-shadow:0 0 0 4px ${t.dark ? "rgba(255,255,255,.06)" : "rgba(28,25,23,.05)"}}
  .bullets-layout{justify-content:center}
  .s-note{font-size:25px;color:var(--muted);line-height:1.5;max-width:42ch}

  /* Columns */
  .cols{display:grid;gap:22px;align-content:center;grid-auto-rows:minmax(0,1fr)}
  .cols-1{grid-template-columns:1fr}.cols-2{grid-template-columns:1fr 1fr}.cols-3{grid-template-columns:1fr 1fr 1fr}
  .col{padding:26px;overflow:hidden}
  .col h3{font-family:var(--head);font-size:23px;font-weight:700;margin-bottom:16px;color:var(--accent2)}
  .col .blist{gap:12px}.col .blist li{font-size:18px;line-height:1.35}

  /* Stats */
  .stats{display:grid;gap:22px;align-content:center}
  .stats-1{grid-template-columns:1fr}.stats-2{grid-template-columns:1fr 1fr}.stats-3{grid-template-columns:repeat(3,1fr)}.stats-4{grid-template-columns:repeat(4,1fr)}
  .stat{padding:34px 18px;text-align:center;display:flex;flex-direction:column;justify-content:center;gap:10px}
  .stat-v{font-family:var(--head);font-weight:800;font-size:58px;line-height:1;background:linear-gradient(135deg,var(--accent),var(--accent2));-webkit-background-clip:text;background-clip:text;-webkit-text-fill-color:transparent}
  .stat-l{font-size:17px;color:var(--muted)}

  /* Timeline */
  .timeline{list-style:none;display:flex;flex-direction:column;justify-content:center;gap:18px;height:100%}
  .tl-item{position:relative;display:grid;grid-template-columns:1fr;gap:4px;padding-left:30px}
  .tl-item::before{content:"";position:absolute;left:6px;top:18px;bottom:-18px;width:2px;background:${t.dark ? "rgba(255,255,255,.16)" : "rgba(28,25,23,.14)"}}
  .tl-item:last-child::before{display:none}
  .tl-node{position:absolute;left:0;top:6px;width:14px;height:14px;border-radius:50%;background:var(--accent);box-shadow:0 0 0 5px ${t.dark ? "rgba(124,131,255,.18)" : "rgba(28,25,23,.06)"}}
  .tl-time{font-family:var(--head);font-weight:700;color:var(--accent2);font-size:19px}
  .tl-text{font-size:22px;color:var(--text);line-height:1.35}

  /* Process / steps diagram */
  .proc{flex-direction:row;align-items:stretch;gap:12px}
  .proc-card{flex:1;display:flex;flex-direction:column;gap:12px;padding:26px 22px;min-width:0}
  .proc-num{width:46px;height:46px;border-radius:13px;background:linear-gradient(135deg,var(--accent),var(--accent2));
    color:${t.dark ? "#0b0b12" : "#fff"};display:flex;align-items:center;justify-content:center;font-family:var(--head);font-weight:800;font-size:21px}
  .proc-card h4{font-family:var(--head);font-weight:700;font-size:21px;line-height:1.2}
  .proc-card p{font-size:16px;color:var(--muted);line-height:1.4}
  .proc-arrow{flex:none;display:flex;align-items:center;color:var(--accent);font-size:34px;font-weight:300}

  /* Bar chart */
  .chart{justify-content:flex-end}
  .bars{display:flex;align-items:flex-end;justify-content:space-around;gap:20px;height:100%;padding-top:24px}
  .bar-col{flex:1;max-width:130px;height:100%;display:flex;flex-direction:column;align-items:center;justify-content:flex-end;gap:10px}
  .bar-val{font-family:var(--head);font-weight:700;font-size:19px;color:var(--accent2)}
  .bar{width:100%;border-radius:10px 10px 4px 4px;background:linear-gradient(180deg,var(--accent),var(--accent2));min-height:8px;
    box-shadow:0 0 36px -8px var(--accent), inset 0 1px 0 rgba(255,255,255,.25)}
  .bar-lbl{font-size:15px;color:var(--muted);text-align:center;line-height:1.25}

  /* Quote */
  .quote-wrap{max-width:82%}
  .qmark{font-family:var(--head);font-size:120px;line-height:.5;color:var(--accent);opacity:.4}
  .quote{font-family:var(--head);font-weight:700;font-size:44px;line-height:1.2;letter-spacing:-.01em;margin-top:6px}
  .qauthor{margin-top:22px;color:var(--accent2);font-size:21px;font-weight:600}

  /* Image */
  .image-layout{display:flex;gap:28px}
  .image-layout.full .img-frame{flex:1}
  .image-layout.split .img-frame{flex:1.15}.image-layout.split .img-side{flex:1;display:flex;align-items:center}
  .img-frame{overflow:hidden;border-radius:18px;min-height:0}
  .img-frame img{width:100%;height:100%;object-fit:cover;display:block}
  .img-frame.placeholder{background:linear-gradient(135deg,var(--surface),${t.mesh[0]})}
  .caption{flex:none;margin-top:14px;font-size:14px;color:var(--muted)}

  /* Chrome */
  .progress{position:fixed;top:0;left:0;height:3px;background:linear-gradient(90deg,var(--accent),var(--accent2));z-index:40;transition:width .4s ease}
  .dots{position:fixed;bottom:16px;left:50%;transform:translateX(-50%);display:flex;gap:8px;z-index:40}
  .dots button{width:8px;height:8px;border-radius:50%;border:none;cursor:pointer;padding:0;background:${t.dark ? "rgba(255,255,255,.3)" : "rgba(28,25,23,.25)"};transition:all .25s}
  .dots button.on{width:22px;border-radius:5px;background:var(--accent)}
  .counter{position:fixed;bottom:14px;right:18px;font-size:12px;color:${t.dark ? "rgba(255,255,255,.55)" : "rgba(28,25,23,.5)"};z-index:40;font-variant-numeric:tabular-nums}
  .nav{position:fixed;top:0;bottom:0;width:16%;z-index:30;cursor:pointer;border:none;background:transparent}
  .nav.left{left:0}.nav.right{right:0}
  @media (prefers-reduced-motion: reduce){.slide,.slide.active [style*="--d"],.glow{transition:none!important;animation:none!important}}
</style></head>
<body>
  <div class="progress" id="progress"></div>
  <div class="viewport"><div class="deck" id="deck">
    <div class="ambient"><span class="glow g1"></span><span class="glow g2"></span><span class="glow g3"></span></div>
    <div class="vignette"></div><div class="grain"></div>
    ${slides || '<section class="slide active center"><div class="slide-inner"><div class="hero"><h1 class="hero-title">Empty deck</h1></div></div></section>'}
  </div></div>
  <button class="nav left" id="navL" aria-label="Previous"></button>
  <button class="nav right" id="navR" aria-label="Next"></button>
  <div class="dots" id="dots"></div>
  <div class="counter" id="counter"></div>
<script>
  (function(){
    var BW=${BW}, BH=${BH};
    var deck=document.getElementById('deck');
    function fit(){
      var s=Math.min(window.innerWidth/BW, window.innerHeight/BH);
      deck.style.transform='translate(-50%,-50%) scale('+s+')';
    }
    window.addEventListener('resize', fit); fit();

    var slides=[].slice.call(document.querySelectorAll('.slide'));
    var n=slides.length, cur=0;
    var dots=document.getElementById('dots');
    slides.forEach(function(_,i){var b=document.createElement('button');b.onclick=function(){go(i)};dots.appendChild(b)});
    var dotEls=[].slice.call(dots.children);
    function go(i){
      cur=Math.max(0,Math.min(n-1,i));
      slides.forEach(function(s,j){s.classList.toggle('active',j===cur)});
      dotEls.forEach(function(d,j){d.className=j===cur?'on':''});
      document.getElementById('progress').style.width=((cur+1)/n*100)+'%';
      document.getElementById('counter').textContent=(cur+1)+' / '+n;
    }
    document.getElementById('navL').onclick=function(){go(cur-1)};
    document.getElementById('navR').onclick=function(){go(cur+1)};
    window.addEventListener('keydown',function(e){
      if(e.key==='ArrowRight'||e.key==='PageDown'||e.key===' '){e.preventDefault();go(cur+1)}
      else if(e.key==='ArrowLeft'||e.key==='PageUp'){e.preventDefault();go(cur-1)}
      else if(e.key==='Home'){go(0)} else if(e.key==='End'){go(n-1)}
      else if(e.key==='f'||e.key==='F'){if(document.fullscreenElement)document.exitFullscreen();else if(document.documentElement.requestFullscreen)document.documentElement.requestFullscreen();}
    });
    window.addEventListener('message',function(e){
      var d=e.data||{};
      if(d.deckCmd==='next')go(cur+1); else if(d.deckCmd==='prev')go(cur-1);
      else if(d.deckCmd==='go')go(d.index|0);
      else if(d.deckCmd==='fullscreen'){if(document.documentElement.requestFullscreen)document.documentElement.requestFullscreen();}
    });
    go(0);
  })();
</script>
</body></html>`;
}
