# Living Site PR-A: Skill Scaffold + Loader — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bundle a "living site" skill into the package and inject it into the architect/page agents on every `md2x site` run, without changing output structure.

**Architecture:** A new package `md2x.site.skill` holds Markdown skill files (shipped as package data). `load_skill(archetype, render_mode, fidelity, artifacts)` composes the relevant files into one instruction string. `agents.run_architect` / `run_page` prepend that string to their existing instructions. Pure-Python loader (no agno) so it imports on the `--no-ai` path. Missing optional files (per-archetype, per-artifact — added in later PRs) are skipped gracefully.

**Tech Stack:** Python 3.10+, `importlib.resources`, setuptools package-data, pytest. This is the foundation PR; render modes / design system / archetype content land in PRs B–F.

This plan corresponds to **PR-A** in `docs/superpowers/specs/2026-06-06-md2x-living-site-design.md`. Subsequent PRs (B–H) get their own plans.

---

## File Structure

- Create: `src/md2x/site/skill/__init__.py` — the `load_skill` loader (the only logic).
- Create: `src/md2x/site/skill/SKILL.md` — spine: thesis + the contract.
- Create: `src/md2x/site/skill/principles.md` — the Thariq principles.
- Create: `src/md2x/site/skill/design-system.md` — the `--ds-*` CSS-var contract.
- Create: `src/md2x/site/skill/export-contract.md` — the `postMessage` export schema.
- Create: `src/md2x/site/skill/render-modes/blocks.md` — blocks-mode guidance (starter).
- Create: `src/md2x/site/skill/render-modes/hybrid.md` — hybrid-mode guidance (starter).
- Create: `src/md2x/site/skill/render-modes/full.md` — full-mode guidance (starter).
- Modify: `pyproject.toml` — add `[tool.setuptools.package-data]` so the `.md` files ship.
- Modify: `src/md2x/site/agents.py` — prepend `load_skill(...)` to architect + page instructions.
- Test: `tests/test_site_skill.py` — loader composition, missing-file tolerance, injection.

**WIP guard:** Never `git add -A`. Each commit stages only the exact paths listed. Do not stage `md2x.yaml` or `examples/sample.md` (local WIP).

---

## Task 1: Skill content files

