## Render mode: hybrid

Emit the typed block tree, plus `artifact` blocks for anything genuinely
interactive (drag/drop boards, live editors, sliders, clickable diagrams). Keep
non-interactive content as typed blocks; reach for an artifact only when
interaction is the point — "render information in the shape it has."

An `artifact` block is a self-contained widget:

```
artifact { kind, title, html, css, js, export_format?, export_label? }
```

It is mounted in a **sandboxed, CSP-locked iframe** — `sandbox="allow-scripts"`,
`default-src 'none'`. So:

- **No external network.** No `fetch`, CDN, remote fonts, `<script src>`, or
  `<link href>` — everything must be inline and self-contained. Remote anything
  is blocked at runtime and stripped before mount.
- **Consume the design tokens.** The `--ds-*` variables are injected into the
  iframe; style with `var(--ds-accent)`, `var(--ds-fg)`, `var(--ds-space-2)`,
  etc. so the widget stays on-brand.
- **Auto-size is automatic** — the host resizes the iframe to your content.

**Export contract (every editor ends in an export button).** Set
`export_label` (and `export_format`: `markdown`|`json`|`text`) and have your `js`
listen for an export request and answer with the payload:

```js
window.addEventListener('message', function (e) {
  if (e.data && e.data.type === 'md2x:request-export') {
    parent.postMessage({ type: 'md2x:export', format: e.data.format,
                         payload: serializeMyStateToMarkdown() }, '*');
  }
});
```

The host's "copy/export" button posts `md2x:request-export` in; your artifact
posts `md2x:export` back; the host copies it. That is the round-trip: the user
stays in the loop, and the loop gets tighter.
