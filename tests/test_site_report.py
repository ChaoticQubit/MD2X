from pathlib import Path

import pytest

from md2x.site.report import (
    ReportPage,
    Stat,
    build_report_page,
    generate_report_site,
    render_report,
)
from md2x.site.report.blocks import extract_stats, split_sections


def _doc(tmp="q.md", title="Quarterly Report", html=None):
    from md2x.site.schemas import Doc
    html = html or (
        "<p>Revenue rose 20% to $1.4M this quarter, our best yet.</p>"
        '<h2 id="rev">Revenue</h2><p>Up 20% year over year.</p>'
        '<h2 id="risks">Risks</h2><blockquote>Watch churn.</blockquote>'
    )
    return Doc(path=Path(tmp), title=title, outline=["Revenue", "Risks"],
               fragment_html=html)


# --- deterministic builder --------------------------------------------------

def test_split_sections_splits_on_h2_and_keeps_body_verbatim():
    html = '<p>intro</p><h2>One</h2><p>a <b>bold</b></p><h2>Two</h2><p>b</p>'
    intro, secs = split_sections(html)
    assert intro == "<p>intro</p>"
    assert [s.title for s in secs] == ["One", "Two"]
    assert "<b>bold</b>" in secs[0].html  # author HTML untouched


def test_split_sections_no_h2_returns_no_sections():
    intro, secs = split_sections("<p>just prose</p>")
    assert secs == []


def test_extract_stats_keeps_units_drops_bare_numbers():
    stats = extract_stats("We saw 20% growth, $1.4M revenue, and 3 outages.")
    values = [s.value for s in stats]
    assert any("%" in v for v in values)
    assert any("$" in v for v in values)
    assert "3" not in values  # bare integer dropped (no unit)


def test_build_report_page_from_doc():
    page = build_report_page(_doc())
    assert isinstance(page, ReportPage)
    assert page.title == "Quarterly Report"
    assert [s.title for s in page.sections] == ["Revenue", "Risks"]
    assert page.dek and page.summary           # derived from intro paragraph
    assert page.stats                          # 20% / $1.4M extracted


# --- renderer ---------------------------------------------------------------

def test_render_report_has_dashboard_blocks():
    page = build_report_page(_doc())
    out = render_report(page, "#2563eb")
    assert "<!doctype html>" in out
    assert "Quarterly Report" in out
    assert "Executive summary" in out
    assert 'class="stats"' in out and 'class="stat"' in out
    assert "Revenue" in out and "Risks" in out
    assert "Watch churn." in out  # verbatim section body rendered


def test_render_report_escapes_ai_text_xss():
    page = ReportPage(slug="x", title="T", dek="<script>alert(1)</script>",
                      summary="ok", stats=[Stat(value="<img src=x>", label="l")],
                      sections=[])
    out = render_report(page, "#2563eb")
    assert "<script>alert(1)</script>" not in out
    assert "&lt;script&gt;" in out
    assert "<img src=x>" not in out


def test_render_report_rejects_unsafe_accent_via_generate(tmp_path):
    # accent validation happens in generate_report_site's _accent()
    cfg = {"site": {"title": None, "theme": {"accent": "red; }body{display:none"}}}
    rc = generate_report_site([_doc()], tmp_path, cfg, use_ai=False)
    assert rc == 0
    html = (tmp_path / "index.html").read_text()
    assert "display:none" not in html  # unsafe accent ignored


# --- orchestration (no AI) --------------------------------------------------

def test_generate_report_site_single_doc_writes_index(tmp_path):
    cfg = {"site": {"title": None, "theme": {"accent": "#2563eb"}}}
    rc = generate_report_site([_doc()], tmp_path, cfg, use_ai=False)
    assert rc == 0
    assert (tmp_path / "index.html").exists()
    assert (tmp_path / "q.html").exists()
    assert "Executive summary" in (tmp_path / "index.html").read_text()


# --- AI path (guardrails / merge) -------------------------------------------

def test_run_report_page_merges_and_caps(monkeypatch):
    pytest.importorskip("agno")
    from md2x.site.report import agent as ag

    class FakeResp:
        content = ag._ReportTopModel(
            dek="AI dek", summary="AI summary.",
            stats=[ag._StatModel(value=f"{i}%", label=f"m{i}") for i in range(6)],
            findings=["f1", "", "  ", "f2", "f3", "f4"],
        )

    class FakeAgent:
        def __init__(self, *a, **k): pass
        def run(self, prompt): return FakeResp()

    monkeypatch.setattr(ag, "Agent", FakeAgent)
    cfg = {"site": {"fidelity": "synthesize", "theme": {"accent": "#2563eb"}},
           "ai": {"model": "x:y", "page_model": None, "temperature": 0.4,
                  "max_tokens": None, "retries": 1}}
    page = ag.run_report_page(_doc(), cfg)
    assert page.dek == "AI dek"
    assert page.summary == "AI summary."
    assert len(page.stats) == 4          # capped
    assert len(page.findings) == 3       # capped + empties dropped
    assert [c.text for c in page.findings] == ["f1", "f2", "f3"]
    # sections still come from the author's HTML, verbatim
    assert [s.title for s in page.sections] == ["Revenue", "Risks"]


def test_run_report_page_preserve_skips_agent(monkeypatch):
    pytest.importorskip("agno")
    from md2x.site.report import agent as ag

    def _boom(*a, **k):
        raise AssertionError("agent must not be constructed under fidelity=preserve")

    monkeypatch.setattr(ag, "Agent", _boom)
    cfg = {"site": {"fidelity": "preserve", "theme": {"accent": "#2563eb"}},
           "ai": {"model": "x:y"}}
    page = ag.run_report_page(_doc(), cfg)
    assert isinstance(page, ReportPage)
    assert [s.title for s in page.sections] == ["Revenue", "Risks"]
