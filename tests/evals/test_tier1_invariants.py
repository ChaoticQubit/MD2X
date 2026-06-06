"""Tier-1 evals: deterministic structural invariants over generated sites.

These run in CI on every push — no LLM, no pandoc. Docs are constructed directly
and the writers are exercised on the deterministic (no-AI) path, then the output
HTML is checked against the contract every render mode must uphold.
"""
import re
from pathlib import Path

import md2x.config as config
from md2x.site.blocks_render import write_blocks_site
from md2x.site.full_render import write_full_site
from md2x.site.render import default_site_plan
from md2x.site.sanitize import is_self_contained
from md2x.site.schemas import Doc, PageEnhancement

_SIZE_CAP = 300_000  # bytes per page — catches runaway output

_HREF = re.compile(r'href="([^"]+\.html)"')


def _docs():
    return [
        Doc(path=Path("intro.md"), title="Intro", outline=["Overview"],
            fragment_html="<p>The quick brown fox jumps.</p>"
                          '<h2>Detail</h2><p>More body text.</p>'
                          '<img src="diagrams/intro/d.png" alt="a diagram">'),
        Doc(path=Path("guide.md"), title="Guide", outline=["Steps"],
            fragment_html="<p>Second document body.</p>"),
    ]


def _cfg(**site):
    cfg = config.deep_merge(config.DEFAULTS, {})
    cfg["site"].update(site)
    return cfg


def _pages(out: Path):
    return list(out.glob("*.html"))


def _assert_common(out: Path, docs):
    # every doc -> a page
    for d in docs:
        assert (out / f"{d.slug}.html").exists(), f"missing page for {d.slug}"
    assert (out / "index.html").exists()
    for page in _pages(out):
        html = page.read_text(encoding="utf-8")
        assert "<!doctype html" in html.lower() and "</html>" in html.lower(), \
            f"{page.name} not a complete document"
        assert "<h1" in html, f"{page.name} has no top-level heading"
        assert len(html.encode("utf-8")) < _SIZE_CAP, f"{page.name} over size cap"
        assert is_self_contained(html), f"{page.name} loads a remote resource"
        # a11y: every <img> carries alt
        for img in re.findall(r"<img\b[^>]*>", html):
            assert "alt=" in img, f"{page.name} has an <img> without alt"


def _assert_links_resolve(out: Path):
    index = (out / "index.html").read_text(encoding="utf-8")
    for href in _HREF.findall(index):
        target = href.split("#", 1)[0].split("?", 1)[0]
        assert (out / target).exists(), f"broken internal link: {href}"


def test_blocks_mode_invariants(tmp_path):
    cfg = _cfg(archetype="reading", render_mode="blocks")
    docs = _docs()
    plan = default_site_plan(docs, cfg)
    enh = {d.slug: PageEnhancement() for d in docs}
    out = tmp_path / "blocks"
    write_blocks_site(out, docs, plan, enh, cfg, use_ai=False)
    _assert_common(out, docs)
    _assert_links_resolve(out)
    for page in _pages(out):
        assert "--ds-" in page.read_text(encoding="utf-8"), \
            f"{page.name} missing design tokens"


def test_full_mode_invariants(tmp_path):
    cfg = _cfg(archetype="explainer", render_mode="full")
    docs = _docs()
    plan = default_site_plan(docs, cfg)
    out = tmp_path / "full"
    write_full_site(out, docs, plan, cfg, use_ai=False)
    _assert_common(out, docs)
    _assert_links_resolve(out)
    for page in _pages(out):
        html = page.read_text(encoding="utf-8")
        assert "--ds-" in html, f"{page.name} missing design tokens"
        assert "default-src 'none'" in html, f"{page.name} missing CSP lockdown"
