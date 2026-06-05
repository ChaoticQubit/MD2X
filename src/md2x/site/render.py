"""Assemble HTML pages from fragments + plan + enhancements, and write the site.

Three shells (sidebar / deck / landing) selected by the archetype, so sites
look genuinely different. Self-contained output: shared local assets for the
multi-page sidebar, fully inlined for single-file shells. No external CDN, so
the result deploys anywhere as static files.
"""
from __future__ import annotations

import html
import re
import shutil
from pathlib import Path

from ..log import get_logger
from .archetypes import get_shell
from .schemas import Doc, NavItem, SitePlan, PageEnhancement

log = get_logger(__name__)

# --- shared base + per-shell CSS (%ACCENT% substituted at write time) -------

_BASE_CSS = """\
:root { --accent: %ACCENT%; --bg:#fff; --fg:#1f2328; --muted:#57606a;
        --card:#f6f8fa; --border:#d0d7de; }
@media (prefers-color-scheme: dark) {
  :root { --bg:#0d1117; --fg:#e6edf3; --muted:#9198a1; --card:#161b22; --border:#30363d; } }
* { box-sizing:border-box; }
body { margin:0; font:16px/1.65 -apple-system,BlinkMacSystemFont,"Segoe UI",
       Helvetica,Arial,sans-serif; color:var(--fg); background:var(--bg); }
a { color:var(--accent); }
img { max-width:100%; height:auto; }
pre { background:var(--card); padding:14px; border-radius:8px; overflow:auto; }
code { background:var(--card); padding:.1em .3em; border-radius:4px; }
.tldr { background:var(--card); border-left:3px solid var(--accent);
       padding:12px 16px; border-radius:6px; margin:0 0 24px; }
.takeaways { background:var(--card); border:1px solid var(--border);
       border-radius:8px; padding:12px 20px; margin:24px 0; }
.related a { color:var(--accent); }
"""

_SIDEBAR_CSS = """\
.layout { display:flex; min-height:100vh; }
nav.side { width:260px; flex:0 0 260px; border-right:1px solid var(--border);
       padding:24px 18px; position:sticky; top:0; height:100vh; overflow:auto; }
nav.side a { display:block; color:var(--fg); text-decoration:none; padding:6px 8px;
       border-radius:6px; }
nav.side a:hover, nav.side a.active { background:var(--card); color:var(--accent); }
nav.side .group { color:var(--muted); font-size:12px; text-transform:uppercase;
       letter-spacing:.04em; margin:16px 8px 4px; }
main { flex:1; max-width:820px; margin:0 auto; padding:48px 32px 96px; }
.cards { display:grid; grid-template-columns:repeat(auto-fill,minmax(220px,1fr));
       gap:16px; }
.card { border:1px solid var(--border); border-radius:10px; padding:18px;
       background:var(--card); text-decoration:none; color:var(--fg);
       transition:transform .12s ease, box-shadow .12s ease; }
.card:hover { transform:translateY(-2px); box-shadow:0 6px 20px rgba(0,0,0,.08); }
"""

_DECK_CSS = """\
html, body { height:100%; }
.deck { scroll-snap-type:y mandatory; overflow-y:auto; height:100vh; }
section.slide { scroll-snap-align:start; min-height:100vh; display:flex;
       flex-direction:column; justify-content:center; padding:8vh 10vw;
       border-bottom:1px solid var(--border); }
section.slide h1 { font-size:clamp(2rem,5vw,3.5rem); margin:.2em 0; }
.deck-dots { position:fixed; right:18px; top:50%; transform:translateY(-50%);
       display:flex; flex-direction:column; gap:10px; }
.deck-dots a { width:10px; height:10px; border-radius:50%; background:var(--border); }
"""

_LANDING_CSS = """\
.hero { padding:18vh 8vw 12vh; text-align:center;
       background:linear-gradient(160deg,var(--card),var(--bg)); }
.hero h1 { font-size:clamp(2.2rem,6vw,4rem); margin:0 0 .3em; }
.hero p { color:var(--muted); font-size:1.25rem; max-width:48ch; margin:0 auto; }
section.block { max-width:920px; margin:0 auto; padding:8vh 6vw; opacity:0;
       transform:translateY(24px); transition:opacity .6s ease, transform .6s ease; }
section.block.in { opacity:1; transform:none; }
"""

