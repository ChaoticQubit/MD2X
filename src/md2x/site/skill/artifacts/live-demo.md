## Artifact: live-demo

A tiny interactive demo: sliders/inputs that re-render an output live (a config
driving a preview). **Reach for it** when the source explains behavior that is
better *felt* than described — a setting whose effect you can show.

**Editor-ish — yes.** Implements the export contract so the reader can take the
config they dialed in. Set `export_label:"Copy config"`, `export_format:"json"`.

### Template

```html
<div class="ctl"><label>Radius <output id="vr">10</output></label>
  <input id="r" type="range" min="0" max="40" value="10"></div>
<div class="ctl"><label>Pad <output id="vp">12</output></label>
  <input id="p" type="range" min="0" max="32" value="12"></div>
<div id="preview" class="preview">Live preview</div>
```

```css
.ctl{display:flex;align-items:center;gap:var(--ds-space-2);margin-bottom:var(--ds-space-1);font:13px var(--ds-font-sans);color:var(--ds-fg)}
.ctl label{flex:1;display:flex;justify-content:space-between;color:var(--ds-muted)}
.ctl input{flex:1;accent-color:var(--ds-accent)}
.preview{margin-top:var(--ds-space-2);background:var(--ds-accent);color:#fff;
  font:600 15px var(--ds-font-sans);display:flex;align-items:center;justify-content:center;min-height:64px}
```

```js
var cfg={radius:10,pad:12},prev=document.getElementById('preview');
function bind(id,vid,key){var s=document.getElementById(id),o=document.getElementById(vid);
  s.addEventListener('input',function(){cfg[key]=+s.value;o.textContent=s.value;paint();});}
function paint(){prev.style.borderRadius=cfg.radius+'px';prev.style.padding=cfg.pad+'px';
  prev.style.background='var(--ds-accent)';
  parent.postMessage({type:'md2x:resize',height:document.documentElement.scrollHeight},'*');}
bind('r','vr','radius');bind('p','vp','pad');
window.addEventListener('message',function(e){if(e.data&&e.data.type==='md2x:request-export'){
  parent.postMessage({type:'md2x:export',format:e.data.format,payload:JSON.stringify(cfg,null,2)},'*');}});
paint();
```