These are static content (no test of their own — Task 2's loader tests assert they load and contain key markers). Create the directory tree and the seven Markdown files.

- [ ] **Step 1: Create the core spine file**

Create `src/md2x/site/skill/SKILL.md`:

```markdown
# md2x Living Site Skill

You generate a **living, interactive website** from Markdown — not the Markdown
re-rendered with chrome bolted on. Render information in the shape it actually
has: spatial things as diagrams, comparisons side-by-side, processes as
flowcharts, anything interactive as a real interactive artifact.

You drive three orthogonal axes:
- **archetype** — what kind of site this is.
- **render_mode** — how HTML is produced: `blocks` | `hybrid` | `full`.
- **fidelity** — how much you may rewrite the author's prose:
  `preserve` | `light-enhance` | `synthesize`.

Read the principles, the design-system contract, and the active render-mode and
archetype guidance below, then produce the requested structured output. Never
fabricate facts that are not in the source. Stay on-brand by consuming the
design-system CSS variables — never hardcode colors or spacing.
```

- [ ] **Step 2: Create the principles file**

Create `src/md2x/site/skill/principles.md`:

```markdown
## Principles

1. **Render information in the shape it has.** Markdown flattens spatial and
   interactive information; HTML does not. A diff is an annotated diff; a module
   is boxes and arrows; design tokens are swatches; a process is a flowchart.
2. **Make it interactive where interaction is the point.** Motion and
   interaction cannot be described, only felt — build the real slider, the real
   drag/drop, the real live re-render.
3. **Every editor ends in an export button.** Any interface the reader edits must
   export its state back to Markdown (or a copyable diff) via the export
   contract. The reader stays in the loop; the loop gets tighter.
4. **Optimize for scannability and density.** Color, charts, timelines, and
   structure turn something people skim into something they read.
5. **Be faithful.** Do not invent facts absent from the source. Synthesized prose
   (summaries, captions) is allowed only at `fidelity: synthesize`, and must be
   clearly framed as synthesis.
```

- [ ] **Step 3: Create the design-system contract file**

Create `src/md2x/site/skill/design-system.md`:

```markdown
## Design-system contract

A single design system is derived once and exposed as CSS custom properties.
Consume them; never hardcode.

- Color: `--ds-bg`, `--ds-fg`, `--ds-muted`, `--ds-accent`, `--ds-border`.
- Type: `--ds-font-sans`, `--ds-font-mono`, `--ds-font-serif`, `--ds-scale-*`.
- Space: `--ds-space-1` … `--ds-space-6`; radius `--ds-radius`; density `--ds-density`.

Every page and every artifact iframe receives these variables. Build components
that reference them so free-form output stays on-brand. Do not import external
fonts, stylesheets, or scripts — everything is self-contained.
```

- [ ] **Step 4: Create the export-contract file**

Create `src/md2x/site/skill/export-contract.md`:

```markdown
## Export contract

Interactive editors round-trip their state to the host page.

- The artifact posts: `window.parent.postMessage({ type: "md2x:export",
  format: "markdown" | "json" | "text", payload: <string> }, "*")`.
- It posts on every meaningful change and once on load.
- The host renders a "Copy as Markdown / Download" button wired to the latest
  payload. You only emit the `postMessage`; the host renders the button.
- The artifact also posts `{ type: "md2x:resize", height: <px> }` after layout so
  the host can size the iframe.
```

- [ ] **Step 5: Create the render-mode starter files**

Create `src/md2x/site/skill/render-modes/blocks.md`:

```markdown
## Render mode: blocks

Emit a typed block tree. The renderer owns the HTML, so output is safe and
testable. Use the richest block that fits the content: hero, summary, kpi_strip,
callout, card_grid, timeline, table, code, quote, figure, chart, tabs,
collapsible, steps, diagram_svg, glossary. Prefer structure over prose.
```

Create `src/md2x/site/skill/render-modes/hybrid.md`:

```markdown
## Render mode: hybrid

Emit the typed block tree, plus `artifact` blocks for anything genuinely
interactive. An artifact is a self-contained `{ html, css, js }` widget mounted
in a sandboxed iframe. It must consume the design-system variables and, if it is
an editor, implement the export contract. Keep non-interactive content as typed
blocks; reach for an artifact only when interaction is the point.
```

Create `src/md2x/site/skill/render-modes/full.md`:

```markdown
## Render mode: full

Author one self-contained interactive HTML document for the page. Inline all CSS
and JS; reference the design-system variables; no external network, fonts, or
scripts. If the page is an editor, implement the export contract. The document is
served standalone (no site chrome) but must be valid, self-contained, and safe.
```

- [ ] **Step 6: Commit the content files**

```bash
git add src/md2x/site/skill/SKILL.md src/md2x/site/skill/principles.md \
        src/md2x/site/skill/design-system.md src/md2x/site/skill/export-contract.md \
        src/md2x/site/skill/render-modes/blocks.md \
        src/md2x/site/skill/render-modes/hybrid.md \
        src/md2x/site/skill/render-modes/full.md
git commit -m "feat(site): bundle living-site skill content (PR-A)"
```

---

## Task 2: The `load_skill` loader (TDD)

**Files:**
- Create: `src/md2x/site/skill/__init__.py`
- Test: `tests/test_site_skill.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_site_skill.py`:

```python
from md2x.site.skill import load_skill


def test_load_skill_includes_core_files():
    out = load_skill("reading")
    # Spine + principles + design-system + export-contract always present.
    assert "Living Site Skill" in out
    assert "Render information in the shape" in out
    assert "--ds-accent" in out
    assert "md2x:export" in out


def test_load_skill_includes_active_render_mode():
    assert "Render mode: hybrid" in load_skill("reading", render_mode="hybrid")
    assert "Render mode: full" in load_skill("reading", render_mode="full")
    assert "Render mode: blocks" in load_skill("reading", render_mode="blocks")


def test_load_skill_tolerates_missing_archetype_and_artifacts():
    # No archetypes/*.md or artifacts/*.md exist yet (added in PR-F); must not raise.
    out = load_skill("does-not-exist", render_mode="blocks",
                     artifacts=["nope", "also-nope"])
    assert "Living Site Skill" in out  # still returns the core skill


def test_load_skill_unknown_render_mode_skips_silently():
    out = load_skill("reading", render_mode="banana")
    assert "Living Site Skill" in out
    assert "Render mode:" not in out  # banana.md doesn't exist; nothing injected
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_site_skill.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'md2x.site.skill'` (or import error).

- [ ] **Step 3: Write the loader**

Create `src/md2x/site/skill/__init__.py`:

```python
"""Bundled 'living site' skill: Markdown files composed into agent instructions.

load_skill() reads the relevant files for a given (archetype, render_mode,
fidelity, artifacts) and returns one instruction string injected into the
architect/page agents every run. Pure-Python (no agno/pydantic), so it imports on
the --no-ai path. Per-archetype and per-artifact files are added in later PRs;
their absence is skipped gracefully.
"""
from __future__ import annotations

from importlib.resources import files

from ...log import get_logger

log = get_logger(__name__)

# Always included, in this order.
_CORE = ("SKILL.md", "principles.md", "design-system.md", "export-contract.md")


def _read(rel: str) -> str | None:
    """Read a bundled skill file by package-relative path, or None if absent."""
    try:
        return (files("md2x.site.skill") / rel).read_text(encoding="utf-8")
    except (FileNotFoundError, NotADirectoryError, OSError):
        return None


def load_skill(archetype: str, render_mode: str = "blocks",
               fidelity: str = "light-enhance",
               artifacts: list[str] | None = None) -> str:
    """Compose the skill for one (archetype, render_mode, fidelity, artifacts).

    Returns a single instruction string. Missing optional files (render-mode,
    archetype, artifacts not yet authored) are skipped and logged at DEBUG.
    """
    parts: list[str] = []
    sources: list[str] = []

    def add(rel: str, *, optional: bool) -> None:
        txt = _read(rel)
        if txt:
            parts.append(txt.strip())
            sources.append(rel)
        elif optional:
            log.debug("skill: optional file missing, skipped: %s", rel)

    for name in _CORE:
        add(name, optional=False)
    add(f"render-modes/{render_mode}.md", optional=True)
    add(f"archetypes/{archetype}.md", optional=True)
    for art in (artifacts or []):
        add(f"artifacts/{art}.md", optional=True)

    composed = "\n\n---\n\n".join(parts)
    log.debug("skill: composed %d chars from %d source(s): %s",
              len(composed), len(sources), ", ".join(sources))
    return composed
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_site_skill.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add src/md2x/site/skill/__init__.py tests/test_site_skill.py
git commit -m "feat(site): load_skill composes the bundled skill (PR-A)"
```

---

## Task 3: Ship the skill files as package data

**Files:**
- Modify: `pyproject.toml`
- Test: `tests/test_site_skill.py` (add a resolution test)

Without this, a `pip install`ed wheel omits the `.md` files and `load_skill` returns only whatever is importable — the bundled skill silently disappears in production.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_site_skill.py`:

```python
def test_skill_files_are_resolvable_as_package_data():
    from importlib.resources import files
    root = files("md2x.site.skill")
    assert (root / "SKILL.md").is_file()
    assert (root / "render-modes" / "hybrid.md").is_file()
```

- [ ] **Step 2: Run the test (passes from source tree, but pin packaging intent)**

Run: `python -m pytest tests/test_site_skill.py::test_skill_files_are_resolvable_as_package_data -v`
Expected: PASS from the source checkout (files exist on disk). The pyproject change below guarantees they also ship in a built wheel.

- [ ] **Step 3: Add package-data to `pyproject.toml`**

Insert after the `[tool.setuptools.packages.find]` block (currently lines 39-40):

```toml
[tool.setuptools.package-data]
"md2x.site.skill" = ["*.md", "render-modes/*.md", "archetypes/*.md", "artifacts/*.md"]
```

- [ ] **Step 4: Verify the wheel includes the skill files**

Run:
```bash
python -m pip install --quiet build 2>/dev/null || true
python -m build --wheel --outdir /tmp/md2x-wheel 2>/dev/null && \
  python - <<'PY'
import zipfile, glob
whl = sorted(glob.glob("/tmp/md2x-wheel/*.whl"))[-1]
names = zipfile.ZipFile(whl).namelist()
md = [n for n in names if "site/skill/" in n and n.endswith(".md")]
print(f"skill .md files in wheel: {len(md)}")
assert any(n.endswith("SKILL.md") for n in md), "SKILL.md missing from wheel"
assert any("render-modes/hybrid.md" in n for n in md), "render-modes missing"
print("OK")
PY
```
Expected: prints `skill .md files in wheel: 7` (or more) and `OK`. If `build` is unavailable offline, skip this verification step — the package-data glob is standard setuptools and the resolution test in Step 1 covers source-tree behavior.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml tests/test_site_skill.py
git commit -m "build: ship living-site skill files as package data (PR-A)"
```

---

## Task 4: Inject the skill into the agents (TDD)

**Files:**
- Modify: `src/md2x/site/agents.py` (imports near line 19; `run_architect` ~line 99; `run_page` ~line 124)
- Test: `tests/test_site_skill.py`

The architect and page agents prepend the composed skill to their existing
instructions. `render_mode`/`fidelity` are read with `.get()` defaults because the
config key for `render_mode` is not added until PR-B.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_site_skill.py`:

```python
def test_run_architect_injects_skill_into_instructions(monkeypatch):
    import pytest
    pytest.importorskip("agno")
    from pathlib import Path
    from md2x.site import agents
    from md2x.site.schemas import Doc

    captured = {}

    def fake_make_agent(cfg, role, instructions, schema):
        captured["instructions"] = instructions

        class _Resp:
            content = agents._SitePlanModel(
                nav=[agents._NavItemModel(title="A", slug="a", group="")],
                order=["a"], index_title="Docs", index_intro="")

        class _Agent:
            def run(self, prompt):
                return _Resp()

        return _Agent()

    monkeypatch.setattr(agents, "_make_agent", fake_make_agent)
    docs = [Doc(path=Path("a.md"), title="A", outline=["x"], fragment_html="<p>a</p>")]
    cfg = {"site": {"archetype": "reading", "style_prompt": "", "layout": "auto"},
           "ai": {"model": "x:y", "architect_model": None, "retries": 1}}
    agents.run_architect(docs, cfg)
    assert "Living Site Skill" in captured["instructions"]
    assert "Plan a calm long-form reading site" in captured["instructions"]  # archetype instr still present


def test_run_page_injects_skill_into_instructions(monkeypatch):
    import pytest
    pytest.importorskip("agno")
    from pathlib import Path
    from md2x.site import agents
    from md2x.site.schemas import Doc, SitePlan

    captured = {}

    def fake_make_agent(cfg, role, instructions, schema):
        captured["instructions"] = instructions

        class _Resp:
            content = agents._EnhancementModel(tldr="t", takeaways=[], related=[])

        class _Agent:
            def run(self, prompt):
                return _Resp()

        return _Agent()

    monkeypatch.setattr(agents, "_make_agent", fake_make_agent)
    doc = Doc(path=Path("a.md"), title="A", outline=["x"], fragment_html="<p>a</p>")
    plan = SitePlan(nav=[], order=["a"])
    cfg = {"site": {"archetype": "reading", "fidelity": "light-enhance"},
           "ai": {"model": "x:y", "page_model": None, "retries": 1}}
    agents.run_page(doc, plan, cfg)
    assert "Living Site Skill" in captured["instructions"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_site_skill.py -k injects -v`
Expected: FAIL — `"Living Site Skill"` not in instructions (skill not yet wired).

- [ ] **Step 3: Wire the loader into `agents.py`**

Add the import after line 19 (`from .archetypes import ...`):

```python
from .skill import load_skill
```

In `run_architect`, replace the `instr = (...)` assignment (currently lines 103-109) with:

```python
    skill = load_skill(site["archetype"],
                       site.get("render_mode", "blocks"),
                       site.get("fidelity", "light-enhance"))
    instr = (
        (skill + "\n\n---\n\n" if skill else "")
        + arch["architect_instructions"]
        + (f"\n\nUser style brief: {site['style_prompt']}"
           if site.get("style_prompt") else "")
        + f"\n\nTarget layout: {layout}."
        + "\n\nUse exactly the given slugs. Output a complete SitePlan."
    )
```

In `run_page`, replace the `instr = (...)` assignment (currently lines 132-138) with:

```python
    skill = load_skill(cfg["site"]["archetype"],
                       cfg["site"].get("render_mode", "blocks"),
                       cfg["site"].get("fidelity", "light-enhance"))
    instr = (
        (skill + "\n\n---\n\n" if skill else "")
        + arch["page_instructions"]
        + "\n\nProduce ONLY additive aids: a one-sentence TL;DR, up to 4 key "
          "takeaways, and slugs of related pages. Do NOT rewrite or quote the "
          "body. Leave fields empty if nothing adds value."
        + f"\n\nOther pages you may relate to: {other}."
    )
```

- [ ] **Step 4: Run the full site test suite to verify green**

Run: `python -m pytest tests/test_site_skill.py tests/test_site_agents.py -v`
Expected: PASS — the new injection tests pass and the existing agent tests stay green (they monkeypatch `Agent`/short-circuit, so prepended instructions don't affect their assertions).

- [ ] **Step 5: Commit**

```bash
git add src/md2x/site/agents.py tests/test_site_skill.py
git commit -m "feat(site): inject the living-site skill into architect+page agents (PR-A)"
```

---

## Task 5: Full regression

- [ ] **Step 1: Run the whole suite**

Run: `python -m pytest -q`
Expected: all tests pass (existing + new `tests/test_site_skill.py`). If `agno` is not installed, agent tests `importorskip` and are skipped; the pure loader tests still run.

- [ ] **Step 2: Confirm no WIP staged**

Run: `git status --porcelain=v1`
Expected: `md2x.yaml` and `examples/sample.md` still appear as unstaged changes (` M` / ` D`) — never committed by this PR.

---

## Self-Review

- **Spec coverage:** PR-A row of the spec = "Skill scaffold + loader; inject into architect/page instructions." Task 1 (content) + Task 2 (loader) + Task 4 (injection) cover it; Task 3 (package-data) is the shipping requirement implied by "bundled into the package." ✓
- **Placeholder scan:** No TBD/TODO; every step has concrete code/commands. ✓
- **Type consistency:** `load_skill(archetype, render_mode, fidelity, artifacts)` signature is identical across the loader, its tests, and both call sites in `agents.py`. The marker strings asserted in tests (`"Living Site Skill"`, `"Render information in the shape"`, `"--ds-accent"`, `"md2x:export"`, `"Render mode: hybrid"`) match the exact content written in Task 1. ✓
- **Behavior preservation:** Schemas (`_SitePlanModel`, `_EnhancementModel`) and converters are untouched; only instruction text changes. Existing tests use `FakeAgent` / the `preserve` short-circuit, so they stay green. ✓
