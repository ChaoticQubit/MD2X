"""Output-format registry and detection.

The single source of truth for what each target format needs from pandoc.
PDF is engine-driven (writer is None → handled by the dedicated PDF builder);
every other format names a pandoc writer and a small set of portable flags.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Target:
    name: str            # "pdf" | "docx" | "html" | "epub" | "latex"
    writer: str | None   # pandoc -t writer; None for pdf (xelatex engine)
    suffix: str          # ".pdf", ".docx", ...
    standalone: bool     # pass --standalone
    embed: bool          # pass --embed-resources (html: single self-contained file)
    needs_xelatex: bool  # pdf only


TARGETS: dict[str, Target] = {
    "pdf":   Target("pdf",   None,    ".pdf",  False, False, True),
    "docx":  Target("docx",  "docx",  ".docx", False, False, False),
    "html":  Target("html",  "html",  ".html", True,  True,  False),
    "epub":  Target("epub",  "epub",  ".epub", False, False, False),
    "latex": Target("latex", "latex", ".tex",  True,  False, False),
}

# extension -> target name
EXT_TO_TARGET: dict[str, str] = {t.suffix: t.name for t in TARGETS.values()}
EXT_TO_TARGET[".htm"] = "html"


def detect_target(out_path: Path | None, override: str | None) -> Target:
    """
    Determine which output Target to use.
    
    Parameters:
        out_path (Path | None): Optional output file path; when provided, the file extension (case-insensitive) is used to infer the target.
        override (str | None): Optional explicit target name; when provided it must be one of the keys in TARGETS.
    
    Returns:
        Target: The resolved Target instance — the explicit override if given and valid, otherwise the target inferred from out_path's extension, otherwise the PDF target.
    """
    if override:
        if override not in TARGETS:
            raise ValueError(
                f"unknown format: {override!r} (choose from {sorted(TARGETS)})"
            )
        return TARGETS[override]
    if out_path is not None:
        name = EXT_TO_TARGET.get(out_path.suffix.lower())
        if name:
            return TARGETS[name]
    return TARGETS["pdf"]
