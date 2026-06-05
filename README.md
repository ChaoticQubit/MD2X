# md2x — Markdown to PDF, Word, HTML & EPUB

Convert any Markdown file (including **Mermaid diagrams**) to **PDF, DOCX, HTML, EPUB, or LaTeX**. Diagrams are rendered to images automatically; the rest is handled by [pandoc](https://pandoc.org).

![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)

## Why md2x

- **One source, many formats** — `md2x doc.md` (PDF) · `--to docx` · `--to html` · `--to epub` · `--to latex`.
- **Mermaid that just works** — fenced ` ```mermaid ` blocks render via `mmdc`, with a Graphviz `dot` fallback for flowcharts.
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

What `make install` puts inside the project folder (~700 MB total, all git-ignored):

| Component | Where it lands | Approx size |
|---|---|---|
| Python venv + PyYAML | `.venv/` | ~12 MB |
| Node.js (pinned 20.18.0) | `.tools/node/` | ~95 MB |
| Pandoc (pinned 3.5) | `.tools/pandoc/` | ~150 MB |
| TinyTeX (xelatex + minimal LaTeX) | `.tools/tinytex/` | ~70 MB |
| mmdc + puppeteer (bundled Chromium) | `node_modules/` | ~350 MB |
| Convenience symlinks | `.bin/` | tiny |
| graphviz `dot` (system, optional) | uses system if found | n/a |

Nothing installed globally. No `sudo` required. `make distclean` removes it all.

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

Format is taken from `--to`, else inferred from the `-o` extension, else PDF. Page/font/color settings apply to PDF only.

## AI reading-site (`md2x site`)

Turn a folder of Markdown into a polished, navigable website — multi-page by
default, single-page optional — with one-click deploy to Vercel.

```bash
pip install 'md2x[ai]'           # agno + every provider SDK (works out of the box)
export ANTHROPIC_API_KEY=sk-...  # or any provider's key (see below)

md2x site docs/                  # generates ./site
md2x site docs/ --archetype flyer --layout single-page
md2x site docs/ --no-ai          # deterministic, no LLM/network
md2x site docs/ --deploy vercel  # needs VERCEL_TOKEN
```

**Model & provider agnostic.** Set `ai.model` in `md2x.yaml`:
`"anthropic:claude-sonnet-4-6"`, `"openai:gpt-4o"`, `"groq:llama-3.3-70b-versatile"`, … or
point at any OpenAI-compatible/local endpoint with a `provider: openai-like`
block (`id` + `base_url` + `api_key_env`). Switching models is one config line —
`md2x[ai]` bundles the provider SDKs (via `agno[models]`), so any of them works
with no extra installs; just set the model and its API-key env var.

**Archetypes:** `reading` (default), `presentation`, `flyer`, `product`, `docs`,
`report`, `custom` (drive it entirely from `site.style_prompt`).

**Fidelity:** `preserve` or `light-enhance` (default). Your prose is always
emitted verbatim — pandoc renders the body, the AI only builds the design,
navigation, and additive aids (TL;DR, takeaways, related links).

**Secrets** live in environment variables only; `md2x.yaml` just names them
(`ai.model` provider keys, `deploy.token_env`). Safe to commit. md2x also
auto-loads a `.env` file from the current directory or project root (real
environment variables take precedence) — copy [`.env.example`](./.env.example)
to `.env` and fill in your key. `.env` is git-ignored.

## Configuration

Settings resolve in this order (first match wins): `--config` → `md2x.yaml` next to the input → `md2x.yaml` in the project root → built-in defaults. CLI flags override everything. See the annotated [`md2x.yaml`](./md2x.yaml) for every knob.

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

Drop a `md2x.yaml` next to a specific markdown file and only those keys override the project default — the rest fall through. Useful when one document needs landscape orientation or a different font:

```yaml
page:
  paper: a4
  orientation: landscape
images:
  width: 9in
```

## How It Works

Each render runs the following pipeline:

1. **Read source markdown.** The input `.md` file is loaded as-is.
2. **Find every ` ```mermaid ``` ` fenced block.** The extractor locates all Mermaid code blocks along with any caption comment on the first line.
3. **Render each diagram to PNG.**
   - `mmdc` is tried first — it handles the full Mermaid syntax (flowchart, sequence, gantt, state, class, ER, journey, mind-map, quadrant, timeline).
   - If `mmdc` is missing or fails, `dot` (Graphviz) is used as a fallback for `flowchart` / `graph` diagram types.
   - If neither renderer succeeds, the `mermaid.on_failure` policy decides what happens: `keep_source` (leave the raw block), `omit` (drop it), or `error` (abort the build).
4. **Write PNGs to `<source_dir>/diagrams/mermaid_NN.png`**, sized per `images.mmdc_width` / `images.mmdc_height`.
5. **Rewrite the markdown** with image references sized to `images.width`, plus optional figure captions, producing a temporary `<name>._md2x.md` intermediate file.
6. **Invoke pandoc** with the resolved config flags. For PDF this means `--pdf-engine=xelatex`; for DOCX, HTML, EPUB, and LaTeX, pandoc's own writers are used directly — xelatex is not involved.
7. **Clean up.** The intermediate `<name>._md2x.md` file is deleted unless `--keep-intermediate` or `advanced.keep_intermediate: true`. An optional manifest (`*._md2x.json`) describing every rendered block can be emitted via `advanced.emit_manifest`.

## Troubleshooting

**`pandoc: not found` after `make install`**
Re-run `md2x --check`. If `.bin/pandoc` is missing, re-run `make install` and watch step 3 — it downloads the pandoc tarball from GitHub releases. For the pip install path, ensure pandoc is on your `$PATH` (`which pandoc`).

**`xelatex: not found`**
xelatex is only required for PDF output. For other formats (`--to docx`, `--to html`, etc.) you can ignore this warning entirely. If you do need PDF: for the bundled toolchain, the TinyTeX install (step 4 of `make install`) may have failed — common cause is a network restriction. The installer streams the binary from `https://yihui.org/tinytex/`. Re-run; if it still fails, install TinyTeX manually (`curl -sSL https://yihui.org/tinytex/install-bin-unix.sh | sh`) and point `binaries.xelatex` in `md2x.yaml` at it. For the pip path, install a TeX distribution (`mactex-no-gui` on macOS, `texlive-xetex` on Linux).

**Mermaid block doesn't render — "kept source; no renderer succeeded"**
- mmdc missing → for the bundled toolchain, re-run `make install` (step 2). For the pip path, install mmdc globally: `npm i -g @mermaid-js/mermaid-cli`.
- mmdc present but failing on a complex diagram → check command output (`md2x … 2>&1 | grep mmdc`). Usually a syntax error in the diagram itself.
- Set `mermaid.on_failure: error` to make the build fail loudly instead of silently keeping the source.

**Mermaid diagram looks too small after fit-to-page**
- Bump `images.mmdc_width` (e.g. 2400) and `images.mmdc_height` (e.g. 1700) in `md2x.yaml` — higher-resolution PNG zooms cleanly even though scaled to `images.width` on the page.
- Or restructure the diagram (split into two, shorter labels, switch `rankdir` from `LR` to `TB`).

**Font error: "DejaVu Serif not found" on macOS**
Either install DejaVu (`brew install --cask font-dejavu`) or edit `fonts.main` / `fonts.sans` / `fonts.mono` in `md2x.yaml` to fonts you have (e.g. `Helvetica Neue`, `Menlo`). Font settings only affect PDF output.

**LaTeX complains about a missing `.sty`**
The bundled TinyTeX is intentionally minimal. To add a package:

```bash
.bin/tlmgr install <package-name>
```

Then add it to `advanced.header_includes` in `md2x.yaml` if needed. This applies to PDF output only.

**You want to use system pandoc / xelatex instead of the bundled ones**
Set explicit paths in `md2x.yaml`:

```yaml
binaries:
  pandoc:  /usr/local/bin/pandoc
  xelatex: /Library/TeX/texbin/xelatex
```

Or delete `.bin/` / `.tools/` and the script falls back to `$PATH`.

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
