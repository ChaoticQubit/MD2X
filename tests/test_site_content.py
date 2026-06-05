import shutil
import subprocess

import pytest

import md2x.config as config
import md2x.site.content as content


def _cfg():
    return config.deep_merge(config.DEFAULTS, {})


def test_extract_title_prefers_h1(tmp_path):
    md = tmp_path / "doc.md"
    md.write_text("# Real Title\n\nbody\n")
    assert content.extract_title(md) == "Real Title"


def test_extract_title_falls_back_to_filename(tmp_path):
    md = tmp_path / "my-notes.md"
    md.write_text("no heading here\n")
    assert content.extract_title(md) == "my-notes"


def test_extract_outline_collects_headings(tmp_path):
    md = tmp_path / "doc.md"
    md.write_text("# Title\n\n## One\n\ntext\n\n## Two\n")
    assert content.extract_outline(md) == ["One", "Two"]


def test_md_to_fragment_does_not_pass_standalone(tmp_path, monkeypatch):
    md = tmp_path / "doc.md"
    md.write_text("# Hello\n\nworld\n")
    captured = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        return subprocess.CompletedProcess(cmd, 0, stdout="<h1>Hello</h1>", stderr="")

    monkeypatch.setattr("md2x.site.content.resolve_binary",
                        lambda name, override=None: "pandoc" if name == "pandoc" else None)
    monkeypatch.setattr("md2x.site.content.subprocess.run", fake_run)
    content.md_to_fragment(md, _cfg())
    assert "--standalone" not in captured["cmd"]
    assert "-t" in captured["cmd"] and "html" in captured["cmd"]


@pytest.mark.skipif(not shutil.which("pandoc"), reason="pandoc not installed")
def test_md_to_fragment_preserves_body_text(tmp_path):
    md = tmp_path / "doc.md"
    md.write_text("# Heading\n\nThe quick brown fox jumps.\n")
    frag = content.md_to_fragment(md, _cfg())
    assert "The quick brown fox jumps." in frag
    assert "<html" not in frag.lower()  # fragment, not a full document
