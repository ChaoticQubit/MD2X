# MD2X Multi-Format + Packaging + Rename Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rename `md2pdf` → `md2x`, package it as a pip-installable open-source CLI, and add DOCX/HTML/EPUB/LaTeX output alongside the existing PDF — without changing PDF behavior.

**Architecture:** Multi-format is a *parallel* code path: the PDF pandoc builder is never edited (a snapshot test locks it); a new `formats.py` registry + `build_generic_cmd` handle non-PDF writers. The package moves to `src/md2x/` with a `pyproject.toml` console entry point and `__main__.py`, eliminating the root shim. Binary resolution already falls back to `$PATH`, so the same code serves both `pip install md2x` (bring-your-own tools) and the bundled `install.sh` toolchain.

**Tech Stack:** Python ≥3.10, setuptools, pytest, pandoc + xelatex (PDF) / pandoc-only (other formats), Mermaid via mmdc/Graphviz dot, PyYAML.

**Spec:** `docs/superpowers/specs/2026-06-04-md2x-multiformat-packaging-design.md`

---

## File Structure (after this plan)

```
md2x/                          (repo root; folder name cosmetic — code is path-agnostic)
├── pyproject.toml             NEW — PEP 621 metadata, console script, pytest config
├── LICENSE                    NEW — MIT
├── README.md                  REWRITTEN — open-source landing page
├── md2x.yaml                  RENAMED from md2pdf.yaml; + `output.format` knob
├── Makefile                   targets use `python -m md2x`; check uses `--check`
├── install.sh                 + `pip install -e .`
├── .gitignore                 un-ignore docs/; add build/dist/egg-info
├── examples/sample.md         unchanged
├── src/md2x/                  RENAMED from src/md2pdf/
│   ├── __init__.py            re-exports (+ formats); venv-yaml bootstrap
│   ├── __main__.py            NEW — `python -m md2x`
│   ├── paths.py               unchanged
│   ├── config.py              + output.format=None; − default_suffix; md2x.yaml lookup
│   ├── binaries.py            unchanged
│   ├── mermaid.py             unchanged
│   ├── renderers.py           unchanged (already format-agnostic)
│   ├── formats.py             NEW — Target registry + detect_target
│   ├── pandoc.py              build_pandoc_cmd UNCHANGED + build_generic_cmd + build_cmd
│   ├── pipeline.py            target dispatch; xelatex gated on pdf
│   └── cli.py                 -t/--to, --check, target-driven output naming
└── tests/                     renamed imports + new format/cli/pipeline/e2e tests
    ├── conftest.py            test_formats.py        test_e2e.py (+docx)
    └── (existing 9 files, renamed) ...
```

**Deleted:** `md2pdf.py` (shim), `_check.py`, `pytest.ini`.

---

## Conventions for every task

- Run tests with the project venv: `.venv/bin/python -m pytest` (pytest + pyyaml already installed there).
- Run a single test file: `.venv/bin/python -m pytest tests/test_X.py -v`.
- The full suite must be green at the end of every task (existing 44 tests + whatever the task added).
- Commit messages: normal English (not caveman). End with the Co-Authored-By trailer the repo uses.

---

### Task 1: Rename `md2pdf` → `md2x` (mechanical; suite stays green)

Pure rename. No behavior change. The existing 44 tests are the safety net.

**Files:**
- Move: `src/md2pdf/` → `src/md2x/`, `md2pdf.yaml` → `md2x.yaml`, `md2pdf.py` → `md2x.py`
- Modify (string replace `md2pdf`→`md2x`): everything under `src/`, `tests/`, plus `_check.py`, `md2x.py`, `md2x.yaml`, `Makefile`, `install.sh`, `.gitignore`
- Do NOT touch: `README.md` (rewritten in Task 9), `docs/` (historical specs)

- [ ] **Step 1: Baseline — confirm suite green before touching anything**

Run: `.venv/bin/python -m pytest -q`
Expected: `44 passed`

- [ ] **Step 2: Move the package, config, and shim files with git**

```bash
git mv src/md2pdf src/md2x
git mv md2pdf.yaml md2x.yaml
git mv md2pdf.py md2x.py
```

- [ ] **Step 3: Global string replace `md2pdf` → `md2x` across code, tests, tooling**

This single substitution also fixes `._md2pdf.md` → `._md2x.md`, `[md2pdf]` → `[md2x]`, `md2pdf.yaml` lookups, and every `import md2pdf`:

```bash
grep -rl 'md2pdf' src tests _check.py md2x.py md2x.yaml Makefile install.sh .gitignore \
  | xargs perl -pi -e 's/md2pdf/md2x/g'
```

- [ ] **Step 4: Verify no stray `md2pdf` remains in the renamed surface**

Run: `grep -rn 'md2pdf' src tests _check.py md2x.py md2x.yaml Makefile install.sh .gitignore`
Expected: no output (exit 1). (README/docs intentionally still contain it.)

- [ ] **Step 5: Run the full suite — must still be green**

Run: `.venv/bin/python -m pytest -q`
Expected: `44 passed`

If a test fails with `ModuleNotFoundError: No module named 'md2pdf'`, a test import was missed — re-run Step 3's grep to find it.

- [ ] **Step 6: Smoke-test the (temporary) shim entry point**

Run: `./md2x.py --help`
Expected: argparse usage text prints (mentions `md2x`), exit 0.

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "refactor: rename md2pdf -> md2x across package, tests, tooling

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: Packaging skeleton — pyproject, `__main__`, LICENSE; drop shim + pytest.ini

