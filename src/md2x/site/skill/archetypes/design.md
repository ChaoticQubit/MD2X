## Archetype: design

For a living design system or style guide — tokens, components, and motion you can see and copy.

**Shell:** sidebar. **Render mode:** hybrid (default).

**Structure.** Lead with foundations: render the design tokens as copyable swatches and specimens — color chips (click to copy the value), type scale, spacing and radius samples — each pulled from the `--ds-*` variables, not hardcoded. Then a component-variants sheet: each component shown in its states (default/hover/disabled, sizes, variants) side by side, with the markup viewable. Add a motion section with an animation sandbox to tune and preview easings/durations. Sidebar nav: Tokens / Color / Type / Components / Motion.

**Favor.** `animation-sandbox` for live motion tuning and `comparison` for variant/before-after sheets. Hybrid so swatches copy and the sandbox runs.

**Avoid.** Never hardcode hex/px that should reference a token; the page must reflect the real token values. Don't invent components or states the source doesn't define.
