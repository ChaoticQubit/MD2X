## Artifact: comparison

N options side by side with a criteria grid and a toggle to highlight the column
that wins on the selected criterion. **Reach for it** when the source weighs
approaches, plans, or designs against shared criteria.

**Editor — no.** Read-only comparison, so no export contract needed.

### Template

```html
<div class="crit" id="crit"></div>
<table class="cmp"><thead id="head"></thead><tbody id="body"></tbody></table>
```

```css
.crit{display:flex;gap:var(--ds-space-1);flex-wrap:wrap;margin-bottom:var(--ds-space-2)}
.crit button{font:12px var(--ds-font-sans);padding:4px 10px;cursor:pointer;color:var(--ds-fg);
  background:var(--ds-bg);border:1px solid var(--ds-border);border-radius:var(--ds-radius)}
.crit button.on{background:var(--ds-accent);color:#fff;border-color:var(--ds-accent)}
.cmp{width:100%;border-collapse:collapse;font:13px var(--ds-font-sans)}
.cmp th,.cmp td{padding:var(--ds-space-1) var(--ds-space-2);border:1px solid var(--ds-border);text-align:left;color:var(--ds-fg)}
.cmp th{background:var(--ds-card);color:var(--ds-muted);font-weight:600}
.cmp col.win,.cmp td.win{background:color-mix(in srgb,var(--ds-accent) 14%,transparent)}
```

```js
// Adapt: options, criteria, and a score per (criterion, option); higher wins.
var OPTS=['Monolith','Modular','Microservices'];
var CRIT=['Speed to ship','Scale ceiling','Ops cost'];
var SCORE={'Speed to ship':[3,2,1],'Scale ceiling':[1,2,3],'Ops cost':[3,2,1]};
var CELL={'Speed to ship':['Fast','Medium','Slow'],'Scale ceiling':['Low','Medium','High'],'Ops cost':['Low','Medium','High']};
var crit=document.getElementById('crit'),head=document.getElementById('head'),body=document.getElementById('body'),sel=CRIT[0];
function winner(c){var s=SCORE[c],best=0;s.forEach(function(v,i){if(v>s[best])best=i;});return best;}
function render(){
  crit.innerHTML='';CRIT.forEach(function(c){var b=document.createElement('button');b.textContent=c;
    if(c===sel)b.className='on';b.addEventListener('click',function(){sel=c;render();});crit.appendChild(b);});
  var w=winner(sel);
  head.innerHTML='<tr><th>Criterion</th>'+OPTS.map(function(o,i){return '<th'+(i===w?' class="win"':'')+'>'+o+'</th>';}).join('')+'</tr>';
  body.innerHTML=CRIT.map(function(c){var win=winner(c);
    return '<tr><th>'+c+'</th>'+OPTS.map(function(_,i){
      return '<td'+(c===sel&&i===w?' class="win"':'')+'>'+CELL[c][i]+(i===win?' ★':'')+'</td>';}).join('')+'</tr>';}).join('');
  parent.postMessage({type:'md2x:resize',height:document.documentElement.scrollHeight},'*');}
render();
```