Make it a real installable package. After this, `md2x` (console script) and `python -m md2x` both work; the root shim is gone.

**Files:**
- Create: `pyproject.toml`, `src/md2x/__main__.py`, `LICENSE`
- Delete: `pytest.ini`, `md2x.py` (shim)
- Modify: `Makefile`, `install.sh`, `.gitignore`

- [ ] **Step 1: Create `pyproject.toml`**

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

- [ ] **Step 2: Delete the old pytest config (now in pyproject)**

```bash
git rm pytest.ini
```

- [ ] **Step 3: Verify pytest still discovers config from pyproject**

Run: `.venv/bin/python -m pytest -q`
Expected: `44 passed` (pytest reads `[tool.pytest.ini_options]`; `pythonpath = ["src"]` resolves `md2x`).

- [ ] **Step 4: Create `src/md2x/__main__.py`**

```python
"""Enable `python -m md2x`."""
from .cli import main

raise SystemExit(main())
```

- [ ] **Step 5: Create `LICENSE` (MIT)**

```text
MIT License

Copyright (c) 2026 ChaoticQubit

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

- [ ] **Step 6: Editable-install the package into the venv, then delete the shim**

```bash
.venv/bin/python -m pip install -e . --quiet
git rm md2x.py
```

- [ ] **Step 7: Verify both entry points work without the shim**

Run: `.venv/bin/md2x --help` and `.venv/bin/python -m md2x --help`
Expected: both print argparse usage, exit 0.

- [ ] **Step 8: Update `Makefile` — drop the shim, use `python -m md2x`**

Replace the variable block and the `sample`/`pdf` targets. Current `Makefile` lines:

```makefile
PY ?= python3
SCRIPT := md2pdf.py
SAMPLE := examples/sample.md
```
(Note: after Task 1 `SCRIPT` reads `md2x.py`.) Change to:

```makefile
PY ?= python3
RUN := PYTHONPATH=src $(PY) -m md2x
SAMPLE := examples/sample.md
```

Then change the `sample` and `pdf` recipes from `@$(PY) $(SCRIPT) ...` to:

```makefile
sample: $(SAMPLE)
	@$(RUN) $(SAMPLE)

pdf:
	@if [ -z "$(IN)" ]; then echo "Usage: make pdf IN=path/to/file.md"; exit 1; fi
	@$(RUN) $(IN)
```

Leave `check:` as `@$(PY) _check.py` for now (replaced in Task 8).

- [ ] **Step 9: Update `install.sh` — add editable install**

Find the venv step (currently installs pyyaml + pytest):
```bash
python -m pip install --quiet pyyaml pytest
deactivate
echo "       PyYAML + pytest installed in .venv"
```
Change to:
```bash
python -m pip install --quiet pyyaml pytest
python -m pip install --quiet -e .
deactivate
echo "       PyYAML + pytest + md2x (editable) installed in .venv"
```

- [ ] **Step 10: Update `.gitignore` — track docs, ignore build artifacts**

Remove the `docs/` line (specs/plans should be tracked). Add build artifacts. The `# Python noise` block becomes:

```gitignore
# Python noise
__pycache__/
*.pyc
*.pyo
build/
dist/
*.egg-info/
```

And delete the trailing `docs/` entry (keep `.claude/`).

- [ ] **Step 11: Verify suite + entry points once more**

Run: `.venv/bin/python -m pytest -q`
Expected: `44 passed`

- [ ] **Step 12: Commit**

```bash
git add -A
git commit -m "build: add pyproject packaging, console script, __main__, LICENSE; drop shim + pytest.ini

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: `formats.py` — output-format registry + detection

The single source of truth for "what each output format needs."

**Files:**
- Create: `src/md2x/formats.py`
- Test: `tests/test_formats.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_formats.py`:
```python
from pathlib import Path
import pytest
from md2x.formats import detect_target, TARGETS


def test_detect_by_extension():
    assert detect_target(Path("a.pdf"), None).name == "pdf"
    assert detect_target(Path("a.docx"), None).name == "docx"
    assert detect_target(Path("a.html"), None).name == "html"
    assert detect_target(Path("a.htm"), None).name == "html"
    assert detect_target(Path("a.epub"), None).name == "epub"
    assert detect_target(Path("a.tex"), None).name == "latex"


def test_override_beats_extension():
    assert detect_target(Path("a.pdf"), "docx").name == "docx"


def test_default_pdf_when_none_or_unknown_ext():
    assert detect_target(None, None).name == "pdf"
    assert detect_target(Path("a.weird"), None).name == "pdf"


def test_unknown_override_raises():
    with pytest.raises(ValueError):
        detect_target(Path("a.pdf"), "rtf")


