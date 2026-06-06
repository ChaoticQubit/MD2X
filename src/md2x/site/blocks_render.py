"""Block→DOM renderer for `blocks` mode, plus the site writer.

`render.py` owns the page chrome; this module owns the typed-block body. Every
AI/derived string is HTML-escaped here; only `Prose` (author-verbatim),
`DiagramSvg`, and `RawHtml` carry markup, and the latter two are sanitized first.
Output is fully self-contained (inline CSS/JS, no network), so it deploys as
static files. Interactivity (tabs) rides one shared JS string; collapsibles use
native `<details>` and steps use CSS counters — no per-block model JS.
"""
from __future__ import annotations

import html
import re
from pathlib import Path

from ..log import get_logger
from .blocks import (
    Artifact, Block, Callout, CardGrid, Chart, Code, Collapsible, DiagramSvg,
    Figure, Glossary, Hero, KpiStrip, PageDoc, Prose, Quote, RawHtml, Steps,
    Summary, Table, Tabs, Timeline, build_page_doc,
)
from .design_css import design_css_vars, render_design_system_page
from .render import (
    SHELLS, SHELL_JS, _accent, _copy_diagrams, _design_for, _enhancement_html,
    _nav_html,
)
from .schemas import PageEnhancement, SitePlan

log = get_logger(__name__)


def _e(text) -> str:
    return html.escape("" if text is None else str(text), quote=True)


# --- sanitizers (minimal; PR-G hardens) -------------------------------------

_SCRIPT_RE = re.compile(r"(?is)<script\b.*?</script\s*>")
_DANGER_TAGS_RE = re.compile(r"(?is)</?(?:iframe|object|embed|link|meta|base|form)\b[^>]*>")
_ON_ATTR_RE = re.compile(r"(?is)\son\w+\s*=\s*(?:\"[^\"]*\"|'[^']*'|[^\s>]+)")
_JS_URL_RE = re.compile(r"(?i)(href|src|xlink:href)\s*=\s*([\"'])\s*javascript:[^\"']*\2")
_EXT_URL_RE = re.compile(r"(?i)(href|src|xlink:href)\s*=\s*([\"'])\s*https?:[^\"']*\2")
_FOREIGN_RE = re.compile(r"(?is)<foreignObject\b.*?</foreignObject\s*>")


def sanitize_inline(markup: str) -> str:
    """Strip scripts, event handlers, dangerous tags, and remote/JS URLs."""
    s = _SCRIPT_RE.sub("", markup or "")
    s = _DANGER_TAGS_RE.sub("", s)
    s = _ON_ATTR_RE.sub("", s)
    s = _JS_URL_RE.sub(r"\1=\2#\2", s)
    s = _EXT_URL_RE.sub(r"\1=\2#\2", s)
    return s


def sanitize_svg(svg: str) -> str:
    """Keep drawing markup; drop scripts, foreignObject, handlers, remote refs."""
    s = _SCRIPT_RE.sub("", svg or "")
    s = _FOREIGN_RE.sub("", s)
    s = _ON_ATTR_RE.sub("", s)
    s = _JS_URL_RE.sub(r"\1=\2#\2", s)
    s = _EXT_URL_RE.sub(r"\1=\2#\2", s)
    return s


# --- per-block renderers ----------------------------------------------------

_TONES = {"info", "warn", "success"}


def _hero(b: Hero) -> str:
    kicker = f'<div class="b-kicker">{_e(b.kicker)}</div>' if b.kicker else ""
    sub = f'<p class="b-sub">{_e(b.subtitle)}</p>' if b.subtitle else ""
    return (f'<header class="b-hero">{kicker}'
            f"<h1>{_e(b.title)}</h1>{sub}</header>")


def _summary(b: Summary) -> str:
    return ('<div class="b-summary"><div class="b-label">Summary</div>'
            f"<p>{_e(b.text)}</p></div>")


def _prose(b: Prose) -> str:
    # Author-verbatim — intentionally not escaped.
    return f'<div class="b-prose">{b.html}</div>'


def _kpi_strip(b: KpiStrip) -> str:
    cards = "".join(
        f'<div class="b-kpi-card"><div class="v">{_e(k.value)}</div>'
        f'<div class="l">{_e(k.label)}</div></div>' for k in b.items
    )
    return f'<div class="b-kpi">{cards}</div>'


