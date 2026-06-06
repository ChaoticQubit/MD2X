# PR-B — DesignSystem + render_mode axis — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The architect emits a `DesignSystem` (design DNA) → a `--ds-*` CSS-variable layer consumed by every shell plus a living-design-system tokens→swatches page; and `site.render_mode` becomes a validated config axis (`blocks|hybrid|full`).

**Architecture:** `DesignSystem` is a plain dataclass carried on `SitePlan.design` (default-factory so the `--no-ai` path and existing callers keep working). `render.py` injects a sanitized `:root{--ds-*}` block ahead of the shell CSS; the existing palette vars (`--bg/--fg/...`) derive from the `--ds-*` layer with today's hardcoded values as fallback, so default output is byte-identical while a custom DesignSystem restyles the site. Validation of the two prose-independent axes (`render_mode`, `fidelity`) lives in a small `modes.py` and is applied once in the pipeline (warn + fall back, never crash — matches the existing unsafe-accent pattern). Colour/length/font sanitization at render time is the single trust boundary (defense in depth, like `_accent`).

**Tech Stack:** Python 3.10+, dataclasses, agno/pydantic (architect output only), pytest. No new deps.

---

## File Structure

- Create: `src/md2x/site/modes.py` — `RENDER_MODES`, `FIDELITIES`, `validate_render_mode`, `validate_fidelity`.
- Create: `src/md2x/site/design_css.py` — `design_css_vars(ds)` → `:root{--ds-*}`; `render_design_system_page(ds)` → standalone swatch page.
- Modify: `src/md2x/config.py` — add `site.render_mode: "blocks"` to DEFAULTS.
- Modify: `src/md2x/site/schemas.py` — add `DesignSystem` dataclass + `SitePlan.design`.
- Modify: `src/md2x/site/render.py` — `--ds-*` layer in `_document`; palette vars derive from it; seed `default_site_plan().design` from cfg accent; write `design-system.html` (multi-page).
- Modify: `src/md2x/site/agents.py` — `_DesignSystemModel`, `_SitePlanModel.design`, `_to_site_plan` conversion, architect instruction nudge.
- Modify: `src/md2x/site/pipeline.py` — normalize/validate render_mode+fidelity once at generate_site start.
- Modify: `src/md2x/site/skill/design-system.md` — document the concrete `--ds-*` contract.
- Test: `tests/test_site_modes.py`, `tests/test_site_design_css.py` (new); extend `tests/test_site_config.py`, `tests/test_site_schemas.py`, `tests/test_site_render.py`, `tests/test_site_agents.py`.

---

### Task 1: modes.py — render_mode + fidelity validation

**Files:** Create `src/md2x/site/modes.py`; Test `tests/test_site_modes.py`.

- [ ] **Step 1: Failing test**

```python
# tests/test_site_modes.py
from md2x.site import modes


def test_valid_render_modes_pass_through():
    for m in ("blocks", "hybrid", "full"):
        assert modes.validate_render_mode(m) == m


def test_unknown_render_mode_falls_back_to_default():
    assert modes.validate_render_mode("banana") == modes.DEFAULT_RENDER_MODE
    assert modes.DEFAULT_RENDER_MODE == "blocks"


def test_valid_fidelities_pass_through():
    for f in ("preserve", "light-enhance", "synthesize"):
        assert modes.validate_fidelity(f) == f


def test_unknown_fidelity_falls_back_to_default():
    assert modes.validate_fidelity("nope") == modes.DEFAULT_FIDELITY
```

- [ ] **Step 2: Run — expect ImportError/FAIL.** `.venv/bin/python -m pytest tests/test_site_modes.py -q`

- [ ] **Step 3: Implement**