def test_target_fields():
    assert TARGETS["pdf"].needs_xelatex is True
    assert TARGETS["pdf"].writer is None
    h = TARGETS["html"]
    assert h.writer == "html" and h.standalone and h.embed and not h.needs_xelatex
    assert TARGETS["docx"].suffix == ".docx" and not TARGETS["docx"].needs_xelatex
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_formats.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'md2x.formats'`

- [ ] **Step 3: Implement `src/md2x/formats.py`**

```python
"""Output-format registry and detection.

The single source of truth for what each target format needs from pandoc.
PDF is engine-driven (writer is None → handled by the dedicated PDF builder);
every other format names a pandoc writer and a small set of portable flags.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Target:
    name: str            # "pdf" | "docx" | "html" | "epub" | "latex"
    writer: str | None   # pandoc -t writer; None for pdf (xelatex engine)
    suffix: str          # ".pdf", ".docx", ...
    standalone: bool     # pass --standalone
    embed: bool          # pass --embed-resources (html: single self-contained file)
    needs_xelatex: bool  # pdf only


TARGETS: dict[str, Target] = {
    "pdf":   Target("pdf",   None,    ".pdf",  False, False, True),
    "docx":  Target("docx",  "docx",  ".docx", False, False, False),
    "html":  Target("html",  "html",  ".html", True,  True,  False),
    "epub":  Target("epub",  "epub",  ".epub", False, False, False),
    "latex": Target("latex", "latex", ".tex",  True,  False, False),
}

# extension -> target name
EXT_TO_TARGET: dict[str, str] = {t.suffix: t.name for t in TARGETS.values()}
EXT_TO_TARGET[".htm"] = "html"


def detect_target(out_path: Path | None, override: str | None) -> Target:
    """Resolve the output Target.

    Precedence: explicit override (e.g. --to / config) wins; else infer from
    the output file's extension; else default to pdf.
    """
    if override:
        if override not in TARGETS:
            raise ValueError(
                f"unknown format: {override!r} (choose from {sorted(TARGETS)})"
            )
        return TARGETS[override]
    if out_path is not None:
        name = EXT_TO_TARGET.get(out_path.suffix.lower())
        if name:
            return TARGETS[name]
    return TARGETS["pdf"]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_formats.py -q`
Expected: `5 passed`

- [ ] **Step 5: Commit**

```bash
git add src/md2x/formats.py tests/test_formats.py
git commit -m "feat: add formats registry + detect_target (pdf/docx/html/epub/latex)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: `pandoc.py` — generic builder + dispatcher + PDF snapshot lock

Add the non-PDF command builder and a dispatcher. **`build_pandoc_cmd` is not edited** — and a snapshot test makes any accidental change to it fail loudly.

**Files:**
- Modify: `src/md2x/pandoc.py` (append two functions; existing function untouched)
- Test: `tests/test_pandoc_cmd.py` (add cases; existing cases unchanged)

- [ ] **Step 1: Write the failing tests (append to `tests/test_pandoc_cmd.py`)**

Add these imports at the top (the file already imports `Path`, `pandoc`, `DEFAULTS`, `deep_merge`):
```python
from md2x.formats import TARGETS
```

Append:
```python
def test_pdf_command_snapshot():
    """Lock the exact PDF pandoc invocation. If this changes, PDF output changed."""
    cfg = deep_merge(DEFAULTS, {})
    cmd = pandoc.build_pandoc_cmd(Path("in.md"), Path("out.pdf"), cfg, "pandoc", "xelatex")
    hi = "".join([
        r"\usepackage{float}",
        r"\floatplacement{figure}{H}",
        r"\usepackage[export]{adjustbox}",
        r"\usepackage{microtype}",
        r"\usepackage{booktabs}",
    ])
    assert cmd == [
        "pandoc", "in.md", "-o", "out.pdf",
        "--pdf-engine=xelatex",
        "-V", "geometry:margin=0.85in",
        "-V", "fontsize=10.5pt",
        "-V", "papersize=letter",
        "-V", "linestretch=1.15",
        "-V", "colorlinks=true",
        "-V", "linkcolor=NavyBlue",
        "-V", "urlcolor=NavyBlue",
        "-V", "toccolor=NavyBlue",
        "--highlight-style=tango",
        "--toc", "--toc-depth=2",
        "-V", "header-includes=" + hi,
    ]


def _gen(target_name, over=None):
    cfg = deep_merge(DEFAULTS, over or {})
    t = TARGETS[target_name]
    return pandoc.build_generic_cmd(Path("in.md"), Path("out" + t.suffix), cfg, "pandoc", t)


def test_generic_docx_excludes_latex_flags():
    cmd = _gen("docx")
    assert "-t" in cmd and "docx" in cmd
    assert "--highlight-style=tango" in cmd
    assert not any("--pdf-engine" in c for c in cmd)
    assert not any("geometry" in c for c in cmd)
    assert "-V" not in cmd  # generic builder emits no template variables


def test_generic_html_standalone_embed():
    cmd = _gen("html")
    assert "-t" in cmd and "html" in cmd
    assert "--standalone" in cmd
    assert "--embed-resources" in cmd


def test_generic_passthrough_flags():
    cmd = _gen("docx", {"output": {"number_sections": True, "citation_processing": True},
                        "advanced": {"pandoc_extra_args": ["--reference-doc=ref.docx"]}})
    assert "--number-sections" in cmd
    assert "--citeproc" in cmd
    assert "--reference-doc=ref.docx" in cmd


def test_generic_toc_toggle_off():
    cmd = _gen("html", {"output": {"toc": False}})
    assert "--toc" not in cmd


def test_build_cmd_dispatch():
    cfg = deep_merge(DEFAULTS, {})
    pdf = pandoc.build_cmd(Path("in.md"), Path("out.pdf"), cfg, TARGETS["pdf"], "pandoc", "xelatex")
    assert "--pdf-engine=xelatex" in pdf
    docx = pandoc.build_cmd(Path("in.md"), Path("out.docx"), cfg, TARGETS["docx"], "pandoc", "xelatex")
    assert "--pdf-engine=xelatex" not in docx
    assert "-t" in docx and "docx" in docx
```

- [ ] **Step 2: Run tests to verify the new ones fail**

Run: `.venv/bin/python -m pytest tests/test_pandoc_cmd.py -q`
Expected: FAIL — `AttributeError: module 'md2x.pandoc' has no attribute 'build_generic_cmd'`. (`test_pdf_command_snapshot` should already PASS — it documents current behavior.)

- [ ] **Step 3: Append `build_generic_cmd` and `build_cmd` to `src/md2x/pandoc.py`**

Add the import for `Target` at the top (the file already imports `Path`):
```python
from .formats import Target
```

Append after `build_pandoc_cmd` (do not modify `build_pandoc_cmd`):
```python
def build_generic_cmd(input_md: Path, output: Path, cfg: dict,
                      pandoc_bin: str, target: Target) -> list[str]:
    """Pandoc command for non-PDF writers (docx/html/epub/latex).

    Only portable flags — no LaTeX/PDF-only template variables, so pandoc never
    warns or errors on writers that don't understand them.
    """
    cmd: list[str] = [pandoc_bin, str(input_md), "-o", str(output)]
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
    cmd.append(f"--highlight-style={cfg['code']['highlight_style']}")
    cmd += cfg["advanced"].get("pandoc_extra_args", [])
    return cmd


def build_cmd(input_md: Path, output: Path, cfg: dict, target: Target,
              pandoc_bin: str, xelatex_bin: str) -> list[str]:
    """Dispatch to the PDF builder (unchanged) or the generic builder."""
    if target.name == "pdf":
        return build_pandoc_cmd(input_md, output, cfg, pandoc_bin, xelatex_bin)
    return build_generic_cmd(input_md, output, cfg, pandoc_bin, target)
```

- [ ] **Step 4: Run the full pandoc test file**

Run: `.venv/bin/python -m pytest tests/test_pandoc_cmd.py -q`
Expected: all pass (4 original + 1 snapshot + 5 new = 10).

- [ ] **Step 5: Commit**

```bash
git add src/md2x/pandoc.py tests/test_pandoc_cmd.py
git commit -m "feat: add build_generic_cmd + build_cmd dispatcher; lock PDF command via snapshot test

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: `config.py` — add `output.format` knob (additive)

Add the format key (default `None` = infer). `default_suffix` stays until the CLI stops using it (Task 7).

**Files:**
- Modify: `src/md2x/config.py:13-19` (the `output` block in `DEFAULTS`)
- Modify: `md2x.yaml` (document the knob)
- Test: `tests/test_config.py` (add 1 case)

- [ ] **Step 1: Write the failing test (append to `tests/test_config.py`)**

```python
def test_defaults_have_format_none():
    assert config.DEFAULTS["output"]["format"] is None
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_config.py::test_defaults_have_format_none -q`
Expected: FAIL — `KeyError: 'format'`

- [ ] **Step 3: Add `format` to the `output` defaults**

In `src/md2x/config.py`, the `output` block currently is:
```python
    "output": {
        "toc": True,
        "toc_depth": 2,
        "default_suffix": ".pdf",
        "number_sections": False,
        "citation_processing": False,
    },
```
Change to (add `format`, keep `default_suffix` for now):
```python
    "output": {
        "toc": True,
        "toc_depth": 2,
        "default_suffix": ".pdf",
        "format": None,  # null = infer from output extension (defaults to pdf)
        "number_sections": False,
        "citation_processing": False,
    },
```

- [ ] **Step 4: Document the knob in `md2x.yaml`**

In the `output:` section of `md2x.yaml`, add the `format` key with a comment. Place it near the existing `toc` keys:
```yaml
  # Output format. null = infer from the -o extension (defaults to pdf).
  # Force one of: pdf | docx | html | epub | latex.
  # NOTE: page/, fonts/, colors/, and advanced.header_includes apply to PDF/LaTeX only.
  format: null
```

- [ ] **Step 5: Run config tests**

Run: `.venv/bin/python -m pytest tests/test_config.py -q`
Expected: `8 passed` (7 original + 1 new).

- [ ] **Step 6: Commit**

```bash
git add src/md2x/config.py md2x.yaml tests/test_config.py
git commit -m "feat: add output.format config knob (null = infer from extension)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 6: `pipeline.py` — target dispatch; gate xelatex on PDF

`build()` now picks a Target, requires xelatex only for PDF, and uses the dispatcher. Existing PDF pipeline tests stay green; add a hermetic DOCX test and a gated real DOCX E2E.

**Files:**
- Modify: `src/md2x/pipeline.py` (imports + 3 edits inside `build`)
- Test: `tests/test_pipeline.py` (add 1 hermetic test), `tests/test_e2e.py` (add 1 gated test)

- [ ] **Step 1: Write the failing hermetic DOCX test (append to `tests/test_pipeline.py`)**

```python
def _fake_pandoc_recording(tmp_path: Path):
    """Fake pandoc that records argv and writes a zip-magic file to -o."""
    p = tmp_path / "pandoc"
    log = tmp_path / "pandoc_argv.txt"
    p.write_text(
        "#!/usr/bin/env python3\n"
        "import sys\n"
        f"open(r'{log}', 'w').write(' '.join(sys.argv))\n"
        "out = sys.argv[sys.argv.index('-o') + 1]\n"
        "open(out, 'wb').write(b'PK\\x03\\x04 fake docx')\n"
    )
    p.chmod(p.stat().st_mode | stat.S_IEXEC)
    return str(p), log


def test_build_docx_does_not_require_xelatex(monkeypatch, tmp_path):
    pan, log = _fake_pandoc_recording(tmp_path)
    # xelatex intentionally MISSING — must not abort for a docx target.
    def fake_resolve(name, override=None):
        return {"pandoc": pan, "xelatex": None, "mmdc": "mmdc", "dot": "dot"}[name]
    monkeypatch.setattr(pipeline, "resolve_binary", fake_resolve)

    def fake_render(src, png, cfg, mmdc_bin, dot_bin):
        Path(png).write_bytes(b"\x89PNG")
        return True, "dot"
    monkeypatch.setattr(pipeline, "render_block", fake_render)

    md = _make_md(tmp_path, MD)
    cfg = deep_merge(DEFAULTS, {})
    rc = pipeline.build(md, tmp_path / "out.docx", cfg)
    assert rc == 0
    assert (tmp_path / "out.docx").exists()
    argv = log.read_text()
    assert "-t docx" in argv
    assert "--pdf-engine" not in argv
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_pipeline.py::test_build_docx_does_not_require_xelatex -q`
Expected: FAIL — `SystemExit: ERROR: xelatex not found...` (current `build()` requires xelatex unconditionally).

- [ ] **Step 3: Update imports in `src/md2x/pipeline.py`**

Current lines 9-12:
```python
from .binaries import resolve_binary
from .mermaid import MERMAID_RE, extract_caption
from .renderers import render_block
from .pandoc import build_pandoc_cmd
```
Change to:
```python
from .binaries import resolve_binary
from .mermaid import MERMAID_RE, extract_caption
from .renderers import render_block
from .pandoc import build_cmd
from .formats import detect_target
```

- [ ] **Step 4: Resolve the target near the top of `build()`**

Current lines 16-20:
```python
    md_path = md_path.resolve()
    out_path = out_path.resolve()
    work_dir = md_path.parent
    diag_dir = work_dir / "diagrams"
    diag_dir.mkdir(exist_ok=True)
```
Insert the target resolution right after `out_path` is resolved:
```python
    md_path = md_path.resolve()
    out_path = out_path.resolve()
    target = detect_target(out_path, cfg["output"].get("format"))
    work_dir = md_path.parent
    diag_dir = work_dir / "diagrams"
    diag_dir.mkdir(exist_ok=True)
```

- [ ] **Step 5: Gate the xelatex requirement on the PDF target**

Current lines 33-34:
```python
    if not xelatex_bin:
        sys.exit("ERROR: xelatex not found. Run ./install.sh")
```
Change to:
```python
    if target.needs_xelatex and not xelatex_bin:
        sys.exit("ERROR: xelatex not found (required for PDF). "
                 "Run ./install.sh, or choose another format with --to.")
```

- [ ] **Step 6: Use the dispatcher to build the command**

Current line 95:
```python
    cmd = build_pandoc_cmd(tmp_md, out_path, cfg, pandoc_bin, xelatex_bin)
```
Change to:
```python
    cmd = build_cmd(tmp_md, out_path, cfg, target, pandoc_bin, xelatex_bin)
```

- [ ] **Step 7: Run the full pipeline test file**

Run: `.venv/bin/python -m pytest tests/test_pipeline.py -q`
Expected: all pass (8 original + 1 new = 9). The PDF tests still pass because `out.pdf` → pdf target → `build_pandoc_cmd` unchanged.

- [ ] **Step 8: Add a gated real DOCX E2E (append to `tests/test_e2e.py`)**

The file already imports `shutil`, `Path`, `pytest`, `resolve_binary`, `DEFAULTS`, `deep_merge`, `build`, and defines `SAMPLE`. Append:
```python
_HAVE_PANDOC = bool(resolve_binary("pandoc"))


@pytest.mark.skipif(not _HAVE_PANDOC, reason="pandoc not resolvable")
def test_real_md_to_docx(tmp_path):
    work = tmp_path / "doc.md"
    shutil.copy(SAMPLE, work)
    out = tmp_path / "doc.docx"
    # Force dot renderer; if no renderer is present the Mermaid block degrades
    # to source text and the DOCX still builds (pandoc-only path).
    cfg = deep_merge(DEFAULTS, {"mermaid": {"prefer": "dot"}})
    rc = build(work, out, cfg)
    assert rc == 0
    assert out.exists()
    assert out.stat().st_size > 1024
    assert out.read_bytes()[:4] == b"PK\x03\x04"  # .docx is a zip container
```

- [ ] **Step 9: Run the E2E file**

Run: `.venv/bin/python -m pytest tests/test_e2e.py -q`
Expected: `2 passed` (PDF + DOCX) if pandoc/xelatex/dot are installed; otherwise some skip. Neither fails.

- [ ] **Step 10: Run the whole suite**

Run: `.venv/bin/python -m pytest -q`
Expected: all green (no failures; E2E may show as passed or skipped depending on binaries).

- [ ] **Step 11: Commit**

```bash
git add src/md2x/pipeline.py tests/test_pipeline.py tests/test_e2e.py
git commit -m "feat: pipeline dispatches by output format; xelatex required only for PDF

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 7: `cli.py` — `-t/--to` flag + target-driven output naming

Wire the CLI to choose a format and name the output file accordingly. Remove the now-dead `default_suffix`.

**Files:**
- Modify: `src/md2x/cli.py` (import, one argparse arg, output-naming block)
- Modify: `src/md2x/config.py` (remove `default_suffix`)
- Test: `tests/test_cli.py` (add 2 cases)

- [ ] **Step 1: Write the failing tests (append to `tests/test_cli.py`)**

```python
def test_main_to_flag_sets_output_suffix(monkeypatch, tmp_path):
    md = tmp_path / "doc.md"
    md.write_text("# hi")
    captured = {}
    monkeypatch.setattr(cli, "build",
                        lambda m, o, cfg: captured.update(out=o, cfg=cfg) or 0)
    monkeypatch.setattr("sys.argv", ["md2x", str(md), "--to", "docx"])
    assert cli.main() == 0
    assert captured["out"].name == "doc.docx"
    assert captured["cfg"]["output"]["format"] == "docx"


def test_main_output_extension_infers_format(monkeypatch, tmp_path):
    md = tmp_path / "doc.md"
    md.write_text("# hi")
    captured = {}
    monkeypatch.setattr(cli, "build",
                        lambda m, o, cfg: captured.update(cfg=cfg) or 0)
    monkeypatch.setattr("sys.argv", ["md2x", str(md), "-o", str(tmp_path / "x.html")])
    cli.main()
    assert captured["cfg"]["output"]["format"] == "html"
```

- [ ] **Step 2: Run to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_cli.py::test_main_to_flag_sets_output_suffix -q`
Expected: FAIL — argparse rejects `--to` (`error: unrecognized arguments: --to docx`) → `SystemExit`.

- [ ] **Step 3: Import `detect_target` in `cli.py`**

Current lines 34-35:
```python
from .config import load_config
from .pipeline import build
```
Change to:
```python
from .config import load_config
from .pipeline import build
from .formats import detect_target
```

- [ ] **Step 4: Add the `--to` argument**

After the `-c/--config` argument (around line 62), add:
```python
    ap.add_argument("-t", "--to", default=None,
                    choices=["pdf", "docx", "html", "epub", "latex"],
                    help="Output format (default: infer from -o extension, else pdf)")
```

- [ ] **Step 5: Replace the output-naming block**

Current lines 78-82:
```python
    cfg = load_config(args.config, args.input)
    cfg = apply_cli_overrides(cfg, args)

    out = args.output or args.input.with_suffix(cfg["output"]["default_suffix"])
    return build(args.input, out, cfg)
```
Change to:
```python
    cfg = load_config(args.config, args.input)
    cfg = apply_cli_overrides(cfg, args)

    # Resolve format once; write it back so build() is authoritative.
    target = detect_target(args.output, args.to or cfg["output"].get("format"))
    cfg["output"]["format"] = target.name
    out = args.output or args.input.with_suffix(target.suffix)
    return build(args.input, out, cfg)
```

- [ ] **Step 6: Remove the dead `default_suffix` from `config.py`**

In `src/md2x/config.py`, delete the line:
```python
        "default_suffix": ".pdf",
```
(The `output` block keeps `toc`, `toc_depth`, `format`, `number_sections`, `citation_processing`.)

- [ ] **Step 7: Verify nothing else references `default_suffix`**

Run: `grep -rn "default_suffix" src tests`
Expected: no output.

- [ ] **Step 8: Run CLI tests + full suite**

Run: `.venv/bin/python -m pytest tests/test_cli.py -q` → expected `7 passed` (5 original + 2 new).
Run: `.venv/bin/python -m pytest -q` → expected all green.

- [ ] **Step 9: Commit**

```bash
git add src/md2x/cli.py src/md2x/config.py tests/test_cli.py
git commit -m "feat: add -t/--to format flag with extension inference; drop default_suffix

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 8: `cli.py` — `--check` subcommand; delete `_check.py`

Fold the binary-check helper into the CLI so there's one entry point.

**Files:**
- Modify: `src/md2x/cli.py` (make `input` optional; add `--check` handling)
- Delete: `_check.py`
- Modify: `Makefile` (`check` target)
- Test: `tests/test_cli.py` (add 1 case)

- [ ] **Step 1: Write the failing test (append to `tests/test_cli.py`)**

```python
def test_main_check_prints_binaries_and_exits(monkeypatch, capsys):
    monkeypatch.setattr("md2x.binaries.resolve_binary",
                        lambda name, override=None: f"/fake/{name}")
    monkeypatch.setattr("sys.argv", ["md2x", "--check"])
    assert cli.main() == 0
    out = capsys.readouterr().out
    assert "pandoc" in out and "/fake/pandoc" in out
    assert "xelatex" in out and "mmdc" in out and "dot" in out
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_cli.py::test_main_check_prints_binaries_and_exits -q`
Expected: FAIL — argparse errors that `input` is required (`SystemExit`), since `--check` is unknown and `input` is positional/required.

- [ ] **Step 3: Make `input` optional and add `--check`**

Current line 58:
```python
    ap.add_argument("input", type=Path, help="Path to source .md")
```
Change to:
```python
    ap.add_argument("input", nargs="?", type=Path, default=None,
                    help="Path to source .md")
```
After the `--keep-intermediate` argument (around line 72), add:
```python
    ap.add_argument("--check", action="store_true",
                    help="Print resolved binary paths and exit")
```

- [ ] **Step 4: Handle `--check` and the now-optional input**

Current lines 73-76:
```python
    args = ap.parse_args()

    if not args.input.exists():
        sys.exit(f"input not found: {args.input}")
```
Change to:
```python
    args = ap.parse_args()

    if args.check:
        from .binaries import resolve_binary
        for n in ("pandoc", "xelatex", "mmdc", "dot"):
            print(f"  {n:8s} {resolve_binary(n) or 'MISSING'}")
        return 0

    if args.input is None:
        ap.error("input is required (or use --check)")
    if not args.input.exists():
        sys.exit(f"input not found: {args.input}")
```

- [ ] **Step 5: Delete `_check.py`**

```bash
git rm _check.py
```

- [ ] **Step 6: Point the Makefile `check` target at the CLI**

Current:
```makefile
check:
	@$(PY) _check.py
```
Change to:
```makefile
check:
	@PYTHONPATH=src $(PY) -m md2x --check
```

- [ ] **Step 7: Verify `make check` and the test**

Run: `.venv/bin/python -m pytest tests/test_cli.py -q` → expected `8 passed`.
Run: `make check`
Expected: four lines like `  pandoc   /…/.bin/pandoc` (or `MISSING`), exit 0.

- [ ] **Step 8: Run the whole suite**

Run: `.venv/bin/python -m pytest -q`
Expected: all green.

- [ ] **Step 9: Commit**

```bash
git add src/md2x/cli.py Makefile tests/test_cli.py
git commit -m "feat: fold binary check into 'md2x --check'; remove _check.py

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 9: README rewrite — open-source landing page

Rewrite `README.md` so a stranger on GitHub understands and adopts the tool, with both install paths and the format table.

**Files:**
- Modify: `README.md` (full rewrite)
- Reference: `src/md2x/__init__.py` docstring — update the one-line summary if it still says "→ PDF" only

- [ ] **Step 1: Replace `README.md` with the open-source structure**

Write the following (fill the existing sections' factual content — install sizes, config table, troubleshooting — forward from the current README, updating every `md2pdf`→`md2x` and `./md2pdf.py`→`md2x`):

```markdown
# md2x — Markdown to PDF, Word, HTML & EPUB

Convert any Markdown file (including **Mermaid diagrams**) to **PDF, DOCX, HTML, EPUB, or LaTeX**. Diagrams are rendered to images automatically; the rest is handled by [pandoc](https://pandoc.org).

![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)

## Why md2x

- **One source, many formats** — `md2x doc.md` (PDF) · `--to docx` · `--to html` · `--to epub` · `--to latex`.
- **Mermaid that just works** — fenced ```` ```mermaid ```` blocks render via `mmdc`, with a Graphviz `dot` fallback for flowcharts.
- **Per-document config** — drop a `md2x.yaml` next to a file to override margins, fonts, themes, and more.
- **Two ways to run** — install with `pip` and use your own pandoc, or clone and get a fully self-contained local toolchain (nothing global, no `sudo`).

## Install

### Option A — pip (use your own tools)

```bash
pip install md2x          # or: pipx install md2x
```

You supply the converters on your `$PATH`:

| Tool | macOS | Linux | Needed for |
|---|---|---|---|
| pandoc | `brew install pandoc` | `sudo apt install pandoc` | all formats |
| xelatex | `brew install --cask mactex-no-gui` | `sudo apt install texlive-xetex` | **PDF only** |
| node + mmdc | `brew install node && npm i -g @mermaid-js/mermaid-cli` | same | Mermaid diagrams |
| graphviz (`dot`) | `brew install graphviz` | `sudo apt install graphviz` | Mermaid fallback (optional) |

### Option B — clone + bundled toolchain (zero global install)

```bash
git clone https://github.com/ChaoticQubit/MD2X.git
cd MD2X
make install            # downloads pandoc, TinyTeX, node, mmdc into ./.tools and ./.bin
```

Everything lands inside the project folder (~700 MB, all git-ignored). `make distclean` removes it.

## Quickstart

```bash
md2x doc.md                       # → doc.pdf
md2x doc.md -o report.docx        # → Word
md2x doc.md --to html             # → doc.html (single self-contained file)
md2x doc.md --to epub             # → doc.epub
md2x doc.md --theme dark --no-toc
md2x --check                      # show which binaries were found
```

`md2x --help` lists every flag.

## Supported formats

| Format | Flag / extension | Requires |
|---|---|---|
| PDF (default) | `.pdf` | pandoc + xelatex |
| Word | `--to docx` / `.docx` | pandoc |
| HTML | `--to html` / `.html` | pandoc |
| EPUB | `--to epub` / `.epub` | pandoc |
| LaTeX | `--to latex` / `.tex` | pandoc |

Format is taken from `--to`, else inferred from the `-o` extension, else PDF. Page/font/color settings apply to PDF (and LaTeX) only.

## Configuration

Settings resolve in this order (first match wins): `--config` → `md2x.yaml` next to the input → `md2x.yaml` in the project root → built-in defaults. CLI flags override everything. See the annotated [`md2x.yaml`](./md2x.yaml) for every knob.

## How it works

(Keep the current README's "How It Works" pipeline section, updated for multi-format: render Mermaid → rewrite Markdown with image references → hand to pandoc with the writer for the chosen format. xelatex is only invoked for PDF.)

## Troubleshooting

(Carry over the current README's troubleshooting entries, updating `md2pdf`→`md2x` and noting xelatex is PDF-only.)

## Contributing

```bash
git clone https://github.com/ChaoticQubit/MD2X.git
cd MD2X
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
make test           # or: python -m pytest
```

Source lives in `src/md2x/` (one responsibility per module); tests in `tests/`.

## License

MIT — see [LICENSE](./LICENSE).
```

- [ ] **Step 2: Update the package docstring if needed**

Open `src/md2x/__init__.py`. If its first docstring line still reads `Markdown (+Mermaid) → PDF`, change it to `Markdown (+Mermaid) → PDF / DOCX / HTML / EPUB / LaTeX.`

- [ ] **Step 3: Verify no `md2pdf` remains anywhere except historical specs**

Run: `grep -rn 'md2pdf' README.md src tests Makefile install.sh md2x.yaml pyproject.toml`
Expected: no output.

- [ ] **Step 4: Commit**

```bash
git add README.md src/md2x/__init__.py
git commit -m "docs: rewrite README as open-source landing page with multi-format usage

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 10: Final integration verification

Prove the whole thing works end to end: clean rename, all tests green, real renders for PDF **and** a second format, both entry points.

**Files:** none (verification only; may add a `git commit` if Step 6 finds something).

- [ ] **Step 1: Grep-clean check**

Run: `grep -rn 'md2pdf' . --include='*.py' --include='*.yaml' --include='*.toml' --include='Makefile' --include='*.sh' --include='*.md' | grep -v node_modules | grep -v '.venv' | grep -v 'docs/superpowers/specs/2026-06-04-md2pdf'`
Expected: no output (the only remaining hits are the historical decompose spec, excluded here).

- [ ] **Step 2: Reinstall editable + run the full suite**

```bash
.venv/bin/python -m pip install -e . --quiet
.venv/bin/python -m pytest -q
```
Expected: all green. Count = 44 original + 5 (formats) + 6 (pandoc: snapshot + 5 generic/dispatch) + 1 (config) + 1 (pipeline docx) + 1 (e2e docx) + 2 (cli --to) + 1 (cli --check) = **61 tests** (E2E may report passed or skipped by binary availability).

- [ ] **Step 3: Both entry points**

Run: `.venv/bin/md2x --help` and `PYTHONPATH=src .venv/bin/python -m md2x --help`
Expected: identical usage text, exit 0.

- [ ] **Step 4: `make check`**

Run: `make check`
Expected: four binary lines, exit 0.

- [ ] **Step 5: Real renders — PDF must look the same; second format must be valid**

```bash
make sample                                   # → examples/sample.pdf (PDF path, unchanged)
PYTHONPATH=src .venv/bin/python -m md2x examples/sample.md -o /tmp/sample.docx
```
Expected:
- `examples/sample.pdf` exists, starts with `%PDF`.
- `/tmp/sample.docx` exists, is a non-trivial zip (`file /tmp/sample.docx` → "Microsoft Word 2007+").
Run: `head -c4 examples/sample.pdf` → `%PDF`; `head -c4 /tmp/sample.docx | xxd` → `5048 0304` (`PK\x03\x04`).

- [ ] **Step 6: Clean up generated artifacts and confirm tree is clean**

```bash
make clean
git status --short
```
Expected: working tree clean (all changes already committed across Tasks 1-9). If anything is untracked/modified unexpectedly, investigate before finishing.

- [ ] **Step 7 (optional): tag a release-ready commit**

If desired:
```bash
git tag -a v0.1.0 -m "md2x 0.1.0 — multi-format, packaged"
```
(Push/publish are deliberately out of scope — see spec.)

---

## Self-Review (completed by plan author)

**Spec coverage** — every spec section maps to a task:
- Rename map → Task 1. Packaging (pyproject/__main__/LICENSE/drop shim+pytest.ini) → Task 2. `formats.py` → Task 3. `build_generic_cmd`/`build_cmd`/PDF snapshot → Task 4. `output.format` + md2x.yaml → Task 5. Pipeline dispatch + xelatex gate + hermetic/gated docx → Task 6. CLI `--to` + drop `default_suffix` → Task 7. `--check` + delete `_check.py` → Task 8. README + LICENSE wiring → Task 9 (+2). Hybrid distribution → Tasks 2/9 (PATH fallback unchanged, documented). `.gitignore` docs/ → Task 2. Final grep + gated docx E2E + verification → Tasks 6/10. PDF-invariance guarantee → Task 4 snapshot + Task 10 real render.
- Out-of-scope items (gfm, PyPI upload, CI, Windows, dir/repo rename) are excluded — no tasks, as intended.

**Placeholder scan** — new files (pyproject, `__main__.py`, LICENSE, `formats.py`) and all edits are shown in full; every test has real assertions; every run step has an exact command + expected output. README Task 9 explicitly says to carry the existing factual "How it works"/"Troubleshooting" content forward (not a placeholder — the source text already exists in the repo).

**Type/signature consistency** — `Target` fields (`name/writer/suffix/standalone/embed/needs_xelatex`) are used identically in `formats.py`, `pandoc.build_generic_cmd`/`build_cmd`, `pipeline.build`, and `cli.main`. `detect_target(out_path, override)` signature is identical at all three call sites (pipeline, cli, tests). `build_cmd(input_md, output, cfg, target, pandoc_bin, xelatex_bin)` matches between Task 4 definition and Task 6 call. `cfg["output"]["format"]` is written by the CLI (Task 7) and read by the pipeline (Task 6) — consistent key.
