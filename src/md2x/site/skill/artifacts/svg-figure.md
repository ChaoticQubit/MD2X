## Artifact: svg-figure

A labelled inline-SVG figure — a conceptual diagram drawn on-brand via the design
tokens (no photo, no library). **Reach for it** when the prose describes a mental
model, a relationship, or a shape that a picture would land faster than words.

**Editor — no.** A static figure, so no export contract needed. (Use this when
nothing is interactive; if nodes should be clickable, use `module-map` or
`flowchart` instead.)

### Template

```html
<figure class="fig">
  <svg viewBox="0 0 300 150" role="img" aria-label="Layered model">
    <rect x="20" y="20"  width="260" height="34" rx="6" class="band a"/>
    <rect x="20" y="62"  width="260" height="34" rx="6" class="band b"/>
    <rect x="20" y="104" width="260" height="34" rx="6" class="band c"/>
    <text x="150" y="42"  class="lbl">Interface</text>
    <text x="150" y="84"  class="lbl">Domain logic</text>
    <text x="150" y="126" class="lbl">Storage</text>
  </svg>
  <figcaption>Three layers; each only talks to the one below.</figcaption>
</figure>
```

```css
.fig{margin:0}
.fig svg{width:100%;height:auto;display:block}
.band{stroke:var(--ds-border)}
.band.a{fill:color-mix(in srgb,var(--ds-accent) 22%,var(--ds-card))}
.band.b{fill:color-mix(in srgb,var(--ds-accent) 12%,var(--ds-card))}
.band.c{fill:var(--ds-card)}
.lbl{fill:var(--ds-fg);font:600 13px var(--ds-font-sans);text-anchor:middle}
.fig figcaption{margin-top:var(--ds-space-2);font:13px var(--ds-font-sans);color:var(--ds-muted)}
```

```js
// Static figure: just report height so the host sizes the frame.
parent.postMessage({type:'md2x:resize',height:document.documentElement.scrollHeight},'*');
```