```python
# src/md2x/site/modes.py
"""The two prose-independent site axes, validated.

render_mode = HOW html is produced: blocks | hybrid | full.
fidelity    = how much the AI may rewrite prose: preserve | light-enhance | synthesize.
Both are orthogonal to the archetype. Unknown values warn and fall back to the
default rather than crash (consistent with the unsafe-accent fallback).
"""
from __future__ import annotations

from ..log import get_logger

log = get_logger(__name__)

RENDER_MODES = ("blocks", "hybrid", "full")
DEFAULT_RENDER_MODE = "blocks"
FIDELITIES = ("preserve", "light-enhance", "synthesize")
DEFAULT_FIDELITY = "light-enhance"


def validate_render_mode(mode: str) -> str:
    if mode in RENDER_MODES:
        return mode
    log.warning("unknown render_mode %r; using %r (choose from %s)",
                mode, DEFAULT_RENDER_MODE, ", ".join(RENDER_MODES))
    return DEFAULT_RENDER_MODE


def validate_fidelity(fidelity: str) -> str:
    if fidelity in FIDELITIES:
        return fidelity
    log.warning("unknown fidelity %r; using %r (choose from %s)",
                fidelity, DEFAULT_FIDELITY, ", ".join(FIDELITIES))
    return DEFAULT_FIDELITY
```

- [ ] **Step 4: Run — expect PASS.**
- [ ] **Step 5: Commit** `feat(site): render_mode + fidelity validation (PR-B)`

---

### Task 2: config — site.render_mode default

**Files:** Modify `src/md2x/config.py`; Test `tests/test_site_config.py`.

- [ ] **Step 1: Failing test** (append)

```python
def test_defaults_have_render_mode():
    cfg = config.deep_merge(config.DEFAULTS, {})
    assert cfg["site"]["render_mode"] == "blocks"
```

- [ ] **Step 2: Run — FAIL (KeyError).**
- [ ] **Step 3: Implement** — in `DEFAULTS["site"]`, add after `archetype`:

```python
        "render_mode": "blocks",     # blocks | hybrid | full  (flips to hybrid in PR-H)
```

- [ ] **Step 4: Run — PASS.**
- [ ] **Step 5: Commit** `feat(config): add site.render_mode key (PR-B)`

---

### Task 3: schemas — DesignSystem dataclass + SitePlan.design

**Files:** Modify `src/md2x/site/schemas.py`; Test `tests/test_site_schemas.py`.

- [ ] **Step 1: Failing test** (append)

```python
def test_designsystem_defaults():
    from md2x.site.schemas import DesignSystem
    ds = DesignSystem()
    assert ds.accent == "#2563eb"
    assert ds.density == "comfortable"
    assert ds.bg and ds.fg and ds.font_sans


def test_siteplan_has_default_designsystem():
    plan = SitePlan(nav=[NavItem(title="A", slug="a")], order=["a"])
    assert plan.design.accent == "#2563eb"
```

- [ ] **Step 2: Run — FAIL (ImportError/AttributeError).**
- [ ] **Step 3: Implement** — add `DesignSystem` above `SitePlan`, then a field on `SitePlan`.

```python
@dataclass
class DesignSystem:
    """Design DNA → CSS custom properties (--ds-*). Consumed by every shell and
    (later) every artifact iframe, so even free-form output stays on-brand.
    Raw strings here; sanitized at render time (single trust boundary)."""
    accent: str = "#2563eb"
    bg: str = "#ffffff"
    fg: str = "#1f2328"
    muted: str = "#57606a"
    card: str = "#f6f8fa"
    border: str = "#d0d7de"
    radius: str = "8px"
    font_sans: str = ('-apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,'
                      'Arial,sans-serif')
    font_mono: str = ('ui-monospace,SFMono-Regular,"SF Mono",Menlo,Consolas,'
                      'monospace')
    density: str = "comfortable"        # comfortable | compact
```

Add to `SitePlan` (after `theme_accent`):

```python
    design: DesignSystem = field(default_factory=DesignSystem)
```

- [ ] **Step 4: Run — PASS.**
- [ ] **Step 5: Commit** `feat(site): DesignSystem schema + SitePlan.design (PR-B)`

---

