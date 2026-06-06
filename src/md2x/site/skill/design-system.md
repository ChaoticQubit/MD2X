## Design-system contract

The architect emits one `DesignSystem` (palette, radius, font stacks, density). It
is sanitized once and exposed as CSS custom properties on `:root`. Consume the
tokens; never hardcode a colour, length, or font.

The concrete tokens (this exact set is emitted — use these names):

- Colour: `--ds-accent`, `--ds-bg`, `--ds-fg`, `--ds-muted`, `--ds-card`, `--ds-border`.
- Type: `--ds-font-sans`, `--ds-font-mono`.
- Shape: `--ds-radius`.
- Space: `--ds-space-1` … `--ds-space-4` (a 4-step scale; tightens when `--ds-density` is `compact`).
- Density: `--ds-density` (`comfortable` | `compact`).

Every page — and every artifact iframe — receives these variables. Build
components that reference them (e.g. `background:var(--ds-card)`,
`padding:var(--ds-space-2)`, `border-radius:var(--ds-radius)`) so even free-form
`hybrid`/`full` output stays on-brand. The site also ships a living
design-system page that renders these tokens as copyable swatches.

Do not import external fonts, stylesheets, or scripts — everything is
self-contained and ships as static files with no network access.
