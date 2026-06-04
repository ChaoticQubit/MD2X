import argparse
import pytest
import md2x.cli as cli
from md2x.config import DEFAULTS, deep_merge


def test_apply_cli_overrides_each_flag():
    cfg = deep_merge(DEFAULTS, {})
    args = argparse.Namespace(no_toc=True, toc_depth=4, margin="2in",
                              fontsize="12pt", keep_intermediate=True, theme="forest")
    out = cli.apply_cli_overrides(cfg, args)
    assert out["output"]["toc"] is False
    assert out["output"]["toc_depth"] == 4
    assert out["page"]["margin"] == "2in"
    assert out["page"]["fontsize"] == "12pt"
    assert out["advanced"]["keep_intermediate"] is True
    assert out["mermaid"]["theme"] == "forest"


def test_apply_cli_overrides_noops_when_unset():
    cfg = deep_merge(DEFAULTS, {})
    args = argparse.Namespace(no_toc=False, toc_depth=None, margin=None,
                              fontsize=None, keep_intermediate=False, theme=None)
    out = cli.apply_cli_overrides(cfg, args)
    assert out["output"]["toc"] is True
    assert out["page"]["margin"] == "0.85in"


def test_main_input_not_found_exits(monkeypatch, tmp_path):
    monkeypatch.setattr("sys.argv", ["md2x", str(tmp_path / "nope.md")])
    with pytest.raises(SystemExit):
        cli.main()


def test_main_default_output_suffix(monkeypatch, tmp_path):
    md = tmp_path / "doc.md"
    md.write_text("# hi")
    captured = {}
    def fake_build(md_path, out_path, cfg):
        captured["out"] = out_path
        return 0
    monkeypatch.setattr(cli, "build", fake_build)
    monkeypatch.setattr("sys.argv", ["md2x", str(md)])
    assert cli.main() == 0
    assert captured["out"].name == "doc.pdf"


def test_main_flags_reach_config(monkeypatch, tmp_path):
    md = tmp_path / "doc.md"
    md.write_text("# hi")
    captured = {}
    monkeypatch.setattr(cli, "build",
                        lambda m, o, cfg: captured.update(cfg=cfg) or 0)
    monkeypatch.setattr("sys.argv", ["md2x", str(md), "--no-toc", "--margin", "3in"])
    cli.main()
    assert captured["cfg"]["output"]["toc"] is False
    assert captured["cfg"]["page"]["margin"] == "3in"


def test_main_to_flag_sets_output_suffix(monkeypatch, tmp_path):
    md = tmp_path / "doc.md"
    md.write_text("# hi")
    captured = {}
    monkeypatch.setattr(cli, "build",
                        lambda m, o, cfg: captured.update(out=o, cfg=cfg) or 0)
    monkeypatch.setattr("sys.argv", ["md2x", str(md), "--to", "docx"])
    assert cli.main() == 0
    assert captured["out"].name == "doc.docx"
    assert captured["cfg"]["output"]["format"] == "docx"


def test_main_output_extension_infers_format(monkeypatch, tmp_path):
    md = tmp_path / "doc.md"
    md.write_text("# hi")
    captured = {}
    monkeypatch.setattr(cli, "build",
                        lambda m, o, cfg: captured.update(cfg=cfg) or 0)
    monkeypatch.setattr("sys.argv", ["md2x", str(md), "-o", str(tmp_path / "x.html")])
    cli.main()
    assert captured["cfg"]["output"]["format"] == "html"


def test_main_check_prints_binaries_and_exits(monkeypatch, capsys):
    monkeypatch.setattr("md2x.binaries.resolve_binary",
                        lambda name, override=None: f"/fake/{name}")
    monkeypatch.setattr("sys.argv", ["md2x", "--check"])
    assert cli.main() == 0
    out = capsys.readouterr().out
    assert "pandoc" in out and "/fake/pandoc" in out
    assert "xelatex" in out and "mmdc" in out and "dot" in out
