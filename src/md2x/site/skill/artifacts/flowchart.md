## Artifact: flowchart

A process drawn as an inline-SVG flowchart whose steps are clickable: clicking a
node reveals its detail, timing, and failure path. **Reach for it** when the
source describes a request path, pipeline, or sequence of stages.

**Editor — no.** Read-only (no editable state), so no export contract needed.

### Template

```html
<svg id="fc" viewBox="0 0 320 90" role="img" aria-label="Flow"></svg>
<div id="detail" class="detail">Click a step.</div>
```

```css
#fc{width:100%;height:auto;display:block}
#fc .box{fill:var(--ds-card);stroke:var(--ds-border);cursor:pointer}
#fc .box.sel{stroke:var(--ds-accent);stroke-width:2}
#fc text{fill:var(--ds-fg);font:600 11px var(--ds-font-sans);pointer-events:none}
#fc line{stroke:var(--ds-muted)}
.detail{margin-top:var(--ds-space-2);padding:var(--ds-space-2);background:var(--ds-card);
  border:1px solid var(--ds-border);border-left:3px solid var(--ds-accent);
  border-radius:var(--ds-radius);font:14px var(--ds-font-sans);color:var(--ds-fg)}
.detail .fail{color:var(--ds-accent)}
```

```js
// Adapt: steps with label, timing, and failure path.
var STEPS=[{k:'Edge',t:'~5ms',f:'503 if pool drained'},
  {k:'Auth',t:'~12ms',f:'401 on bad token'},
  {k:'Handler',t:'~40ms',f:'500 on DB timeout'}];
var svg=document.getElementById('fc'),det=document.getElementById('detail'),NS='http://www.w3.org/2000/svg';
function el(n,a){var e=document.createElementNS(NS,n);for(var k in a)e.setAttribute(k,a[k]);return e;}
STEPS.forEach(function(s,i){var x=8+i*104;
  if(i)svg.appendChild(el('line',{x1:x-8,y1:40,x2:x,y2:40}));
  var r=el('rect',{x:x,y:24,width:88,height:32,rx:6,class:'box'});r.dataset.i=i;
  r.addEventListener('click',function(){[].forEach.call(svg.querySelectorAll('.box'),function(b){b.classList.remove('sel');});
    r.classList.add('sel');
    det.innerHTML='<strong>'+s.k+'</strong> · '+s.t+'<br><span class="fail">fail: '+s.f+'</span>';
    parent.postMessage({type:'md2x:resize',height:document.documentElement.scrollHeight},'*');});
  svg.appendChild(r);var tx=el('text',{x:x+44,y:44,'text-anchor':'middle'});tx.textContent=s.k;svg.appendChild(tx);});
parent.postMessage({type:'md2x:resize',height:document.documentElement.scrollHeight},'*');
```
