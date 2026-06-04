# MD2X — Multi-Format + Packaging + Rename Design

**Date:** 2026-06-04
**Status:** Approved for planning
**Supersedes naming in:** `2026-06-04-md2pdf-decompose-design.md`

## Goal

Turn the `md2pdf` project into **`md2x`**: a properly packaged, pip-installable, open-source-ready CLI that converts Markdown (with Mermaid diagrams) to **PDF, DOCX, HTML, EPUB, and LaTeX** — while keeping the existing PDF output byte-for-byte identical.

## Top Constraint (non-negotiable)

**PDF functionality must not change.** Same pandoc+xelatex command, same flags, same output. Multi-format is added as a *parallel* code path; the PDF path is never edited. A snapshot test locks the PDF pandoc command so any regression fails loudly.

---

## Locked Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Scope | Multi-format **now** + rename + packaging | Rename "MD2X" only honest if it emits >1 format; pandoc already supports them cheaply |
| Distribution | **Hybrid** | `pip install md2x` uses `$PATH` binaries; `install.sh` stays as optional bundled toolchain. Code already falls back to PATH via `shutil.which` |
| Layout | Keep `src/` layout | pip best practice; prevents accidental uninstalled-import |
| Entry | `pyproject.toml` console script + `__main__.py` | Drops the root shim entirely |
| Shim | **Deleted** (`md2pdf.py`) | No longer needed once it's a real package |
| `pytest.ini` | **Deleted**, folded into `pyproject.toml` `[tool.pytest.ini_options]` | One less root file |
| `_check.py` | **Deleted**, folded into `md2x --check` | Single entry point |
| Format set | pdf, docx, html, epub, latex | All pandoc-native, clean suffixes, no input-extension collision |
| Dropped | gfm/`.md` output | `.md` collides with input; YAGNI |

---

## Rename Map (`md2pdf` → `md2x`)

| Item | From | To |
|---|---|---|
| Package dir | `src/md2pdf/` | `src/md2x/` |
| Import / CLI command | `md2pdf` | `md2x` |
| Config file | `md2pdf.yaml` / `.yml` | `md2x.yaml` / `.yml` |
| Intermediate md | `*._md2pdf.md` | `*._md2x.md` |
| Manifest json | `*._md2pdf.json` | `*._md2x.json` |
| Log prefix | `[md2pdf]` | `[md2x]` |
| Root shim | `md2pdf.py` | *(deleted)* |
| Check helper | `_check.py` | *(deleted → `md2x --check`)* |
| GitHub repo | `ChaoticQubit/MD2PDF` | user renames on GitHub; GitHub auto-redirects old URL, optional `git remote set-url` |
| Local dir | `~/Tools/MD2PDF` | optional `mv` by user; **code is path-agnostic** (`PROJECT_ROOT` computed via `parents[2]`) |

The working-directory rename is **out of scope for this change** (cwd cannot be moved mid-session safely). All code resolves paths dynamically, so the folder name is cosmetic.

---

## Architecture

### Module map (after change)

```
src/md2x/
├── __init__.py      public API re-exports + venv-yaml bootstrap (rename refs)
├── __main__.py      NEW — `python -m md2x` → cli.main()
├── paths.py         PROJECT_ROOT + local layout (rename .venv refs only)
├── config.py        DEFAULTS, deep_merge, load_config (rename md2x.yaml; add output.format)
├── binaries.py      resolve_binary (unchanged logic; no rename needed inside)
├── mermaid.py       extraction/captions/dot (unchanged)
├── renderers.py     mmdc/dot PNG (unchanged — already format-agnostic)
├── formats.py       NEW — format registry + detection
├── pandoc.py        build_pandoc_cmd (PDF, UNCHANGED) + build_generic_cmd (NEW)
├── pipeline.py      build(): target dispatch, xelatex gated on pdf
└── cli.py           argparse: add --to / --check; output-format inference
```

### `formats.py` (new)

A small registry — the single source of truth for "what does each target need."

