## Archetype: editor

For turning the document into a working editing interface — the page IS a custom editor for the source's content.

**Shell:** sidebar. **Render mode:** hybrid (default).

**Structure.** Skip the read-it layout: parse the source into editable state and render a purpose-built tool around its shape. Items/cards/tasks → a board; settings/parameters → toggles and sliders; prompts/templates → a tuner. Sidebar holds navigation, filters, or a section list; the main pane is the live editor with inline add/edit/remove/reorder. Seed every control from the actual source content. The interface ALWAYS ends in an export button that round-trips the edited state back to clean Markdown/JSON matching the input format.

**Favor.** `triage-board` for status/kanban content, `prompt-tuner` for prompt or template text, and `feature-flags` for toggle/config sets. Hybrid (a real artifact) is required — this archetype is interactive by definition.

**Avoid.** Don't ship a read-only render or forget the export — without a working round-trip back to source format it has failed. Preserve all original fields/values; don't drop or invent data.