### Task 4: design_css — sanitized --ds-* vars + living-design-system page

**Files:** Create `src/md2x/site/design_css.py`; Test `tests/test_site_design_css.py`.

- [ ] **Step 1: Failing test**

```python
# tests/test_site_design_css.py
from md2x.site.schemas import DesignSystem
from md2x.site import design_css as dc


def test_vars_emit_ds_custom_properties():
    css = dc.design_css_vars(DesignSystem())
    for v in ("--ds-accent", "--ds-bg", "--ds-fg", "--ds-muted", "--ds-card",
              "--ds-border", "--ds-radius", "--ds-font-sans", "--ds-space-1"):
        assert v in css
    assert ":root" in css


def test_custom_accent_flows_in():
    css = dc.design_css_vars(DesignSystem(accent="#ff0000"))
    assert "#ff0000" in css


def test_unsafe_color_falls_back_to_default():
    bad = DesignSystem(accent="red}</style><script>x</script>")
    css = dc.design_css_vars(bad)
    assert "<script>" not in css
    assert "#2563eb" in css  # default accent restored


def test_unsafe_radius_and_font_rejected():
    css = dc.design_css_vars(DesignSystem(radius="8px;}evil", font_sans="a;}b"))
    assert "evil" not in css and "}b" not in css


def test_compact_density_tightens_spacing():
    comfy = dc.design_css_vars(DesignSystem(density="comfortable"))
    compact = dc.design_css_vars(DesignSystem(density="compact"))
    assert comfy != compact


def test_design_system_page_is_self_contained_swatches():
    page = dc.render_design_system_page(DesignSystem(accent="#ff0000"))
    assert "<!doctype html>" in page.lower()
    assert "#ff0000" in page                    # swatch label
    assert "--ds-accent" in page                 # consumes the token layer
    assert "http://" not in page and "https://" not in page
```

- [ ] **Step 2: Run — FAIL.**
- [ ] **Step 3: Implement**

