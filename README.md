# md2pdf — Markdown → PDF with Mermaid Diagrams

A self-contained, **local-only** pipeline that turns any Markdown file
(containing Mermaid fenced code blocks) into a clean, paginated PDF.
Every binary lives inside the project folder — nothing global on your
system, nothing in `/usr/local`, nothing in your global `npm` cache.

This is the tool that produced `FDET_Charter.pdf`.

---

## Project Layout

```
~/Tools/MD2PDF/
├── md2pdf.py          # entry shim (executable) — delegates to src/md2pdf
├── src/md2pdf/        # the package (one responsibility per module)
│   ├── __init__.py    #   public API re-exports + venv-yaml bootstrap
│   ├── paths.py       #   PROJECT_ROOT + local install layout
│   ├── config.py      #   defaults, deep_merge, YAML loader
│   ├── binaries.py    #   executable resolution
│   ├── mermaid.py     #   block extraction, captions, dot conversion
│   ├── renderers.py   #   mmdc / dot PNG renderers + fallback chain
│   ├── pandoc.py      #   pandoc command builder
│   ├── pipeline.py    #   build(): render -> rewrite -> pandoc
│   └── cli.py         #   argparse + main()
├── tests/             # pytest suite (hermetic + gated real E2E)
├── pytest.ini         # test config (pythonpath = src)
├── md2pdf.yaml        # YAML config (every knob documented inline)
├── install.sh         # local installer — venv + node + pandoc + TinyTeX
├── Makefile           # convenience targets
├── package.json       # mmdc + puppeteer pinned versions
├── README.md          # this file
├── .gitignore         # excludes everything install.sh creates
└── examples/
    └── sample.md      # tiny mermaid test doc

After install.sh runs (additional, all local):
├── .venv/             # Python virtualenv (only PyYAML)
├── .tools/
│   ├── node/          # Node.js binary
│   ├── pandoc/        # Pandoc binary
│   └── tinytex/       # TinyTeX (xelatex + minimal LaTeX packages)
├── .bin/              # symlinks: pandoc, xelatex, mmdc, [dot]
└── node_modules/      # mmdc + bundled Chromium (via puppeteer)
```

Everything in `.venv/`, `.tools/`, `.bin/`, and `node_modules/` is
git-ignored. To uninstall: `make distclean` (or just delete the folder).

---

## Install (local, one-shot)

```bash
cd ~/Tools/MD2PDF
make install                # runs install.sh
```

What `install.sh` does — strictly inside this folder:

| Component | Where it lands | Approx size |
|---|---|---|
| Python venv + PyYAML | `.venv/` | ~12 MB |
| Node.js (pinned 20.18.0) | `.tools/node/` | ~95 MB |
| Pandoc (pinned 3.5) | `.tools/pandoc/` | ~150 MB |
| TinyTeX (xelatex + minimal LaTeX) | `.tools/tinytex/` | ~70 MB |
| mmdc + puppeteer (bundled Chromium) | `node_modules/` | ~350 MB |
| Convenience symlinks | `.bin/` | tiny |
| graphviz `dot` (system, optional) | uses system if found | n/a |

Total: ~700 MB on disk. Nothing installed globally. No `sudo` required.

Verify:

```bash
make check
#   pandoc   /Users/.../MD2PDF/.bin/pandoc
#   xelatex  /Users/.../MD2PDF/.bin/xelatex
#   mmdc     /Users/.../MD2PDF/.bin/mmdc
#   dot      /usr/local/bin/dot   (optional, system)
```

---

## Usage

### Render any markdown

```bash
cd ~/Tools/MD2PDF
./md2pdf.py /path/to/your.md                 # → /path/to/your.pdf
./md2pdf.py your.md -o ~/Desktop/out.pdf     # custom output
./md2pdf.py your.md --toc-depth 3            # deeper ToC
./md2pdf.py your.md --no-toc                 # no ToC
./md2pdf.py your.md --margin 0.6in --fontsize 10pt
./md2pdf.py your.md --theme dark             # mermaid dark theme
./md2pdf.py your.md -c path/to/custom.yaml   # explicit config file
./md2pdf.py your.md --keep-intermediate      # debug intermediate .md
```

Make-driven equivalents:

```bash
make sample                  # render examples/sample.md
make pdf IN=path/to/file.md  # render arbitrary file
make clean                   # delete generated PDFs / intermediates
make distclean               # also wipe .venv / .tools / node_modules
```

`./md2pdf.py --help` lists every flag.

---

## Testing

The logic lives in `src/md2pdf/` as focused modules, covered by a pytest suite
in `tests/`:

```bash
make test                    # run the whole suite
.venv/bin/python -m pytest   # same thing directly
```

- **Hermetic tests** (always run) cover config merge/precedence, binary
  resolution order, Mermaid→dot conversion, the renderer fallback chain, the
  pandoc command matrix, and the `build()` pipeline (figure embedding,
  `on_failure` policies, manifest, `no_clobber`, intermediate cleanup) using
  fake executable stubs — no heavy binaries needed.
- **One gated end-to-end test** renders `examples/sample.md` to a real PDF via
  pandoc + xelatex + dot. It is skipped automatically if those binaries don't
  resolve. `pytest` is installed into `.venv` by `install.sh`.

---

## Configuration (`md2pdf.yaml`)

Every parameter the script understands is in `md2pdf.yaml` with inline
documentation. The script resolves config in this order (first match wins):

