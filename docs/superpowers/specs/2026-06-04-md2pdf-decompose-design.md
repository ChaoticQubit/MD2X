# md2pdf — Package Decomposition + Integration Tests

**Date:** 2026-06-04
**Status:** Approved
**Type:** Refactor (behavior-preserving) + new test suite

## Goal

Split the 580-line `md2pdf.py` into a readable `src/md2pdf/` package of focused
modules, keep every existing entry point working unchanged, and add a detailed
integration test suite (hermetic always-run + gated real `md→PDF` E2E).

This is a **behavior-preserving** refactor. Every `sys.exit`, stderr message,
print line, and return code stays byte-identical. The tests lock current
behavior in place so the split is provably safe.

## Constraints (discovered from codebase)

- `md2pdf.py` is invoked three ways, all must keep working:
  1. `./md2pdf.py INPUT.md` (shebang, `chmod +x`, documented in README)
  2. `Makefile`: `$(PY) md2pdf.py $(IN)` (targets `sample`, `pdf`)
  3. `_check.py`: `sys.path.insert(0, "."); import md2pdf as m; m.resolve_binary(...)`
- `PROJECT_ROOT = Path(__file__).resolve().parent` anchors resolution of
  `.bin/`, `.tools/`, `.venv/`, `node_modules/.bin/`. Moving code must NOT move
  this anchor off the repo root.
- Dependency-light by design (`package.json`: "No globals"). `.venv` currently
  holds only `pip` + `PyYAML`. Python 3.14.
- Binaries present on this machine: `pandoc`, `xelatex` (TinyTeX), `dot` all
  resolve via `.bin/`; `mmdc` only via `.bin/`/`node_modules` (not system PATH).
  → real E2E is feasible using the `dot` renderer (flowchart only, no mmdc).

## Target Layout

```
MD2PDF/
├── md2pdf.py                 # thin back-compat shim (entry + re-exports)
├── src/md2pdf/
│   ├── __init__.py           # runs ensure_venv_yaml(); re-exports public API
│   ├── paths.py              # PROJECT_ROOT, LOCAL_BIN/TOOLS/NPM_BIN/VENV, ensure_venv_yaml
│   ├── config.py             # DEFAULTS, deep_merge, load_config
│   ├── binaries.py           # resolve_binary
│   ├── mermaid.py            # MERMAID_RE, CAPTION/EDGE/NODE regexes, extract_caption, mermaid_to_dot
│   ├── renderers.py          # render_via_mmdc, render_via_dot, render_block
│   ├── pandoc.py             # build_pandoc_cmd
│   ├── pipeline.py           # build
│   └── cli.py                # apply_cli_overrides, main, argument parser
├── tests/
│   ├── conftest.py
│   ├── fixtures/
│   │   ├── sample.md         # has a ```mermaid flowchart``` block
│   │   └── sample.yaml       # minimal config override
│   ├── test_config.py
│   ├── test_binaries.py
│   ├── test_mermaid.py
│   ├── test_renderers.py
│   ├── test_pandoc_cmd.py
│   ├── test_pipeline.py
│   ├── test_cli.py
│   └── test_e2e.py
├── pytest.ini
└── _check.py                 # UNCHANGED
```

## Module Boundaries (acyclic dependency graph)

| Module | Public surface | Depends on |
|---|---|---|
| `paths.py` | `PROJECT_ROOT`, `LOCAL_BIN`, `LOCAL_TOOLS`, `LOCAL_NPM_BIN`, `LOCAL_VENV`, `ensure_venv_yaml()` | stdlib only |
| `config.py` | `DEFAULTS`, `deep_merge()`, `load_config()` | `paths` (PROJECT_ROOT), `yaml` |
| `binaries.py` | `resolve_binary()` | `paths` (LOCAL_*) |
| `mermaid.py` | `MERMAID_RE`, `extract_caption()`, `mermaid_to_dot()` | stdlib `re` only |
| `renderers.py` | `render_via_mmdc()`, `render_via_dot()`, `render_block()` | `mermaid` (mermaid_to_dot) |
| `pandoc.py` | `build_pandoc_cmd()` | stdlib only |
| `pipeline.py` | `build()` | `config`, `binaries`, `mermaid`, `renderers`, `pandoc` |
| `cli.py` | `apply_cli_overrides()`, `main()` | `config`, `pipeline` |

Rule: lower rows never import higher rows. No cycles.

## Key Mechanics

### PROJECT_ROOT relocation
`paths.py` lives at `src/md2pdf/paths.py`, so:
```python
PROJECT_ROOT = Path(__file__).resolve().parents[2]   # md2pdf → src → repo root
```
All `LOCAL_*` derive from `PROJECT_ROOT` exactly as before, so `.bin/`,
`.tools/`, `.venv/`, `node_modules/.bin/` resolve identically.

### Back-compat shim (`md2pdf.py`)
```python
#!/usr/bin/env python3
"""Entry shim. Real code lives in src/md2pdf/. Kept at repo root so
`./md2pdf.py`, `make`, and `import md2pdf` (from _check.py) keep working."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from md2pdf.cli import main                       # noqa: E402
from md2pdf.binaries import resolve_binary        # noqa: E402,F401  (_check.py)
from md2pdf.pipeline import build                 # noqa: E402,F401
from md2pdf.config import load_config, deep_merge, DEFAULTS  # noqa: E402,F401

if __name__ == "__main__":
    sys.exit(main() or 0)
```
The module docstring of the original (usage text) moves to `cli.py`.