```python
# src/md2x/site/design_css.py
"""DesignSystem -> sanitized CSS custom properties (--ds-*), plus the living
design-system page (Thariq's tokens -> copyable swatches).

Sanitization here is the single trust boundary for design DNA: an unsafe colour,
length, or font-stack from config or the model can never break out of <style>.
"""
from __future__ import annotations

import html
import re

from ..log import get_logger
from .render import _DEFAULT_ACCENT, _SAFE_COLOR
from .schemas import DesignSystem

log = get_logger(__name__)

_SAFE_LEN = re.compile(r"^[0-9]+(?:\.[0-9]+)?(?:px|rem|em|%)$")
# Font stacks: letters/digits/space/comma plus quotes and hyphen only.
_SAFE_FONT = re.compile(r'^[\w ,"\'\-]+$')
_DEFAULTS = DesignSystem()

# Density -> 4-step spacing scale (rem).
_SPACE = {
    "comfortable": ("0.5rem", "1rem", "1.5rem", "2.5rem"),
    "compact":     ("0.35rem", "0.7rem", "1.1rem", "1.8rem"),
}


def _color(value: str, fallback: str) -> str:
    value = (value or "").strip()
    if _SAFE_COLOR.match(value):
        return value
    log.warning("design: unsafe colour %r; using %s", value, fallback)
    return fallback


def _len(value: str, fallback: str) -> str:
    value = (value or "").strip()
    if _SAFE_LEN.match(value):
        return value
    log.warning("design: unsafe length %r; using %s", value, fallback)
    return fallback


def _font(value: str, fallback: str) -> str:
    value = (value or "").strip()
    if _SAFE_FONT.match(value):
        return value
    log.warning("design: unsafe font %r; using default", value)
    return fallback


def _tokens(ds: DesignSystem) -> dict[str, str]:
    density = ds.density if ds.density in _SPACE else "comfortable"
    s1, s2, s3, s4 = _SPACE[density]
    return {
        "--ds-accent": _color(ds.accent, _DEFAULT_ACCENT),
        "--ds-bg": _color(ds.bg, _DEFAULTS.bg),
        "--ds-fg": _color(ds.fg, _DEFAULTS.fg),
        "--ds-muted": _color(ds.muted, _DEFAULTS.muted),
        "--ds-card": _color(ds.card, _DEFAULTS.card),
        "--ds-border": _color(ds.border, _DEFAULTS.border),
        "--ds-radius": _len(ds.radius, _DEFAULTS.radius),
        "--ds-font-sans": _font(ds.font_sans, _DEFAULTS.font_sans),
        "--ds-font-mono": _font(ds.font_mono, _DEFAULTS.font_mono),
        "--ds-density": density,
        "--ds-space-1": s1, "--ds-space-2": s2,
        "--ds-space-3": s3, "--ds-space-4": s4,
    }


def design_css_vars(ds: DesignSystem) -> str:
    """`:root{--ds-*: ...}` — sanitized, ready to drop in a <style>."""
    body = ";".join(f"{k}:{v}" for k, v in _tokens(ds).items())
    return f":root{{{body}}}"


def render_design_system_page(ds: DesignSystem, *, title: str = "Design System") -> str:
    """Standalone tokens -> copyable swatches page. Self-contained, no network."""
    toks = _tokens(ds)
    swatches = "".join(
        f'<button class="sw" data-c="{html.escape(v, quote=True)}" '
        f'style="--c:{v}"><span class="chip"></span>'
        f'<code>{html.escape(k)}</code><code class="val">{html.escape(v)}</code>'
        f"</button>"
        for k, v in toks.items() if k.endswith(("accent", "bg", "fg", "muted",
                                                 "card", "border"))
    )
    spaces = "".join(
        f'<div class="sp"><span style="width:{toks[k]}"></span><code>{html.escape(k)}</code>'
        f'<code class="val">{html.escape(toks[k])}</code></div>'
        for k in ("--ds-space-1", "--ds-space-2", "--ds-space-3", "--ds-space-4")
    )
    css = (
        f"{design_css_vars(ds)}"
        "*{box-sizing:border-box}body{margin:0;background:var(--ds-bg);"
        "color:var(--ds-fg);font-family:var(--ds-font-sans);padding:var(--ds-space-4)}"
        "h1{font-size:1.8rem}h2{margin-top:var(--ds-space-4);font-size:1.1rem;"
        "text-transform:uppercase;letter-spacing:.08em;color:var(--ds-muted)}"
        ".grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));"
        "gap:var(--ds-space-2)}"
        ".sw{display:flex;flex-direction:column;gap:6px;align-items:flex-start;"
        "padding:var(--ds-space-2);border:1px solid var(--ds-border);"
        "border-radius:var(--ds-radius);background:var(--ds-card);cursor:pointer;"
        "font-family:var(--ds-font-mono);font-size:.78rem;color:var(--ds-fg)}"
        ".chip{width:100%;height:46px;border-radius:calc(var(--ds-radius) - 2px);"
        "background:var(--c);border:1px solid var(--ds-border)}"
        ".val{color:var(--ds-muted)}"
        ".sp{display:flex;align-items:center;gap:10px;margin:8px 0;"
        "font-family:var(--ds-font-mono);font-size:.78rem}"
        ".sp span{height:14px;background:var(--ds-accent);border-radius:3px;display:inline-block}"
        ".copied{outline:2px solid var(--ds-accent)}"
    )
    js = ("document.querySelectorAll('.sw').forEach(function(b){"
          "b.addEventListener('click',function(){var c=b.getAttribute('data-c');"
          "if(navigator.clipboard)navigator.clipboard.writeText(c);"
          "b.classList.add('copied');setTimeout(function(){b.classList.remove('copied')},700);"
          "});});")
    return (
        '<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>{html.escape(title)}</title>\n<style>{css}</style>\n</head>\n<body>\n"
        f"<h1>{html.escape(title)}</h1>\n"
        f'<h2>Colour tokens</h2>\n<div class="grid">{swatches}</div>\n'
        f"<h2>Spacing</h2>\n{spaces}\n"
        f"<script>{js}</script>\n</body>\n</html>\n"
    )
```

