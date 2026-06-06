# PR-H — flip defaults to hybrid + synthesize, + docs — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development or superpowers:executing-plans.

**Goal:** Make the living-site experience the out-of-box default — `render_mode: hybrid` + `fidelity: synthesize` — now that the eval gate (Tier-1) is green; expose the two new axes on the CLI; and document the three-axis model. A prerequisite correctness fix: thread `use_ai` into the blocks writer so `--no-ai` never invokes the synthesize agent.

**Architecture:** Flipping `fidelity` to `synthesize` makes `_page_doc_for` reach for the block-authoring agent on the default path — which must be suppressed when the user passed `--no-ai`. So `write_blocks_site`/`_page_doc_for` take an explicit `use_ai`, mirroring `write_full_site`. Then the DEFAULTS flip, CLI flags, and README/example-config docs land. The user's working `md2x.yaml` is never touched — the commented config lives in `README.md` + a new committed `md2x.example.yaml`.

**Tech Stack:** Python, argparse, pytest, Markdown/YAML docs.

---

## File Structure
- Modify `src/md2x/site/blocks_render.py` — `write_blocks_site(..., *, use_ai)`, `_page_doc_for(doc, cfg, plan, use_ai)`; agent only when `use_ai and fidelity == "synthesize"`.
- Modify `src/md2x/site/pipeline.py` — pass `use_ai=use_ai` to `write_blocks_site`.
- Modify tests that call `write_blocks_site` — pass `use_ai=`.
- Modify `src/md2x/config.py` — DEFAULTS `render_mode: "hybrid"`, `fidelity: "synthesize"`.
- Modify `src/md2x/site/cli.py` — add `--render-mode` (blocks|hybrid|full); add `synthesize` to `--fidelity`; wire both into overrides.
- Create `md2x.example.yaml` — fully commented example (NOT the user's md2x.yaml).
- Modify `README.md` — three-axis model, archetypes, render modes, artifacts, guardrails/evals.
- Test: `tests/test_site_config.py`, `tests/test_site_blocks_pipeline.py`, `tests/test_site_cli.py`, `tests/test_site_render.py`/`test_site_blocks_render.py` (use_ai threading).

---

### Task 1: thread use_ai into the blocks writer (correctness)
- [ ] Failing test (`tests/test_site_blocks_render.py`): with `fidelity="synthesize"` and `use_ai=False`, `write_blocks_site` produces deterministic pages and NEVER calls `run_page_blocks` (monkeypatch `blocks_render._page_doc_for`'s agent path to explode, or monkeypatch `blocks_agent.run_page_blocks` to raise; assert deterministic body still written).
- [ ] Implement: `_page_doc_for(doc, cfg, plan, use_ai)` → `if use_ai and cfg["site"].get("fidelity") == "synthesize": run_page_blocks(...)`; `write_blocks_site(out_dir, docs, plan, enh, cfg, *, use_ai)`; `_render_doc_page(..., use_ai)`. Update `pipeline` to pass `use_ai`.
- [ ] Update existing callers/tests: `tests/test_site_blocks_render.py::test_write_blocks_site_emits_pages` → `use_ai=False`; `tests/evals/test_tier1_invariants.py` → `use_ai=False`; the pipeline monkeypatch fakes (`tests/test_site_pipeline.py`, `tests/test_site_blocks_pipeline.py`) → accept `use_ai` (`**_` or explicit kw).
- [ ] PASS. Commit `fix(site): thread use_ai into the blocks writer so --no-ai never calls the agent (PR-H)`.

### Task 2: flip defaults
- [ ] Failing test (`tests/test_site_config.py`): `cfg["site"]["render_mode"] == "hybrid"` and `cfg["site"]["fidelity"] == "synthesize"`. (Update the existing `test_defaults_have_render_mode` / `test_defaults_have_site_block` expectations.)
- [ ] Implement: DEFAULTS `"render_mode": "hybrid"`, `"fidelity": "synthesize"` (update the inline comments).
- [ ] Run the full suite; fix any test that hardcoded the old defaults (e.g. anything asserting `fidelity == "light-enhance"` from DEFAULTS).
- [ ] PASS. Commit `feat(config): default to render_mode=hybrid + fidelity=synthesize (PR-H)`.

### Task 3: CLI flags
- [ ] Failing test (`tests/test_site_cli.py`): the site subparser accepts `--render-mode hybrid` and `--fidelity synthesize`; `_apply_site_overrides` sets them.
- [ ] Implement: `--render-mode` (choices from `modes.RENDER_MODES`), add `synthesize` to `--fidelity` choices (from `modes.FIDELITIES`), set both in `_apply_site_overrides`.
- [ ] PASS. Commit `feat(cli): --render-mode flag + synthesize fidelity (PR-H)`.

### Task 4: docs (README + example config)
- [ ] Write `md2x.example.yaml` — a commented `site:` + `ai:` block documenting archetype (12), render_mode (blocks|hybrid|full), fidelity (preserve|light-enhance|synthesize), theme, guardrails. (Plain file; the loader is unaffected; never overwrites the user's md2x.yaml.)
- [ ] Update `README.md` — a "Living sites" section: the three orthogonal axes, the 12 archetypes table, the three render modes (with the safety ladder + CSP/sandbox note), the artifact library, guardrails + the 3 eval tiers, and a pointer to `md2x.example.yaml`.
- [ ] Commit `docs: README living-site model + md2x.example.yaml (PR-H)`.

### Task 5: regression + milestone
- [ ] Full suite green; WIP (`md2x.yaml`/`examples`) still untouched. Update PR-H task. The 8-PR living-site rebuild is complete.

---

## Self-Review
- Spec coverage: defaults flipped to hybrid+synthesize after the eval gate ✓ (T2); README + commented config docs ✓ (T4, via example file to respect the never-touch-md2x.yaml constraint); CLI exposure of the new axes ✓ (T3). The use_ai correctness fix (T1) is the safe precondition for the synthesize default.
- Constraint: `md2x.yaml` (user WIP) is never staged; config docs ship as `md2x.example.yaml` + README.
- Backward-compat: `--no-ai` stays fully deterministic after the flip (T1); `preserve`/`light-enhance`/`blocks` remain available as opt-downs.
