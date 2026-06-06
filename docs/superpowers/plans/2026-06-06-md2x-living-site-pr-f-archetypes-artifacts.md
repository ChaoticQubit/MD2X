# PR-F — 12 archetypes + artifact-pattern library + architect selection — Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development or superpowers:executing-plans.

**Goal:** Rebuild the archetype registry on Thariq's taxonomy (12 presets, each carrying a `default_render_mode` + `suggested_artifacts`), ship the artifact-pattern library as skill files, and let the architect select per-page artifacts/mode that flow into the per-page agent's skill injection.

**Architecture:** The skill loader (PR-A) already composes `archetypes/<name>.md` + `artifacts/<id>.md` when present — so adding those files lights them up automatically. `archetypes.py` gains the 5 new presets + two metadata fields. The architect emits, per nav item, an optional `render_mode` + `artifacts`; `_to_site_plan` collects these into `SitePlan.page_artifacts`/`page_modes`; the block/full writers pass a page's artifacts into `load_skill(..., artifacts=...)`, so the author agent receives exactly the patterns the architect chose.

**Tech Stack:** Python, agno/pydantic, pytest, Markdown skill content.

---

## File Structure
- Modify `src/md2x/site/archetypes.py` — 12 archetypes; add `default_render_mode`, `suggested_artifacts`; new accessors.
- Modify `src/md2x/site/schemas.py` — `SitePlan.page_artifacts: dict[str,list[str]]`, `page_modes: dict[str,str]`.
- Modify `src/md2x/site/agents.py` — `_NavItemModel` gains `render_mode`/`artifacts`; `_to_site_plan` builds the dicts; architect instruction teaches per-page selection.
- Modify `src/md2x/site/blocks_render.py` + `blocks_agent.py` — thread a page's artifacts into `run_page_blocks` → `load_skill(artifacts=...)`.
- Modify `src/md2x/site/full_render.py` + `full_agent.py` — thread artifacts into `run_full_page`.
- Modify `src/md2x/site/cli.py` + `src/md2x/config.py` comment — expand archetype choices to 12.
- Create `src/md2x/site/skill/archetypes/{reading,presentation,flyer,product,docs,review,plan,explainer,report,editor,design,custom}.md` (12).
- Create `src/md2x/site/skill/artifacts/{triage-board,prompt-tuner,feature-flags,flowchart,module-map,annotated-diff,live-demo,deck,animation-sandbox,clickable-flow,svg-figure,comparison,chart}.md` (13).
- Test: `tests/test_site_archetypes.py` (extend), `tests/test_site_skill.py` (extend), `tests/test_site_agents.py` (per-page selection).

---

## Registry shape (pin)

```python
ARCHETYPES["explainer"] = {
    "shell": "sidebar", "default_layout": "multi-page",
    "default_render_mode": "hybrid",
    "suggested_artifacts": ["live-demo", "flowchart", "svg-figure", "comparison"],
    "architect_instructions": "...", "page_instructions": "...",
}
```

12 presets + their (shell, default_render_mode, suggested_artifacts):
- reading (sidebar, blocks, [svg-figure, comparison])
- presentation (deck, hybrid, [deck, chart, svg-figure])
- flyer (landing, blocks, [clickable-flow, svg-figure])
- product (landing, hybrid, [comparison, clickable-flow, chart])
- docs (sidebar, blocks, [annotated-diff, module-map, live-demo])
- review (sidebar, hybrid, [annotated-diff, module-map, flowchart])
- plan (sidebar, hybrid, [flowchart, comparison, chart])
- explainer (sidebar, hybrid, [live-demo, flowchart, svg-figure, comparison])
- report (sidebar, blocks, [chart])
- editor (sidebar, hybrid, [triage-board, prompt-tuner, feature-flags])
- design (sidebar, hybrid, [animation-sandbox, comparison])
- custom (sidebar, blocks, [])

New accessors: `get_default_render_mode(archetype)`, `get_suggested_artifacts(archetype)`.

---