def _callout(b: Callout) -> str:
    tone = b.tone if b.tone in _TONES else "info"
    return (f'<div class="b-callout tone-{tone}"><div class="b-label">{_e(b.label)}</div>'
            f"<div>{_e(b.text)}</div></div>")


def _card_grid(b: CardGrid) -> str:
    out = []
    for c in b.cards:
        inner = (f"<h3>{_e(c.title)}</h3>"
                 + (f"<p>{_e(c.body)}</p>" if c.body else ""))
        if c.href and not re.match(r"(?i)^(https?:|javascript:)", c.href.strip()):
            out.append(f'<a class="b-card" href="{_e(c.href)}">{inner}</a>')
        else:
            out.append(f'<div class="b-card">{inner}</div>')
    return f'<div class="b-cards">{"".join(out)}</div>'


def _timeline(b: Timeline) -> str:
    items = "".join(
        f'<li class="b-ev"><div class="when">{_e(ev.when)}</div>'
        f'<div class="t">{_e(ev.title)}</div>'
        + (f'<div class="d">{_e(ev.body)}</div>' if ev.body else "")
        + "</li>" for ev in b.events
    )
    return f'<ul class="b-timeline">{items}</ul>'


def _table(b: Table) -> str:
    head = ("<thead><tr>" + "".join(f"<th>{_e(h)}</th>" for h in b.headers)
            + "</tr></thead>") if b.headers else ""
    body = "".join(
        "<tr>" + "".join(f"<td>{_e(c)}</td>" for c in row) + "</tr>"
        for row in b.rows
    )
    return f'<table class="b-table">{head}<tbody>{body}</tbody></table>'


def _code(b: Code) -> str:
    cls = f' class="language-{_e(b.lang)}"' if b.lang else ""
    return f'<pre class="b-code"><code{cls}>{_e(b.code)}</code></pre>'


def _quote(b: Quote) -> str:
    cite = f"<cite>{_e(b.cite)}</cite>" if b.cite else ""
    return f'<blockquote class="b-quote"><p>{_e(b.text)}</p>{cite}</blockquote>'


def _figure(b: Figure) -> str:
    src = b.src.strip()
    if re.match(r"(?i)^(https?:|javascript:|data:)", src):
        log.warning("blocks: dropping non-local figure src %r", src)
        return ""
    cap = f"<figcaption>{_e(b.caption)}</figcaption>" if b.caption else ""
    return (f'<figure class="b-figure"><img src="{_e(src)}" '
            f'alt="{_e(b.alt)}" loading="lazy">{cap}</figure>')


def _chart_svg(b: Chart) -> str:
    pts = [(p.label, p.value) for p in b.points if isinstance(p.value, (int, float))]
    if not pts:
        return ""
    w, h, pad = 320, 160, 24
    vmax = max((v for _, v in pts), default=0) or 1
    n = len(pts)
    inner_w = w - 2 * pad
    inner_h = h - 2 * pad
    body = []
    if b.kind == "line":
        step = inner_w / max(1, n - 1)
        coords = [
            (pad + i * step, h - pad - (v / vmax) * inner_h) for i, (_, v) in enumerate(pts)
        ]
        path = " ".join(f"{x:.1f},{y:.1f}" for x, y in coords)
        body.append(f'<polyline class="b-line" points="{path}" fill="none"/>')
        for x, y in coords:
            body.append(f'<circle class="b-dot" cx="{x:.1f}" cy="{y:.1f}" r="3"/>')
    else:  # bar
        bw = inner_w / n * 0.62
        gap = inner_w / n
        for i, (_, v) in enumerate(pts):
            bh = (v / vmax) * inner_h
            x = pad + i * gap + (gap - bw) / 2
            y = h - pad - bh
            body.append(f'<rect class="b-bar" x="{x:.1f}" y="{y:.1f}" '
                        f'width="{bw:.1f}" height="{bh:.1f}" rx="2"/>')
    labels = "".join(
        f'<text class="b-axis" x="{pad + (i + 0.5) * inner_w / n:.1f}" '
        f'y="{h - 6}" text-anchor="middle">{_e(lbl)}</text>'
        for i, (lbl, _) in enumerate(pts)
    )
    return (f'<svg class="b-chart" viewBox="0 0 {w} {h}" '
            f'role="img" preserveAspectRatio="xMidYMid meet">'
            f'{"".join(body)}{labels}</svg>')


