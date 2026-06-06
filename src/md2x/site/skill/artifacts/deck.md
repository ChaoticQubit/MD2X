## Artifact: deck

A self-contained slide deck: one idea per slide, navigated with arrow keys (and
on-screen buttons), with a slide counter. **Reach for it** for a talk-style
sequence where each beat deserves the full frame.

**Editor — no.** Navigation only, so no export contract needed.

### Template

```html
<div class="deck" tabindex="0">
  <div id="stage" class="stage"></div>
  <div class="nav"><button id="prev">‹</button>
    <span id="count" class="count"></span><button id="next">›</button></div>
</div>
```

```css
.deck{background:var(--ds-card);border:1px solid var(--ds-border);border-radius:var(--ds-radius);
  padding:var(--ds-space-3);outline:none}
.stage{min-height:120px;display:flex;flex-direction:column;justify-content:center}
.stage h2{margin:0 0 var(--ds-space-1);font:700 22px var(--ds-font-sans);color:var(--ds-fg)}
.stage p{margin:0;font:15px var(--ds-font-sans);color:var(--ds-muted)}
.nav{display:flex;align-items:center;justify-content:flex-end;gap:var(--ds-space-2);margin-top:var(--ds-space-2)}
.nav button{font:600 16px var(--ds-font-sans);width:32px;height:32px;cursor:pointer;
  background:var(--ds-bg);color:var(--ds-fg);border:1px solid var(--ds-border);border-radius:var(--ds-radius)}
.count{font:13px var(--ds-font-mono);color:var(--ds-muted)}
```

```js
// Adapt: one entry per slide.
var SLIDES=[{h:'The problem',p:'Markdown flattens what wants to be spatial.'},
  {h:'The shift',p:'Render information in the shape it has.'},
  {h:'The payoff',p:'Readers explore instead of skim.'}];
var i=0,stage=document.getElementById('stage'),count=document.getElementById('count'),deck=document.querySelector('.deck');
function show(){var s=SLIDES[i];stage.innerHTML='<h2>'+s.h+'</h2><p>'+s.p+'</p>';
  count.textContent=(i+1)+' / '+SLIDES.length;
  parent.postMessage({type:'md2x:resize',height:document.documentElement.scrollHeight},'*');}
function go(d){i=Math.max(0,Math.min(SLIDES.length-1,i+d));show();}
document.getElementById('next').addEventListener('click',function(){go(1);});
document.getElementById('prev').addEventListener('click',function(){go(-1);});
deck.addEventListener('keydown',function(e){if(e.key==='ArrowRight')go(1);if(e.key==='ArrowLeft')go(-1);});
deck.focus();show();
```