```python
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path

@dataclass(frozen=True)
class Target:
    name: str          # "pdf" | "docx" | "html" | "epub" | "latex"
    writer: str | None # pandoc -t writer; None for pdf (engine-driven)
    suffix: str        # ".pdf" etc.
    standalone: bool    # pass --standalone
    embed: bool         # pass --embed-resources (html only)
    needs_xelatex: bool

TARGETS: dict[str, Target] = {
    "pdf":   Target("pdf",   None,    ".pdf",  False, False, True),
    "docx":  Target("docx",  "docx",  ".docx", False, False, False),
    "html":  Target("html",  "html",  ".html", True,  True,  False),
    "epub":  Target("epub",  "epub",  ".epub", False, False, False),
    "latex": Target("latex", "latex", ".tex",  True,  False, False),
}

EXT_TO_TARGET = {t.suffix: t.name for t in TARGETS.values()}
EXT_TO_TARGET[".htm"] = "html"

def detect_target(out_path: Path | None, override: str | None) -> Target:
    """--to override wins; else infer from output suffix; else pdf."""
    if override:
        if override not in TARGETS:
            raise ValueError(f"unknown format: {override}")
        return TARGETS[override]
    if out_path is not None:
        name = EXT_TO_TARGET.get(out_path.suffix.lower())
        if name:
            return TARGETS[name]
    return TARGETS["pdf"]
```

### `pandoc.py` (PDF path untouched; generic path added)

- `build_pandoc_cmd(input_md, output_pdf, cfg, pandoc_bin, xelatex_bin)` — **kept verbatim.** This is the PDF builder. Not edited.
- `build_generic_cmd(input_md, output, cfg, pandoc_bin, target)` — NEW. Portable subset only:

```python
def build_generic_cmd(input_md, output, cfg, pandoc_bin, target):
    cmd = [pandoc_bin, str(input_md), "-o", str(output)]
    if target.writer:
        cmd += ["-t", target.writer]
    if target.standalone:
        cmd.append("--standalone")
    if target.embed:
        cmd.append("--embed-resources")
    if cfg["output"]["toc"]:
        cmd += ["--toc", f"--toc-depth={cfg['output']['toc_depth']}"]
    if cfg["output"]["number_sections"]:
        cmd.append("--number-sections")
    if cfg["output"]["citation_processing"]:
        cmd.append("--citeproc")
    cmd += [f"--highlight-style={cfg['code']['highlight_style']}"]
    cmd += cfg["advanced"].get("pandoc_extra_args", [])
    return cmd
```

No `geometry`/`fontsize`/`papersize`/`linestretch`/`mainfont`/`classoption`/`header-includes`/`--listings`/`--pdf-engine` — those are LaTeX-only and would warn/error or be silently dropped for other writers. Excluding them keeps non-PDF output clean and robust.

- `build_cmd(input_md, output, cfg, target, pandoc_bin, xelatex_bin)` — dispatcher:

```python
def build_cmd(input_md, output, cfg, target, pandoc_bin, xelatex_bin):
    if target.name == "pdf":
        return build_pandoc_cmd(input_md, output, cfg, pandoc_bin, xelatex_bin)
    return build_generic_cmd(input_md, output, cfg, pandoc_bin, target)
```

### `pipeline.py`

- `build(md_path, out_path, cfg)` signature **unchanged** (keeps blast radius tiny).
- Derive `target = detect_target(out_path, cfg["output"].get("format"))` near the top. Output suffix is already correct because the CLI set it.
- Gate the binary requirement: `xelatex` is required **only** when `target.needs_xelatex`. pandoc always required. mmdc/dot warning unchanged.
- Replace `build_pandoc_cmd(...)` call with `build_cmd(..., target, ...)`.
- Mermaid rendering + markdown rewrite: **unchanged.** Image refs + `{width=...}` work across writers (LaTeX, docx, html, epub all honor width).
- Intermediate filename `._md2pdf.md` → `._md2x.md`; manifest `._md2pdf.json` → `._md2x.json`; log prefixes `[md2x]`.

### `cli.py`

- Add `-t/--to`, choices = `["pdf","docx","html","epub","latex"]`, default `None`.
- Add `--check` (action store_true) and make `input` `nargs="?"` so `md2x --check` needs no input. If `--check`: print resolved binaries (the old `_check.py` body) and return 0.
- Output naming + **single source of truth** for format. Precedence: `--to` > yaml `output.format` > `-o` extension > pdf. CLI resolves it once and writes the concrete name back into `cfg` so `build()` never re-guesses differently:

```python
from .formats import detect_target
target = detect_target(args.output, args.to or cfg["output"].get("format"))
cfg["output"]["format"] = target.name          # concrete; pipeline trusts this
out = args.output or args.input.with_suffix(target.suffix)
```

  → `md2x doc.md` still produces `doc.pdf` (identical default). `md2x doc.md -o out.docx` → docx. `md2x doc.md --to html` → `doc.html`.
- `main()` returns `int` (console-script exit code).

### `config.py`

