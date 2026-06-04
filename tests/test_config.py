import textwrap
import argparse
import md2pdf.config as config


def test_deep_merge_override_wins_and_preserves():
    base = {"a": 1, "b": {"x": 1, "y": 2}}
    over = {"b": {"y": 99}, "c": 3}
    out = config.deep_merge(base, over)
    assert out == {"a": 1, "b": {"x": 1, "y": 99}, "c": 3}


def test_deep_merge_nondict_replaces_dict():
    assert config.deep_merge({"a": {"x": 1}}, {"a": 5}) == {"a": 5}


def test_load_config_defaults_when_none(tmp_path):
    md = tmp_path / "doc.md"
    md.write_text("# hi")
    cfg = config.load_config(None, md)
    assert cfg["page"]["margin"] == "0.85in"
    assert cfg["output"]["toc"] is True


def test_load_config_sibling_yaml_overrides(tmp_path):
    (tmp_path / "md2pdf.yaml").write_text(
        textwrap.dedent("""
        page:
          margin: 2in
        """)
    )
    md = tmp_path / "doc.md"
    md.write_text("# hi")
    cfg = config.load_config(None, md)
    assert cfg["page"]["margin"] == "2in"
    assert cfg["page"]["fontsize"] == "10.5pt"  # default preserved


def test_load_config_malformed_yaml_falls_back(tmp_path, capsys):
    bad = tmp_path / "bad.yaml"
    bad.write_text("page: [unclosed")
    md = tmp_path / "doc.md"
    md.write_text("# hi")
    cfg = config.load_config(bad, md)
    assert cfg["page"]["margin"] == "0.85in"
    assert "WARN" in capsys.readouterr().err
