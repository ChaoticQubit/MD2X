"""Block→DOM renderer for `blocks` mode, plus the site writer.

`render.py` owns the page chrome; this module owns the typed-block body. Every
AI/derived string is HTML-escaped here; only `Prose` (author-verbatim),
`DiagramSvg`, and `RawHtml` carry markup, and the latter two are sanitized first.
Output deploys as static files with no network: the design system and the
interaction engine live in shared `assets/site.css` + `assets/site.js` (see
`theme.py`), which every page links; a page inlines only its own `--ds-*` tokens.
Blocks carry behaviour hooks (`data-reveal`, `data-count`, `data-sortable`, a code
copy button) that `site.js` wires up — no per-block model JS.
"""
from __future__ import annotations

import html
import re
from pathlib import Path

from ..log import get_logger
from .blocks import (
    Artifact, Block, Callout, CardGrid, Chart, Code, Collapsible, DiagramSvg,
    Figure, Glossary, Hero, KpiStrip, PageDoc, Prose, Quote, RawHtml, Section,
    Steps, Summary, Table, Tabs, Timeline, build_page_doc,
)
from .design_css import design_css_vars, render_design_system_page
from .render import (
    _accent, _copy_diagrams, _design_for, _enhancement_html, _href, _nav_html,
)
from .sanitize import sanitize_inline, sanitize_svg
from .schemas import PageEnhancement, SitePlan
from .theme import SITE_CSS, SITE_JS

log = get_logger(__name__)


def _e(text) -> str:
    return html.escape("" if text is None else str(text), quote=True)


# sanitize_inline / sanitize_svg are the canonical sanitizers from sanitize.py,
# imported above and re-exposed here for callers that reference them on this module.


# --- per-block renderers ----------------------------------------------------
# `data-reveal` marks a block for the scroll-in animation; `data-count` marks a
# number for count-up; `data-sortable` makes a table's headers clickable. All are
# wired by assets/site.js (theme.py) — the markup degrades to static without JS.

_TONES = {"info", "warn", "success"}


def _hero(b: Hero) -> str:
    kicker = f'<div class="b-kicker">{_e(b.kicker)}</div>' if b.kicker else ""
    sub = f'<p class="b-sub">{_e(b.subtitle)}</p>' if b.subtitle else ""
    return (f'<header class="b-hero" data-reveal>{kicker}'
            f"<h1>{_e(b.title)}</h1>{sub}</header>")


def _summary(b: Summary) -> str:
    return ('<div class="b-summary" data-reveal><div class="b-label">Summary</div>'
            f"<p>{_e(b.text)}</p></div>")


def _prose(b: Prose) -> str:
    # Author-verbatim — intentionally not escaped.
    return f'<div class="b-prose" data-reveal>{b.html}</div>'


def _kpi_strip(b: KpiStrip) -> str:
    cards = "".join(
        f'<div class="b-kpi-card"><div class="v" data-count>{_e(k.value)}</div>'
        f'<div class="l">{_e(k.label)}</div></div>' for k in b.items
    )
    return f'<div class="b-kpi" data-reveal>{cards}</div>'


