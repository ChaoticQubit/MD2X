from pathlib import Path
import shutil
import pytest
import md2x.config as config
from md2x.site import pipeline


def _cfg():
    return config.deep_merge(config.DEFAULTS, {})


def test_resolve_inputs_globs_dirs_and_keeps_files(tmp_path):
    (tmp_path / "a.md").write_text("# A")
    sub = tmp_path / "sub"; sub.mkdir()
    (sub / "b.md").write_text("# B")
    (tmp_path / "note.txt").write_text("ignore")
    files = pipeline.resolve_inputs([tmp_path], recursive=True)
    names = sorted(f.name for f in files)
    assert names == ["a.md", "b.md"]


def test_resolve_inputs_dedupes(tmp_path):
    f = tmp_path / "a.md"; f.write_text("# A")
    files = pipeline.resolve_inputs([f, f], recursive=True)
    assert len(files) == 1


@pytest.mark.skipif(not shutil.which("pandoc"), reason="pandoc not installed")
def test_generate_site_no_ai_builds_multipage(tmp_path):
    docs_dir = tmp_path / "docs"; docs_dir.mkdir()
    (docs_dir / "intro.md").write_text("# Intro\n\nThe quick brown fox.\n")
    (docs_dir / "guide.md").write_text("# Guide\n\nSecond page body.\n")
    out = tmp_path / "site"
    cfg = _cfg()
    rc = pipeline.generate_site([docs_dir], out, cfg, use_ai=False,
                                layout="multi-page")
    assert rc == 0
    assert (out / "index.html").exists()
    assert "The quick brown fox." in (out / "intro.html").read_text()
    assert "Second page body." in (out / "guide.html").read_text()


@pytest.mark.skipif(not shutil.which("pandoc"), reason="pandoc not installed")
def test_generate_site_ai_uses_agents(tmp_path, monkeypatch):
    docs_dir = tmp_path / "docs"; docs_dir.mkdir()
    (docs_dir / "intro.md").write_text("# Intro\n\nThe quick brown fox.\n")
    out = tmp_path / "site"
    cfg = _cfg()

    from md2x.site import schemas
    monkeypatch.setattr(pipeline, "run_architect",
        lambda docs, c: schemas.SitePlan(
            nav=[schemas.NavItem(title=d.title, slug=d.slug) for d in docs],
            order=[d.slug for d in docs], index_title="Docs"))
    monkeypatch.setattr(pipeline, "run_page",
        lambda doc, plan, c: schemas.PageEnhancement(tldr="Summary here."))

    rc = pipeline.generate_site([docs_dir], out, cfg, use_ai=True,
                                layout="multi-page")
    assert rc == 0
    assert "Summary here." in (out / "intro.html").read_text()
    assert "The quick brown fox." in (out / "intro.html").read_text()


def test_generate_site_normalizes_bad_render_mode(tmp_path, monkeypatch):
    """An invalid render_mode is normalized to the default before render."""
    from md2x.site import schemas
    seen = {}
    monkeypatch.setattr(pipeline, "build_doc", lambda p, c: schemas.Doc(
        path=p, title="A", outline=[], fragment_html="<p>a</p>"))

    def fake_write_site(out_dir, docs, plan, enh, cfg, *, layout):
        seen["render_mode"] = cfg["site"]["render_mode"]

    monkeypatch.setattr(pipeline, "write_site", fake_write_site)
    md = tmp_path / "a.md"; md.write_text("# A\n\nbody\n")
    cfg = _cfg()
    cfg["site"]["render_mode"] = "banana"
    rc = pipeline.generate_site([md], tmp_path / "out", cfg,
                                use_ai=False, layout="multi-page")
    assert rc == 0
    assert seen["render_mode"] == "blocks"   # normalized


def test_generate_site_no_md_files_returns_2(tmp_path):
    empty_dir = tmp_path / "docs"
    empty_dir.mkdir()
    rc = pipeline.generate_site([empty_dir], tmp_path / "out",
                                _cfg(), use_ai=False, layout="multi-page")
    assert rc == 2


@pytest.mark.skipif(not shutil.which("pandoc"), reason="pandoc not installed")
def test_generate_site_ai_without_agno_returns_3(tmp_path, monkeypatch):
    (tmp_path / "a.md").write_text("# A\n\nbody\n")
    monkeypatch.setattr(pipeline, "run_architect", None)
    rc = pipeline.generate_site([tmp_path], tmp_path / "out",
                                _cfg(), use_ai=True, layout="multi-page")
    assert rc == 3


@pytest.mark.skipif(not shutil.which("pandoc"), reason="pandoc not installed")
def test_generate_site_architect_failure_degrades_to_default(tmp_path, monkeypatch):
    docs_dir = tmp_path / "docs"; docs_dir.mkdir()
    (docs_dir / "intro.md").write_text("# Intro\n\nThe quick brown fox.\n")
    out = tmp_path / "site"

    def boom(docs, c):
        raise RuntimeError("architect exploded")

    monkeypatch.setattr(pipeline, "run_architect", boom)
    monkeypatch.setattr(pipeline, "run_page",
        lambda doc, plan, c: __import__("md2x.site.schemas", fromlist=["PageEnhancement"]).PageEnhancement())

    rc = pipeline.generate_site([docs_dir], out, _cfg(), use_ai=True,
                                layout="multi-page")
    assert rc == 0
    assert (out / "index.html").exists()
    assert "The quick brown fox." in (out / "intro.html").read_text()
