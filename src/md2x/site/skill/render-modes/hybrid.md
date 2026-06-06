## Render mode: hybrid

Emit the typed block tree, plus `artifact` blocks for anything genuinely
interactive. An artifact is a self-contained `{ html, css, js }` widget mounted
in a sandboxed iframe. It must consume the design-system variables and, if it is
an editor, implement the export contract. Keep non-interactive content as typed
blocks; reach for an artifact only when interaction is the point.
