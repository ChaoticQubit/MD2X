# md2x AI Reading-Site — Design

**Date:** 2026-06-05
**Status:** Approved (pending spec review)
**Author:** ChaoticQubit (with Claude)

## Summary

Add a new capability to `md2x`: turn one or more Markdown files into an
AI-generated, reading-optimized **website** (multi-page by default, single-page
optional), with optional one-click deploy to Vercel. The feature is exposed as a
new `md2x site` subcommand, is driven entirely by config (model, provider,
archetype, fidelity, deploy target), and keeps the existing single-file
converter (`md2x convert`, a.k.a. bare `md2x doc.md`) untouched.

The intelligence layer uses the **agno** agent framework. Models and providers
are fully config-driven (model-as-string for native providers, `OpenAILike` for
any OpenAI-compatible/local endpoint) so swapping models is a one-line config
change with no code edits. Body **content fidelity** is guaranteed by reusing
`md2x`'s existing pandoc pipeline to convert each Markdown file to a faithful
HTML fragment; agno only builds the surrounding design, navigation, and
*additive* enhancements. This mirrors the trust model of the PDF leg, which
never alters the author's words.

## Goals

- `md2x site INPUTS...` → a static, dynamic-feeling website from a set of
  Markdown files, "as good as the PDF" to read and navigate.
- Model-agnostic and provider-agnostic via config; works out of the box by
  changing a single config value. No code edits to switch model/provider.
- Secrets (LLM API keys, Vercel token) live in environment variables only;
  config references them by name and is safe to commit/share.
- Configurable **archetype** (presentation / flyer / product / docs / reading /
  report / custom) so the user declares the *kind* of site they want.
- Configurable **fidelity** (preserve / light-enhance); default light-enhance.
  The author's words are never altered. (A future `rewrite` mode is explicitly
  deferred — see Non-Goals.)
- One-click deploy to Vercel from a token.
- Core `pip install md2x` stays dependency-light; AI is an opt-in extra.

## Non-Goals (v1)

- Deploy providers other than Vercel (the deploy layer is abstracted so
  Netlify / GitHub Pages / S3 can be added later).
