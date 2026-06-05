"""Orchestrate site generation: resolve inputs, build fragments, plan, enhance,
render, write. Works with or without the AI layer.

run_architect/run_page are imported at module scope so tests can monkeypatch
them on this module; the import is wrapped so --no-ai works without agno.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from ..log import get_logger
from .content import build_doc
from .render import default_site_plan, write_site
from .schemas import Doc, PageEnhancement, SitePlan

log = get_logger(__name__)

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
        log.error("no .md files found in the given inputs")
        return 2

    log.info("resolved %d document(s); layout=%s ai=%s",
             len(md_files), layout, "on" if use_ai else "off")
    for p in md_files:
        log.debug("input document: %s", p)
    docs: list[Doc] = [build_doc(p, cfg) for p in md_files]
    log.info("built %d HTML fragment(s)", len(docs))

    # AI site v2: the report archetype uses the editorial "blocks" pipeline
    # (hero + synthesized summary + KPI strip + findings + verbatim sections),
    # not the architect/page enhancement path. Other archetypes are unchanged.
    if cfg["site"]["archetype"] == "report":
        from .report import generate_report_site
        return generate_report_site(docs, out_dir, cfg, use_ai=use_ai)

    if use_ai:
        if run_architect is None:
            log.error("AI site needs agno — run: pip install md2x[ai] "
                      "(or pass --no-ai)")
            return 3
        try:
            log.info("architect: planning site")
            plan = run_architect(docs, cfg)
            log.info("architect: plan ready (%d nav items, %d in order)",
                     len(plan.nav), len(plan.order))
        except Exception as e:  # degrade to deterministic plan
            log.warning("architect agent failed (%s); using default layout", e)
            log.debug("architect failure traceback", exc_info=True)
            plan = default_site_plan(docs, cfg)
        enh = _enhance_all(docs, plan, cfg)
    else:
        log.debug("AI disabled; using deterministic plan + empty enhancements")
        plan = default_site_plan(docs, cfg)
        enh = {d.slug: PageEnhancement() for d in docs}

    write_site(out_dir, docs, plan, enh, cfg, layout=layout)
    log.info("wrote site to %s", out_dir)
    return 0


def _enhance_all(docs: list[Doc], plan: SitePlan,
                 cfg: dict) -> dict[str, PageEnhancement]:
    workers = max(1, int(cfg["ai"].get("concurrency", 4)))
    log.info("enhancing %d page(s) with concurrency=%d", len(docs), workers)

    def one(doc: Doc) -> tuple[str, PageEnhancement]:
        try:
            return doc.slug, run_page(doc, plan, cfg)
        except Exception as e:  # per-page degrade
            log.warning("page agent failed for %s (%s); emitting plain page",
                        doc.slug, e)
            log.debug("page %s failure traceback", doc.slug, exc_info=True)
            return doc.slug, PageEnhancement()

    with ThreadPoolExecutor(max_workers=workers) as ex:
        return dict(ex.map(one, docs))