- `load_config` candidate filenames: `md2x.yaml`, `md2x.yml` (next to input and in project root).
- Add `"format": None` under `output` — **null means infer from output extension** (defaulting to pdf). An explicit value (`pdf`/`docx`/…) forces that format. This keeps direct `build(md, "x.docx", cfg)` API callers correct: with `format=None` the pipeline infers `docx` from the suffix. Remove `default_suffix` (replaced by `target.suffix`). Update the two `[md2pdf]` prints to `[md2x]`.

---

## Packaging

### `pyproject.toml` (new, PEP 621, setuptools backend)

```toml
[build-system]
requires = ["setuptools>=64", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "md2x"
version = "0.1.0"
description = "Convert Markdown (with Mermaid diagrams) to PDF, DOCX, HTML, EPUB, and LaTeX."
readme = "README.md"
requires-python = ">=3.10"
license = { text = "MIT" }
authors = [{ name = "ChaoticQubit", email = "chaoticqubit@gmail.com" }]
keywords = ["markdown", "pdf", "pandoc", "mermaid", "docx", "html", "epub", "converter"]
classifiers = [
    "Development Status :: 4 - Beta",
    "Environment :: Console",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: MIT License",
    "Programming Language :: Python :: 3",
    "Topic :: Text Processing :: Markup",
    "Topic :: Documentation",
]
dependencies = ["pyyaml>=6"]

[project.optional-dependencies]
dev = ["pytest>=8"]

[project.urls]
Homepage = "https://github.com/ChaoticQubit/MD2X"
Repository = "https://github.com/ChaoticQubit/MD2X"
Issues = "https://github.com/ChaoticQubit/MD2X/issues"

[project.scripts]
md2x = "md2x.cli:main"

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src"]
addopts = "-ra"
```

### `src/md2x/__main__.py` (new)

```python
from .cli import main
raise SystemExit(main())
```

### `LICENSE` (new)

Standard MIT text, "Copyright (c) 2026 ChaoticQubit". Matches the README's MIT claim (currently unbacked).

### Why hybrid distribution works with no resolution changes

`resolve_binary` order is `.bin/ → .tools/**/bin → node_modules/.bin → shutil.which(PATH)`.
- **Editable clone** (`pip install -e .`): `paths.py` stays in `src/md2x/`, `parents[2]` = repo root → local bundled binaries found if `install.sh` was run.
- **pip from PyPI/site-packages**: `parents[2]` points outside any project; `.bin`/`.tools` don't exist → silently falls through to `$PATH`. `ensure_venv_yaml` finds no `.venv` → no-op (PyYAML is a declared dependency, already importable).

No code change needed for either mode.

---

## Tooling Updates

- **`install.sh`**: after `pip install pyyaml pytest`, add `pip install -e .` (editable) so `.venv/bin/md2x` exists. Update echoes/comments `md2pdf`→`md2x`. The PDF toolchain steps (node/pandoc/tinytex/graphviz) are unchanged.
- **`Makefile`**: drop `SCRIPT`; `sample`/`pdf` targets run `PYTHONPATH=src $(PY) -m md2x ...`; `check` runs `PYTHONPATH=src $(PY) -m md2x --check`; clean targets update `._md2x.*` glob. `test` unchanged.
- **`.gitignore`**: stop ignoring `docs/` (track specs/plans). Update ignore globs `*._md2pdf.*` → `*._md2x.*`. Keep `.claude/`, build artifacts (`build/`, `dist/`, `*.egg-info/`) added.
- **`md2pdf.yaml`** → **`md2x.yaml`**: rename file, update inline docs, add `output.format: null` (comment: `null` = infer from output extension; set `pdf`/`docx`/`html`/`epub`/`latex` to force) and note that `page`/`fonts`/`colors`/`advanced.header_includes` apply to **PDF/LaTeX only**.

---

## Testing Strategy

All existing 44 tests keep passing (import paths `md2pdf`→`md2x`). New coverage for multi-format and packaging.

### Rename (mechanical)
- Every `import md2pdf...` / `md2pdf.` → `md2x`. `tests/conftest.py`, `test_e2e.py` references.

### PDF-invariance lock (new)
- `test_pandoc_cmd.py::test_pdf_command_snapshot`: assert `build_pandoc_cmd(in, out.pdf, deep_merge(DEFAULTS,{}), "pandoc","xelatex")` equals the exact current arg list (hard-coded golden). Any drift = fail.
- Existing PDF flag assertions retained.

### `formats.py` (new — `test_formats.py`)
- `.pdf`/`.docx`/`.html`/`.htm`/`.epub`/`.tex` → correct target.
- `--to` override beats extension.
- unknown `--to` raises; unknown extension with no override → pdf default.

