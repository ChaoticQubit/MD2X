# PR-G — guardrails + evals — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development or superpowers:executing-plans.

**Goal:** Two guardrail layers on every generation (agno-native, provider-agnostic) + a consolidated HTML sanitizer boundary + a 3-tier eval harness (deterministic Tier-1 in CI, opt-in LLM-judge Tier-2 + performance Tier-3).

**Architecture (verified against agno 2.6.11):**
- Input guardrails = `agno.guardrails` classes passed as `Agent(pre_hooks=[...])`. `PromptInjectionGuardrail` default-on (a hostile Markdown doc can't hijack the agent); `PIIDetectionGuardrail` + `OpenAIModerationGuardrail` opt-in via `ai.guardrails` config. A trip raises `InputCheckError`, which each pipeline stage's existing try/except degrades to the deterministic path (logged WARNING).
- One `sanitize.py` owns every HTML sanitizer (consolidating the per-mode copies): `sanitize_inline` (block escape-hatch — no scripts at all), `sanitize_svg`, `sanitize_artifact_html` + `sanitize_full` (keep inline scripts, strip external/network), `is_self_contained`. The artifact iframe CSP + the full-page CSP remain the runtime boundary; the sanitizer is the deterministic, testable defense-in-depth.
- Evals: Tier-1 `tests/evals/` runs in CI over synthetic Docs (no pandoc, no LLM) asserting structural invariants per render mode. Tier-2/3 `evals/` are opt-in scripts (need `[ai]` + a real model) using `AccuracyEval` (Agent-as-Judge, Thariq rubric) and `PerformanceEval`; a smoke test just imports them.

**Tech Stack:** Python, agno 2.6.11 (`agno.guardrails`, `agno.eval.accuracy.AccuracyEval`, `agno.eval.performance.PerformanceEval`), pytest.

---

## File Structure
- Create `src/md2x/site/guardrails.py` — `build_pre_hooks(cfg) -> list`.
- Create `src/md2x/site/sanitize.py` — canonical sanitizers + `is_self_contained`.
- Modify `src/md2x/site/blocks_render.py`, `blocks_agent.py`, `full_render.py` — import sanitizers from `sanitize.py` (re-export the names tests use); pass `pre_hooks` to their agents.
- Modify `src/md2x/site/agents.py`, `report/agent.py` — `pre_hooks=build_pre_hooks(cfg)`.
- Modify `src/md2x/config.py` — `ai.guardrails` block.
- Modify `src/md2x/site/skill/principles.md` — add a guardrails section (faithfulness, real slugs, no external network).
- Create `tests/test_site_guardrails.py`, `tests/test_site_sanitize.py`.
- Create `tests/evals/__init__.py`, `tests/evals/fixtures/*.md` (synthetic), `tests/evals/test_tier1_invariants.py`.
- Create `evals/README.md`, `evals/reference/*.md`, `evals/thariq_rubric.py`, `evals/run_quality_eval.py`, `evals/run_performance_eval.py`, `tests/evals/test_eval_scripts_import.py` (smoke).

---

### Task 1: sanitize.py (consolidate + harden)
- [ ] Failing test (`tests/test_site_sanitize.py`): `sanitize_inline` strips all `<script>` + `onclick`; `sanitize_svg` keeps `<rect>` drops `<script>`; `sanitize_artifact_html` drops external `<script src=https>` keeps inline `<script>`; `sanitize_full` drops external `<link>`/`<img src=https>` keeps inline script; `is_self_contained("<img src='https://e/x'>")` is False, `is_self_contained('<svg xmlns="http://www.w3.org/2000/svg"><rect/></svg>')` is True (namespace URI ignored).
- [ ] Implement `sanitize.py` (move the canonical regexes here; `is_self_contained` checks `(?:src|href)=` / `url(` with `https?:`, ignoring `xmlns`/namespace).
- [ ] Re-point `blocks_render` (`from .sanitize import sanitize_inline, sanitize_svg`), `blocks_agent` (`sanitize_artifact_html`), `full_render` (`sanitize_full`); delete their local copies. Run the full suite — existing sanitizer tests stay green via the re-exported names.
- [ ] PASS. Commit `feat(site): consolidate HTML sanitizers into sanitize.py + is_self_contained (PR-G)`.

### Task 2: guardrails.py + config + wiring
- [ ] Failing test (`tests/test_site_guardrails.py`): `build_pre_hooks({"ai":{"guardrails":{"prompt_injection":True}}})` returns a list with one `PromptInjectionGuardrail`; `pii:True` adds a second; all-off returns `[]`. (importorskip agno.)
- [ ] Implement `guardrails.py` (`build_pre_hooks`, lazy agno import inside). Add `ai.guardrails={prompt_injection:True, pii:False, moderation:False}` to DEFAULTS. Wire `pre_hooks=build_pre_hooks(cfg)` into `agents._make_agent`, `blocks_agent`, `full_agent`, `report/agent`.
- [ ] Failing test: `_make_agent` builds an Agent with non-empty `pre_hooks` when default config (capture via monkeypatched Agent).
- [ ] PASS. Commit `feat(site): agno input guardrails (prompt-injection default-on) wired into every agent (PR-G)`.

### Task 3: Tier-1 deterministic evals (CI)
- [ ] Failing test (`tests/evals/test_tier1_invariants.py`): build 2 synthetic Docs; for blocks + full modes, write the site (no LLM) and assert: every doc → a `<slug>.html`; index internal links all resolve to written files; `--ds-` tokens present; full-mode pages carry the CSP `default-src 'none'`; an `<h1>` exists on each page; no external `http(s)://` resource refs (`is_self_contained`); page size under a cap.
- [ ] Implement `tests/evals/fixtures/*.md` + the test (construct `Doc` directly, call `write_blocks_site`/`write_full_site` — no pandoc).
- [ ] PASS. Commit `test(evals): Tier-1 deterministic structural invariants (PR-G)`.

### Task 4: Tier-2/3 opt-in eval scripts  [DELEGATED to subagent, reviewed here]
- [ ] `evals/thariq_rubric.py` (5 dimensions: information-in-its-shape, density/scannability, faithfulness, interactivity-where-warranted, on-brand), `evals/run_quality_eval.py` (AccuracyEval Agent-as-Judge over `evals/reference/*.md`, guarded behind `__main__` + an env/flag, never auto-runs), `evals/run_performance_eval.py` (PerformanceEval), `evals/README.md`, 4 reference docs. Smoke test `tests/evals/test_eval_scripts_import.py` imports the modules (agno-gated) without running them.
- [ ] PASS. Commit `feat(evals): opt-in Tier-2 LLM-judge + Tier-3 performance harness (PR-G)`.

### Task 5: skill principles + regression
- [ ] Add a guardrails section to `skill/principles.md`. Commit `docs(skill): guardrails in the prompt layer (PR-G)`.
- [ ] Full suite green; WIP untouched. Update PR-G task; proceed to PR-H.

---

## Self-Review
- Spec coverage: pre-hooks prompt-injection default-on + PII/moderation opt-in ✓ (T2); post/sanitizer boundary consolidated ✓ (T1); render invariants ✓ (T3); Tier-1 deterministic in CI ✓ (T3); Tier-2 Agent-as-Judge + Tier-3 performance opt-in ✓ (T4). All agno-native → provider-agnostic.
- Safety: guardrail trips degrade (never crash); sanitizer is deterministic + tested; CSP remains the runtime boundary.
- Backward-compat: sanitizers re-exported under old names; guardrails default to one cheap local hook (no network); evals additive.
