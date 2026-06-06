## Design-system contract

A single design system is derived once and exposed as CSS custom properties.
Consume them; never hardcode.

- Color: `--ds-bg`, `--ds-fg`, `--ds-muted`, `--ds-accent`, `--ds-border`.
- Type: `--ds-font-sans`, `--ds-font-mono`, `--ds-font-serif`, `--ds-scale-*`.
- Space: `--ds-space-1` … `--ds-space-6`; radius `--ds-radius`; density `--ds-density`.

Every page and every artifact iframe receives these variables. Build components
that reference them so free-form output stays on-brand. Do not import external
fonts, stylesheets, or scripts — everything is self-contained.
