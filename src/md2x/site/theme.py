"""The shared `blocks`-mode engine: one design-system stylesheet and one
interaction script, emitted as `assets/site.css` + `assets/site.js`.

Why a module of its own: `blocks_render.py` owns the block→DOM mapping; this file
owns the *look and behaviour* that mapping rides on. Splitting them keeps each file
focused and lets the whole engine be asserted in isolation.

`SITE_CSS` is a semantic token layer over the per-page `--ds-*` tokens (so the
accent/density/fonts a site picks still drive everything), plus refined typography,
depth, the component design system, animation primitives, and dark mode. `SITE_JS`
is one dependency-free IIFE built from small named state functions around a
`createStore` primitive — reduced-motion aware and defensive so a single feature
failing never blanks the page. Both are self-contained: no network, no CDN.
"""
from __future__ import annotations

# --- the design system + animation primitives -------------------------------
# Semantic vars resolve from the page's inline --ds-* tokens (with sane fallbacks),
# so one shared stylesheet themes every site. Dark mode overrides the *semantic*
# vars AND the neutral --ds-* tokens (bg/fg/muted/card/border): authored-section
# CSS is bound by the css_contract to the --ds-* tokens, so flipping them is what
# makes authored sections follow dark mode instead of staying light. --ds-accent
# (brand) and the type/space/radius scales (layout) deliberately do NOT flip.
SITE_CSS = """\
:root{
  --accent: var(--ds-accent,#2563eb);
  --accent-press: var(--ds-accent,#2563eb);
  --bg: var(--ds-bg,#ffffff);
  --fg: var(--ds-fg,#0f172a);
  --muted: var(--ds-muted,#64748b);
  --card: var(--ds-card,#f8fafc);
  --border: var(--ds-border,#e6e8ec);
  --radius: var(--ds-radius,14px);
  --font: var(--ds-font-sans,-apple-system,BlinkMacSystemFont,"Segoe UI",Inter,Helvetica,Arial,sans-serif);
  --mono: var(--ds-font-mono,ui-monospace,SFMono-Regular,"SF Mono",Menlo,Consolas,monospace);
  --accent-soft: color-mix(in srgb, var(--accent) 10%, transparent);
  --accent-line: color-mix(in srgb, var(--accent) 22%, transparent);
  --ring: color-mix(in srgb, var(--accent) 32%, transparent);
  --surface: color-mix(in srgb, var(--card) 60%, var(--bg));
  --shadow-sm: 0 1px 2px rgba(15,23,42,.04), 0 1px 3px rgba(15,23,42,.05);
  --shadow-md: 0 6px 14px -6px rgba(15,23,42,.12), 0 10px 30px -12px rgba(15,23,42,.10);
  --shadow-lg: 0 18px 40px -12px rgba(15,23,42,.22);
  --maxw: 760px;
  --ease: cubic-bezier(.2,.7,.2,1);
}
@media (prefers-color-scheme: dark){
  :root:not([data-theme="light"]){
    --bg:#0b0f17; --fg:#e8edf4; --muted:#93a0b4; --card:#141a24; --border:#222b38;
    --surface:#10151e;
    /* flip the neutral contract tokens too, so authored-section CSS themes */
    --ds-bg:#0b0f17; --ds-fg:#e8edf4; --ds-muted:#93a0b4; --ds-card:#141a24; --ds-border:#222b38;
    --shadow-md: 0 8px 18px -8px rgba(0,0,0,.5), 0 12px 36px -14px rgba(0,0,0,.5);
    --shadow-lg: 0 22px 48px -14px rgba(0,0,0,.6);
  }
}
[data-theme="dark"]{
  --bg:#0b0f17; --fg:#e8edf4; --muted:#93a0b4; --card:#141a24; --border:#222b38;
  --surface:#10151e;
  --ds-bg:#0b0f17; --ds-fg:#e8edf4; --ds-muted:#93a0b4; --ds-card:#141a24; --ds-border:#222b38;
  --shadow-md: 0 8px 18px -8px rgba(0,0,0,.5), 0 12px 36px -14px rgba(0,0,0,.5);
  --shadow-lg: 0 22px 48px -14px rgba(0,0,0,.6);
}

*{box-sizing:border-box}
html{scroll-behavior:smooth}
@media (prefers-reduced-motion: reduce){html{scroll-behavior:auto}}
body{margin:0;background:var(--bg);color:var(--fg);font-family:var(--font);
  font-size:17px;line-height:1.7;-webkit-font-smoothing:antialiased;
  text-rendering:optimizeLegibility;font-feature-settings:"kern","liga";}
h1,h2,h3,h4{line-height:1.18;letter-spacing:-.021em;font-weight:680;color:var(--fg)}
a{color:var(--accent);text-decoration:none}
a:hover{text-decoration:underline}
p{margin:0 0 1em}
hr{border:0;border-top:1px solid var(--border);margin:2em 0}
::selection{background:var(--accent-soft)}
:focus-visible{outline:2px solid var(--ring);outline-offset:2px;border-radius:6px}

/* --- chrome: reading progress + theme toggle (JS-injected) --------------- */
.md2x-progress{position:fixed;top:0;left:0;right:0;height:3px;background:var(--accent);
  transform:scaleX(0);transform-origin:0 50%;z-index:50;
  transition:transform .12s linear;will-change:transform}
.md2x-themetoggle{position:fixed;right:18px;bottom:18px;z-index:50;
  display:inline-flex;align-items:center;gap:6px;padding:8px 13px;font:inherit;
  font-size:.82rem;font-weight:600;color:var(--fg);cursor:pointer;
  background:var(--card);border:1px solid var(--border);border-radius:999px;
  box-shadow:var(--shadow-md);transition:transform .15s var(--ease),border-color .15s}
.md2x-themetoggle:hover{transform:translateY(-1px);border-color:var(--accent)}

/* --- layout (sidebar shell) --------------------------------------------- */
.layout{display:flex;min-height:100vh;gap:0}
nav.side{width:264px;flex:0 0 264px;border-right:1px solid var(--border);
  padding:30px 18px;position:sticky;top:0;height:100vh;overflow:auto;
  background:linear-gradient(180deg,var(--surface),var(--bg))}
nav.side::-webkit-scrollbar{width:8px}
nav.side::-webkit-scrollbar-thumb{background:var(--border);border-radius:8px}
nav.side a{display:block;color:var(--fg);text-decoration:none;padding:6px 10px;
  border-radius:8px;transition:background .15s,color .15s}
nav.side a:hover{background:var(--accent-soft);color:var(--accent);text-decoration:none}
nav.side .group{color:var(--muted);font-size:11px;text-transform:uppercase;
  letter-spacing:.09em;font-weight:700;margin:18px 10px 6px}
main{flex:1;width:100%;max-width:calc(var(--maxw) + 64px);margin:0 auto;
  padding:64px 32px 120px;display:flex;flex-direction:column;gap:var(--ds-space-4,2.4rem)}
main>*{margin:0}
@media (max-width:780px){
  .layout{flex-direction:column}
  nav.side{width:auto;flex:none;height:auto;position:static;border-right:0;
    border-bottom:1px solid var(--border)}
  main{padding:36px 22px 90px}
}

/* --- enhancement aids (TL;DR / takeaways / related) ---------------------- */
.tldr{background:var(--accent-soft);border:1px solid var(--accent-line);
  padding:14px 18px;border-radius:var(--radius);margin:0 0 28px;font-size:.97rem}
.takeaways{background:var(--surface);border:1px solid var(--border);
  border-radius:var(--radius);padding:14px 22px;margin:24px 0}
.related a{color:var(--accent)}

/* --- reveal animation (gated on html.js so no-JS stays visible) ---------- */
html.js [data-reveal]{opacity:0;transform:translateY(18px);
  transition:opacity .6s var(--ease),transform .6s var(--ease);
  transition-delay:calc(var(--i,0) * 65ms)}
html.js [data-reveal].in{opacity:1;transform:none}
@media (prefers-reduced-motion: reduce){
  html.js [data-reveal]{opacity:1;transform:none;transition:none}
}

/* --- blocks: shared rhythm ---------------------------------------------- */
/* one consistent vertical rhythm: sections/main are flex columns with `gap`,
   so every block is evenly spaced regardless of type — no per-block margins to
   drift out of sync. */
.b-section>*{margin:0}
.b-prose>:first-child{margin-top:0}
.b-prose>:last-child{margin-bottom:0}
.b-prose img{border-radius:var(--radius)}
.b-prose h2{margin-top:1.6em;font-size:1.4rem}
.b-prose h3{margin-top:1.4em;font-size:1.13rem}
.b-prose pre{background:var(--card);border:1px solid var(--border);
  border-radius:var(--radius);padding:14px 16px;overflow:auto}
.b-prose code{background:var(--accent-soft);padding:.12em .36em;border-radius:5px;
  font-family:var(--mono);font-size:.9em}
.b-prose pre code{background:none;padding:0}
.b-prose table{width:100%;border-collapse:collapse;border:1px solid var(--border);
  border-radius:var(--radius);overflow:hidden;font-size:.95rem}
.b-prose th,.b-prose td{padding:9px 13px;border-bottom:1px solid var(--border);text-align:left}
.b-prose thead th{background:var(--surface)}
.b-prose blockquote{margin:1.2em 0;padding:.4em 1.1em;border-left:3px solid var(--accent);
  color:var(--muted)}

/* authored sections: the AI authors raw semantic HTML + a little scoped accent
   CSS; the engine supplies the polished base styling so every authored section is
   on-brand and consistent (not bare), no matter what the model emitted. */
.b-authored{font-size:1.02rem;line-height:1.65}
.b-authored p{margin:0;color:var(--fg)}
.b-authored h3{font-size:1.16rem;margin:0;letter-spacing:-.01em}
.b-authored h4{font-size:.95rem;margin:0;color:var(--muted);
  text-transform:uppercase;letter-spacing:.06em}
.b-authored ul,.b-authored ol{margin:0;padding-left:1.2em;display:flex;
  flex-direction:column;gap:.4rem}
.b-authored a{color:var(--accent);text-decoration:none;
  border-bottom:1px solid var(--accent-line)}
.b-authored strong{font-weight:700}
.b-authored code{background:var(--accent-soft);padding:.12em .36em;border-radius:5px;
  font-family:var(--mono);font-size:.9em}
.b-authored blockquote{margin:0;padding:.4em 1.1em;border-left:3px solid var(--accent);
  color:var(--muted)}
.b-authored img{max-width:100%;height:auto;border-radius:var(--radius)}
.b-authored figure{margin:0}
/* common layout helpers an author may reach for */
.b-authored .grid{display:grid;gap:var(--ds-space-2,1rem);
  grid-template-columns:repeat(auto-fit,minmax(180px,1fr))}
.b-authored .cards{display:grid;gap:var(--ds-space-2,1rem);
  grid-template-columns:repeat(auto-fit,minmax(220px,1fr))}
.b-authored .card{border:1px solid var(--border);border-radius:var(--radius);
  padding:16px;background:var(--card)}

/* hero */
.b-hero{margin:0}
.b-hero h1{font-size:clamp(2rem,4.6vw,3rem);margin:.12em 0 .2em;letter-spacing:-.03em}
.b-hero h1::after{content:"";display:block;width:54px;height:4px;margin-top:.5rem;
  border-radius:4px;background:var(--accent)}
.b-kicker{text-transform:uppercase;letter-spacing:.15em;font-size:.72rem;
  font-weight:800;color:var(--accent)}
.b-sub{color:var(--muted);font-size:1.2rem;line-height:1.5;margin:.1em 0 0;max-width:48ch}
.b-label{text-transform:uppercase;letter-spacing:.1em;font-size:.67rem;font-weight:800;
  color:var(--accent);margin-bottom:7px}

/* section */
.b-section{scroll-margin-top:20px;display:flex;flex-direction:column;
  gap:var(--ds-space-3,1.7rem)}
.b-section-h{font-size:1.55rem;margin:0;padding-left:14px;
  position:relative;letter-spacing:-.02em}
.b-section-h::before{content:"";position:absolute;left:0;top:.14em;bottom:.14em;
  width:4px;border-radius:4px;background:var(--accent)}

/* summary + callout */
.b-summary{font-size:1.18rem;line-height:1.55;color:var(--fg);font-weight:450;
  padding:0 0 0 16px;border-left:3px solid var(--accent)}
.b-callout{background:var(--accent-soft);border:1px solid var(--accent-line);
  border-radius:var(--radius);padding:14px 18px}
.b-callout.tone-warn{background:color-mix(in srgb,#d29922 12%,transparent);
  border-color:color-mix(in srgb,#d29922 40%,transparent)}
.b-callout.tone-warn .b-label{color:#b8860b}
.b-callout.tone-success{background:color-mix(in srgb,#2da44e 12%,transparent);
  border-color:color-mix(in srgb,#2da44e 40%,transparent)}
.b-callout.tone-success .b-label{color:#1a7f37}

/* kpi */
.b-kpi{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:14px}
.b-kpi-card{background:var(--card);border:1px solid var(--border);
  border-radius:var(--radius);padding:18px 18px 16px;box-shadow:var(--shadow-sm);
  transition:transform .18s var(--ease),box-shadow .18s var(--ease),border-color .18s}
.b-kpi-card:hover{transform:translateY(-3px);box-shadow:var(--shadow-md);border-color:var(--accent-line)}
.b-kpi-card .v{font-size:2.1rem;font-weight:760;color:var(--accent);line-height:1.05;
  letter-spacing:-.03em;font-variant-numeric:tabular-nums}
.b-kpi-card .l{color:var(--muted);font-size:.86rem;margin-top:6px}

/* cards */
.b-cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(210px,1fr));gap:16px}
.b-card{display:block;background:var(--card);border:1px solid var(--border);
  border-radius:var(--radius);padding:18px;color:inherit;text-decoration:none;
  box-shadow:var(--shadow-sm);transition:transform .18s var(--ease),box-shadow .18s var(--ease),border-color .18s}
.b-card h3{margin:0 0 .35em;font-size:1.05rem}
.b-card p{margin:0;color:var(--muted);font-size:.92rem}
a.b-card:hover{transform:translateY(-3px);box-shadow:var(--shadow-md);
  border-color:var(--accent);text-decoration:none}

/* timeline */
.b-timeline{list-style:none;padding:0;margin-left:9px;border-left:2px solid var(--border)}
.b-ev{position:relative;padding:0 0 22px 24px}
.b-ev::before{content:"";position:absolute;left:-7px;top:5px;width:12px;height:12px;
  border-radius:50%;background:var(--accent);box-shadow:0 0 0 4px var(--accent-soft)}
.b-ev .when{font-size:.78rem;color:var(--muted);font-weight:600;letter-spacing:.02em}
.b-ev .t{font-weight:660;margin-top:1px}
.b-ev .d{color:var(--muted);font-size:.95rem}

/* table */
.b-tablewrap{border:1px solid var(--border);border-radius:var(--radius);
  overflow:auto;box-shadow:var(--shadow-sm)}
.b-table{width:100%;border-collapse:collapse}
.b-table th,.b-table td{padding:11px 15px;border-bottom:1px solid var(--border);text-align:left}
.b-table tbody tr:last-child td{border-bottom:0}
.b-table tbody tr{transition:background .12s}
.b-table tbody tr:hover{background:var(--accent-soft)}
.b-table thead th{background:var(--surface);font-size:.74rem;text-transform:uppercase;
  letter-spacing:.05em;color:var(--muted);position:sticky;top:0}
.b-th-sort{cursor:pointer;user-select:none;white-space:nowrap}
.b-th-sort::after{content:"\\2195";opacity:.35;margin-left:6px;font-size:.8em}
.b-th-sort[aria-sort="ascending"]::after{content:"\\2191";opacity:1;color:var(--accent)}
.b-th-sort[aria-sort="descending"]::after{content:"\\2193";opacity:1;color:var(--accent)}

/* code */
.b-codewrap{position:relative;background:var(--card);border:1px solid var(--border);
  border-radius:var(--radius);overflow:hidden}
.b-codewrap pre{margin:0;padding:16px 18px;overflow:auto;font-family:var(--mono);
  font-size:.88rem;line-height:1.6}
.b-copy{position:absolute;top:9px;right:9px;font:inherit;font-size:.74rem;font-weight:600;
  padding:4px 11px;border-radius:8px;cursor:pointer;color:var(--muted);
  background:var(--bg);border:1px solid var(--border);opacity:0;transition:opacity .15s,color .15s}
.b-codewrap:hover .b-copy{opacity:1}
.b-copy:hover{color:var(--accent);border-color:var(--accent)}
.b-copy.ok{color:#1a7f37;border-color:#1a7f37;opacity:1}

/* quote */
.b-quote{position:relative;margin:0;padding:8px 0 8px 30px;color:var(--fg);
  font-size:1.18rem;line-height:1.5;font-style:italic}
.b-quote::before{content:"\\201C";position:absolute;left:-4px;top:-.1em;
  font-size:2.6rem;line-height:1;color:var(--accent);font-style:normal}
.b-quote p{margin:0}
.b-quote cite{display:block;margin-top:8px;font-size:.86rem;font-style:normal;color:var(--muted)}

/* figure — bounded inline preview; click to open the zoom/pan lightbox */
.b-figure{margin:0;position:relative}
.b-figure img,.b-diagram img{max-width:100%;max-height:60vh;height:auto;
  object-fit:contain;border-radius:var(--radius);box-shadow:var(--shadow-sm);
  background:var(--bg)}
.b-figure figcaption{color:var(--muted);font-size:.85rem;margin-top:8px;text-align:center}
.b-figure::after{content:"\\26F6 zoom";position:absolute;top:10px;right:10px;
  font-size:.7rem;font-weight:600;color:#fff;background:rgba(8,12,20,.55);
  padding:3px 9px;border-radius:999px;opacity:0;transition:opacity .15s;pointer-events:none}
.b-figure:hover::after{opacity:1}
.md2x-zoomable{cursor:zoom-in}
.md2x-lightbox{position:fixed;inset:0;z-index:100;display:none;overflow:hidden;
  align-items:center;justify-content:center;background:rgba(8,12,20,.88)}
.md2x-lightbox.open{display:flex}
.md2x-lb-img{max-width:92vw;max-height:88vh;background:#fff;border-radius:10px;
  box-shadow:0 24px 70px rgba(0,0,0,.55);cursor:grab;user-select:none;
  -webkit-user-drag:none;transform-origin:center;will-change:transform}
.md2x-lb-img:active{cursor:grabbing}
.md2x-lb-bar{position:fixed;top:16px;right:16px;display:flex;gap:8px;z-index:101}
.md2x-lb-bar button{min-width:40px;height:40px;padding:0 14px;border:0;border-radius:10px;
  background:rgba(255,255,255,.16);color:#fff;cursor:pointer;font:inherit;
  font-size:1.05rem;font-weight:650;line-height:1}
.md2x-lb-bar button:hover{background:rgba(255,255,255,.3)}

/* chart (inline svg, bars grow on reveal) */
.b-chartwrap{background:var(--card);border:1px solid var(--border);
  border-radius:var(--radius);padding:16px;box-shadow:var(--shadow-sm)}
.b-chart{width:100%;max-width:560px;height:auto}
.b-chart .b-bar{fill:var(--accent);transform-box:fill-box;transform-origin:bottom;
  transform:scaleY(1)}
html.js .b-chartwrap[data-reveal] .b-chart .b-bar{transform:scaleY(0);
  transition:transform .8s var(--ease)}
html.js .b-chartwrap[data-reveal].in .b-chart .b-bar{transform:scaleY(1)}
.b-chart .b-dot{fill:var(--accent)}
.b-chart .b-line{stroke:var(--accent);stroke-width:2}
.b-chart .b-axis{fill:var(--muted);font-size:9px}

/* tabs */
.b-tablist{display:flex;gap:4px;border-bottom:1px solid var(--border);flex-wrap:wrap}
.b-tab{background:none;border:0;padding:9px 15px;cursor:pointer;color:var(--muted);
  border-bottom:2px solid transparent;font:inherit;font-weight:560;
  transition:color .15s,border-color .15s}
.b-tab:hover{color:var(--fg)}
.b-tab.active{color:var(--accent);border-bottom-color:var(--accent)}
.b-panel{display:none;padding:16px 0;animation:b-fade .35s var(--ease)}
.b-panel.active{display:block}
@keyframes b-fade{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:none}}
@media (prefers-reduced-motion: reduce){.b-panel{animation:none}}

/* collapsible / steps / glossary */
.b-collapsible{border:1px solid var(--border);border-radius:var(--radius);
  padding:6px 16px;background:var(--card)}
.b-collapsible summary{cursor:pointer;font-weight:620;padding:8px 0}
.b-collapsible[open] summary{color:var(--accent)}
.b-steps{counter-reset:step;list-style:none;padding:0}
.b-step{position:relative;padding:2px 0 20px 46px;counter-increment:step}
.b-step:not(:last-child)::after{content:"";position:absolute;left:14px;top:30px;bottom:6px;
  width:2px;background:var(--border)}
.b-step::before{content:counter(step);position:absolute;left:0;top:0;width:30px;height:30px;
  border-radius:50%;background:var(--accent);color:#fff;display:grid;place-items:center;
  font-size:.86rem;font-weight:700;box-shadow:0 0 0 4px var(--accent-soft)}
.b-step .t{font-weight:660}
.b-step .d{color:var(--muted)}
.b-glossary dt{font-weight:680;color:var(--accent);margin-top:12px}
.b-glossary dd{margin:2px 0 0;color:var(--muted)}
.b-diagram{text-align:center}
.b-diagram svg{max-width:100%;height:auto}

/* artifact (hybrid) */
.b-artifact{border:1px solid var(--border);border-radius:var(--radius);overflow:hidden;
  background:var(--card);box-shadow:var(--shadow-sm)}
.b-artifact-bar{display:flex;justify-content:space-between;align-items:center;
  padding:9px 14px;border-bottom:1px solid var(--border);font-size:.82rem}
.b-artifact-title{font-weight:660;color:var(--muted)}
.b-export{background:var(--accent);color:#fff;border:0;border-radius:8px;
  padding:6px 14px;cursor:pointer;font:inherit;font-size:.8rem;font-weight:600;
  transition:transform .15s var(--ease)}
.b-export:hover{transform:translateY(-1px)}
.b-artifact iframe{display:block;width:100%;border:0;min-height:120px;background:var(--bg)}

/* sidebar section TOC + scroll-spy active state */
nav.side .nav-doc{font-weight:740;letter-spacing:-.01em}
nav.side .nav-secs{display:flex;flex-direction:column;margin:4px 0 10px}
nav.side .nav-secs a{font-size:.86rem;padding:5px 10px 5px 18px;color:var(--muted);
  border-left:2px solid transparent;border-radius:0 8px 8px 0}
nav.side .nav-secs a:hover{color:var(--accent)}
nav.side .nav-secs a.active{color:var(--accent);font-weight:620;
  border-left-color:var(--accent);background:var(--accent-soft)}
"""


