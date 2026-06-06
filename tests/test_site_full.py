from pathlib import Path
import pytest

import md2x.config as config
from md2x.site import full_render as fr
from md2x.site.schemas import Doc, NavItem, SitePlan


# --- page wrap + CSP --------------------------------------------------------

def test_render_full_page_injects_csp_and_tokens():
    fp = fr.FullPage(html="<h1>Hi</h1><p>body</p>", title="T")
    h = fr.render_full_page(fp, ":root{--ds-accent:#abc}")
    assert "<!doctype html" in h.lower()
    assert "Content-Security-Policy" in h and "default-src 'none'" in h
    assert "--ds-accent" in h
    assert "Hi" in h and "body" in h


def test_render_full_page_keeps_author_head_and_inline_script():
    fp = fr.FullPage(html=("<!doctype html><html><head><style>.x{color:red}</style>"
                           "</head><body><div id=app></div><script>window.ok=1</script>"
                           "</body></html>"), title="T")
    h = fr.render_full_page(fp, "")
    assert ".x{color:red}" in h                  # author head style kept
    assert "window.ok=1" in h                    # inline script kept
    assert h.count("Content-Security-Policy") == 1   # injected exactly once


# --- sanitizer --------------------------------------------------------------

def test_sanitize_full_strips_external_keeps_inline():
    s = fr.sanitize_full(
        '<script src="https://e/x.js"></script><script>let a=1</script>'
        '<link href="https://e/x.css" rel="stylesheet">'
        '<img src="https://e/x.png">')
    assert "https://e" not in s
    assert "let a=1" in s                        # inline script survives


def test_render_full_page_no_external_urls():
    fp = fr.FullPage(html='<p>ok</p><img src="https://cdn/x.png">', title="T")
    h = fr.render_full_page(fp, "")
    assert "http://" not in h and "https://" not in h


# --- site writer ------------------------------------------------------------

def _cfg():
    return config.deep_merge(config.DEFAULTS, {})


def test_write_full_site_standalone(tmp_path):
    cfg = _cfg()
    docs = [Doc(path=tmp_path / "intro.md", title="Intro", outline=["A"],
                fragment_html="<p>The quick brown fox.</p>"),
            Doc(path=tmp_path / "guide.md", title="Guide", outline=["B"],
                fragment_html="<p>Second page.</p>")]
    plan = SitePlan(nav=[NavItem(title=d.title, slug=d.slug) for d in docs],
                    order=[d.slug for d in docs])
    out = tmp_path / "out"
    fr.write_full_site(out, docs, plan, cfg, use_ai=False)
    assert (out / "index.html").exists() and (out / "intro.html").exists()
    assert (out / "design-system.html").exists()
    intro = (out / "intro.html").read_text()
    assert "default-src 'none'" in intro             # CSP locked down
    assert "The quick brown fox." in intro            # body preserved
    assert 'nav class="side"' not in intro            # standalone, no chrome
    assert "http://" not in intro and "https://" not in intro
    idx = (out / "index.html").read_text()
    assert 'href="intro.html"' in idx and 'href="guide.html"' in idx


# --- author agent -----------------------------------------------------------

def test_run_full_page_converts(monkeypatch):
    pytest.importorskip("agno")
    from md2x.site import full_agent

    class _Resp:
        content = full_agent._FullPageModel(
            html="<!doctype html><html><body>X</body></html>",
            title="Doc", export_format="markdown", export_label="Copy")

    class _Agent:
        def __init__(self, *a, **k):
            pass

        def run(self, prompt):
            return _Resp()

    monkeypatch.setattr(full_agent, "Agent", _Agent)
    monkeypatch.setattr(full_agent, "build_model", lambda ai, role: None)
    doc = Doc(path=Path("a.md"), title="A", outline=[], fragment_html="<p>x</p>")
    cfg = {"site": {"archetype": "explainer", "render_mode": "full",
                    "fidelity": "synthesize"},
           "ai": {"model": "x:y", "page_model": None, "retries": 1}}
    fp = full_agent.run_full_page(doc, cfg)
    assert "X" in fp.html
    assert fp.export is not None and fp.export.format == "markdown"