def _tabs(b: Tabs) -> str:
    if not b.tabs:
        return ""
    btns, panels = [], []
    for i, t in enumerate(b.tabs):
        sel = "true" if i == 0 else "false"
        active = " active" if i == 0 else ""
        btns.append(f'<button class="b-tab{active}" role="tab" '
                    f'aria-selected="{sel}" data-i="{i}">{_e(t.label)}</button>')
        panels.append(f'<div class="b-panel{active}" role="tabpanel" '
                      f'data-i="{i}">{t.html}</div>')
    return (f'<div class="b-tabs"><div class="b-tablist" role="tablist">'
            f'{"".join(btns)}</div>{"".join(panels)}</div>')


def _collapsible(b: Collapsible) -> str:
    op = " open" if b.open else ""
    return (f'<details class="b-collapsible"{op}><summary>{_e(b.summary)}</summary>'
            f"<div>{b.html}</div></details>")


def _steps(b: Steps) -> str:
    items = "".join(
        f'<li class="b-step"><div class="t">{_e(s.title)}</div>'
        + (f"<div class=\"d\">{_e(s.body)}</div>" if s.body else "")
        + "</li>" for s in b.steps
    )
    return f'<ol class="b-steps">{items}</ol>'


def _diagram(b: DiagramSvg) -> str:
    return f'<div class="b-diagram">{sanitize_svg(b.svg)}</div>'


def _glossary(b: Glossary) -> str:
    items = "".join(f"<dt>{_e(t.term)}</dt><dd>{_e(t.definition)}</dd>"
                    for t in b.terms)
    return f'<dl class="b-glossary">{items}</dl>'


def _raw(b: RawHtml) -> str:
    return f'<div class="b-raw">{sanitize_inline(b.html)}</div>'


_RENDERERS = {
    Hero: _hero, Summary: _summary, Prose: _prose, KpiStrip: _kpi_strip,
    Callout: _callout, CardGrid: _card_grid, Timeline: _timeline, Table: _table,
    Code: _code, Quote: _quote, Figure: _figure, Chart: _chart_svg, Tabs: _tabs,
    Collapsible: _collapsible, Steps: _steps, DiagramSvg: _diagram,
    Glossary: _glossary, RawHtml: _raw,
}


# --- artifact (hybrid): sandboxed, CSP-locked iframe ------------------------

# default-src 'none' blocks ALL network (no fetch/xhr/ws/remote anything); only
# inline style + inline script run. Combined with sandbox="allow-scripts" (and no
# allow-same-origin), the artifact cannot reach the parent or the network.
_ARTIFACT_CSP = ("default-src 'none'; style-src 'unsafe-inline'; "
                 "script-src 'unsafe-inline'; img-src data:; font-src data:")

# Posts its height to the host so the iframe auto-sizes (no scrollbars).
_RESIZE_JS = (
    ";(function(){function h(){try{parent.postMessage({type:'md2x:resize',"
    "height:document.documentElement.scrollHeight},'*');}catch(e){}}"
    "window.addEventListener('load',h);"
    "if(window.ResizeObserver){new ResizeObserver(h).observe(document.body);}"
    "setTimeout(h,60);})();"
)