SHELLS = {
    "sidebar": _BASE_CSS + _SIDEBAR_CSS,
    "deck": _BASE_CSS + _DECK_CSS,
    "landing": _BASE_CSS + _LANDING_CSS,
}

_SMOOTH_JS = ('document.querySelectorAll(\'a[href^="#"]\').forEach(function(a){'
              'a.addEventListener("click",function(e){var el=document.querySelector('
              'a.getAttribute("href"));if(el){e.preventDefault();'
              'el.scrollIntoView({behavior:"smooth"});}});});')

_DECK_JS = ('(function(){var s=[].slice.call(document.querySelectorAll('
            '"section.slide"));var i=0;function go(n){i=Math.max(0,Math.min('
            's.length-1,n));if(s[i])s[i].scrollIntoView({behavior:"smooth"});}'
            'document.addEventListener("keydown",function(e){'
            'if(e.key==="ArrowDown"||e.key==="PageDown"||e.key===" "){'
            'e.preventDefault();go(i+1);}'
            'if(e.key==="ArrowUp"||e.key==="PageUp"){e.preventDefault();go(i-1);}'
            '});})();')

_LANDING_JS = ('var io=new IntersectionObserver(function(es){es.forEach('
               'function(en){if(en.isIntersecting)en.target.classList.add("in");'
               '});},{threshold:.15});document.querySelectorAll("section.block")'
               '.forEach(function(b){io.observe(b);});')

SHELL_JS = {"sidebar": _SMOOTH_JS, "deck": _DECK_JS, "landing": _LANDING_JS}

# A conservative CSS-color allowlist: #hex (3-8 digits), a bare CSS keyword
# (e.g. "rebeccapurple"), or rgb()/rgba()/hsl()/hsla() function forms. Anything
# else is rejected so an AI- or config-supplied accent can never break out of
# the <style> block.
_SAFE_COLOR = re.compile(
    r"^#[0-9a-fA-F]{3,8}$"
    r"|^[a-zA-Z]{2,32}$"
    r"|^(rgb|rgba|hsl|hsla)\([0-9.,%\s/]+\)$"
)
_DEFAULT_ACCENT = "#2563eb"


# --- helpers ----------------------------------------------------------------

def _accent(cfg: dict, plan: SitePlan) -> str:
    value = (plan.theme_accent or cfg["site"]["theme"]["accent"] or "").strip()
    if not _SAFE_COLOR.match(value):
        log.warning("ignoring unsafe accent color %r; using default %s",
                    value, _DEFAULT_ACCENT)
        return _DEFAULT_ACCENT
    return value


def _href(slug: str, single_page: bool) -> str:
    """Build a safe in-page or cross-page href from a slug."""
    return html.escape(f"#{slug}" if single_page else f"{slug}.html", quote=True)


def _shell_for(cfg: dict) -> str:
    return get_shell(cfg["site"]["archetype"])


def default_site_plan(docs: list[Doc], cfg: dict) -> SitePlan:
    """Deterministic plan used by --no-ai and as the agent-failure fallback."""
    nav = [NavItem(title=d.title, slug=d.slug) for d in docs]
    return SitePlan(nav=nav, order=[d.slug for d in docs],
                    index_title=cfg["site"].get("title") or "Documentation")


def _nav_html(plan: SitePlan, active_slug: str, single_page: bool) -> str:
    parts = ['<nav class="side">']
    last_group = None
    for item in plan.nav:
        if item.group and item.group != last_group:
            parts.append(f'<div class="group">{html.escape(item.group)}</div>')
            last_group = item.group
        href = _href(item.slug, single_page)
        cls = " class=\"active\"" if item.slug == active_slug else ""
        parts.append(f'<a href="{href}"{cls}>{html.escape(item.title)}</a>')
    parts.append("</nav>")
    return "".join(parts)


