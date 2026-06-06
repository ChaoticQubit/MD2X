## Artifact: prompt-tuner

A prompt-template editor: a template with `{{named}}` slots plus one input per
slot; the interpolated result re-renders live as the reader types. **Reach for
it** when the source documents a prompt, message template, or any fill-in-the-
blanks text the reader will want to copy and reuse.

**Editor — yes.** Implements the export contract: exports the final interpolated
prompt. Set `export_label:"Copy prompt"`, `export_format:"text"`.

### Template

```html
<label class="lbl">Template</label>
<textarea id="tpl" rows="4" class="fld">You are a {{role}}. Summarize {{topic}} for a {{audience}} in {{n}} bullets.</textarea>
<div id="inputs" class="grid"></div>
<label class="lbl">Result</label>
<pre id="out" class="out"></pre>
```

```css
.lbl{display:block;font:600 12px var(--ds-font-sans);color:var(--ds-muted);margin:var(--ds-space-2) 0 4px}
.fld,.inp{width:100%;box-sizing:border-box;font:14px var(--ds-font-mono);padding:var(--ds-space-1) var(--ds-space-2);
  background:var(--ds-bg);color:var(--ds-fg);border:1px solid var(--ds-border);border-radius:var(--ds-radius)}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:var(--ds-space-2)}
.out{white-space:pre-wrap;background:var(--ds-card);border:1px solid var(--ds-border);
  border-radius:var(--ds-radius);padding:var(--ds-space-2);font:14px var(--ds-font-mono);color:var(--ds-fg)}
```

```js
var tpl=document.getElementById('tpl'),box=document.getElementById('inputs'),out=document.getElementById('out');
var vals={role:'staff engineer',topic:'the incident',audience:'exec',n:'3'};
function slots(){var s=new Set(),m,re=/\{\{\s*(\w+)\s*\}\}/g;while(m=re.exec(tpl.value))s.add(m[1]);return[...s];}
function fill(){return tpl.value.replace(/\{\{\s*(\w+)\s*\}\}/g,function(_,k){return vals[k]!=null?vals[k]:'{{'+k+'}}';});}
function render(){box.innerHTML='';slots().forEach(function(k){
  var w=document.createElement('label');w.className='lbl';w.textContent=k;
  var i=document.createElement('input');i.className='inp';i.value=vals[k]||'';
  i.addEventListener('input',function(){vals[k]=i.value;out.textContent=fill();});
  box.appendChild(w);box.appendChild(i);});out.textContent=fill();
  parent.postMessage({type:'md2x:resize',height:document.documentElement.scrollHeight},'*');}
tpl.addEventListener('input',render);
window.addEventListener('message',function(e){if(e.data&&e.data.type==='md2x:request-export'){
  parent.postMessage({type:'md2x:export',format:e.data.format,payload:fill()},'*');}});
render();
```