- [ ] **Step 4: Run — PASS.**
- [ ] **Step 5: Commit** `feat(site): --ds-* vars + living design-system page (PR-B)`

---

### Task 5: render — inject --ds-* layer; seed design; write design-system.html

**Files:** Modify `src/md2x/site/render.py`; Test `tests/test_site_render.py`.

- [ ] **Step 1: Failing tests** (append)

```python
def test_ds_vars_present_in_page():
    cfg = _cfg()
    plan = render.default_site_plan(_docs(), cfg)
    h = render.build_page(_docs()[0], plan, PageEnhancement(), cfg,
                          assets_inline=True)
    assert "--ds-accent" in h and "--ds-bg" in h


def test_custom_designsystem_bg_flows_into_output():
    from md2x.site.schemas import DesignSystem
    cfg = _cfg()
    plan = render.default_site_plan(_docs(), cfg)
    plan.design = DesignSystem(bg="#101010")
    h = render.build_page(_docs()[0], plan, PageEnhancement(), cfg,
                          assets_inline=True)
    assert "#101010" in h


def test_write_site_multipage_emits_design_system_page(tmp_path):
    cfg = _cfg()
    docs = _docs()
    plan = render.default_site_plan(docs, cfg)
    enh = {d.slug: PageEnhancement() for d in docs}
    render.write_site(tmp_path, docs, plan, enh, cfg, layout="multi-page")
    assert (tmp_path / "design-system.html").exists()
```

- [ ] **Step 2: Run — FAIL.**

- [ ] **Step 3: Implement.** In `render.py`:

(a) Import at top: `from .design_css import design_css_vars, render_design_system_page`.

(b) `_BASE_CSS` `:root` — derive palette from ds layer (keep `%ACCENT%` for accent + existing security tests). Replace the first `:root{...}` line:

```python
:root { --accent: %ACCENT%;
        --bg: var(--ds-bg,#fff); --fg: var(--ds-fg,#1f2328);
        --muted: var(--ds-muted,#57606a); --card: var(--ds-card,#f6f8fa);
        --border: var(--ds-border,#d0d7de); --radius: var(--ds-radius,8px); }
```

(c) `default_site_plan` — seed design from cfg accent:

```python
    from .schemas import DesignSystem
    accent = (cfg["site"].get("theme") or {}).get("accent") or DesignSystem().accent
    return SitePlan(nav=nav, order=[d.slug for d in docs],
                    index_title=cfg["site"].get("title") or "Documentation",
                    design=DesignSystem(accent=accent))
```

(d) `_document` — accept `ds_css` and place before head:

```python
def _document(title: str, shell: str, accent: str, body: str,
              *, assets_inline: bool, ds_css: str = "") -> str:
    ds = f"<style>{ds_css}</style>\n" if ds_css else ""
    if assets_inline:
        head = ds + f"<style>{SHELLS[shell].replace('%ACCENT%', accent)}</style>"
        tail = f"<script>{SHELL_JS[shell]}</script>"
    else:
        head = ds + '<link rel="stylesheet" href="assets/site.css">'
        tail = '<script src="assets/site.js"></script>'
    ...
```

(e) Each `build_*` (`build_page`, `build_index`, `build_single_page`, `build_deck`, `build_landing`) computes `ds_css = design_css_vars(plan.design)` (accent override → set `plan.design.accent` to resolved accent first, so iframe-era consumers see the real accent) and passes `ds_css=ds_css` to `_document`. Minimal form, e.g. in `build_page`:

```python
    accent = _accent(cfg, plan)
    ds_css = design_css_vars(_design_for(plan, accent))
    ...
    return _document(doc.title, "sidebar", accent, body,
                     assets_inline=assets_inline, ds_css=ds_css)
```