### Generic command (new — in `test_pandoc_cmd.py`)
- docx/html/epub: command contains `-t <writer>`, `--highlight-style`; **excludes** `--pdf-engine`, `geometry`, any `-V` font var.
- html: contains `--standalone --embed-resources`.
- toc/number_sections/citeproc/pandoc_extra_args flow through.

### CLI (new — in `test_cli.py`)
- `--to docx` with no `-o` → out suffix `.docx`.
- `-o x.html` infers html target.
- default (no flag) → `.pdf` (regression guard).
- `md2x --check` with no input → exits 0, prints binary lines (monkeypatched resolve).

### Pipeline (new — in `test_pipeline.py`)
- Hermetic docx build with fake `pandoc` stub and **no** xelatex on PATH → succeeds (proves xelatex not required for non-pdf). Asserts fake pandoc received `-t docx` and no `--pdf-engine`.
- Existing PDF pipeline tests unchanged.

### Gated E2E (`test_e2e.py`)
- Keep the real PDF test.
- Add `test_real_md_to_docx` gated on `pandoc` only (no xelatex/dot needed): build `examples/sample.md` → `.docx`, assert exists, size > 1024, and ZIP magic `PK\x03\x04` (docx is a zip). Proves the multi-format path end-to-end with the real toolchain.

---

## README Rewrite (open-source oriented)

New structure aimed at a stranger landing on the GitHub page:

1. **Title + one-line pitch** — "md2x — Markdown → PDF, Word, HTML & EPUB, with Mermaid diagrams rendered automatically."
2. **Badges** — License (MIT), Python ≥3.10. (No CI badge; no CI yet.)
3. **Why md2x** — 4–5 feature bullets (multi-format, auto Mermaid render with mmdc/dot fallback, per-document YAML config, optional fully-local toolchain, zero global pollution).
4. **Install — two paths:**
   - **(A) pip** (bring-your-own tools): `pip install md2x` (or `pipx`), plus one-liners for pandoc/xelatex/node/graphviz on macOS (brew) and Linux (apt). Note xelatex only needed for PDF.
   - **(B) clone + bundled toolchain**: `git clone … && make install` for the self-contained ~700 MB local install.
5. **Quickstart** — `md2x doc.md`, `md2x doc.md -o out.docx`, `md2x doc.md --to html`, `--theme dark`, etc.
6. **Supported formats** — table (format / flag / requires).
7. **Configuration** — short `md2x.yaml` overview + precedence list + per-document override; link to the annotated file.
8. **How it works** — the render→rewrite→pandoc pipeline (kept, updated for multi-format).
9. **Troubleshooting** — kept, updated names.
10. **Contributing** — dev install (`pip install -e ".[dev]"`), `make test`, where modules live.
11. **License** — MIT, link to `LICENSE`.

The current install-centric content is preserved but demoted under path (B); the lead now serves discovery and quick adoption.

---

## Out of Scope (YAGNI)

- gfm/plain-markdown output (extension collision, low value).
- Publishing to PyPI (this makes the package *ready*; the actual `twine upload` is a separate manual step).
- CI / GitHub Actions.
- Windows support (installer is bash/macOS-Linux only, unchanged).
- Per-format theming beyond pandoc defaults (e.g. docx reference-doc, custom CSS) — future enhancement.
- Renaming the working directory or the GitHub repo (user actions; code is path-agnostic).

---

## Risks & Mitigations

| Risk | Mitigation |
|---|---|
| PDF output changes | PDF code path untouched; snapshot test + E2E `%PDF` guard |
| Package/module name collision returns | No root `md2x.py`; pure package + console script + `__main__.py` |
| pip-installed `PROJECT_ROOT` garbage | PATH fallback already handles it; documented; `ensure_venv_yaml` no-ops |
| Non-PDF pandoc args error | Generic builder uses only portable args; hermetic + gated docx tests verify |
| Rename misses a reference | Grep sweep for `md2pdf` across repo as a plan task; test suite catches import breaks |

---

## Success Criteria

1. `pip install -e .` → `md2x` command works; `python -m md2x` works; no root shim.
2. `md2x doc.md` produces a PDF **identical** to today (snapshot + E2E pass).
3. `md2x doc.md -o out.docx` / `--to html` / `--to epub` / `--to latex` produce valid files.
4. `md2x --check` replaces `make check`.
5. No file, symbol, config key, or doc references `md2pdf` (grep-clean).
6. `pytest.ini` and `_check.py` gone; config in `pyproject.toml`.
7. All tests green (existing 44 + new format/packaging tests), including a gated real docx E2E.
8. README reads as an open-source tool page with pip + clone install paths; `LICENSE` file present.
