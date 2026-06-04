#!/usr/bin/env python3
"""Helper: print resolved binary paths. Invoked by `make check`."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from md2pdf.binaries import resolve_binary

for n in ("pandoc", "xelatex", "mmdc", "dot"):
    print(f"  {n:8s} {resolve_binary(n) or 'MISSING'}")
