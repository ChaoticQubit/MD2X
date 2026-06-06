## Render mode: full

Author ONE self-contained, interactive HTML document for the page — render the
information in the shape it actually has (diagrams, live widgets, clickable
steps, editors), not a wall of prose. The page is served standalone (no site
chrome), so it must be a complete, valid document.

Hard constraints (enforced by a CSP `<meta>` and a sanitizer at render time):

- **Self-contained.** Inline ALL CSS and JS. NO external network — no CDN, no
  remote fonts, no `<script src>`, no `<link href>`, no `fetch`/XHR. It must work
  fully offline as a single file. Remote references are stripped and blocked.
- **Consume the design tokens.** The `--ds-*` variables are injected into your
  `<head>`; style with `var(--ds-accent)`, `var(--ds-fg)`, `var(--ds-space-2)`,
  `var(--ds-radius)`, etc. so the page stays on-brand.
- **Faithful.** Use only facts present in the source; never invent figures.

If the page is an editor, end it with an export button implementing the export
contract — on a `md2x:request-export` message, `postMessage` to the parent
`{ type:'md2x:export', format, payload }` and set `export_label`/`export_format`.
You stay in the loop; the loop gets tighter.
