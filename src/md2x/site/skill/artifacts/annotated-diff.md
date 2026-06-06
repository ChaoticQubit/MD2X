## Artifact: annotated-diff

A code diff with margin notes: severity-tagged findings attached to specific
lines, plus jump links that scroll between findings. **Reach for it** in a code
review or changelog when specific hunks need inline commentary.

**Editor — no.** Read-only commentary, so no export contract needed.

### Template

```html
<nav id="jump" class="jump"></nav>
<div id="diff" class="diff"></div>
```

```css
.jump{display:flex;gap:var(--ds-space-1);flex-wrap:wrap;margin-bottom:var(--ds-space-2)}
.jump a{font:12px var(--ds-font-sans);color:var(--ds-fg);text-decoration:none;padding:2px 8px;
  border:1px solid var(--ds-border);border-radius:var(--ds-radius);cursor:pointer}
.diff{font:13px/1.6 var(--ds-font-mono);background:var(--ds-card);border:1px solid var(--ds-border);
  border-radius:var(--ds-radius);overflow:hidden}
.ln{display:flex;gap:var(--ds-space-2);padding:0 var(--ds-space-2);white-space:pre}
.ln.add{background:color-mix(in srgb,var(--ds-accent) 12%,transparent)}
.ln.del{background:color-mix(in srgb,var(--ds-muted) 18%,transparent)}
.note{padding:var(--ds-space-1) var(--ds-space-2);font:12px var(--ds-font-sans);color:var(--ds-fg);
  border-left:3px solid var(--ds-accent);background:var(--ds-bg)}
.tag{font:600 10px var(--ds-font-sans);text-transform:uppercase;color:var(--ds-accent);margin-right:6px}
```

```js
// Adapt: rows are {sign:' '|'+'|'-', text} and notes are {after:lineIndex, sev, body}.
var ROWS=[{sign:' ',text:'function pay(amount){'},{sign:'-',text:'  return charge(amount)'},
  {sign:'+',text:'  if(amount<=0) throw Error("bad")'},{sign:'+',text:'  return charge(amount)'},{sign:' ',text:'}'}];
var NOTES=[{after:2,sev:'high',body:'Validate before side effects — good catch.'},
  {after:3,sev:'nit',body:'Consider a typed currency, not a raw number.'}];
var diff=document.getElementById('diff'),jump=document.getElementById('jump'),k=0;
ROWS.forEach(function(r,i){var d=document.createElement('div');
  d.className='ln'+(r.sign==='+'?' add':r.sign==='-'?' del':'');d.textContent=r.sign+' '+r.text;diff.appendChild(d);
  NOTES.filter(function(n){return n.after===i;}).forEach(function(n){var id='f'+(k++);
    var nd=document.createElement('div');nd.className='note';nd.id=id;
    nd.innerHTML='<span class="tag">'+n.sev+'</span>'+n.body;diff.appendChild(nd);
    var a=document.createElement('a');a.textContent=n.sev+' @'+(i+1);
    a.addEventListener('click',function(){document.getElementById(id).scrollIntoView({block:'center'});});jump.appendChild(a);});});
parent.postMessage({type:'md2x:resize',height:document.documentElement.scrollHeight},'*');
```