1. `--config <path>` CLI flag
2. `<input_dir>/md2pdf.yaml` next to the source markdown (per-document override)
3. `<input_dir>/md2pdf.yml`
4. `<project_root>/md2pdf.yaml` (this folder's default)
5. `<project_root>/md2pdf.yml`
6. Built-in defaults baked into `md2pdf.py`

CLI flags always override YAML.

### What's configurable

| Section | Examples |
|---|---|
| `output` | `toc`, `toc_depth`, `number_sections`, `citation_processing` |
| `page` | `margin`, `fontsize`, `paper` (letter/a4/…), `orientation`, `line_spacing` |
| `fonts` | `main`, `sans`, `mono`, `cjk` |
| `colors` | `link`, `url`, `toc`, `heading` (xcolor names or hex) |
| `code` | `highlight_style`, `line_numbers` |
| `images` | `width`, `caption_prefix`, `show_captions`, `dpi`, `mmdc_width`, `mmdc_height` |
| `mermaid` | `theme`, `background`, `prefer` (mmdc/dot/auto), `on_failure` |
| `binaries` | explicit absolute paths for pandoc/xelatex/mmdc/dot |
| `advanced` | `header_includes` (LaTeX preamble lines), `pandoc_extra_args`, `keep_intermediate`, `emit_manifest`, `no_clobber` |

### Per-document overrides

Drop a `md2pdf.yaml` next to a specific markdown file and only those keys
override the project default — the rest fall through. Useful when one
document needs landscape orientation or a different font.

Example per-document override (`mydoc-folder/md2pdf.yaml`):

```yaml
page:
  paper: a4
  orientation: landscape
images:
  width: 9in
```

---

## How It Works (per render)

1. Read source markdown.
2. Find every ```` ```mermaid ... ``` ```` fenced block.
3. For each block:
   - try `mmdc` first (full Mermaid syntax — flowchart, sequence, gantt,
     state, class, ER, journey, mind-map, quadrant, timeline),
   - fall back to `dot` (graphviz) for `flowchart` / `graph` types if
     `mmdc` is missing,
   - if neither works, respect the `mermaid.on_failure` policy
     (`keep_source` / `omit` / `error`).
4. Render to `<source_dir>/diagrams/mermaid_NN.png` sized per
   `images.mmdc_width` / `images.mmdc_height`.
5. Rewrite the markdown with image references sized to `images.width`,
   plus optional figure captions.
6. Invoke pandoc with the resolved config flags:
   `pandoc tmp.md -o OUTPUT.pdf --pdf-engine=xelatex …`
7. Optionally emit a manifest (`*._md2pdf.json`) describing every block.

The rewritten intermediate `<name>._md2pdf.md` is deleted unless
`--keep-intermediate` or `advanced.keep_intermediate: true`.

---

## Troubleshooting

**`pandoc: not found` after `make install`**
Re-run `make check`. If `.bin/pandoc` is missing, re-run `make install`
and watch step 3 — it downloads the pandoc tarball from GitHub releases.

**`xelatex: not found`**
TinyTeX install (step 4) failed. Common cause: network restriction. The
installer streams the bin from `https://yihui.org/tinytex/`. Re-run; if
it still fails, install TinyTeX manually
(`curl -sSL https://yihui.org/tinytex/install-bin-unix.sh | sh`) and
point `binaries.xelatex` in `md2pdf.yaml` at it.

**Mermaid block doesn't render — "kept source; no renderer succeeded"**
- mmdc missing → re-run `make install` (step 2).
- mmdc present but failing on a complex diagram → check command output
  (`./md2pdf.py … 2>&1 | grep mmdc`). Usually a syntax error in the
  diagram itself.
- Set `mermaid.on_failure: error` to make the build fail loudly instead
  of silently keeping the source.

**Mermaid diagram looks too small after fit-to-page**
- Bump `images.mmdc_width` (e.g. 2400) and `images.mmdc_height` (e.g. 1700)
  in `md2pdf.yaml` — higher-resolution PNG zooms cleanly even though
  scaled to `images.width` on the page.
- Or restructure the diagram (split into two, shorter labels, switch
  `rankdir` from `LR` to `TB`).

**Font error: "DejaVu Serif not found" on macOS**
Either install DejaVu (`brew install --cask font-dejavu`) or edit
`fonts.main` / `fonts.sans` / `fonts.mono` in `md2pdf.yaml` to fonts you
have (e.g. `Helvetica Neue`, `Menlo`).

**LaTeX complains about a missing `.sty`**
The bundled TinyTeX is intentionally minimal. To add a package:

```bash
.bin/tlmgr install <package-name>
```

Then add it to `advanced.header_includes` in `md2pdf.yaml` if needed.

**You want to use system pandoc / xelatex instead of the bundled ones**
Set explicit paths in `md2pdf.yaml`:

```yaml
binaries:
  pandoc:  /usr/local/bin/pandoc
  xelatex: /Library/TeX/texbin/xelatex
```

Or delete `.bin/` / `.tools/` and the script falls back to `$PATH`.

---

## Uninstall

```bash
cd ~/Tools/MD2PDF
make distclean         # removes .venv, .tools, .bin, node_modules
rm -rf ~/Tools/MD2PDF  # nuke the whole project
```

No leftovers anywhere else on disk.

---

## Example

```bash
cd ~/Tools/MD2PDF
make install
make sample
open examples/sample.pdf
```

---

## License

MIT-style — copy, modify, redistribute. No warranty.
