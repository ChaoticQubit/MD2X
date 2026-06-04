import sys
from pathlib import Path
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
# Redundant with pyproject.toml `[tool.pytest.ini_options] pythonpath = src`,
# but lets `pytest` run from any cwd and resolve the src-layout package.
sys.path.insert(0, str(REPO_ROOT / "src"))


@pytest.fixture
def repo_root() -> Path:
    return REPO_ROOT


@pytest.fixture
def binaries_available() -> bool:
    """
    Determine whether the required external binaries `pandoc` and `xelatex` are available.
    
    Performs availability checks for both `pandoc` and `xelatex`.
    
    Returns:
        True if both binaries are available, False otherwise.
    """
    from md2x.binaries import resolve_binary
    return bool(resolve_binary("pandoc")) and bool(resolve_binary("xelatex"))