def _enhancement_html(enh: PageEnhancement, plan: SitePlan,
                      single_page: bool) -> str:
    out = []
    if enh.tldr:
        out.append(f'<div class="tldr"><strong>TL;DR</strong> '
                   f'{html.escape(enh.tldr)}</div>')
    blocks = []
    if enh.takeaways:
        items = "".join(f"<li>{html.escape(t)}</li>" for t in enh.takeaways)
        blocks.append(f"<strong>Key takeaways</strong><ul>{items}</ul>")
    if enh.related:
        title_by = {n.slug: n.title for n in plan.nav}
        # Only link slugs that map to a real page. The LLM sometimes returns an
        # invented slug (e.g. derived from a title), which would otherwise be
        # rendered as a dead <slug>.html link.
        links = []
        for slug in enh.related:
            if slug not in title_by:
                continue
            href = _href(slug, single_page)
            links.append(f'<a href="{href}">{html.escape(title_by[slug])}</a>')
        if links:
            blocks.append('<strong>Related</strong> <span class="related">'
                          + " · ".join(links) + "</span>")
    if blocks:
        out.append('<div class="takeaways">' + "".join(blocks) + "</div>")
    return "".join(out)


def _document(title: str, shell: str, accent: str, body: str,
              *, assets_inline: bool) -> str:
    if assets_inline:
        head = f"<style>{SHELLS[shell].replace('%ACCENT%', accent)}</style>"
        tail = f"<script>{SHELL_JS[shell]}</script>"
    else:
        head = '<link rel="stylesheet" href="assets/site.css">'
        tail = '<script src="assets/site.js"></script>'
    return (
        "<!doctype html>\n<html lang=\"en\">\n<head>\n"
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>{html.escape(title)}</title>\n{head}\n</head>\n<body>\n"
        f"{body}\n{tail}\n</body>\n</html>\n"
    )


# --- sidebar shell ----------------------------------------------------------

def build_page(doc: Doc, plan: SitePlan, enh: PageEnhancement, cfg: dict,
               *, assets_inline: bool) -> str:
    accent = _accent(cfg, plan)
    nav = _nav_html(plan, doc.slug, single_page=False)
    enh_html = _enhancement_html(enh, plan, single_page=False)
    body = (
        f'<div class="layout">{nav}<main id="{html.escape(doc.slug, quote=True)}">'
        f"<h1>{html.escape(doc.title)}</h1>{enh_html}{doc.fragment_html}"
        f"</main></div>"
    )
    return _document(doc.title, "sidebar", accent, body,
                     assets_inline=assets_inline)


def build_index(plan: SitePlan, cfg: dict, *, assets_inline: bool) -> str:
    accent = _accent(cfg, plan)
    nav = _nav_html(plan, "", single_page=False)
    cards = "".join(
        f'<a class="card" href="{_href(n.slug, single_page=False)}"><h3>{html.escape(n.title)}</h3></a>'
        for n in plan.nav
    )
    intro = f"<p>{html.escape(plan.index_intro)}</p>" if plan.index_intro else ""
    body = (
        f'<div class="layout">{nav}<main>'
        f"<h1>{html.escape(plan.index_title)}</h1>{intro}"
        f'<div class="cards">{cards}</div></main></div>'
    )
    return _document(plan.index_title, "sidebar", accent, body,
                     assets_inline=assets_inline)


def build_single_page(docs: list[Doc], plan: SitePlan,
                      enh: dict[str, PageEnhancement], cfg: dict) -> str:
    accent = _accent(cfg, plan)
    nav = _nav_html(plan, "", single_page=True)
    by_slug = {d.slug: d for d in docs}
    sections = []
    for slug in plan.order:
        doc = by_slug.get(slug)
        if not doc:
            continue
        e_html = _enhancement_html(enh.get(slug, PageEnhancement()), plan,
                                   single_page=True)
        sections.append(
            f'<section id="{html.escape(slug, quote=True)}">'
            f"<h1>{html.escape(doc.title)}</h1>"
            f"{e_html}{doc.fragment_html}</section>"
        )
    body = f'<div class="layout">{nav}<main>' + "".join(sections) + "</main></div>"
    return _document(plan.index_title, "sidebar", accent, body,
                     assets_inline=True)


# --- deck shell (single file) ----------------------------------------------

