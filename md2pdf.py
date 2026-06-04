#!/usr/bin/env python3
"""Entry shim. Real code lives in src/md2pdf/.

Kept at repo root so `./md2pdf.py INPUT.md` and the Makefile targets keep
working after the package decomposition. Run as a script (__main__); the
src/md2pdf package is resolved by prepending src/ to sys.path.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from md2pdf.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main() or 0)