Add helper:

```python
def _design_for(plan: SitePlan, accent: str):
    """The plan's DesignSystem with its accent reconciled to the resolved accent."""
    from dataclasses import replace
    return replace(plan.design, accent=accent)
```

(f) `write_site`, multi-page branch — after writing pages + index, also write the design-system page and link it from the index footer. Write the file:

```python
        (out_dir / "design-system.html").write_text(
            render_design_system_page(_design_for(plan, accent)), encoding="utf-8")
```

(Index footer link is optional polish; the file existing satisfies the spec + test.)

- [ ] **Step 4: Run full render suite — PASS.** `.venv/bin/python -m pytest tests/test_site_render.py -q`
- [ ] **Step 5: Commit** `feat(site): inject --ds-* layer + emit design-system page (PR-B)`

---

### Task 6: agents — architect emits DesignSystem

**Files:** Modify `src/md2x/site/agents.py`; Test `tests/test_site_agents.py`.

- [ ] **Step 1: Failing test** (append to `tests/test_site_agents.py`, mirroring its FakeAgent pattern)

```python
def test_architect_designsystem_threads_through(monkeypatch):
    import pytest
    pytest.importorskip("agno")
    from pathlib import Path
    from md2x.site import agents
    from md2x.site.schemas import Doc

    def fake_make_agent(cfg, role, instructions, schema):
        class _Resp:
            content = agents._SitePlanModel(
                nav=[agents._NavItemModel(title="A", slug="a", group="")],
                order=["a"], index_title="Docs", index_intro="",
                design=agents._DesignSystemModel(accent="#abcdef", density="compact"))

        class _Agent:
            def run(self, prompt):
                return _Resp()
        return _Agent()

    monkeypatch.setattr(agents, "_make_agent", fake_make_agent)
    docs = [Doc(path=Path("a.md"), title="A", outline=["x"], fragment_html="<p>a</p>")]
    cfg = {"site": {"archetype": "reading", "style_prompt": "", "layout": "auto",
                    "render_mode": "blocks", "fidelity": "light-enhance"},
           "ai": {"model": "x:y", "architect_model": None, "retries": 1}}
    plan = agents.run_architect(docs, cfg)
    assert plan.design.accent == "#abcdef"
    assert plan.design.density == "compact"
```

- [ ] **Step 2: Run — FAIL (no `_DesignSystemModel` / `.design`).**

- [ ] **Step 3: Implement.** In `agents.py`:

Import: add `DesignSystem` to the schemas import line.

Add model:

```python
class _DesignSystemModel(BaseModel):
    accent: str = "#2563eb"
    bg: str = "#ffffff"
    fg: str = "#1f2328"
    muted: str = "#57606a"
    card: str = "#f6f8fa"
    border: str = "#d0d7de"
    radius: str = "8px"
    font_sans: str = Field(default=DesignSystem().font_sans)
    font_mono: str = Field(default=DesignSystem().font_mono)
    density: str = Field(default="comfortable",
                         description="comfortable | compact")
```

Add field to `_SitePlanModel`:

```python
    design: _DesignSystemModel = Field(default_factory=_DesignSystemModel)
```

Convert in `_to_site_plan` (build `DesignSystem` from `pm.design`):

```python
    d = pm.design
    design = DesignSystem(
        accent=d.accent, bg=d.bg, fg=d.fg, muted=d.muted, card=d.card,
        border=d.border, radius=d.radius, font_sans=d.font_sans,
        font_mono=d.font_mono, density=d.density)
    return SitePlan(..., theme_accent=pm.theme_accent, design=design)
```

Architect instruction nudge — in `run_architect`, append to `instr` before the agent call:

```python
        + "\n\nAlso emit a DesignSystem (palette + radius + density) that fits "
          "the content and style brief; it becomes the site's --ds-* tokens."
```

- [ ] **Step 4: Run — PASS** (and full `tests/test_site_agents.py`).
- [ ] **Step 5: Commit** `feat(site): architect emits DesignSystem design DNA (PR-B)`