### venv-yaml bootstrap timing
`ensure_venv_yaml()` is defined in `paths.py` and **called once** from
`src/md2pdf/__init__.py` at package import. The shim imports `md2pdf.cli`,
which triggers `md2pdf/__init__.py` first — same effect as today's
module-level `_ensure_venv_yaml()` call, before any `import yaml` in `config`.

### Public re-exports (`src/md2pdf/__init__.py`)
```python
from .paths import ensure_venv_yaml, PROJECT_ROOT
ensure_venv_yaml()
from .config import DEFAULTS, deep_merge, load_config
from .binaries import resolve_binary
from .pipeline import build
from .cli import main
```

## Test Plan

Framework: **pytest** (added to `.venv`). `pytest.ini` sets `pythonpath = src`
so tests `import md2pdf.config` etc. directly (not via the shim).

### conftest.py fixtures
- `repo_root` — path to the real repo root.
- `fake_bin(tmp_path)` — factory: writes an executable stub script into a temp
  `.bin` dir that, when run, deterministically produces output (e.g. a fake
  `pandoc` that writes a 1-byte `%PDF` file to its `-o` target; a fake `dot`
  that writes a tiny valid PNG; a fake `mmdc`).
- `sample_md` — copies `fixtures/sample.md` into a temp work dir.
- `binaries_available` — bool: `resolve_binary("pandoc")` and
  `resolve_binary("xelatex")` both non-None. Drives `skipUnless`.

### Hermetic suite (always runs — no real heavy binaries)

**test_config.py**
- `deep_merge`: nested override wins, missing keys preserved, non-dict replaces dict.
- `load_config`: explicit path > md-sibling yaml > PROJECT_ROOT yaml > DEFAULTS.
- `load_config`: malformed YAML → warns, falls back to DEFAULTS.
- `apply_cli_overrides`: each flag mutates the right key; `None`/`False` leave config untouched.

**test_binaries.py**
- Resolution order with monkeypatched `LOCAL_BIN`/`LOCAL_NPM_BIN`/`LOCAL_TOOLS`
  and `shutil.which`: override > .bin > node_modules/.bin > .tools/**/bin > PATH.
- Override pointing at non-existent file → `None`.
- `.tools` rglob only matches executable files.

**test_mermaid.py**
- `extract_caption`: title hint, `[bracket]` ≤60 chars, fallback.
- `mermaid_to_dot`: flowchart → digraph with expected nodes/edges; dashed
  (`-.->`), bold (`==>`) styles; direction map (TD→TB, LR→LR…); edge labels.
- `mermaid_to_dot`: returns `None` for non-flowchart/empty source.

**test_renderers.py**
- `render_block`: `prefer=mmdc|dot|auto` selects the right chain; falls through
  to second renderer when first fails; `(False, "none")` when both fail.
  (monkeypatch `render_via_mmdc`/`render_via_dot` to record calls.)
- `render_via_dot`: real call to a `fake_bin` `dot` stub → returns True and the
  PNG exists. (Exercises the subprocess path without needing real Graphviz.)

**test_pandoc_cmd.py**
- `build_pandoc_cmd` flag matrix: toc on/off + depth; fonts `None` omit vs set
  emit `mainfont/sansfont/monofont/CJKmainfont`; landscape classoption;
  number_sections; citeproc; listings; header_includes joined; extra_args appended.

**test_pipeline.py** (the core integration test — hermetic)
- `build()` with monkeypatched `render_block` (returns success + writes a stub
  PNG) and a `fake_bin` `pandoc` stub:
  - rewritten markdown embeds `![caption](rel){width=...}` + caption line.
  - `on_failure`: `keep_source` preserves fenced block; `omit` drops it;
    `error` calls `sys.exit`.
  - `emit_manifest` writes `*._md2pdf.json` with correct entries.
  - `no_clobber` refuses to overwrite.
  - `keep_intermediate` retains vs deletes `*._md2pdf.md`.
  - missing pandoc/xelatex → `sys.exit` with the documented message.

**test_cli.py**
- `main()` (via `argparse`) with `monkeypatch.setattr(sys, "argv", ...)` and a
  patched `build`: default output suffix applied; `--no-toc`/`--margin`/etc.
  reach config; input-not-found → `sys.exit`.

### Gated real E2E — test_e2e.py
`@pytest.mark.skipif(not binaries_available)`:
- Render `fixtures/sample.md` (flowchart mermaid block) to a real PDF using the
  real `pandoc` + `xelatex` + `dot` (force `prefer: dot` so `mmdc` not needed).
- Assert: exit 0, output file exists, size > 1 KB, first bytes == `b"%PDF"`.
- Clean up temp work dir + generated `diagrams/`.

## Tooling Changes

- **install.sh**: append `pytest` to the `.venv` pip install step.
- **Makefile**: add
  ```make
  test:
  	@.venv/bin/python -m pytest
  ```
  and list it in `help`. `.PHONY` updated.
- **pytest.ini**:
  ```ini
  [pytest]
  testpaths = tests
  pythonpath = src
  addopts = -ra
  ```

## Out of Scope (YAGNI)

- No behavior changes, no new CLI flags, no new config keys.
- No new renderers or output formats.
- No type-checking/lint tooling beyond what exists.
- `_check.py` is not rewritten (works through the shim).

## Verification

1. `make check` still prints resolved binaries (proves shim `import md2pdf`).
2. `./md2pdf.py --help` prints the same usage (proves shebang entry).
3. `make test` → all hermetic tests pass + E2E runs (binaries present).
4. `make sample` produces the same PDF as before the refactor.
