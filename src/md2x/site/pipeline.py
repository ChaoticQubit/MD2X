"""Orchestrate site generation: resolve inputs, build fragments, plan, enhance,
render, write. Works with or without the AI layer.

run_architect/run_page are imported at module scope so tests can monkeypatch
them on this module; the import is wrapped so --no-ai works without agno.
"""
from __future__ import annotations

import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .content import build_doc
from .render import default_site_plan, write_site
from .schemas import Doc, PageEnhancement, SitePlan

try:  # agno optional
    from .agents import run_architect, run_page
except ImportError:  # [ai] extra not installed
    run_architect = None  # type: ignore
    run_page = None        # type: ignore


def resolve_inputs(inputs: list[Path], recursive: bool) -> list[Path]:
    """Expand files and directories into an ordered, de-duplicated md list."""
    out: list[Path] = []
    seen: set[Path] = set()

    def add(p: Path) -> None:
        rp = p.resolve()
        if rp not in seen and rp.is_file():
            seen.add(rp)
            out.append(rp)

    for item in inputs:
        item = Path(item)
        if item.is_dir():
            pattern = "**/*.md" if recursive else "*.md"
            for md in sorted(item.glob(pattern)):
                add(md)
        elif item.suffix.lower() == ".md":
            add(item)
    return out


def generate_site(inputs: list[Path], out_dir: Path, cfg: dict, *,
                  use_ai: bool, layout: str) -> int:
    md_files = resolve_inputs([Path(i) for i in inputs],
                              recursive=cfg["site"].get("recursive", True))
    if not md_files:
        sys.stderr.write("ERROR: no .md files found in the given inputs.\n")
        return 2

    print(f"[md2x site] {len(md_files)} document(s); layout={layout}; "
          f"ai={'on' if use_ai else 'off'}")
    docs: list[Doc] = [build_doc(p, cfg) for p in md_files]

    if use_ai:
        if run_architect is None:
            sys.stderr.write(
                "ERROR: AI site needs agno. Run: pip install md2x[ai] "
                "(or pass --no-ai).\n"
            )
            return 3
        try:
            plan = run_architect(docs, cfg)
        except Exception as e:  # degrade to deterministic plan
            sys.stderr.write(f"WARN: architect agent failed ({e}); "
                             f"using default layout.\n")
            plan = default_site_plan(docs, cfg)
        enh = _enhance_all(docs, plan, cfg)
    else:
        plan = default_site_plan(docs, cfg)
        enh = {d.slug: PageEnhancement() for d in docs}

    write_site(out_dir, docs, plan, enh, cfg, layout=layout)
    print(f"[md2x site] wrote site to {out_dir}")
    return 0


def _enhance_all(docs: list[Doc], plan: SitePlan,
                 cfg: dict) -> dict[str, PageEnhancement]:
    workers = max(1, int(cfg["ai"].get("concurrency", 4)))

    def one(doc: Doc) -> tuple[str, PageEnhancement]:
        try:
            return doc.slug, run_page(doc, plan, cfg)
        except Exception as e:  # per-page degrade
            sys.stderr.write(f"WARN: page agent failed for {doc.slug} ({e}); "
                             f"emitting plain page.\n")
            return doc.slug, PageEnhancement()

    with ThreadPoolExecutor(max_workers=workers) as ex:
        return dict(ex.map(one, docs))
