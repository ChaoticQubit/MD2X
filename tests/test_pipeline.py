import json
import stat
from pathlib import Path
import pytest
import md2x.pipeline as pipeline
from md2x.config import DEFAULTS, deep_merge


def _fake_pandoc(tmp_path: Path) -> str:
    p = tmp_path / "pandoc"
    p.write_text(
        "#!/usr/bin/env python3\n"
        "import sys\n"
        "out=sys.argv[sys.argv.index('-o')+1]\n"
        "open(out,'wb').write(b'%PDF-1.5 fake')\n"
    )
    p.chmod(p.stat().st_mode | stat.S_IEXEC)
    return str(p)


def _patch_bins(monkeypatch, tmp_path, mmdc="mmdc", dot="dot"):
    pan = _fake_pandoc(tmp_path)
    def fake_resolve(name, override=None):
        return {"pandoc": pan, "xelatex": "xelatex", "mmdc": mmdc, "dot": dot}[name]
    monkeypatch.setattr(pipeline, "resolve_binary", fake_resolve)


def _make_md(tmp_path: Path, body: str) -> Path:
    md = tmp_path / "doc.md"
    md.write_text(body)
    return md


MD = "# Title\n\n```mermaid\nflowchart TD\nA[Start]-->B[End]\n```\n\nafter\n"


def test_build_embeds_figure_and_caption(monkeypatch, tmp_path):
    _patch_bins(monkeypatch, tmp_path)
    def fake_render(src, png, cfg, mmdc_bin, dot_bin):
        Path(png).write_bytes(b"\x89PNG")
        return True, "dot"
    monkeypatch.setattr(pipeline, "render_block", fake_render)
    md = _make_md(tmp_path, MD)
    cfg = deep_merge(DEFAULTS, {"advanced": {"keep_intermediate": True}})
    rc = pipeline.build(md, tmp_path / "out.pdf", cfg)
    assert rc == 0
    assert (tmp_path / "out.pdf").read_bytes().startswith(b"%PDF")
    rewritten = (tmp_path / "doc._md2x.md").read_text()
    assert "![Start](diagrams/mermaid_01.png)" in rewritten
    assert "Figure 1: Start." in rewritten


def test_on_failure_keep_source(monkeypatch, tmp_path):
    _patch_bins(monkeypatch, tmp_path)
    monkeypatch.setattr(pipeline, "render_block", lambda *a: (False, "none"))
    md = _make_md(tmp_path, MD)
    cfg = deep_merge(DEFAULTS, {"advanced": {"keep_intermediate": True}})
    pipeline.build(md, tmp_path / "out.pdf", cfg)
    rewritten = (tmp_path / "doc._md2x.md").read_text()
    assert "Mermaid source preserved" in rewritten
    assert "flowchart TD" in rewritten


def test_on_failure_omit(monkeypatch, tmp_path):
    _patch_bins(monkeypatch, tmp_path)
    monkeypatch.setattr(pipeline, "render_block", lambda *a: (False, "none"))
    md = _make_md(tmp_path, MD)
    cfg = deep_merge(DEFAULTS, {"mermaid": {"on_failure": "omit"},
                                "advanced": {"keep_intermediate": True}})
    pipeline.build(md, tmp_path / "out.pdf", cfg)
    rewritten = (tmp_path / "doc._md2x.md").read_text()
    assert "flowchart TD" not in rewritten


def test_on_failure_error_exits(monkeypatch, tmp_path):
    _patch_bins(monkeypatch, tmp_path)
    monkeypatch.setattr(pipeline, "render_block", lambda *a: (False, "none"))
    md = _make_md(tmp_path, MD)
    cfg = deep_merge(DEFAULTS, {"mermaid": {"on_failure": "error"}})
    with pytest.raises(SystemExit):
        pipeline.build(md, tmp_path / "out.pdf", cfg)


def test_emit_manifest(monkeypatch, tmp_path):
    _patch_bins(monkeypatch, tmp_path)
    def fake_render(src, png, cfg, mmdc_bin, dot_bin):
        Path(png).write_bytes(b"\x89PNG")
        return True, "dot"
    monkeypatch.setattr(pipeline, "render_block", fake_render)
    md = _make_md(tmp_path, MD)
    cfg = deep_merge(DEFAULTS, {"advanced": {"emit_manifest": True}})
    pipeline.build(md, tmp_path / "out.pdf", cfg)
    man = json.loads((tmp_path / "doc._md2x.json").read_text())
    assert man[0]["renderer"] == "dot" and man[0]["ok"] is True
    assert man[0]["caption"] == "Start"


def test_no_clobber_refuses(monkeypatch, tmp_path):
    _patch_bins(monkeypatch, tmp_path)
    monkeypatch.setattr(pipeline, "render_block", lambda *a: (True, "dot"))
    out = tmp_path / "out.pdf"
    out.write_text("existing")
    md = _make_md(tmp_path, MD)
    cfg = deep_merge(DEFAULTS, {"advanced": {"no_clobber": True}})
    with pytest.raises(SystemExit):
        pipeline.build(md, out, cfg)


def test_missing_pandoc_exits(monkeypatch, tmp_path):
    def fake_resolve(name, override=None):
        return None if name == "pandoc" else "x"
    monkeypatch.setattr(pipeline, "resolve_binary", fake_resolve)
    md = _make_md(tmp_path, MD)
    with pytest.raises(SystemExit):
        pipeline.build(md, tmp_path / "out.pdf", deep_merge(DEFAULTS, {}))


def test_keep_intermediate_false_deletes(monkeypatch, tmp_path):
    _patch_bins(monkeypatch, tmp_path)
    def fake_render(src, png, cfg, mmdc_bin, dot_bin):
        Path(png).write_bytes(b"\x89PNG")
        return True, "dot"
    monkeypatch.setattr(pipeline, "render_block", fake_render)
    md = _make_md(tmp_path, MD)
    pipeline.build(md, tmp_path / "out.pdf", deep_merge(DEFAULTS, {}))
    assert not (tmp_path / "doc._md2x.md").exists()