def _artifact(b: Artifact, ds_css: str = "") -> str:
    srcdoc = (
        '<!doctype html><html><head><meta charset="utf-8">'
        f'<meta http-equiv="Content-Security-Policy" content="{_ARTIFACT_CSP}">'
        f"<style>{ds_css} {b.css} "
        "html,body{margin:0;padding:8px;font-family:var(--ds-font-sans,system-ui);"
        "color:var(--ds-fg,#1f2328);background:transparent}</style></head><body>"
        f"{b.html}<script>{b.js}\n{_RESIZE_JS}</script></body></html>"
    )
    btn = ""
    if b.export is not None:
        btn = (f'<button class="b-export" data-format="{_e(b.export.format)}">'
               f"{_e(b.export.label)}</button>")
    title = (f'<span class="b-artifact-title">{_e(b.title)}</span>'
             if b.title else "<span></span>")
    # The whole srcdoc is attribute-escaped, so artifact markup (even a stray
    # </iframe>) cannot break out into the host document.
    return (
        f'<div class="b-artifact" data-kind="{_e(b.kind)}">'
        f'<div class="b-artifact-bar">{title}{btn}</div>'
        f'<iframe sandbox="allow-scripts" loading="lazy" '
        f'title="{_e(b.title or b.kind)}" srcdoc="{_e(srcdoc)}"></iframe></div>'
    )


def render_block(block: Block, ds_css: str = "") -> str:
    if isinstance(block, Artifact):
        return _artifact(block, ds_css)
    fn = _RENDERERS.get(type(block))
    if fn is None:
        log.warning("blocks: unknown block %r; skipped", type(block).__name__)
        return ""
    return fn(block)


def render_blocks(blocks: list[Block], ds_css: str = "") -> str:
    return "".join(render_block(b, ds_css) for b in blocks)


# --- block CSS + JS (shared; ride the page, not per-block) -------------------

_BLOCKS_CSS = """\
.b-prose, .b-summary, .b-callout, .b-kpi, .b-cards, .b-timeline, .b-table,
.b-code, .b-quote, .b-figure, .b-chart, .b-tabs, .b-collapsible, .b-steps,
.b-glossary, .b-diagram { margin: var(--ds-space-3,1.5rem) 0; }
.b-hero { margin: 0 0 var(--ds-space-3,1.5rem); }
.b-hero h1 { font-size: clamp(1.8rem,4vw,2.6rem); margin:.1em 0; letter-spacing:-.02em; }
.b-kicker { text-transform:uppercase; letter-spacing:.14em; font-size:.72rem;
  font-weight:700; color:var(--accent); }
.b-sub { color:var(--muted); font-size:1.15rem; margin:.4em 0 0; }
.b-label { text-transform:uppercase; letter-spacing:.1em; font-size:.68rem;
  font-weight:700; color:var(--accent); margin-bottom:6px; }
.b-summary { background:var(--card); border-left:3px solid var(--accent);
  border-radius:var(--radius,8px); padding:14px 18px; }
.b-callout { background:var(--card); border:1px solid var(--border);
  border-left:4px solid var(--accent); border-radius:var(--radius,8px); padding:12px 16px; }
.b-callout.tone-warn { border-left-color:#d29922; }
.b-callout.tone-success { border-left-color:#2da44e; }
.b-kpi { display:grid; grid-template-columns:repeat(auto-fit,minmax(140px,1fr)); gap:14px; }
.b-kpi-card { background:var(--card); border:1px solid var(--border);
  border-radius:var(--radius,8px); padding:16px; }
.b-kpi-card .v { font-size:1.9rem; font-weight:750; color:var(--accent); line-height:1.1; }
.b-kpi-card .l { color:var(--muted); font-size:.85rem; margin-top:4px; }
.b-cards { display:grid; grid-template-columns:repeat(auto-fill,minmax(200px,1fr)); gap:14px; }
.b-card { display:block; background:var(--card); border:1px solid var(--border);
  border-radius:var(--radius,8px); padding:16px; color:inherit; text-decoration:none; }
a.b-card:hover { border-color:var(--accent); }
.b-timeline { list-style:none; padding:0; border-left:2px solid var(--border); margin-left:8px; }
.b-ev { position:relative; padding:0 0 18px 20px; }
.b-ev::before { content:""; position:absolute; left:-7px; top:4px; width:10px; height:10px;
  border-radius:50%; background:var(--accent); }
.b-ev .when { font-size:.78rem; color:var(--muted); }
.b-ev .t { font-weight:650; }
.b-table { width:100%; border-collapse:collapse; border:1px solid var(--border);
  border-radius:var(--radius,8px); overflow:hidden; }
.b-table th, .b-table td { padding:9px 13px; border-bottom:1px solid var(--border); text-align:left; }
.b-table thead th { background:var(--card); font-size:.82rem; text-transform:uppercase;
  letter-spacing:.04em; color:var(--muted); }
.b-code { background:var(--card); border:1px solid var(--border);
  border-radius:var(--radius,8px); padding:14px; overflow:auto; }
.b-quote { border-left:3px solid var(--accent); margin:0; padding:6px 18px; color:var(--muted); }
.b-quote cite { display:block; margin-top:6px; font-size:.85rem; font-style:normal; }
.b-figure { margin:0; } .b-figure img { max-width:100%; height:auto; border-radius:var(--radius,8px); }
.b-figure figcaption { color:var(--muted); font-size:.85rem; margin-top:6px; }
.b-chart { width:100%; max-width:520px; height:auto; }
.b-chart .b-bar, .b-chart .b-dot { fill:var(--accent); }
.b-chart .b-line { stroke:var(--accent); stroke-width:2; }
.b-chart .b-axis { fill:var(--muted); font-size:9px; }
.b-tablist { display:flex; gap:4px; border-bottom:1px solid var(--border); }
.b-tab { background:none; border:0; padding:8px 14px; cursor:pointer; color:var(--muted);
  border-bottom:2px solid transparent; font:inherit; }
.b-tab.active { color:var(--accent); border-bottom-color:var(--accent); }
.b-panel { display:none; padding:14px 0; } .b-panel.active { display:block; }
.b-collapsible { border:1px solid var(--border); border-radius:var(--radius,8px); padding:6px 14px; }
.b-collapsible summary { cursor:pointer; font-weight:600; }
.b-steps { counter-reset:step; list-style:none; padding:0; }
.b-step { position:relative; padding:0 0 16px 40px; counter-increment:step; }
.b-step::before { content:counter(step); position:absolute; left:0; top:0; width:26px; height:26px;
  border-radius:50%; background:var(--accent); color:#fff; display:grid; place-items:center;
  font-size:.8rem; font-weight:700; }
.b-step .t { font-weight:650; }
.b-glossary dt { font-weight:650; color:var(--accent); margin-top:10px; }
.b-glossary dd { margin:2px 0 0; color:var(--muted); }
.b-diagram svg { max-width:100%; height:auto; }
.b-artifact { border:1px solid var(--border); border-radius:var(--radius,8px);
  overflow:hidden; background:var(--card); }
.b-artifact-bar { display:flex; justify-content:space-between; align-items:center;
  padding:8px 12px; border-bottom:1px solid var(--border); font-size:.82rem; }
.b-artifact-title { font-weight:650; color:var(--muted); }
.b-export { background:var(--accent); color:#fff; border:0; border-radius:6px;
  padding:5px 12px; cursor:pointer; font:inherit; font-size:.8rem; }
.b-artifact iframe { display:block; width:100%; border:0; min-height:120px;
  background:var(--bg); }
"""

