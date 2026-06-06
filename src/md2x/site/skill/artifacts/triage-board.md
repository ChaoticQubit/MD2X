## Artifact: triage-board

A Kanban board: tickets in columns (e.g. Backlog / In progress / Done) that the
reader drags between columns. **Reach for it** when the source is a task list,
bug triage, or anything with items moving through states.

**Editor — yes.** Implements the export contract: serializes the live board to a
Markdown checklist grouped by column. Set `export_label:"Copy as Markdown"`,
`export_format:"markdown"`.

### Template

```html
<div id="board" class="board"></div>
```

```css
.board{display:flex;gap:var(--ds-space-2);align-items:flex-start}
.col{flex:1;min-width:0;background:var(--ds-card);border:1px solid var(--ds-border);
  border-radius:var(--ds-radius);padding:var(--ds-space-2)}
.col h3{margin:0 0 var(--ds-space-2);font:600 13px/1.2 var(--ds-font-sans);color:var(--ds-muted)}
.tk{background:var(--ds-bg);border:1px solid var(--ds-border);border-radius:var(--ds-radius);
  padding:var(--ds-space-1) var(--ds-space-2);margin-bottom:var(--ds-space-1);cursor:grab;font:14px var(--ds-font-sans)}
.tk:focus-visible,.tk.drag{outline:2px solid var(--ds-accent);outline-offset:1px}
.col.over{border-color:var(--ds-accent)}
```

```js
// Adapt: columns + their starting tickets.
var DATA={Backlog:["Audit auth flow","Write migration"],"In progress":["Cache layer"],Done:["Spec review"]};
var root=document.getElementById('board');
function build(){root.innerHTML='';Object.keys(DATA).forEach(function(name){
  var col=document.createElement('div');col.className='col';col.dataset.col=name;
  col.innerHTML='<h3>'+name+'</h3>';
  DATA[name].forEach(function(t){
    var c=document.createElement('div');c.className='tk';c.draggable=true;c.textContent=t;
    c.addEventListener('dragstart',function(e){c.classList.add('drag');e.dataTransfer.setData('text',name+'|::|'+t);});
    c.addEventListener('dragend',function(){c.classList.remove('drag');});
    col.appendChild(c);});
  col.addEventListener('dragover',function(e){e.preventDefault();col.classList.add('over');});
  col.addEventListener('dragleave',function(){col.classList.remove('over');});
  col.addEventListener('drop',function(e){e.preventDefault();col.classList.remove('over');
    var p=e.dataTransfer.getData('text').split('|::|'),from=p[0],txt=p[1];
    DATA[from]=DATA[from].filter(function(x){return x!==txt;});DATA[name].push(txt);build();});
  root.appendChild(col);});}
function exportMd(){return Object.keys(DATA).map(function(n){
  return '## '+n+'\n'+(DATA[n].length?DATA[n].map(function(t){return '- [ ] '+t;}).join('\n'):'_empty_');}).join('\n\n');}
window.addEventListener('message',function(e){if(e.data&&e.data.type==='md2x:request-export'){
  parent.postMessage({type:'md2x:export',format:e.data.format,payload:exportMd()},'*');}});
build();
parent.postMessage({type:'md2x:resize',height:document.documentElement.scrollHeight},'*');
```