### Task 1: archetype registry (12 + metadata)
- [ ] Failing test (`tests/test_site_archetypes.py`): all 12 names resolve; each has `default_render_mode` in {blocks,hybrid,full} and a `suggested_artifacts` list; `get_default_render_mode("editor")=="hybrid"`.
- [ ] Implement the 12 presets + `default_render_mode`/`suggested_artifacts` + accessors. Keep `architect_instructions`/`page_instructions` (legacy shell path + report).
- [ ] PASS. Commit `feat(site): 12 Thariq archetypes + render-mode/artifact metadata (PR-F)`.

### Task 2: per-page architect selection
- [ ] Failing test (`tests/test_site_agents.py`): a monkeypatched architect emitting a nav item with `artifacts=["chart"]`, `render_mode="hybrid"` → `plan.page_artifacts["a"]==["chart"]` and `plan.page_modes["a"]=="hybrid"`.
- [ ] Implement: `SitePlan.page_artifacts`/`page_modes` (default_factory dict); `_NavItemModel.render_mode/artifacts`; `_to_site_plan` builds the dicts (only real artifact ids — validate against the artifact file set or just pass through and let the loader skip missing); architect instruction teaches: "per page, pick render_mode + the artifact patterns that fit; choose from the archetype's suggested set."
- [ ] PASS. Commit `feat(site): architect selects per-page render_mode + artifacts (PR-F)`.

### Task 3: thread artifacts into the page agents
- [ ] Failing test: `run_page_blocks(doc, cfg, artifacts=["chart"])` loads the skill with that artifact (capture `load_skill` call / assert the chart artifact file content appears in the agent instructions via a monkeypatched `_make`-style capture).
- [ ] Implement: `run_page_blocks(doc, cfg, artifacts=None)` → `load_skill(..., artifacts=artifacts)`; `_page_doc_for(doc, cfg, plan)` passes `plan.page_artifacts.get(doc.slug)`; same for `run_full_page(doc, cfg, artifacts=None)` and `write_full_site`.
- [ ] PASS. Commit `feat(site): inject architect-selected artifacts into page agents (PR-F)`.

### Task 4: CLI + config choices
- [ ] Failing test (`tests/test_site_cli.py` or archetypes): the 12 names are accepted.
- [ ] Implement: expand `cli.py` `--archetype` choices to the 12; update `config.py` archetype comment.
- [ ] PASS. Commit `feat(cli): expand archetype choices to the 12 (PR-F)`.

### Task 5: skill content — archetypes (12 files)
- [ ] Author `skill/archetypes/*.md` (12). Each: what the archetype is, how to structure it in Thariq's shape (which blocks/sections), which artifacts to favor, its default render mode. Each references the block vocabulary + `--ds-*` tokens.
- [ ] Test (`tests/test_site_skill.py`): `load_skill("explainer", "hybrid", "synthesize")` includes archetype-specific marker text.
- [ ] Commit `docs(skill): 12 archetype specialization files (PR-F)`.

### Task 6: skill content — artifact patterns (13 files)
- [ ] Author `skill/artifacts/*.md` (13). Each: what it is + when to use; export contract if it is an editor; a known-good self-contained HTML/CSS/JS template skeleton consuming `--ds-*` tokens (editors implement the `md2x:request-export`→`md2x:export` round-trip; no external network).
- [ ] Test: `load_skill("editor","hybrid","synthesize", artifacts=["triage-board"])` includes the triage-board template marker.
- [ ] Commit `docs(skill): artifact-pattern library (13 patterns) (PR-F)`.

### Task 7: regression
- [ ] Full suite green; WIP untouched. Update PR-F task; proceed to PR-G.

---

## Self-Review
- Spec coverage: 12 archetypes ✓ (T1+T5), artifact-pattern library ✓ (T6), architect per-page selection ✓ (T2+T3). Loader already composes the files (PR-A).
- Backward-compat: new archetypes are additive; existing 7 keep working. Per-page dicts default empty → existing plans unaffected. `run_page_blocks`/`run_full_page` gain an optional `artifacts=None`.
