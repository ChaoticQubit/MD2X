# tomllib is stdlib only on Python 3.11+, but the project floor is 3.10, so we
# read the file's text and parse the optional-dependencies table with a guard
# that prefers tomllib when available and falls back to a text scan otherwise.
import sys
from pathlib import Path


def _extras() -> dict:
    text = (Path(__file__).resolve().parents[1] / "pyproject.toml").read_text()
    if sys.version_info >= (3, 11):
        import tomllib
        return tomllib.loads(text)["project"]["optional-dependencies"]
    # 3.10 fallback: assert against the raw text (no TOML parser needed)
    return {"_text": text}


def test_optional_extras_declared():
    extras = _extras()
    if "_text" in extras:
        text = extras["_text"]
        assert "agno>=2.2" in text
        assert "httpx>=0.27" in text
        assert "ai = [" in text and "deploy = [" in text and "all = [" in text
        return
    assert any(d.startswith("agno") for d in extras["ai"])
    assert any(d.startswith("httpx") for d in extras["ai"])
    assert any(d.startswith("httpx") for d in extras["deploy"])
    assert "all" in extras
