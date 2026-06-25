// Deck renderer — turns a Presentation-skill deck spec (JSON) into a single,
// self-contained, gorgeous HTML slideshow. The SAME html is used for the live
// canvas preview (iframe srcDoc), the "Present" fullscreen window, and the
// standalone .html download — so what you see is exactly what you ship. The
// backend (artifact_service.generate_pptx / generate_deck_pdf) renders the same
// spec to PowerPoint / PDF, so every export stays on-theme.
//
// Theme ids here MUST match backend _DECK_THEMES and skills_spec.DECK_THEME_IDS.

export const THEMES = {
  midnight: {
    name: "Midnight", dark: true,
    bg: "#0b1020", surface: "#141a2e", accent: "#6366f1", accent2: "#22d3ee",
    text: "#f8fafc", muted: "#94a3b8",
    mesh: ["#1e1b4b", "#0b1020", "#062a3a"],
    head: "'Plus Jakarta Sans', sans-serif", body: "'Inter', sans-serif",
  },
  aurora: {
    name: "Aurora", dark: true,
    bg: "#160f2e", surface: "#211641", accent: "#ec4899", accent2: "#8b5cf6",
    text: "#fdf4ff", muted: "#c4b5fd",
    mesh: ["#4c1d95", "#160f2e", "#831843"],
    head: "'Plus Jakarta Sans', sans-serif", body: "'Inter', sans-serif",
  },
  noir: {
    name: "Noir", dark: true,
    bg: "#0a0a0a", surface: "#171717", accent: "#fafafa", accent2: "#a3a3a3",
    text: "#fafafa", muted: "#a3a3a3",
    mesh: ["#262626", "#0a0a0a", "#171717"],
    head: "'Space Grotesk', sans-serif", body: "'Inter', sans-serif",
  },
  sunset: {
    name: "Sunset", dark: true,
    bg: "#1a1110", surface: "#2a1a17", accent: "#fb7185", accent2: "#fbbf24",
    text: "#fff7ed", muted: "#fdba74",
    mesh: ["#7c2d12", "#1a1110", "#9f1239"],
    head: "'Plus Jakarta Sans', sans-serif", body: "'Inter', sans-serif",
  },
  emerald: {
    name: "Emerald", dark: true,
    bg: "#052e2b", surface: "#0a3f3a", accent: "#10b981", accent2: "#34d399",
    text: "#ecfdf5", muted: "#6ee7b7",
    mesh: ["#064e3b", "#052e2b", "#134e4a"],
    head: "'Plus Jakarta Sans', sans-serif", body: "'Inter', sans-serif",
  },
  ivory: {
    name: "Ivory", dark: false,
    bg: "#faf9f6", surface: "#ffffff", accent: "#111111", accent2: "#b45309",
    text: "#1c1917", muted: "#78716c",
    mesh: ["#f5f5f4", "#faf9f6", "#fef3c7"],
    head: "'Fraunces', serif", body: "'Inter', sans-serif",
  },
  royal: {
    name: "Royal", dark: true,
    bg: "#1e1b4b", surface: "#2a2563", accent: "#c4b5fd", accent2: "#fcd34d",
    text: "#f5f3ff", muted: "#a5b4fc",
    mesh: ["#312e81", "#1e1b4b", "#4338ca"],
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

// ── Per-layout slide markup ────────────────────────────────────────────────
function renderSlide(slide, i) {
  const L = String(slide.layout || "bullets").toLowerCase();
  const title = slug(slide.title || "");
  const sub = slug(slide.subtitle || "");

  const bullets = (arr) =>
    (arr || []).map((b, j) =>
      `<li style="--d:${0.12 + j * 0.07}s"><span class="dot"></span><span>${slug(b)}</span></li>`).join("");

  if (L === "cover" || L === "closing") {
    const eyebrow = slug(slide.eyebrow || slide.index || (L === "closing" ? "" : ""));
    return `<div class="hero">
      ${eyebrow ? `<div class="eyebrow" style="--d:.05s">${eyebrow}</div>` : ""}
      <div class="accent-bar" style="--d:.1s"></div>
      <h1 class="hero-title" style="--d:.18s">${title || "Untitled"}</h1>
      ${sub ? `<p class="hero-sub" style="--d:.3s">${sub}</p>` : ""}
      ${slide.footer ? `<div class="hero-foot" style="--d:.42s">${slug(slide.footer)}</div>` : ""}
    </div>`;
  }
  if (L === "section") {
    return `<div class="hero section">
      <div class="sec-index" style="--d:.05s">${slug(slide.index || String(i).padStart(2, "0"))}</div>
      <h1 class="hero-title" style="--d:.18s">${title}</h1>
      ${sub ? `<p class="hero-sub" style="--d:.3s">${sub}</p>` : ""}
    </div>`;
  }

  const header = `<header class="s-head">
      <div class="s-bar"></div>
      <div>
        ${sub ? `<div class="s-kicker">${sub}</div>` : ""}
        <h2 class="s-title">${title}</h2>
      </div>
    </header>`;

  if (L === "two-column") {
    const cols = (slide.columns || []).slice(0, 3).map((c, j) =>
      `<div class="col glass" style="--d:${0.15 + j * 0.1}s">
        <h3>${slug(c.heading || "")}</h3>
        <ul class="blist">${bullets(c.bullets)}</ul>
      </div>`).join("");
    return `${header}<div class="cols cols-${Math.min((slide.columns || []).length, 3)}">${cols}</div>`;
  }
  if (L === "stats") {
    const cards = (slide.stats || []).slice(0, 4).map((st, j) =>
      `<div class="stat glass" style="--d:${0.15 + j * 0.1}s">
        <div class="stat-v">${slug(st.value || "")}</div>
        <div class="stat-l">${slug(st.label || "")}</div>
      </div>`).join("");
    return `${header}<div class="stats stats-${Math.min((slide.stats || []).length || 1, 4)}">${cards}</div>`;
  }
  if (L === "timeline") {
    const items = (slide.items || []).slice(0, 6).map((it, j) =>
      `<li class="tl-item" style="--d:${0.15 + j * 0.09}s">
        <div class="tl-node"></div>
        <div class="tl-time">${slug(it.time || "")}</div>
        <div class="tl-text">${slug(it.text || "")}</div>
      </li>`).join("");
    return `${header}<ul class="timeline">${items}</ul>`;
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
      ? `<div class="img-frame glass" style="--d:.15s"><img loading="lazy" src="${esc(slide.image)}" alt="${title}"/></div>`
      : `<div class="img-frame glass placeholder" style="--d:.15s"></div>`;
    const side = (slide.bullets && slide.bullets.length)
      ? `<div class="img-side"><ul class="blist">${bullets(slide.bullets)}</ul></div>` : "";
    return `${header}<div class="image-layout ${side ? "split" : "full"}">
      ${img}${side}
    </div>${slide.caption ? `<div class="caption">${slug(slide.caption)}</div>` : ""}`;
  }
  // default: bullets
  const list = slide.bullets && slide.bullets.length
    ? `<ul class="blist big">${bullets(slide.bullets)}</ul>`
    : slide.note ? `<p class="s-note">${slug(slide.note)}</p>` : "";
  return `${header}<div class="bullets-layout">${list}</div>`;
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
  const aspect = data.aspect === "4:3" ? "4 / 3" : "16 / 9";
  const slides = (data.slides || []).slice(0, DECK_MAX_SLIDES).map((s, i) => {
    const L = String(s.layout || "bullets").toLowerCase();
    const centered = ["cover", "closing", "section", "quote"].includes(L);
    return `<section class="slide${centered ? " center" : ""}" data-layout="${esc(L)}" aria-label="Slide ${i + 1}">
      <div class="slide-inner">${renderSlide(s, i + 1)}</div>
    </section>`;
  }).join("\n");

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
  body{background:var(--bg);color:var(--text);font-family:var(--body);overflow:hidden;
    -webkit-font-smoothing:antialiased;display:flex;align-items:center;justify-content:center}
  /* Stage scales the fixed-aspect deck to fit any container */
  .stage{position:relative;width:100vw;height:100vh;display:flex;align-items:center;justify-content:center;
    ${depth === "3d" ? "perspective:2200px;" : ""}}
  .deck{position:relative;width:min(100vw, calc(100vh * 16 / 9));aspect-ratio:${aspect};
    max-height:100vh;max-width:100vw;overflow:hidden;border-radius:8px;isolation:isolate;
    background:
      radial-gradient(130% 130% at 10% 6%, ${t.mesh[0]} 0%, transparent 46%),
      radial-gradient(120% 120% at 94% 98%, ${t.mesh[2]} 0%, transparent 52%),
      var(--bg);}
  /* Animated ambient field behind the slides (premium, slow-drifting orbs) */
  .ambient{position:absolute;inset:-20%;z-index:0;pointer-events:none;filter:blur(46px) saturate(135%);opacity:${t.dark ? ".7" : ".5"}}
  .orb{position:absolute;border-radius:50%;mix-blend-mode:${t.dark ? "screen" : "multiply"};will-change:transform}
  .orb.a{width:46%;aspect-ratio:1;left:-6%;top:-8%;background:radial-gradient(circle at 30% 30%, var(--accent), transparent 65%);animation:drift1 18s ease-in-out infinite}
  .orb.b{width:52%;aspect-ratio:1;right:-10%;bottom:-12%;background:radial-gradient(circle at 60% 40%, var(--accent2), transparent 64%);animation:drift2 22s ease-in-out infinite}
  .orb.c{width:34%;aspect-ratio:1;left:38%;top:30%;background:radial-gradient(circle at 50% 50%, ${t.mesh[0]}, transparent 62%);animation:drift3 26s ease-in-out infinite}
  @keyframes drift1{0%,100%{transform:translate(0,0) scale(1)}50%{transform:translate(10%,8%) scale(1.12)}}
  @keyframes drift2{0%,100%{transform:translate(0,0) scale(1)}50%{transform:translate(-9%,-7%) scale(1.08)}}
  @keyframes drift3{0%,100%{transform:translate(0,0) scale(1)}50%{transform:translate(6%,-9%) scale(.92)}}
  /* Fine grain + vignette for depth */
  .deck::after{content:"";position:absolute;inset:0;z-index:5;pointer-events:none;
    box-shadow:inset 0 0 180px ${t.dark ? "rgba(0,0,0,.55)" : "rgba(0,0,0,.08)"};
    background-image:radial-gradient(${t.dark ? "rgba(255,255,255,.018)" : "rgba(0,0,0,.015)"} 1px, transparent 1px);background-size:3px 3px}
  .slide{position:absolute;inset:0;padding:6.2% 7%;display:flex;flex-direction:column;justify-content:center;z-index:1;
    opacity:0;visibility:hidden;transform:translateX(7%) rotateY(-9deg) scale(.96);transform-origin:left center;
    transition:opacity .55s ease, transform .7s cubic-bezier(.16,.84,.28,1), visibility .7s;
    ${depth === "3d" ? "transform-style:preserve-3d;backface-visibility:hidden;" : ""}}
  .slide.center{align-items:flex-start}
  .slide.active{opacity:1;visibility:visible;transform:none;z-index:3}
  .slide.prev{transform:translateX(-7%) rotateY(9deg) scale(.96);transform-origin:right center}
  .slide-inner{width:100%;height:100%;display:flex;flex-direction:column;justify-content:center;position:relative;
    ${depth === "3d" ? "transform-style:preserve-3d;" : ""}}
  /* Entrance choreography for children (each carries a --d delay) */
  .slide.active [style*="--d"]{animation:rise .7s both;animation-delay:var(--d)}
  @keyframes rise{from{opacity:0;transform:translateY(22px)${depth === "3d" ? " translateZ(-40px)" : ""}}to{opacity:1;transform:none}}
  ${depth === "3d" ? `.slide.active .glass,.slide.active .img-frame{transform:translateZ(28px)}
  .slide.active .s-head{transform:translateZ(46px)} .slide.active .hero-title{transform:translateZ(60px)}` : ""}

  /* Hero / cover / closing / section */
  .hero{max-width:88%}
  .eyebrow,.sec-index{font-family:var(--head);font-weight:700;letter-spacing:.22em;text-transform:uppercase;
    font-size:clamp(11px,1.3vw,15px);color:var(--accent2);margin-bottom:1.4em}
  .sec-index{font-size:clamp(34px,6vw,64px);-webkit-text-stroke:1.5px var(--accent2);color:transparent;letter-spacing:0;margin-bottom:.2em}
  .accent-bar{width:64px;height:6px;border-radius:6px;background:linear-gradient(90deg,var(--accent),var(--accent2));margin-bottom:1.1em}
  .hero-title{font-family:var(--head);font-weight:800;line-height:1.02;letter-spacing:-.02em;
    font-size:clamp(34px,6.4vw,76px);background:linear-gradient(180deg,var(--text),var(--text) 60%, ${t.dark ? "var(--muted)" : "var(--accent2)"});
    -webkit-background-clip:text;background-clip:text;-webkit-text-fill-color:transparent}
  .hero-sub{margin-top:.7em;font-size:clamp(16px,2vw,26px);color:var(--muted);max-width:34ch;line-height:1.5}
  .hero-foot{margin-top:2.2em;font-size:clamp(12px,1.3vw,16px);color:var(--muted);letter-spacing:.04em}

  /* Content header */
  .s-head{display:flex;align-items:flex-start;gap:18px;margin-bottom:4.2%}
  .s-bar{flex:none;width:10px;height:clamp(30px,4vw,48px);border-radius:6px;
    background:linear-gradient(180deg,var(--accent),var(--accent2));margin-top:6px}
  .s-kicker{font-family:var(--head);font-weight:700;letter-spacing:.18em;text-transform:uppercase;
    font-size:clamp(10px,1.1vw,13px);color:var(--accent2);margin-bottom:.5em}
  .s-title{font-family:var(--head);font-weight:800;letter-spacing:-.015em;line-height:1.05;
    font-size:clamp(24px,3.8vw,46px)}

  .glass{background:${t.dark ? "rgba(255,255,255,.05)" : "rgba(17,17,17,.035)"};
    border:1px solid ${t.dark ? "rgba(255,255,255,.09)" : "rgba(17,17,17,.08)"};
    border-radius:18px;backdrop-filter:blur(6px);
    ${depth === "3d" ? `box-shadow:0 24px 60px -28px ${t.dark ? "rgba(0,0,0,.7)" : "rgba(0,0,0,.18)"}, inset 0 1px 0 ${t.dark ? "rgba(255,255,255,.06)" : "rgba(255,255,255,.6)"};` : ""}}

  /* Bullets */
  .blist{list-style:none;display:flex;flex-direction:column;gap:.85em}
  .blist.big{gap:1.05em}
  .blist li{display:flex;align-items:flex-start;gap:.7em;font-size:clamp(15px,1.9vw,24px);line-height:1.4;color:var(--text)}
  .blist.big li{font-size:clamp(16px,2.2vw,27px)}
  .blist .dot{flex:none;width:.62em;height:.62em;margin-top:.5em;border-radius:50%;
    background:linear-gradient(135deg,var(--accent),var(--accent2));box-shadow:0 0 0 4px ${t.dark ? "rgba(255,255,255,.05)" : "rgba(17,17,17,.04)"}}
  .bullets-layout{flex:1;display:flex;flex-direction:column;justify-content:center}

  /* Columns */
  .cols{flex:1;display:grid;gap:22px;align-content:center}
  .cols-2{grid-template-columns:1fr 1fr}.cols-3{grid-template-columns:1fr 1fr 1fr}
  .col{padding:26px 26px}
  .col h3{font-family:var(--head);font-size:clamp(16px,2vw,24px);font-weight:700;margin-bottom:.8em;color:var(--accent2)}
  .col .blist li{font-size:clamp(13px,1.5vw,19px)}

  /* Stats */
  .stats{flex:1;display:grid;gap:20px;align-content:center}
  .stats-1{grid-template-columns:1fr}.stats-2{grid-template-columns:1fr 1fr}
  .stats-3{grid-template-columns:repeat(3,1fr)}.stats-4{grid-template-columns:repeat(4,1fr)}
  .stat{padding:30px 18px;text-align:center}
  .stat-v{font-family:var(--head);font-weight:800;font-size:clamp(30px,5vw,58px);line-height:1;
    background:linear-gradient(135deg,var(--accent),var(--accent2));-webkit-background-clip:text;background-clip:text;-webkit-text-fill-color:transparent}
  .stat-l{margin-top:.6em;font-size:clamp(12px,1.4vw,17px);color:var(--muted)}

  /* Timeline */
  .timeline{list-style:none;flex:1;display:flex;flex-direction:column;justify-content:center;gap:1.1em;position:relative;padding-left:8px}
  .tl-item{position:relative;display:grid;grid-template-columns:auto 1fr;gap:.3em 1em;padding-left:24px}
  .tl-item::before{content:"";position:absolute;left:5px;top:14px;bottom:-1.1em;width:2px;background:${t.dark ? "rgba(255,255,255,.14)" : "rgba(17,17,17,.12)"}}
  .tl-item:last-child::before{display:none}
  .tl-node{position:absolute;left:0;top:6px;width:12px;height:12px;border-radius:50%;background:var(--accent);box-shadow:0 0 0 4px ${t.dark ? "rgba(99,102,241,.18)" : "rgba(17,17,17,.06)"}}
  .tl-time{grid-column:2;font-family:var(--head);font-weight:700;color:var(--accent2);font-size:clamp(13px,1.5vw,19px)}
  .tl-text{grid-column:2;font-size:clamp(14px,1.7vw,22px);color:var(--text)}

  /* Quote */
  .quote-wrap{max-width:84%}
  .qmark{font-family:var(--head);font-size:clamp(60px,10vw,120px);line-height:.6;color:var(--accent);opacity:.45}
  .quote{font-family:var(--head);font-weight:700;font-size:clamp(24px,4vw,48px);line-height:1.18;letter-spacing:-.01em;margin-top:.1em}
  .qauthor{margin-top:1em;color:var(--accent2);font-size:clamp(14px,1.7vw,22px);font-weight:600}

  /* Image */
  .image-layout{flex:1;display:flex;gap:26px;min-height:0}
  .image-layout.full .img-frame{flex:1}
  .image-layout.split .img-frame{flex:1.15}.image-layout.split .img-side{flex:1;display:flex;align-items:center}
  .img-frame{overflow:hidden;border-radius:18px;min-height:0}
  .img-frame img{width:100%;height:100%;object-fit:cover;display:block}
  .img-frame.placeholder{background:linear-gradient(135deg,var(--surface),${t.mesh[0]})}
  .caption{margin-top:.8em;font-size:clamp(11px,1.2vw,14px);color:var(--muted)}
  .s-note{font-size:clamp(16px,2.1vw,26px);color:var(--muted);line-height:1.5;max-width:40ch}

  /* Chrome: progress + dots + counter */
  .progress{position:fixed;top:0;left:0;height:3px;background:linear-gradient(90deg,var(--accent),var(--accent2));z-index:30;transition:width .4s ease}
  .dots{position:fixed;bottom:16px;left:50%;transform:translateX(-50%);display:flex;gap:8px;z-index:30}
  .dots button{width:8px;height:8px;border-radius:50%;border:none;cursor:pointer;padding:0;
    background:${t.dark ? "rgba(255,255,255,.28)" : "rgba(17,17,17,.22)"};transition:all .25s}
  .dots button.on{width:22px;border-radius:5px;background:var(--accent)}
  .counter{position:fixed;bottom:14px;right:18px;font-size:12px;color:var(--muted);z-index:30;font-variant-numeric:tabular-nums}
  .nav{position:fixed;top:0;bottom:0;width:18%;z-index:20;cursor:pointer;border:none;background:transparent}
  .nav.left{left:0}.nav.right{right:0}
  @media (prefers-reduced-motion: reduce){.slide,.slide.active [style*="--d"],.orb{transition:none!important;animation:none!important}}
</style></head>
<body>
  <div class="progress" id="progress"></div>
  <div class="stage"><div class="deck" id="deck">
    <div class="ambient"><span class="orb a"></span><span class="orb b"></span><span class="orb c"></span></div>
    ${slides || '<section class="slide active center"><div class="slide-inner"><div class="hero"><h1 class="hero-title">Empty deck</h1></div></div></section>'}
  </div></div>
  <button class="nav left" id="navL" aria-label="Previous"></button>
  <button class="nav right" id="navR" aria-label="Next"></button>
  <div class="dots" id="dots"></div>
  <div class="counter" id="counter"></div>
<script>
  (function(){
    var slides=[].slice.call(document.querySelectorAll('.slide'));
    var n=slides.length, cur=0;
    var dots=document.getElementById('dots');
    slides.forEach(function(_,i){var b=document.createElement('button');b.onclick=function(){go(i)};dots.appendChild(b)});
    var dotEls=[].slice.call(dots.children);
    function go(i){
      cur=Math.max(0,Math.min(n-1,i));
      slides.forEach(function(s,j){s.classList.remove('active','prev');if(j===cur)s.classList.add('active');else if(j<cur)s.classList.add('prev')});
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
      else if((e.key==='f'||e.key==='F')&&document.documentElement.requestFullscreen){
        if(document.fullscreenElement)document.exitFullscreen();else document.documentElement.requestFullscreen();
      }
    });
    // message API so the React canvas can drive nav / fullscreen from its toolbar
    window.addEventListener('message',function(e){
      var d=e.data||{};
      if(d.deckCmd==='next')go(cur+1); else if(d.deckCmd==='prev')go(cur-1);
      else if(d.deckCmd==='go')go(d.index|0);
      else if(d.deckCmd==='fullscreen'&&document.documentElement.requestFullscreen)document.documentElement.requestFullscreen();
    });
    go(0);
  })();
</script>
</body></html>`;
}
