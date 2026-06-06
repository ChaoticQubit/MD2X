"""`full` render mode: standalone, CSP-locked author pages.

In full mode the model authors one self-contained interactive HTML document per
page (max fidelity). The page is served standalone — a bare file linked from the
index, no md2x chrome — but locked down: a CSP `<meta>` of `default-src 'none'`
plus `sanitize_full` strip every external/network reference, so the page can run
its own inline JS yet cannot fetch, phone home, or pull remote code. Inline
scripts/styles are intentionally kept; the CSP is the real network boundary and
the sanitizer is defense-in-depth.

Pure-Python (no agno) — the author agent lives in full_agent.py and is imported
lazily, so `--no-ai` / `fidelity: preserve` never need the [ai] extra.
"""
from __future__ import annotations

import html
import re
from dataclasses import dataclass
from pathlib import Path

from ..log import get_logger
from .blocks import Export
from .design_css import design_css_vars, render_design_system_page
from .render import _accent, _copy_diagrams, _design_for
from .sanitize import sanitize_full
from .schemas import SitePlan

log = get_logger(__name__)


@dataclass
class FullPage:
    html: str                              # author's document (full doc or fragment)
    title: str = ""
    export: "Export | None" = None


_FULL_CSP = ("default-src 'none'; style-src 'unsafe-inline'; "
             "script-src 'unsafe-inline'; img-src data:; font-src data:")


def _e(text) -> str:
    return html.escape("" if text is None else str(text), quote=True)


# sanitize_full is the canonical sanitizer from sanitize.py, imported above and
# re-exposed here for callers that reference it on this module.


# --- standalone page assembly -----------------------------------------------

_HEAD_RE = re.compile(r"(?i)(<head[^>]*>)")
_HTML_RE = re.compile(r"(?i)(<html[^>]*>)")


def render_full_page(fp: FullPage, ds_css: str) -> str:
    """Inject the CSP + design tokens into the author's document, then sanitize.

    Handles a full author document (inject into its <head>), an <html> without a
    head, or a bare fragment (wrap it). The CSP meta is a real tag here (not an
    escaped srcdoc), so it is enforced by the browser."""
    inject = (f'<meta http-equiv="Content-Security-Policy" content="{_FULL_CSP}">'
              f"<style>{ds_css}</style>")
    doc = fp.html or ""
    if _HEAD_RE.search(doc):
        doc = _HEAD_RE.sub(r"\1" + inject, doc, count=1)
    elif _HTML_RE.search(doc):
        doc = _HTML_RE.sub(r"\1<head><meta charset=\"utf-8\">" + inject + "</head>",
                           doc, count=1)
    else:
        doc = (
            '<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
            f"{inject}\n<title>{_e(fp.title)}</title>\n</head>\n<body>\n{doc}\n"
            "</body>\n</html>\n"
        )
    return sanitize_full(doc)


def _deterministic_page(doc) -> FullPage:
    """No-AI / fallback: wrap the verbatim fragment as a minimal standalone page."""
    body = (f'<main style="max-width:760px;margin:0 auto;padding:48px 24px;'
            f'font-family:var(--ds-font-sans,system-ui);color:var(--ds-fg,#1f2328);'
            f'background:var(--ds-bg,#fff)">'
            f"<h1>{_e(doc.title)}</h1>{doc.fragment_html}</main>")
    return FullPage(html=body, title=doc.title)


def _index_html(plan: SitePlan, ds_css: str) -> str:
    links = "".join(
        f'<li><a href="{_e(n.slug)}.html">{_e(n.title)}</a></li>' for n in plan.nav
    )
    return (
        '<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f'<meta http-equiv="Content-Security-Policy" content="{_FULL_CSP}">\n'
        f"<style>{ds_css}*{{box-sizing:border-box}}body{{margin:0;"
        "font-family:var(--ds-font-sans,system-ui);color:var(--ds-fg,#1f2328);"
        "background:var(--ds-bg,#fff);max-width:760px;margin:0 auto;padding:48px 24px}"
        "a{color:var(--ds-accent,#2563eb)}li{margin:8px 0}</style>\n"
        f"<title>{_e(plan.index_title)}</title>\n</head>\n<body>\n"
        f"<h1>{_e(plan.index_title)}</h1>\n<ul>{links}</ul>\n</body>\n</html>\n"
    )


def write_full_site(out_dir: Path, docs, plan: SitePlan, cfg: dict,
                    *, use_ai: bool) -> None:
    """Write one standalone CSP-locked page per doc + an index + design-system."""
    out_dir.mkdir(parents=True, exist_ok=True)
    accent = _accent(cfg, plan)
    ds_css = design_css_vars(_design_for(plan, accent))
    fidelity = cfg["site"].get("fidelity")
    log.info("full site: %d doc(s), ai=%s, fidelity=%s",
             len(docs), "on" if use_ai else "off", fidelity)
    for doc in docs:
        if use_ai and fidelity != "preserve":
            try:
                from .full_agent import run_full_page   # lazy: needs agno
                fp = run_full_page(doc, cfg,
                                   artifacts=plan.page_artifacts.get(doc.slug))
            except Exception as e:
                log.warning("full agent failed for %s (%s); deterministic page",
                            doc.slug, e)
                log.debug("full %s failure", doc.slug, exc_info=True)
                fp = _deterministic_page(doc)
        else:
            fp = _deterministic_page(doc)
        (out_dir / f"{doc.slug}.html").write_text(
            render_full_page(fp, ds_css), encoding="utf-8")
        log.debug("wrote full page %s.html", doc.slug)
    (out_dir / "index.html").write_text(_index_html(plan, ds_css), encoding="utf-8")
    (out_dir / "design-system.html").write_text(
        render_design_system_page(_design_for(plan, accent)), encoding="utf-8")
    _copy_diagrams(out_dir, docs)
    log.info("wrote full site to %s", out_dir)
