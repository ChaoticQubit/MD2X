"""Static-site deploy providers (Vercel today; abstracted for more later)."""
from __future__ import annotations

from pathlib import Path


def deploy(out_dir: Path, cfg: dict) -> str:
    provider = cfg["deploy"]["provider"]
    if provider == "vercel":
        from .vercel import deploy_vercel
        return deploy_vercel(out_dir, cfg)
    raise ValueError(f"unknown deploy provider: {provider!r}")