- Per-document archetype override (archetype is global per run in v1).
- Incremental / cached regeneration.
- Watch mode / live dev server.
- Auth-gated or access-controlled sites.
- A `rewrite` fidelity mode (AI rewords the author's prose). Deferred until a
  real need appears — the body is always preserved verbatim in v1.

## CLI Surface

Argparse gains subcommands: `convert` (the existing flow) and `site` (new).

**Back-compatibility:** an argv shim in `main()` prepends `convert` when the
first token is not a recognized subcommand or top-level flag. So every existing
invocation — `md2x doc.md`, `md2x doc.md --to docx`, `md2x --check` — keeps
working with identical behavior. All current `convert` flags stay on the
`convert` subparser.

```
md2x site INPUTS...                  # one or more files and/or directories
  -o, --out-dir PATH                 # default: ./site
  --archetype {reading,presentation,flyer,product,docs,report,custom}
  --layout {auto,multi-page,single-page}
  --style "free-text nudge"
  --fidelity {preserve,light-enhance}
  --model "provider:model_id"        # CLI override of ai.model
  --no-ai                            # deterministic template, no agno/LLM/network
  --deploy {vercel}
  --open                             # open index in browser after build
  -c, --config md2x.yaml
```

Directories in `INPUTS` are globbed for `*.md` (recursive when
`site.recursive: true`, the default). Precedence is unchanged: CLI flags >
`md2x.yaml` > built-in defaults.

## Module Layout

```
src/md2x/site/
  __init__.py
  cli.py         # add_site_subparser(ap), run_site(args) -> int
  config.py      # SITE/AI/DEPLOY default blocks, merged into config.DEFAULTS
  models.py      # build_model(ai_cfg, role) -> agno model (str | OpenAILike)
  agents.py      # architect / page / index agent factories + schemas
  content.py     # md -> faithful HTML fragment (reuses pandoc + mermaid)
  archetypes.py  # preset registry: design contract + agent instructions
  pipeline.py    # generate_site(inputs, out_dir, cfg) -> int  (orchestrator)
  render.py      # assemble shell + fragment + enhancements -> write files
  assets/        # bundled CSS/JS shells per archetype (local, no external CDN)
  deploy/
    __init__.py  # dispatch by provider
    vercel.py    # deploy_vercel(out_dir, cfg) -> url
```

### Targeted refactor (serves this feature)

The Mermaid-render loop currently inlined in `pipeline.build` (roughly lines
107–153) is extracted into a reusable function:

```python
# mermaid.py
def render_into_markdown(md: str, work_dir: Path, cfg: dict, bins: dict)
    -> tuple[str, list[dict]]:
    """Render every ```mermaid``` block to an image and return the rewritten
    Markdown plus a manifest. Pure function of its inputs; no I/O beyond writing
    the diagram PNGs."""
```

Both `convert` (`pipeline.build`) and `site` (`content.py`) call it. This is a
behavior-preserving extraction for `convert` — covered by existing
`tests/test_pipeline.py` and a new direct unit test.

## Configuration Schema

Three new top-level sections, all optional. Absent → built-in defaults. Added to
`config.DEFAULTS` via `deep_merge` exactly like the existing sections, and
documented (commented) in the annotated `md2x.yaml`.

```yaml
site:
  layout: auto              # auto | multi-page | single-page
                            # auto = the archetype's default_layout
  archetype: reading        # reading|presentation|flyer|product|docs|report|custom
  style_prompt: ""          # free-text nudge for any archetype;
                            # full brief when archetype: custom
  fidelity: light-enhance   # preserve | light-enhance
  theme:
    accent: "#2563eb"
    dark_mode: true
  features: [search, animations, smooth-scroll]
  recursive: true           # recurse into directory inputs

ai:
  # Native providers — model-as-string "provider:model_id":
  model: "anthropic:claude-sonnet-4-5"
  # OR any OpenAI-compatible / local endpoint:
  # model:
  #   provider: openai-like
  #   id: llama-3.3-70b
  #   base_url: http://localhost:1234/v1
  #   api_key_env: LOCAL_LLM_KEY
  architect_model: null     # optional per-role override; null = use `model`
  page_model: null          # optional per-role override; null = use `model`
  temperature: 0.4
  max_tokens: null
  concurrency: 4            # parallel page agents
  retries: 2

deploy:
  provider: vercel
  token_env: VERCEL_TOKEN
  project: null            # optional Vercel project name
  team_id: null            # optional Vercel team id
  production: true
```

### Secrets policy

No secret is ever stored in `md2x.yaml`.

- **Native providers:** agno reads the standard provider env vars
  (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GROQ_API_KEY`, …) automatically.
- **OpenAI-compatible / local:** config names the env var via `api_key_env`;
  `build_model` reads `os.environ[api_key_env]`.
- **Vercel:** token read from the env var named by `deploy.token_env`
  (default `VERCEL_TOKEN`).

Missing required env var → fail fast with a message naming the exact variable.

## Generation Pipeline

`generate_site(inputs, out_dir, cfg)` orchestrates:

1. **Resolve inputs** → an ordered list of Markdown files (files kept in
   argument order; directory contents sorted; deduplicated).
2. **Per document** — `content.py`:
   - `mermaid.render_into_markdown(...)` renders diagrams to images (reuses the
     existing renderers; static PNG/SVG, guaranteed to match the PDF output).
   - pandoc `-t html` (no `--standalone`) produces a **faithful HTML fragment**.
   - Extract metadata: title (frontmatter or first H1), heading outline, word
     count. Produce a `Doc{path, title, outline, fragment_html, assets}`.
3. **Architect agent** — input: all docs' titles + outlines + `archetype` +
   `style_prompt` + resolved `layout`. Output (structured schema)
   `SitePlan{nav, groups, order, index_spec, theme_tokens}`. Uses
   `ai.architect_model or ai.model`.
4. **Page agents** — run in parallel bounded by `ai.concurrency`. Each receives
   one `Doc` + the `SitePlan` + the archetype's design contract, and behaves per
   `fidelity`:
   - `preserve`: returns only nav/design metadata; the fragment is emitted
     verbatim.
   - `light-enhance` (default): returns **additive** blocks (TL;DR,
     key-takeaways, related links) injected *around* the verbatim fragment; the
     original body is never modified.
   In both modes the author's words are emitted verbatim — no fidelity mode in
   v1 rewrites the body. Uses `ai.page_model or ai.model`.
5. **Index agent** — `SitePlan` → the home page. A landing page for
   flyer/product/presentation archetypes; a document hub for
   reading/docs/report.
6. **Assemble & write** — `render.py` composes archetype shell + fragment +
   enhancements:
   - multi-page → shared local `assets/` directory (CSS/JS once, referenced
     relatively).
   - single-page → all CSS/JS inlined into the one file.
   - Either way: **no external CDN**, so the output is a self-contained static
     site that deploys anywhere.

## Model Factory (provider/model agnostic)

```python
# models.py
def build_model(ai_cfg: dict, role: str = "model"):
    spec = ai_cfg.get(f"{role}_model") or ai_cfg["model"]
    if isinstance(spec, str):
        return spec                      # agno accepts "provider:model_id"
    provider = spec.get("provider", "openai-like")
    if provider == "openai-like":
        from agno.models.openai.like import OpenAILike
        return OpenAILike(
            id=spec["id"],
            base_url=spec["base_url"],
            api_key=os.environ[spec["api_key_env"]],
        )
    raise ValueError(f"unknown ai model provider: {provider!r}")
```

Agents are constructed with `Agent(model=build_model(cfg["ai"], role), ...)`,
plus `temperature`, `max_tokens`, `retries` from config. Switching from
Anthropic to a local Llama is a config edit only.

## Archetypes

`archetypes.py` is a registry mapping each preset to:

```python
{
  "design_contract": ...,        # CSS/JS shell choice + layout rules
  "architect_instructions": ..., # how to plan IA for this style
  "page_instructions": ...,      # how to render a page in this style
  "default_layout": "multi-page" | "single-page",
  "default_fidelity": "light-enhance",
}
```

| Archetype      | Generates                                                              | default_layout |
|----------------|-----------------------------------------------------------------------|----------------|
| `reading`*     | Long-form reading site: sidebar TOC, prose-optimized, cross-links     | multi-page     |
| `presentation` | Slide deck: section-per-slide, keyboard nav, big type, minimal text    | single-page    |
| `flyer`        | One punchy landing page: hero, bold visuals, CTAs, scroll animations   | single-page    |
| `product`      | Product page: hero + feature grid + screenshots + section blocks       | single-page    |
| `docs`         | Technical docs portal: persistent sidebar nav tree, search, code-first | multi-page     |
| `report`       | Status/data report: tables, callouts, summary cards                    | multi-page     |
| `custom`       | `style_prompt` is the full brief; architect interprets                 | from prompt    |

(*default.) `style_prompt` is appended to the architect/page instructions for
any archetype. `layout: auto` resolves to the archetype's `default_layout`; an
explicit `layout` value overrides.

## Mermaid & Assets

Mermaid blocks are rendered to static images via the existing renderers and
embedded in the fragment — guaranteed render, identical to the PDF leg.
`features: [animations, smooth-scroll, search]` add motion/behavior in the
*shell* (CSS/JS), never in the author's content. All assets are written locally;
nothing loads from a CDN.

## Vercel Deploy

`deploy/vercel.py`:

1. Walk `out_dir` → build `files: [{file: <relpath>, data: <base64>,
   encoding: "base64"}, ...]`.
2. `POST https://api.vercel.com/v13/deployments` (with `?teamId=` when
   `deploy.team_id` set), headers `Authorization: Bearer $VERCEL_TOKEN`, body
   `{name, files, projectSettings: {framework: null}, target: "production"}`.
3. Poll the deployment `readyState` until `READY` (or error); print the live
   `https://<url>`.

Token from the env var named by `deploy.token_env`. The dispatch in
`deploy/__init__.py` selects the provider, leaving room for future targets.

## Packaging

```toml
[project.optional-dependencies]
ai     = ["agno>=2.2", "httpx>=0.27"]
deploy = ["httpx>=0.27"]
all    = ["md2x[ai]", "md2x[deploy]"]
```

- `pip install md2x` — unchanged, pandoc-only, no AI deps.
- `pip install md2x[ai]` — agno + httpx for the AI site.
- `pip install md2x[deploy]` — httpx for Vercel deploy without AI (e.g. with
  `--no-ai`).
- Console entry point unchanged (`md2x = md2x.cli:main`); `main()` now dispatches
  subcommands.
- README gains an "AI reading-site" section; `md2x.yaml` gains commented
  `site` / `ai` / `deploy` blocks.

## Error Handling & Graceful Degradation

- `md2x site` without agno installed and without `--no-ai`
  → `ERROR: AI site needs agno. Run: pip install md2x[ai]` (exit non-zero).
- Missing required API-key / token env var → fail fast naming the exact variable.
- A page agent failure → fall back to a plain pandoc page (fragment + minimal
  shell) so the site still builds; emit a warning. (Mirrors the Mermaid
  `on_failure: keep_source` philosophy.)
- LLM structured-output failure → agno retries (`ai.retries`); on exhaustion,
  degrade as above.
- `--no-ai` → archetype templates render deterministically: pandoc body +
  code-generated nav and index, no LLM, no network. Always yields a site; also
  the CI-safe end-to-end path.
- Deploy failure → keep the local site, print the error and a token hint;
  non-zero exit.

## Testing

- **models.py:** `str` spec → passthrough; `dict` spec → `OpenAILike` with the
  right `id`/`base_url`/`api_key`. agno mocked or `importorskip("agno")`.
- **archetypes.py:** every preset returns a complete contract; `layout: auto`
  resolves correctly.
- **content.py:** body text of a sample doc is byte-for-byte present in the
  fragment (the fidelity guarantee), with Mermaid replaced by an image.
- **deploy/vercel.py:** payload builder walks the dir, base64-encodes, and emits
  the correct JSON shape and headers (httpx mocked).
- **pipeline `--no-ai` e2e:** a sample multi-file set → a complete site
  directory, no network. CI gate.
- **agno paths:** mock `agent.run` to return a canned `SitePlan` / enhancement,
  asserting deterministic assembly without real API calls.
- **CLI:** argv shim routes bare `md2x doc.md` to `convert`; `md2x site` parses
  all flags.

## Open Questions

None blocking. Future considerations parked under Non-Goals.
