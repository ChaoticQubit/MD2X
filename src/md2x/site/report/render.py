"""Render a ReportPage as a self-contained editorial-dashboard HTML page, and
orchestrate building + writing a report-archetype site.

All AI/derived text (dek, summary, stat values/labels, findings) is HTML-escaped
here; section bodies are the author's verbatim fragment HTML. CSS/JS are inlined
so the output deploys anywhere as static files (no CDN).
"""
from __future__ import annotations

import html
from pathlib import Path

from ...log import get_logger
from ..render import _DEFAULT_ACCENT, _SAFE_COLOR, _copy_diagrams
from .blocks import ReportPage, Section, build_report_page

log = get_logger(__name__)

_CSS = """\
:root{--accent:%ACCENT%;--bg:#fff;--fg:#1b1f24;--muted:#5b6470;--card:#f6f8fa;
 --border:#e2e6ea;--shadow:0 1px 2px rgba(0,0,0,.04),0 8px 24px rgba(0,0,0,.06);}
@media (prefers-color-scheme:dark){:root{--bg:#0c0f14;--fg:#e6edf3;--muted:#9aa4b2;
 --card:#161b22;--border:#272d36;--shadow:0 1px 2px rgba(0,0,0,.3),0 8px 24px rgba(0,0,0,.4);}}
*{box-sizing:border-box}
body{margin:0;color:var(--fg);background:var(--bg);
 font:16px/1.65 -apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif;
 -webkit-font-smoothing:antialiased}
a{color:var(--accent)}
.hero{padding:72px 24px 56px;text-align:center;color:#fff;
 background:linear-gradient(135deg,var(--accent),color-mix(in srgb,var(--accent) 55%,#000));}
.hero h1{margin:0 auto;max-width:18ch;font-size:clamp(2rem,5vw,3.2rem);
 letter-spacing:-.02em;line-height:1.1}
.hero .dek{margin:18px auto 0;max-width:60ch;font-size:1.15rem;opacity:.92}
.hero .kicker{text-transform:uppercase;letter-spacing:.16em;font-size:.72rem;
 font-weight:700;opacity:.8;margin-bottom:14px}
.wrap{max-width:960px;margin:0 auto;padding:0 24px 96px}
.toc{display:flex;flex-wrap:wrap;gap:8px;justify-content:center;margin:-22px auto 0;
 max-width:960px;padding:0 24px;position:relative}
.toc a{background:var(--bg);border:1px solid var(--border);border-radius:999px;
 padding:6px 14px;font-size:.85rem;text-decoration:none;color:var(--fg);box-shadow:var(--shadow)}
.toc a:hover{border-color:var(--accent);color:var(--accent)}
.exec{margin:40px 0 8px;background:var(--card);border:1px solid var(--border);
 border-left:4px solid var(--accent);border-radius:12px;padding:22px 26px;box-shadow:var(--shadow)}
.exec .label{text-transform:uppercase;letter-spacing:.12em;font-size:.72rem;
 font-weight:700;color:var(--accent);margin-bottom:8px}
.exec p{margin:0;font-size:1.08rem}
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));
 gap:16px;margin:28px 0}
.stat{background:var(--card);border:1px solid var(--border);border-radius:12px;
 padding:20px;box-shadow:var(--shadow)}
.stat .v{font-size:2rem;font-weight:750;letter-spacing:-.02em;color:var(--accent);line-height:1.1}
.stat .l{margin-top:6px;color:var(--muted);font-size:.9rem}
.findings{margin:28px 0;display:grid;gap:12px}
.callout{display:flex;gap:12px;align-items:flex-start;background:var(--card);
 border:1px solid var(--border);border-left:4px solid var(--accent);
 border-radius:10px;padding:14px 18px}
.callout .dot{flex:0 0 auto;width:22px;height:22px;border-radius:50%;
 background:var(--accent);color:#fff;display:grid;place-items:center;font-size:.8rem;font-weight:800}
.callout .l{font-size:.68rem;text-transform:uppercase;letter-spacing:.1em;
 color:var(--muted);font-weight:700;margin-bottom:2px}
section.sec{margin:48px 0 0;scroll-margin-top:18px}
section.sec>h2{font-size:1.6rem;letter-spacing:-.01em;margin:0 0 14px;
 padding-bottom:10px;border-bottom:2px solid var(--accent);display:inline-block}
section.sec :is(pre){background:var(--card);border:1px solid var(--border);
 padding:14px;border-radius:10px;overflow:auto}
section.sec code{background:var(--card);padding:.12em .35em;border-radius:5px}
section.sec table{width:100%;border-collapse:collapse;margin:16px 0;
 border:1px solid var(--border);border-radius:10px;overflow:hidden}
section.sec th,section.sec td{padding:10px 14px;border-bottom:1px solid var(--border);text-align:left}
section.sec thead th{background:var(--card);font-size:.85rem;text-transform:uppercase;
 letter-spacing:.04em;color:var(--muted)}
section.sec blockquote{margin:16px 0;padding:8px 18px;border-left:3px solid var(--accent);
 color:var(--muted)}
section.sec img{max-width:100%;height:auto;border-radius:10px}
footer.gen{max-width:960px;margin:48px auto 0;padding:24px;color:var(--muted);
 font-size:.82rem;text-align:center;border-top:1px solid var(--border)}
"""


