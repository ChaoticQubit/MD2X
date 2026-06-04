import stat
from pathlib import Path
import md2x.binaries as binaries


def _make_exe(p: Path):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("#!/bin/sh\necho hi\n")
    p.chmod(p.stat().st_mode | stat.S_IEXEC)


def test_override_existing_wins(tmp_path):
    exe = tmp_path / "mybin"
    _make_exe(exe)
    assert binaries.resolve_binary("pandoc", str(exe)) == str(exe)


def test_override_missing_returns_none(tmp_path):
    assert binaries.resolve_binary("pandoc", str(tmp_path / "nope")) is None


def test_order_bin_before_path(tmp_path, monkeypatch):
    binp = tmp_path / ".bin" / "pandoc"
    _make_exe(binp)
    monkeypatch.setattr(binaries, "LOCAL_BIN", tmp_path / ".bin")
    monkeypatch.setattr(binaries, "LOCAL_NPM_BIN", tmp_path / "nm")
    monkeypatch.setattr(binaries, "LOCAL_TOOLS", tmp_path / ".tools")
    monkeypatch.setattr(binaries.shutil, "which", lambda n: "/usr/bin/pandoc")
    assert binaries.resolve_binary("pandoc") == str(binp)


def test_falls_through_to_path(tmp_path, monkeypatch):
    monkeypatch.setattr(binaries, "LOCAL_BIN", tmp_path / ".bin")
    monkeypatch.setattr(binaries, "LOCAL_NPM_BIN", tmp_path / "nm")
    monkeypatch.setattr(binaries, "LOCAL_TOOLS", tmp_path / ".tools")
    monkeypatch.setattr(binaries.shutil, "which", lambda n: "/usr/bin/" + n)
    assert binaries.resolve_binary("xelatex") == "/usr/bin/xelatex"


def test_tools_rglob_finds_nested(tmp_path, monkeypatch):
    nested = tmp_path / ".tools" / "tex" / "bin" / "xelatex"
    _make_exe(nested)
    monkeypatch.setattr(binaries, "LOCAL_BIN", tmp_path / ".bin")
    monkeypatch.setattr(binaries, "LOCAL_NPM_BIN", tmp_path / "nm")
    monkeypatch.setattr(binaries, "LOCAL_TOOLS", tmp_path / ".tools")
    monkeypatch.setattr(binaries.shutil, "which", lambda n: None)
    assert binaries.resolve_binary("xelatex") == str(nested)