# --- the interaction engine -------------------------------------------------
# Raw string so backslashes (JS regex \\d, \\u unicode) pass straight through.
SITE_JS = r"""(function(){
  "use strict";
  var doc=document, root=document.documentElement, win=window;
  var reduce=false; try{reduce=matchMedia("(prefers-reduced-motion: reduce)").matches;}catch(e){}

  // createStore — the state primitive every widget below is built from.
  function createStore(initial, render){
    var state=Object.assign({}, initial);
    function set(patch){ Object.assign(state, patch); if(render) render(state); }
    return { state:state, get:function(k){return state[k];}, set:set };
  }

  function ready(fn){
    if(doc.readyState!=="loading") fn();
    else doc.addEventListener("DOMContentLoaded", fn);
  }
  function observeOnce(el, cb){
    if(!("IntersectionObserver" in win)){ cb(); return; }
    var io=new IntersectionObserver(function(es){
      es.forEach(function(e){ if(e.isIntersecting){ cb(); io.disconnect(); } });
    },{threshold:0.2});
    io.observe(el);
  }

  // reveal on scroll, staggered per nearest section/main
  function revealOnScroll(){
    var els=[].slice.call(doc.querySelectorAll("[data-reveal]"));
    if(!els.length) return;
    var seen=new Map();
    els.forEach(function(el){
      var grp=el.closest("section, main, body")||doc.body;
      var n=seen.get(grp)||0; seen.set(grp, n+1);
      el.style.setProperty("--i", n);
    });
    if(reduce || !("IntersectionObserver" in win)){
      els.forEach(function(el){ el.classList.add("in"); }); return;
    }
    var io=new IntersectionObserver(function(entries){
      entries.forEach(function(en){
        if(en.isIntersecting){ en.target.classList.add("in"); io.unobserve(en.target); }
      });
    },{rootMargin:"0px 0px -8% 0px", threshold:0.06});
    els.forEach(function(el){ io.observe(el); });
  }

  // count up numeric values when they first scroll into view
  function countUp(){
    [].slice.call(doc.querySelectorAll("[data-count]")).forEach(function(el){
      var raw=(el.textContent||"").trim();
      var m=raw.match(/^([^\d-]*)(-?[\d,]*\.?\d+)(.*)$/);
      if(!m) return;
      var prefix=m[1], suffix=m[3], num=m[2].replace(/,/g,"");
      if(/[A-Za-z]/.test(prefix)) return;                 // dates/labels: "June 2026", "Q3 …"
      if(prefix===""&&suffix===""&&/^(19|20)\d\d$/.test(num)) return;   // a bare year
      var target=parseFloat(num); if(isNaN(target)) return;
      var dec=(num.split(".")[1]||"").length;
      if(reduce) return;
      var store=createStore({shown:0}, function(s){ el.textContent=prefix+fmt(s.shown,dec)+suffix; });
      observeOnce(el, function(){
        var start=null, dur=1100;
        function tick(ts){
          if(start===null) start=ts;
          var p=Math.min(1,(ts-start)/dur), eased=1-Math.pow(1-p,3);
          store.set({shown:target*eased});
          if(p<1) requestAnimationFrame(tick); else store.set({shown:target});
        }
        requestAnimationFrame(tick);
      });
    });
  }
  function fmt(n, dec){ return dec? n.toFixed(dec) : Math.round(n).toLocaleString(); }

  // scroll-spy — highlight the in-view section in the sidebar
  function scrollSpy(){
    var links=[].slice.call(doc.querySelectorAll(".nav-secs a"));
    if(!links.length || !("IntersectionObserver" in win)) return;
    var map={}; links.forEach(function(a){ map[a.getAttribute("href").slice(1)]=a; });
    var io=new IntersectionObserver(function(es){
      es.forEach(function(e){
        if(e.isIntersecting){
          links.forEach(function(a){ a.classList.remove("active"); });
          var a=map[e.target.id]; if(a) a.classList.add("active");
        }
      });
    },{rootMargin:"-12% 0px -78% 0px"});
    doc.querySelectorAll("section.b-section").forEach(function(s){ io.observe(s); });
  }

  // tabs — store-backed active panel
  function tabs(){
    doc.querySelectorAll(".b-tabs").forEach(function(w){
      var btns=[].slice.call(w.querySelectorAll(".b-tab"));
      var pans=[].slice.call(w.querySelectorAll(".b-panel"));
      var store=createStore({active:"0"}, function(s){
        btns.forEach(function(b){
          var on=b.getAttribute("data-i")===s.active;
          b.classList.toggle("active", on); b.setAttribute("aria-selected", on);
        });
        pans.forEach(function(p){ p.classList.toggle("active", p.getAttribute("data-i")===s.active); });
      });
      btns.forEach(function(b){
        b.addEventListener("click", function(){ store.set({active:b.getAttribute("data-i")}); });
      });
    });
  }

  // sortable tables — store-backed {col,dir}
  function sortableTables(){
    doc.querySelectorAll("table.b-table[data-sortable]").forEach(function(table){
      var ths=[].slice.call(table.querySelectorAll("thead th"));
      var tbody=table.querySelector("tbody");
      if(!ths.length || !tbody) return;
      function cell(tr,i){ var c=tr.children[i]; return c?(c.textContent||"").trim():""; }
      var store=createStore({col:-1,dir:1}, function(s){
        ths.forEach(function(th,i){
          th.setAttribute("aria-sort", i===s.col?(s.dir>0?"ascending":"descending"):"none");
        });
        if(s.col<0) return;
        var rows=[].slice.call(tbody.querySelectorAll("tr"));
        rows.sort(function(a,b){
          var x=cell(a,s.col), y=cell(b,s.col);
          var nx=parseFloat(x.replace(/[^0-9.\-]/g,"")), ny=parseFloat(y.replace(/[^0-9.\-]/g,""));
          var cmp=(!isNaN(nx)&&!isNaN(ny))? nx-ny : x.localeCompare(y);
          return cmp*s.dir;
        });
        rows.forEach(function(r){ tbody.appendChild(r); });
      });
      ths.forEach(function(th,i){
        th.classList.add("b-th-sort"); th.setAttribute("aria-sort","none");
        th.addEventListener("click", function(){
          store.set({col:i, dir: store.get("col")===i? -store.get("dir") : 1});
        });
      });
    });
  }

  // copy buttons on code blocks
  function copyButtons(){
    doc.querySelectorAll(".b-copy").forEach(function(btn){
      btn.addEventListener("click", function(){
        var wrap=btn.closest(".b-codewrap"), pre=wrap&&wrap.querySelector("pre");
        var text=pre? pre.innerText : "";
        if(navigator.clipboard && text) navigator.clipboard.writeText(text);
        var old=btn.textContent; btn.textContent="Copied"; btn.classList.add("ok");
        setTimeout(function(){ btn.textContent=old; btn.classList.remove("ok"); },1200);
      });
    });
  }

  // theme toggle — auto / light / dark, persisted
  function themeToggle(){
    var KEY="md2x-theme", order=["auto","light","dark"];
    var saved=null; try{ saved=localStorage.getItem(KEY); }catch(e){}
    apply(saved||"auto");
    var btn=doc.createElement("button");
    btn.className="md2x-themetoggle"; btn.type="button";
    btn.setAttribute("aria-label","Toggle colour theme"); label();
    btn.addEventListener("click", function(){
      var cur=root.getAttribute("data-theme-pref")||"auto";
      var next=order[(order.indexOf(cur)+1)%order.length];
      apply(next); try{ localStorage.setItem(KEY,next); }catch(e){} label();
    });
    doc.body.appendChild(btn);
    function apply(mode){
      if(mode==="auto") root.removeAttribute("data-theme"); else root.setAttribute("data-theme",mode);
      root.setAttribute("data-theme-pref", mode);
    }
    function label(){
      var m=root.getAttribute("data-theme-pref")||"auto";
      btn.textContent = m==="dark"? "◑ Dark" : m==="light"? "○ Light" : "◐ Auto";
    }
  }

  // reading progress bar
  function readingProgress(){
    var bar=doc.createElement("div"); bar.className="md2x-progress"; doc.body.appendChild(bar);
    function on(){
      var h=doc.documentElement, max=h.scrollHeight-h.clientHeight;
      var p=max>0? (h.scrollTop||doc.body.scrollTop)/max : 0;
      bar.style.transform="scaleX("+Math.min(1,Math.max(0,p))+")";
    }
    on(); win.addEventListener("scroll", on, {passive:true}); win.addEventListener("resize", on);
  }

  // smooth in-page anchors
  function smoothAnchors(){
    doc.querySelectorAll('a[href^="#"]').forEach(function(a){
      a.addEventListener("click", function(e){
        var id=a.getAttribute("href"); if(id.length<2) return;
        var el=null; try{ el=doc.querySelector(id); }catch(err){ return; }
        if(el){ e.preventDefault(); el.scrollIntoView({behavior:reduce?"auto":"smooth"});
          try{ history.replaceState(null,"",id); }catch(err){} }
      });
    });
  }

  // hybrid artifact broker — resize sandboxed iframes + copy their exports
  function hybridBroker(){
    win.addEventListener("message", function(e){
      var d=e.data||{};
      if(d.type==="md2x:resize" && d.height){
        doc.querySelectorAll(".b-artifact iframe").forEach(function(f){
          if(f.contentWindow===e.source) f.style.height=(d.height+4)+"px";
        });
      }
      if(d.type==="md2x:export"){
        var p=typeof d.payload==="string"? d.payload : JSON.stringify(d.payload,null,2);
        if(navigator.clipboard && p) navigator.clipboard.writeText(p);
      }
    });
    doc.querySelectorAll(".b-export").forEach(function(b){
      b.addEventListener("click", function(){
        var w=b.closest(".b-artifact"), f=w&&w.querySelector("iframe");
        if(f&&f.contentWindow) f.contentWindow.postMessage({type:"md2x:request-export",
          format:b.getAttribute("data-format")}, "*");
      });
    });
  }

  // image viewer — click a figure/diagram to open it in a zoom + pan lightbox
  function imageViewer(){
    var imgs=doc.querySelectorAll('.b-figure img, .b-diagram img, .b-prose img');
    if(!imgs.length) return;
    var overlay, view, store, drag=false, ox=0, oy=0;
    function zoom(f){ var s=Math.min(8, Math.max(1, store.get('s')*f));
      store.set(s===1?{s:1,x:0,y:0}:{s:s}); }
    function build(){
      overlay=doc.createElement('div'); overlay.className='md2x-lightbox';
      overlay.innerHTML='<div class="md2x-lb-bar">'
        +'<button data-a="out" aria-label="Zoom out">−</button>'
        +'<button data-a="reset" aria-label="Fit">Fit</button>'
        +'<button data-a="in" aria-label="Zoom in">+</button>'
        +'<button data-a="close" aria-label="Close">✕</button></div>'
        +'<img class="md2x-lb-img" alt="">';
      doc.body.appendChild(overlay);
      view=overlay.querySelector('.md2x-lb-img');
      store=createStore({s:1,x:0,y:0}, function(st){
        view.style.transform='translate('+st.x+'px,'+st.y+'px) scale('+st.s+')'; });
      overlay.addEventListener('click', function(e){
        var a=e.target.getAttribute&&e.target.getAttribute('data-a');
        if(a==='close'||e.target===overlay) return close();
        if(a==='in') zoom(1.25); else if(a==='out') zoom(1/1.25);
        else if(a==='reset') store.set({s:1,x:0,y:0}); });
      view.addEventListener('wheel', function(e){ e.preventDefault();
        zoom(e.deltaY<0?1.12:1/1.12); }, {passive:false});
      view.addEventListener('dblclick', function(){
        store.set(store.get('s')>1?{s:1,x:0,y:0}:{s:2}); });
      view.addEventListener('mousedown', function(e){ drag=true;
        ox=e.clientX-store.get('x'); oy=e.clientY-store.get('y'); e.preventDefault(); });
      win.addEventListener('mousemove', function(e){ if(drag)
        store.set({x:e.clientX-ox, y:e.clientY-oy}); });
      win.addEventListener('mouseup', function(){ drag=false; });
      view.addEventListener('touchstart', function(e){ if(e.touches.length===1){
        drag=true; ox=e.touches[0].clientX-store.get('x');
        oy=e.touches[0].clientY-store.get('y'); } }, {passive:true});
      view.addEventListener('touchmove', function(e){ if(drag&&e.touches.length===1)
        store.set({x:e.touches[0].clientX-ox, y:e.touches[0].clientY-oy}); }, {passive:true});
      view.addEventListener('touchend', function(){ drag=false; });
      doc.addEventListener('keydown', function(e){
        if(!overlay.classList.contains('open')) return;
        if(e.key==='Escape') close();
        else if(e.key==='+'||e.key==='=') zoom(1.25);
        else if(e.key==='-') zoom(1/1.25); });
    }
    function open(src,alt){ if(!overlay) build();
      view.src=src; view.alt=alt||''; store.set({s:1,x:0,y:0});
      overlay.classList.add('open'); doc.body.style.overflow='hidden'; }
    function close(){ if(overlay){ overlay.classList.remove('open');
      doc.body.style.overflow=''; } }
    imgs.forEach(function(im){ im.classList.add('md2x-zoomable');
      im.addEventListener('click', function(){ open(im.currentSrc||im.src, im.alt); }); });
  }

  ready(function(){
    [revealOnScroll,countUp,scrollSpy,tabs,sortableTables,copyButtons,themeToggle,
     readingProgress,smoothAnchors,hybridBroker,imageViewer].forEach(function(fn){
      try{ fn(); }catch(e){ if(win.console) console.warn("md2x:", e); }
    });
  });

  win.md2x={ createStore:createStore };
})();
"""
