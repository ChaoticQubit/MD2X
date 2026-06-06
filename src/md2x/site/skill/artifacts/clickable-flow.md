## Artifact: clickable-flow

A multi-screen clickable flow (screen 1 → 2 → 3) with next/back and a progress
dot row. **Reach for it** for a "how it works" or sign-up/onboarding walkthrough
the reader should step through screen by screen.

**Editor — no.** Navigation only, so no export contract needed.

### Template

```html
<div class="flow">
  <div id="screen" class="screen"></div>
  <div class="bar"><button id="back">Back</button>
    <span id="dots" class="dots"></span><button id="fwd">Next</button></div>
</div>
```

```css
.flow{background:var(--ds-card);border:1px solid var(--ds-border);border-radius:var(--ds-radius);padding:var(--ds-space-3)}
.screen{min-height:96px}
.screen h3{margin:0 0 var(--ds-space-1);font:700 18px var(--ds-font-sans);color:var(--ds-fg)}
.screen p{margin:0;font:14px var(--ds-font-sans);color:var(--ds-muted)}
.bar{display:flex;align-items:center;justify-content:space-between;margin-top:var(--ds-space-2)}
.bar button{font:600 13px var(--ds-font-sans);padding:6px 14px;cursor:pointer;
  background:var(--ds-bg);color:var(--ds-fg);border:1px solid var(--ds-border);border-radius:var(--ds-radius)}
.bar button:disabled{opacity:.4;cursor:default}
.dots{display:flex;gap:6px}.dot{width:8px;height:8px;border-radius:50%;background:var(--ds-border)}
.dot.on{background:var(--ds-accent)}
```

```js
// Adapt: one screen per step.
var SCREENS=[{h:'1 · Connect',p:'Point md2x at a Markdown file.'},
  {h:'2 · Shape',p:'It picks the artifact each section wants.'},
  {h:'3 · Ship',p:'A self-contained site falls out the other side.'}];
var i=0,screen=document.getElementById('screen'),dots=document.getElementById('dots'),
  back=document.getElementById('back'),fwd=document.getElementById('fwd');
function show(){var s=SCREENS[i];screen.innerHTML='<h3>'+s.h+'</h3><p>'+s.p+'</p>';
  dots.innerHTML=SCREENS.map(function(_,j){return '<span class="dot'+(j===i?' on':'')+'"></span>';}).join('');
  back.disabled=i===0;fwd.disabled=i===SCREENS.length-1;
  parent.postMessage({type:'md2x:resize',height:document.documentElement.scrollHeight},'*');}
fwd.addEventListener('click',function(){if(i<SCREENS.length-1){i++;show();}});
back.addEventListener('click',function(){if(i>0){i--;show();}});
show();
```
