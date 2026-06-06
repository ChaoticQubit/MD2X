## Archetype: docs

For technical documentation — reference and guides a reader scans, searches, and copies from.

**Shell:** sidebar. **Render mode:** blocks (default).

**Structure.** Persistent left nav listing every section; every heading is an anchor with a stable slug for deep links. Lead each page with a one-line summary of what it covers, then ordered sections. Make `code` blocks first-class — syntactic, copyable, labeled by language. Use `tabs` for config/install variants (npm/pnpm/yarn, OS, language). Reach for `steps` for procedures, `callout` for notes/warnings/gotchas, `table` for parameter and option references, and `collapsible` for advanced or rarely-needed detail.

**Favor.** `annotated-diff` to show before/after changes, `module-map` to orient the reader in the codebase, and `live-demo` for a runnable snippet. Default blocks; go hybrid only where a live demo genuinely helps.

**Avoid.** Don't paraphrase API names, signatures, flags, or commands — copy them exactly from the source. No marketing tone; correctness and findability win.