def _accent(cfg: dict) -> str:
    value = (cfg["site"]["theme"].get("accent") or "").strip()
    if not _SAFE_COLOR.match(value):
        log.warning("ignoring unsafe accent color %r; using default %s",
                    value, _DEFAULT_ACCENT)
        return _DEFAULT_ACCENT
    return value


def _e(text: str) -> str:
    return html.escape(text or "", quote=True)


def _section_html(sec: Section) -> str:
    anchor = _e(sec.title.lower().replace(" ", "-"))
    # sec.html is the author's verbatim fragment HTML — intentionally not escaped.
    return (f'<section class="sec" id="{anchor}">'
            f"<h2>{_e(sec.title)}</h2>{sec.html}</section>")


def render_report(page: ReportPage, accent: str) -> str:
    """Editorial-dashboard HTML for one ReportPage."""
    hero = (
        '<header class="hero"><div class="kicker">Report</div>'
        f"<h1>{_e(page.title)}</h1>"
        + (f'<p class="dek">{_e(page.dek)}</p>' if page.dek else "")
        + "</header>"
    )
    toc = ""
    titled = [s for s in page.sections if s.title]
    if len(titled) > 1:
        links = "".join(
            f'<a href="#{_e(s.title.lower().replace(" ", "-"))}">{_e(s.title)}</a>'
            for s in titled
        )
        toc = f'<nav class="toc">{links}</nav>'

    parts = ['<div class="wrap">']
    if page.summary:
        parts.append('<div class="exec"><div class="label">Executive summary</div>'
                     f"<p>{_e(page.summary)}</p></div>")
    if page.stats:
        cards = "".join(f'<div class="stat"><div class="v">{_e(s.value)}</div>'
                        f'<div class="l">{_e(s.label)}</div></div>'
                        for s in page.stats)
        parts.append(f'<div class="stats">{cards}</div>')
    if page.findings:
        items = "".join(
            '<div class="callout"><div class="dot">!</div><div>'
            f'<div class="l">{_e(c.label)}</div>{_e(c.text)}</div></div>'
            for c in page.findings
        )
        parts.append(f'<div class="findings">{items}</div>')
    for sec in page.sections:
        parts.append(_section_html(sec))
    parts.append('<footer class="gen">Generated by md2x · editorial report</footer>')
    parts.append("</div>")

    css = _CSS.replace("%ACCENT%", accent)
    return (
        '<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>{_e(page.title)}</title>\n<style>{css}</style>\n</head>\n<body>\n"
        f'{hero}\n{toc}\n{"".join(parts)}\n</body>\n</html>\n'
    )


def _render_index(pages: list[ReportPage], accent: str, cfg: dict) -> str:
    title = cfg["site"].get("title") or "Reports"
    cards = "".join(
        f'<a class="stat" href="{_e(p.slug)}.html" style="text-decoration:none">'
        f'<div class="v" style="font-size:1.2rem">{_e(p.title)}</div>'
        f'<div class="l">{_e(p.dek)}</div></a>'
        for p in pages
    )
    css = _CSS.replace("%ACCENT%", accent)
    return (
        '<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>{_e(title)}</title>\n<style>{css}</style>\n</head>\n<body>\n"
        f'<header class="hero"><div class="kicker">Reports</div><h1>{_e(title)}</h1></header>\n'
        f'<div class="wrap"><div class="stats">{cards}</div></div>\n</body>\n</html>\n'
    )


def generate_report_site(docs, out_dir: Path, cfg: dict, *, use_ai: bool) -> int:
    """Build + render + write an editorial-report site (one page per doc)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    accent = _accent(cfg)
    log.info("report site: %d doc(s), ai=%s, accent=%s",
             len(docs), "on" if use_ai else "off", accent)

    pages: list[ReportPage] = []
    for doc in docs:
        if use_ai:
            try:
                from .agent import run_report_page  # lazy: needs agno
                page = run_report_page(doc, cfg)
            except Exception as e:
                log.warning("report agent failed for %s (%s); deterministic page",
                            doc.slug, e)
                log.debug("report %s failure", doc.slug, exc_info=True)
                page = build_report_page(doc)
        else:
            page = build_report_page(doc)
        (out_dir / f"{doc.slug}.html").write_text(
            render_report(page, accent), encoding="utf-8")
        log.debug("wrote report %s.html", doc.slug)
        pages.append(page)

    if len(pages) == 1:
        (out_dir / "index.html").write_text(
            render_report(pages[0], accent), encoding="utf-8")
    else:
        (out_dir / "index.html").write_text(
            _render_index(pages, accent, cfg), encoding="utf-8")
    _copy_diagrams(out_dir, docs)
    log.info("wrote report site to %s", out_dir)
    return 0
