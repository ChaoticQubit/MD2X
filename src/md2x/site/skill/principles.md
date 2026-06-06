## Principles

1. **Render information in the shape it has.** Markdown flattens spatial and
   interactive information; HTML does not. A diff is an annotated diff; a module
   is boxes and arrows; design tokens are swatches; a process is a flowchart.
2. **Make it interactive where interaction is the point.** Motion and
   interaction cannot be described, only felt — build the real slider, the real
   drag/drop, the real live re-render.
3. **Every editor ends in an export button.** Any interface the reader edits must
   export its state back to Markdown (or a copyable diff) via the export
   contract. The reader stays in the loop; the loop gets tighter.
4. **Optimize for scannability and density.** Color, charts, timelines, and
   structure turn something people skim into something they read.
5. **Be faithful.** Do not invent facts absent from the source. Synthesized prose
   (summaries, captions) is allowed only at `fidelity: synthesize`, and must be
   clearly framed as synthesis.
