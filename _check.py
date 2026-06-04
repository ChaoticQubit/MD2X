#!/usr/bin/env python3
"""Helper: print resolved binary paths. Invoked by `make check`."""
import sys
sys.path.insert(0, ".")
import md2pdf as m

for n in ("pandoc", "xelatex", "mmdc", "dot"):
    print(f"  {n:8s} {m.resolve_binary(n) or 'MISSING'}")