def _callout(b: Callout) -> str:
    tone = b.tone if b.tone in _TONES else "info"
    return (f'<div class="b-callout tone-{tone}" data-reveal>'
            f'<div class="b-label">{_e(b.label)}</div>'
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
    return f'<div class="b-cards" data-reveal>{"".join(out)}</div>'


def _timeline(b: Timeline) -> str:
    items = "".join(
        f'<li class="b-ev"><div class="when">{_e(ev.when)}</div>'
        f'<div class="t">{_e(ev.title)}</div>'
        + (f'<div class="d">{_e(ev.body)}</div>' if ev.body else "")
        + "</li>" for ev in b.events
    )
    return f'<ul class="b-timeline" data-reveal>{items}</ul>'


def _table(b: Table) -> str:
    head = ("<thead><tr>" + "".join(f"<th>{_e(h)}</th>" for h in b.headers)
            + "</tr></thead>") if b.headers else ""
    body = "".join(
        "<tr>" + "".join(f"<td>{_e(c)}</td>" for c in row) + "</tr>"
        for row in b.rows
    )
    sortable = " data-sortable" if b.headers else ""
    return (f'<div class="b-tablewrap" data-reveal>'
            f'<table class="b-table"{sortable}>{head}<tbody>{body}</tbody>'
            f"</table></div>")


def _code(b: Code) -> str:
    cls = f' class="language-{_e(b.lang)}"' if b.lang else ""
    return (f'<div class="b-codewrap" data-reveal>'
            f'<button class="b-copy" type="button" aria-label="Copy code">Copy</button>'
            f"<pre><code{cls}>{_e(b.code)}</code></pre></div>")


def _quote(b: Quote) -> str:
    cite = f"<cite>{_e(b.cite)}</cite>" if b.cite else ""
    return (f'<blockquote class="b-quote" data-reveal><p>{_e(b.text)}</p>'
            f"{cite}</blockquote>")


def _figure(b: Figure) -> str:
    src = b.src.strip()
    if re.match(r"(?i)^(https?:|javascript:|data:)", src):
        log.warning("blocks: dropping non-local figure src %r", src)
        return ""
    cap = f"<figcaption>{_e(b.caption)}</figcaption>" if b.caption else ""
    return (f'<figure class="b-figure" data-reveal><img src="{_e(src)}" '
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
    return (f'<div class="b-chartwrap" data-reveal>'
            f'<svg class="b-chart" viewBox="0 0 {w} {h}" '
            f'role="img" preserveAspectRatio="xMidYMid meet">'
            f'{"".join(body)}{labels}</svg></div>')


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
    return (f'<div class="b-tabs" data-reveal><div class="b-tablist" role="tablist">'
            f'{"".join(btns)}</div>{"".join(panels)}</div>')


def _collapsible(b: Collapsible) -> str:
    op = " open" if b.open else ""
    return (f'<details class="b-collapsible" data-reveal{op}>'
            f"<summary>{_e(b.summary)}</summary>"
            f"<div>{b.html}</div></details>")


def _steps(b: Steps) -> str:
    items = "".join(
        f'<li class="b-step"><div class="t">{_e(s.title)}</div>'
        + (f'<div class="d">{_e(s.body)}</div>' if s.body else "")
        + "</li>" for s in b.steps
    )
    return f'<ol class="b-steps" data-reveal>{items}</ol>'


def _diagram(b: DiagramSvg) -> str:
    return f'<div class="b-diagram" data-reveal>{sanitize_svg(b.svg)}</div>'


def _glossary(b: Glossary) -> str:
    items = "".join(f"<dt>{_e(t.term)}</dt><dd>{_e(t.definition)}</dd>"
                    for t in b.terms)
    return f'<dl class="b-glossary" data-reveal>{items}</dl>'


def _raw(b: RawHtml) -> str:
    return f'<div class="b-raw" data-reveal>{sanitize_inline(b.html)}</div>'


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
    if isinstance(block, Section):
        inner = render_blocks(block.blocks, ds_css)
        return (f'<section id="{_e(block.anchor)}" class="b-section">'
                f'<h2 class="b-section-h">{_e(block.title)}</h2>{inner}</section>')
    fn = _RENDERERS.get(type(block))
    if fn is None:
        log.warning("blocks: unknown block %r; skipped", type(block).__name__)
        return ""
    return fn(block)


def render_blocks(blocks: list[Block], ds_css: str = "") -> str:
    return "".join(render_block(b, ds_css) for b in blocks)


# --- page + site assembly ---------------------------------------------------

def _blocks_page_html(title: str, ds_css: str, body: str) -> str:
    """One blocks page: inline only its `--ds-*` tokens, link the shared engine
    (`assets/site.css` + `assets/site.js`). The tiny head script adds `js` to
    <html> so the reveal animation only hides content when JS is actually live —
    no-JS readers see everything."""
    head = (
        '<script>document.documentElement.classList.add("js")</script>\n'
        f"<style>{ds_css}</style>\n"
        '<link rel="stylesheet" href="assets/site.css">'
    )
    return (
        '<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>{_e(title)}</title>\n{head}\n</head>\n<body>\n{body}\n"
        '<script src="assets/site.js"></script>\n</body>\n</html>\n'
    )


def _page_doc_for(doc, cfg: dict, plan: SitePlan, use_ai: bool) -> PageDoc:
    """AI block tree at synthesize (with the architect's per-page artifacts),
    else the deterministic builder. The agent runs only when AI is enabled —
    `--no-ai` is always deterministic, regardless of fidelity."""
    if use_ai and cfg["site"].get("fidelity") == "synthesize":
        try:
            from .blocks_agent import run_page_blocks   # lazy: needs agno
            return run_page_blocks(doc, cfg,
                                   artifacts=plan.page_artifacts.get(doc.slug))
        except Exception as e:
            log.warning("blocks agent failed for %s (%s); deterministic page",
                        doc.slug, e)
            log.debug("blocks %s failure", doc.slug, exc_info=True)
    return build_page_doc(doc)


def _section_nav_html(page: PageDoc, plan: SitePlan, active_slug: str) -> str:
    """Sidebar built from THIS page's sections: the doc title, an anchor link per
    H2 section (the in-page table of contents), and — when the site has more than
    one doc — links to the others. Replaces one-file-one-link nav so a single
    large document is actually navigable."""
    secs = [b for b in page.blocks if isinstance(b, Section)]
    parts = ['<nav class="side">']
    parts.append(f'<a class="nav-doc active" href="#{_e(page.slug)}">'
                 f"{_e(page.title)}</a>")
    if secs:
        parts.append('<div class="nav-secs">')
        for s in secs:
            parts.append(f'<a href="#{_e(s.anchor)}">{_e(s.title)}</a>')
        parts.append("</div>")
    others = [n for n in plan.nav if n.slug != active_slug]
    if others:
        parts.append('<div class="group">More</div>')
        for n in others:
            parts.append(f'<a href="{_href(n.slug, False)}">{_e(n.title)}</a>')
    parts.append("</nav>")
    return "".join(parts)


def _render_doc_page(doc, plan: SitePlan, enh: PageEnhancement, cfg: dict,
                     use_ai: bool) -> str:
    accent = _accent(cfg, plan)
    ds_css = design_css_vars(_design_for(plan, accent))
    page = _page_doc_for(doc, cfg, plan, use_ai)
    nav = _section_nav_html(page, plan, doc.slug)
    enh_html = _enhancement_html(enh, plan, single_page=False)
    main = (f'<main id="{_e(doc.slug)}">{enh_html}'
            f"{render_blocks(page.blocks, ds_css=ds_css)}</main>")
    body = f'<div class="layout">{nav}{main}</div>'
    return _blocks_page_html(doc.title, ds_css, body)


def _render_index(plan: SitePlan, cfg: dict) -> str:
    accent = _accent(cfg, plan)
    ds_css = design_css_vars(_design_for(plan, accent))
    nav = _nav_html(plan, "", single_page=False)
    cards = "".join(
        f'<a class="b-card" href="{_href(n.slug, False)}"><h3>{_e(n.title)}</h3></a>'
        for n in plan.nav
    )
    intro = f"<p>{_e(plan.index_intro)}</p>" if plan.index_intro else ""
    main = (f'<main><header class="b-hero" data-reveal>'
            f"<h1>{_e(plan.index_title)}</h1></header>"
            f'{intro}<div class="b-cards" data-reveal>{cards}</div></main>')
    body = f'<div class="layout">{nav}{main}</div>'
    return _blocks_page_html(plan.index_title, ds_css, body)


def write_blocks_site(out_dir: Path, docs, plan: SitePlan,
                      enh: dict, cfg: dict, *, use_ai: bool) -> None:
    """Write a typed-block site: shared engine assets + one page per doc + index
    + design-system page."""
    out_dir.mkdir(parents=True, exist_ok=True)
    accent = _accent(cfg, plan)

    # The shared engine (design system + interaction JS), written once; pages link it.
    assets = out_dir / "assets"
    assets.mkdir(exist_ok=True)
    (assets / "site.css").write_text(SITE_CSS, encoding="utf-8")
    (assets / "site.js").write_text(SITE_JS, encoding="utf-8")
    log.info("blocks engine: assets/site.css (%d B) + assets/site.js (%d B)",
             len(SITE_CSS), len(SITE_JS))

    log.info("blocks site: %d doc(s), ai=%s, fidelity=%s, accent=%s",
             len(docs), "on" if use_ai else "off",
             cfg["site"].get("fidelity"), accent)
    for doc in docs:
        page_html = _render_doc_page(doc, plan, enh.get(doc.slug, PageEnhancement()),
                                     cfg, use_ai)
        (out_dir / f"{doc.slug}.html").write_text(page_html, encoding="utf-8")
        log.debug("wrote blocks page %s.html", doc.slug)
    (out_dir / "index.html").write_text(_render_index(plan, cfg), encoding="utf-8")
    (out_dir / "design-system.html").write_text(
        render_design_system_page(_design_for(plan, accent)), encoding="utf-8")
    _copy_diagrams(out_dir, docs)
    log.info("wrote blocks site to %s", out_dir)