_BLOCKS_JS = (
    "document.querySelectorAll('.b-tabs').forEach(function(w){"
    "var tabs=w.querySelectorAll('.b-tab'),pans=w.querySelectorAll('.b-panel');"
    "tabs.forEach(function(t){t.addEventListener('click',function(){"
    "var i=t.getAttribute('data-i');"
    "tabs.forEach(function(x){var on=x.getAttribute('data-i')===i;"
    "x.classList.toggle('active',on);x.setAttribute('aria-selected',on);});"
    "pans.forEach(function(p){p.classList.toggle('active',"
    "p.getAttribute('data-i')===i);});});});});"
)

# Host-side broker for hybrid artifacts: resize each iframe to its content, and
# copy the payload an editor artifact exports. The export button posts a request
# INTO the iframe; the artifact answers with md2x:export.
_HYBRID_JS = (
    "window.addEventListener('message',function(e){var d=e.data||{};"
    "if(d.type==='md2x:resize'&&d.height){"
    "document.querySelectorAll('.b-artifact iframe').forEach(function(f){"
    "if(f.contentWindow===e.source){f.style.height=(d.height+4)+'px';}});}"
    "if(d.type==='md2x:export'){var p=typeof d.payload==='string'?d.payload:"
    "JSON.stringify(d.payload,null,2);if(navigator.clipboard&&p){"
    "navigator.clipboard.writeText(p);}}});"
    "document.querySelectorAll('.b-export').forEach(function(b){"
    "b.addEventListener('click',function(){var w=b.closest('.b-artifact'),"
    "f=w&&w.querySelector('iframe');if(f&&f.contentWindow){"
    "f.contentWindow.postMessage({type:'md2x:request-export',"
    "format:b.getAttribute('data-format')},'*');}});});"
)


