"""Project layout + lazy PyYAML bootstrap from the local .venv."""
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
LOCAL_BIN     = PROJECT_ROOT / ".bin"
LOCAL_TOOLS   = PROJECT_ROOT / ".tools"
LOCAL_NPM_BIN = PROJECT_ROOT / "node_modules" / ".bin"
LOCAL_VENV    = PROJECT_ROOT / ".venv"


def ensure_venv_yaml() -> None:
    """If PyYAML is missing but .venv has it, add .venv site-packages to sys.path."""
    try:
        import yaml  # noqa: F401
        return
    except ImportError:
        pass
    for pattern in ("lib/python*/site-packages", "Lib/site-packages"):
        for p in LOCAL_VENV.glob(pattern):
            sys.path.insert(0, str(p))
    try:
        import yaml  # noqa: F401
    except ImportError:
        sys.stderr.write(
            "WARN: PyYAML not found. Config file will be ignored. "
            "Run ./install.sh to set up the venv with PyYAML.\n"
        )
