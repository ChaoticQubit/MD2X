import stat
import pytest
from pathlib import Path
import md2x.renderers as rnd

CFG = {
    "mermaid": {"theme": "default", "background": "white", "prefer": "auto"},
    "images": {"dpi": 120, "mmdc_width": 1600, "mmdc_height": 1100},
}


def test_render_block_auto_prefers_mmdc_when_present(monkeypatch):
    calls = []
    monkeypatch.setattr(rnd, "render_via_mmdc",
                        lambda *a, **k: calls.append("mmdc") or True)
    monkeypatch.setattr(rnd, "render_via_dot",
                        lambda *a, **k: calls.append("dot") or True)
    ok, who = rnd.render_block("flowchart TD\nA-->B", Path("x.png"), CFG, "mmdc", "dot")
    assert (ok, who) == (True, "mmdc")
    assert calls == ["mmdc"]


def test_render_block_prefer_dot(monkeypatch):
    monkeypatch.setattr(rnd, "render_via_mmdc", lambda *a, **k: True)
    monkeypatch.setattr(rnd, "render_via_dot", lambda *a, **k: True)
    cfg = {**CFG, "mermaid": {**CFG["mermaid"], "prefer": "dot"}}
    ok, who = rnd.render_block("flowchart TD\nA-->B", Path("x.png"), cfg, "mmdc", "dot")
    assert (ok, who) == (True, "dot")


def test_render_block_falls_through_then_fails(monkeypatch):
    monkeypatch.setattr(rnd, "render_via_mmdc", lambda *a, **k: False)
    monkeypatch.setattr(rnd, "render_via_dot", lambda *a, **k: False)
    ok, who = rnd.render_block("flowchart TD\nA-->B", Path("x.png"), CFG, "mmdc", "dot")
    assert (ok, who) == (False, "none")


def _fake_dot(tmp_path: Path) -> str:
    # stub `dot`: reads stdin, writes a PNG magic header to the -o argument
    script = tmp_path / "dot"
    script.write_text(
        "#!/usr/bin/env python3\n"
        "import sys\n"
        "out=sys.argv[sys.argv.index('-o')+1]\n"
        "sys.stdin.read()\n"
        "open(out,'wb').write(bytes.fromhex('89504e470d0a1a0a'))\n"
    )
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    return str(script)


def test_render_via_dot_invokes_stub(tmp_path):
    out = tmp_path / "d.png"
    ok = rnd.render_via_dot("flowchart TD\nA[Start]-->B[End]", out, CFG, _fake_dot(tmp_path))
    assert ok is True
    assert out.exists() and out.stat().st_size > 0


def _cfg():
    import md2x.config as config
    return config.deep_merge(config.DEFAULTS, {})


def test_render_into_markdown_no_blocks_returns_input(tmp_path):
    md = "# Title\n\nplain text, no diagrams.\n"
    out, manifest = rnd.render_into_markdown(md, tmp_path, _cfg(), None, None)
    assert out == md
    assert manifest == []


def test_render_into_markdown_keeps_source_when_no_renderer(tmp_path):
    md = "intro\n\n```mermaid\nflowchart LR\nA-->B\n```\n\nafter\n"
    cfg = _cfg()  # on_failure default == keep_source
    out, manifest = rnd.render_into_markdown(md, tmp_path, cfg, None, None)
    assert len(manifest) == 1
    assert manifest[0]["ok"] is False
    assert "Mermaid source preserved" in out
    assert "intro" in out and "after" in out


def test_render_into_markdown_error_policy_raises(tmp_path):
    md = "```mermaid\nflowchart LR\nA-->B\n```\n"
    cfg = _cfg()
    cfg["mermaid"]["on_failure"] = "error"
    with pytest.raises(rnd.MermaidRenderError):
        rnd.render_into_markdown(md, tmp_path, cfg, None, None)


def test_render_into_markdown_diag_subdir_namespaces_dir(tmp_path):
    rnd.render_into_markdown("no diagrams here\n", tmp_path, _cfg(),
                             None, None, diag_subdir="intro")
    assert (tmp_path / "diagrams" / "intro").is_dir()