# --- page + site assembly ---------------------------------------------------

def _blocks_page_html(title: str, accent: str, ds_css: str, body: str) -> str:
    shell_css = SHELLS["sidebar"].replace("%ACCENT%", accent)
    head = (f"<style>{ds_css}</style>\n<style>{shell_css}\n{_BLOCKS_CSS}</style>")
    tail = (f"<script>{SHELL_JS['sidebar']}</script>\n<script>{_BLOCKS_JS}</script>\n"
            f"<script>{_HYBRID_JS}</script>")
    return (
        '<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>{_e(title)}</title>\n{head}\n</head>\n<body>\n{body}\n{tail}\n"
        "</body>\n</html>\n"
    )


def _page_doc_for(doc, cfg: dict) -> PageDoc:
    """AI block tree at synthesize, else the deterministic builder."""
    if cfg["site"].get("fidelity") == "synthesize":
        try:
            from .blocks_agent import run_page_blocks   # lazy: needs agno
            return run_page_blocks(doc, cfg)
        except Exception as e:
            log.warning("blocks agent failed for %s (%s); deterministic page",
                        doc.slug, e)
            log.debug("blocks %s failure", doc.slug, exc_info=True)
    return build_page_doc(doc)


def _render_doc_page(doc, plan: SitePlan, enh: PageEnhancement, cfg: dict) -> str:
    accent = _accent(cfg, plan)
    ds_css = design_css_vars(_design_for(plan, accent))
    nav = _nav_html(plan, doc.slug, single_page=False)
    page = _page_doc_for(doc, cfg)
    enh_html = _enhancement_html(enh, plan, single_page=False)
    main = (f'<main id="{_e(doc.slug)}">{enh_html}'
            f"{render_blocks(page.blocks, ds_css=ds_css)}</main>")
    body = f'<div class="layout">{nav}{main}</div>'
    return _blocks_page_html(doc.title, accent, ds_css, body)


def _render_index(plan: SitePlan, cfg: dict) -> str:
    accent = _accent(cfg, plan)
    ds_css = design_css_vars(_design_for(plan, accent))
    nav = _nav_html(plan, "", single_page=False)
    from .render import _href
    cards = "".join(
        f'<a class="b-card" href="{_href(n.slug, False)}"><h3>{_e(n.title)}</h3></a>'
        for n in plan.nav
    )
    intro = f"<p>{_e(plan.index_intro)}</p>" if plan.index_intro else ""
    main = (f"<main><header class=\"b-hero\"><h1>{_e(plan.index_title)}</h1></header>"
            f'{intro}<div class="b-cards">{cards}</div></main>')
    body = f'<div class="layout">{nav}{main}</div>'
    return _blocks_page_html(plan.index_title, accent, ds_css, body)


def write_blocks_site(out_dir: Path, docs, plan: SitePlan,
                      enh: dict, cfg: dict) -> None:
    """Write a typed-block site: one page per doc + index + design-system page."""
    out_dir.mkdir(parents=True, exist_ok=True)
    accent = _accent(cfg, plan)
    log.info("blocks site: %d doc(s), fidelity=%s, accent=%s",
             len(docs), cfg["site"].get("fidelity"), accent)
    for doc in docs:
        page_html = _render_doc_page(doc, plan, enh.get(doc.slug, PageEnhancement()),
                                     cfg)
        (out_dir / f"{doc.slug}.html").write_text(page_html, encoding="utf-8")
        log.debug("wrote blocks page %s.html", doc.slug)
    (out_dir / "index.html").write_text(_render_index(plan, cfg), encoding="utf-8")
    (out_dir / "design-system.html").write_text(
        render_design_system_page(_design_for(plan, accent)), encoding="utf-8")
    _copy_diagrams(out_dir, docs)
    log.info("wrote blocks site to %s", out_dir)
