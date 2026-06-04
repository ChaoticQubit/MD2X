"""md2x — Markdown (+Mermaid) → PDF / DOCX / HTML / EPUB / LaTeX.

Public API re-exported for convenience (used by tests and external callers).
"""
from .paths import ensure_venv_yaml, PROJECT_ROOT

ensure_venv_yaml()

from .config import DEFAULTS, deep_merge, load_config       # noqa: E402
from .binaries import resolve_binary                        # noqa: E402
from .mermaid import extract_caption, mermaid_to_dot        # noqa: E402
from .pipeline import build                                 # noqa: E402
from .cli import apply_cli_overrides, main                  # noqa: E402

__all__ = [
    "PROJECT_ROOT", "ensure_venv_yaml", "DEFAULTS", "deep_merge",
    "load_config", "resolve_binary", "extract_caption", "mermaid_to_dot",
    "build", "apply_cli_overrides", "main",
]
