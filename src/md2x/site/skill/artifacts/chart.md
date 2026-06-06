## Artifact: chart

A small bar or line chart rendered as inline SVG straight from a data array — no
charting library. **Reach for it** for a handful of numbers worth showing as a
shape: a trend, a breakdown, a before/after. (For richer block-level charts the
`blocks` renderer also has a native `chart`; use this artifact in hybrid/full.)

**Editor — no.** Static visualization, so no export contract needed.

### Template

```html
<figure class="ch">
  <svg id="svg" viewBox="0 0 300 160" role="img" aria-label="Chart"></svg>
  <figcaption id="cap"></figcaption>
</figure>
```

```css
.ch{margin:0}.ch svg{width:100%;height:auto;display:block}
.ch .bar{fill:var(--ds-accent)}
.ch .axis{stroke:var(--ds-border)}
.ch .vlbl{fill:var(--ds-muted);font:10px var(--ds-font-mono)}
.ch .xlbl{fill:var(--ds-fg);font:11px var(--ds-font-sans);text-anchor:middle}
.ch figcaption{margin-top:var(--ds-space-2);font:13px var(--ds-font-sans);color:var(--ds-muted)}
```

```js
// Adapt: data + caption. (Swap the bar loop for a polyline to make it a line chart.)
var DATA=[{x:'Q1',y:42},{x:'Q2',y:58},{x:'Q3',y:50},{x:'Q4',y:73}],CAP='Signups per quarter (k)';
var W=300,H=160,PAD=28,svg=document.getElementById('svg'),NS='http://www.w3.org/2000/svg';
var max=Math.max.apply(null,DATA.map(function(d){return d.y;})),
  bw=(W-PAD*2)/DATA.length,sc=function(v){return (H-PAD)-v/max*(H-PAD*2);};
function el(n,a,t){var e=document.createElementNS(NS,n);for(var k in a)e.setAttribute(k,a[k]);if(t!=null)e.textContent=t;return e;}
svg.appendChild(el('line',{x1:PAD,y1:H-PAD,x2:W-PAD/2,y2:H-PAD,class:'axis'}));
svg.appendChild(el('line',{x1:PAD,y1:PAD/2,x2:PAD,y2:H-PAD,class:'axis'}));
DATA.forEach(function(d,i){var x=PAD+i*bw+bw*0.15,y=sc(d.y);
  svg.appendChild(el('rect',{x:x,y:y,width:bw*0.7,height:(H-PAD)-y,rx:3,class:'bar'}));
  svg.appendChild(el('text',{x:x+bw*0.35,y:y-4,'text-anchor':'middle',class:'vlbl'},String(d.y)));
  svg.appendChild(el('text',{x:x+bw*0.35,y:H-PAD+14,class:'xlbl'},d.x));});
document.getElementById('cap').textContent=CAP;
parent.postMessage({type:'md2x:resize',height:document.documentElement.scrollHeight},'*');
```
