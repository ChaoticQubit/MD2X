## Artifact: module-map

Modules drawn as inline-SVG boxes joined by arrows, with one highlighted "hot
path"; clicking a box shows that module's role. **Reach for it** when the source
describes a system's architecture, package layout, or how components depend on
each other.

**Editor — no.** Read-only, so no export contract needed.

### Template

```html
<svg id="mm" viewBox="0 0 320 130" role="img" aria-label="Module map"></svg>
<div id="role" class="role">Click a module.</div>
```

```css
#mm{width:100%;height:auto;display:block}
#mm .mod{fill:var(--ds-card);stroke:var(--ds-border);cursor:pointer}
#mm .mod.hot{stroke:var(--ds-accent);stroke-width:2}
#mm .edge{stroke:var(--ds-muted);fill:none}
#mm .edge.hot{stroke:var(--ds-accent)}
#mm text{fill:var(--ds-fg);font:600 11px var(--ds-font-sans);pointer-events:none}
.role{margin-top:var(--ds-space-2);padding:var(--ds-space-2);background:var(--ds-card);
  border:1px solid var(--ds-border);border-radius:var(--ds-radius);font:14px var(--ds-font-sans);color:var(--ds-fg)}
```

```js
// Adapt: nodes (x,y,role), edges [from,to], and which ids are on the hot path.
var N={api:{x:16,y:16,r:'HTTP entry; validates + routes'},
  svc:{x:120,y:60,r:'Business logic; owns transactions'},
  db:{x:224,y:104,r:'Persistence; Postgres'}};
var E=[['api','svc'],['svc','db']],HOT=['api','svc','db'];
var svg=document.getElementById('mm'),out=document.getElementById('role'),NS='http://www.w3.org/2000/svg';
function el(n,a){var e=document.createElementNS(NS,n);for(var k in a)e.setAttribute(k,a[k]);return e;}
E.forEach(function(p){var a=N[p[0]],b=N[p[1]],hot=HOT.indexOf(p[0])>=0&&HOT.indexOf(p[1])>=0;
  svg.appendChild(el('line',{x1:a.x+44,y1:a.y+14,x2:b.x+44,y2:b.y+14,class:'edge'+(hot?' hot':'')}));});
Object.keys(N).forEach(function(id){var m=N[id],hot=HOT.indexOf(id)>=0;
  var r=el('rect',{x:m.x,y:m.y,width:88,height:28,rx:6,class:'mod'+(hot?' hot':'')});
  r.addEventListener('click',function(){out.innerHTML='<strong>'+id+'</strong> — '+m.r;
    parent.postMessage({type:'md2x:resize',height:document.documentElement.scrollHeight},'*');});
  svg.appendChild(r);var t=el('text',{x:m.x+44,y:m.y+18,'text-anchor':'middle'});t.textContent=id;svg.appendChild(t);});
parent.postMessage({type:'md2x:resize',height:document.documentElement.scrollHeight},'*');
```
