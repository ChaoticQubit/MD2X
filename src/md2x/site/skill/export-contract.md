## Export contract

Interactive editors round-trip their state to the host page.

- The artifact posts: `window.parent.postMessage({ type: "md2x:export",
  format: "markdown" | "json" | "text", payload: <string> }, "*")`.
- It posts on every meaningful change and once on load.
- The host renders a "Copy as Markdown / Download" button wired to the latest
  payload. You only emit the `postMessage`; the host renders the button.
- The artifact also posts `{ type: "md2x:resize", height: <px> }` after layout so
  the host can size the iframe.