def build_deck(docs: list[Doc], plan: SitePlan,
               enh: dict[str, PageEnhancement], cfg: dict) -> str:
    accent = _accent(cfg, plan)
    by_slug = {d.slug: d for d in docs}
    slides = []
    dots = ['<div class="deck-dots">']
    for slug in plan.order:
        doc = by_slug.get(slug)
        if not doc:
            continue
        e_html = _enhancement_html(enh.get(slug, PageEnhancement()), plan,
                                   single_page=True)
        slides.append(
            f'<section class="slide" id="{html.escape(slug, quote=True)}">'
            f"<h1>{html.escape(doc.title)}</h1>{e_html}{doc.fragment_html}"
            f"</section>"
        )
        dots.append(f'<a href="{_href(slug, single_page=True)}"></a>')
    dots.append("</div>")
    body = f'<div class="deck">{"".join(slides)}</div>{"".join(dots)}'
    return _document(plan.index_title, "deck", accent, body, assets_inline=True)


# --- landing shell (single file) -------------------------------------------

def build_landing(docs: list[Doc], plan: SitePlan,
                  enh: dict[str, PageEnhancement], cfg: dict) -> str:
    accent = _accent(cfg, plan)
    by_slug = {d.slug: d for d in docs}
    intro = html.escape(plan.index_intro) if plan.index_intro else ""
    hero = (f'<header class="hero"><h1>{html.escape(plan.index_title)}</h1>'
            f"<p>{intro}</p></header>")
    blocks = []
    for slug in plan.order:
        doc = by_slug.get(slug)
        if not doc:
            continue
        e_html = _enhancement_html(enh.get(slug, PageEnhancement()), plan,
                                   single_page=True)
        blocks.append(
            f'<section class="block" id="{html.escape(slug, quote=True)}">'
            f"<h2>{html.escape(doc.title)}</h2>{e_html}{doc.fragment_html}"
            f"</section>"
        )
    body = hero + "".join(blocks)
    return _document(plan.index_title, "landing", accent, body,
                     assets_inline=True)


# --- diagram copy + dispatch ------------------------------------------------

def _copy_diagrams(out_dir: Path, docs: list[Doc]) -> None:
    """Copy each doc's per-slug diagrams into out_dir/diagrams/<slug>/."""
    for doc in docs:
        src = doc.path.parent / "diagrams" / doc.slug
        if src.is_dir():
            dest = out_dir / "diagrams" / doc.slug
            dest.mkdir(parents=True, exist_ok=True)
            for png in src.glob("*.png"):
                shutil.copy2(png, dest / png.name)


def write_site(out_dir: Path, docs: list[Doc], plan: SitePlan,
               enh: dict[str, PageEnhancement], cfg: dict, *, layout: str) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    shell = _shell_for(cfg)
    log.info("rendering: shell=%s layout=%s -> %s", shell, layout, out_dir)

    if shell == "deck":
        (out_dir / "index.html").write_text(
            build_deck(docs, plan, enh, cfg), encoding="utf-8")
    elif shell == "landing":
        (out_dir / "index.html").write_text(
            build_landing(docs, plan, enh, cfg), encoding="utf-8")
    elif layout == "single-page":
        (out_dir / "index.html").write_text(
            build_single_page(docs, plan, enh, cfg), encoding="utf-8")
    else:  # sidebar, multi-page: shared assets + one file per doc + index
        assets = out_dir / "assets"
        assets.mkdir(exist_ok=True)
        accent = _accent(cfg, plan)
        (assets / "site.css").write_text(
            SHELLS["sidebar"].replace("%ACCENT%", accent), encoding="utf-8")
        (assets / "site.js").write_text(SHELL_JS["sidebar"], encoding="utf-8")
        for doc in docs:
            page = build_page(doc, plan, enh.get(doc.slug, PageEnhancement()),
                              cfg, assets_inline=False)
            (out_dir / f"{doc.slug}.html").write_text(page, encoding="utf-8")
            log.debug("wrote %s.html", doc.slug)
        (out_dir / "index.html").write_text(
            build_index(plan, cfg, assets_inline=False), encoding="utf-8")
        log.info("wrote %d page(s) + index + shared assets", len(docs))

    _copy_diagrams(out_dir, docs)
