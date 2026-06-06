## Archetype: review

For a code-review / change write-up — what changed, what's risky, what to look at.

**Shell:** sidebar. **Render mode:** hybrid (default).

**Structure.** Lead with a PR/change `summary` (title, scope, files touched, intent). Then a findings section: one `callout` per finding, severity-tagged (use accent for critical, muted for nits) and ordered worst-first. Follow with an annotated diff of the load-bearing hunks, then a `module-map` showing which parts of the system the change reaches. Optionally a `steps` checklist for the reviewer and a `table` of files-by-risk. Sidebar nav jumps to Summary / Findings / Diff / Map.

**Favor.** `annotated-diff` for inline review comments on real hunks, `module-map` for blast radius, and `flowchart` when the change alters control or data flow. Hybrid so the diff and map are explorable.

**Avoid.** Don't invent issues, line numbers, or severities — only flag what the source diff/notes actually support. Quote code verbatim.
