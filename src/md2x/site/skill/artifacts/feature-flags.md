## Artifact: feature-flags

A flag panel: toggle switches with dependency rules — turning one flag on can
require another (warn or auto-enable). **Reach for it** when the source describes
configuration, rollout flags, or settings with interdependencies.

**Editor — yes.** Implements the export contract: exports the chosen flag set as
JSON. Set `export_label:"Copy as JSON"`, `export_format:"json"`.

### Template

```html
<div id="flags" class="flags"></div>
```

```css
.flags{display:flex;flex-direction:column;gap:var(--ds-space-1)}
.row{display:flex;align-items:center;gap:var(--ds-space-2);padding:var(--ds-space-1) var(--ds-space-2);
  background:var(--ds-card);border:1px solid var(--ds-border);border-radius:var(--ds-radius)}
.row .meta{flex:1;min-width:0}.row .name{font:600 14px var(--ds-font-sans);color:var(--ds-fg)}
.row .warn{font:12px var(--ds-font-sans);color:var(--ds-accent);margin-top:2px;display:none}
.row.bad .warn{display:block}
.sw{width:38px;height:22px;border-radius:11px;border:1px solid var(--ds-border);background:var(--ds-bg);position:relative;cursor:pointer;flex:none}
.sw::after{content:"";position:absolute;top:2px;left:2px;width:16px;height:16px;border-radius:50%;background:var(--ds-muted);transition:.15s}
.sw[aria-checked=true]{background:var(--ds-accent);border-color:var(--ds-accent)}
.sw[aria-checked=true]::after{left:18px;background:#fff}
```

```js
// Adapt: flags + `needs` (id of a flag that must also be on).
var FLAGS=[{id:'beta_ui',name:'New UI',on:false},
  {id:'edge_cache',name:'Edge cache',on:false},
  {id:'fast_paint',name:'Fast paint',on:false,needs:'edge_cache'}];
var byId={};FLAGS.forEach(function(f){byId[f.id]=f;});
var root=document.getElementById('flags');
function build(){root.innerHTML='';FLAGS.forEach(function(f){
  var dep=f.needs?byId[f.needs]:null,bad=f.on&&dep&&!dep.on;
  var row=document.createElement('div');row.className='row'+(bad?' bad':'');
  row.innerHTML='<div class="meta"><div class="name">'+f.name+'</div>'+
    (dep?'<div class="warn">requires "'+dep.name+'"</div>':'')+'</div>';
  var sw=document.createElement('div');sw.className='sw';sw.tabIndex=0;sw.setAttribute('role','switch');
  sw.setAttribute('aria-checked',String(f.on));
  function tog(){f.on=!f.on;if(f.on&&dep)dep.on=true;build();}
  sw.addEventListener('click',tog);sw.addEventListener('keydown',function(e){if(e.key===' '||e.key==='Enter'){e.preventDefault();tog();}});
  row.appendChild(sw);root.appendChild(row);});
  parent.postMessage({type:'md2x:resize',height:document.documentElement.scrollHeight},'*');}
function exportJson(){var o={};FLAGS.forEach(function(f){o[f.id]=f.on;});return JSON.stringify(o,null,2);}
window.addEventListener('message',function(e){if(e.data&&e.data.type==='md2x:request-export'){
  parent.postMessage({type:'md2x:export',format:e.data.format,payload:exportJson()},'*');}});
build();
```