---

### Task 7: pipeline — validate the two axes once

**Files:** Modify `src/md2x/site/pipeline.py`; Test `tests/test_site_pipeline.py` (add one).

- [ ] **Step 1: Failing test** (append; mirror existing pipeline test style — monkeypatch render.write_site to capture cfg)

```python
def test_generate_site_normalizes_bad_render_mode(tmp_path, monkeypatch):
    from md2x.site import pipeline
    seen = {}
    def fake_write_site(out_dir, docs, plan, enh, cfg, *, layout):
        seen["render_mode"] = cfg["site"]["render_mode"]
    monkeypatch.setattr(pipeline, "write_site", fake_write_site)
    md = tmp_path / "a.md"; md.write_text("# A\n\nbody\n")
    import md2x.config as config
    cfg = config.deep_merge(config.DEFAULTS, {})
    cfg["site"]["render_mode"] = "banana"
    rc = pipeline.generate_site([md], tmp_path / "out", cfg,
                                use_ai=False, layout="multi-page")
    assert rc == 0
    assert seen["render_mode"] == "blocks"   # normalized
```

- [ ] **Step 2: Run — FAIL.**
- [ ] **Step 3: Implement.** In `generate_site`, after `md_files` resolved and before archetype dispatch:

```python
    from .modes import validate_render_mode, validate_fidelity, DEFAULT_RENDER_MODE, DEFAULT_FIDELITY
    cfg["site"]["render_mode"] = validate_render_mode(
        cfg["site"].get("render_mode", DEFAULT_RENDER_MODE))
    cfg["site"]["fidelity"] = validate_fidelity(
        cfg["site"].get("fidelity", DEFAULT_FIDELITY))
    log.info("axes: render_mode=%s fidelity=%s",
             cfg["site"]["render_mode"], cfg["site"]["fidelity"])
```

- [ ] **Step 4: Run — PASS.**
- [ ] **Step 5: Commit** `feat(site): validate render_mode + fidelity in pipeline (PR-B)`

---

### Task 8: skill — document the --ds-* contract

**Files:** Modify `src/md2x/site/skill/design-system.md`.

- [ ] **Step 1:** Ensure the file names the concrete tokens the architect/author must consume: `--ds-accent --ds-bg --ds-fg --ds-muted --ds-card --ds-border --ds-radius --ds-font-sans --ds-font-mono --ds-space-1..4 --ds-density`, the rule "never hardcode colour/space — use the tokens", and that the architect emits the DesignSystem that seeds them. Keep the existing `--ds-accent` marker (test_site_skill relies on it).
- [ ] **Step 2: Commit** `docs(skill): concrete --ds-* token contract (PR-B)`

---

### Task 9: Regression + close-out

- [ ] **Step 1:** Run the full suite. `.venv/bin/python -m pytest -q`
- [ ] **Step 2:** Confirm WIP untouched: `git status --short` still shows only ` D examples/sample.md` and ` M md2x.yaml` (unstaged). `git log main..HEAD --oneline -- md2x.yaml examples/sample.md` is empty.
- [ ] **Step 3:** Mark PR-B task complete; proceed to PR-C.

---

## Self-Review

- **Spec coverage:** DesignSystem→CSS vars ✓ (Task 3/4/5); living-design-system page ✓ (Task 4/5); `render_mode` key+validation ✓ (Task 1/2/7). All PR-B spec rows covered.
- **Placeholders:** none — every code/test step is concrete.
- **Type consistency:** `DesignSystem` field names identical across schemas.py, design_css.py `_tokens`, agents.py `_DesignSystemModel`, and `_to_site_plan`. `design_css_vars`/`render_design_system_page` names consistent between Task 4 and Task 5.
- **Backward-compat:** default DesignSystem reproduces today's palette values, so existing render output/tests stay green; accent keeps the `%ACCENT%` path so the accent security tests are untouched.
