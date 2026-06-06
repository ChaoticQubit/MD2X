## Artifact: animation-sandbox

Duration and easing sliders that drive a live-previewed animation; the reader
tunes the motion and copies the resulting CSS. **Reach for it** when the source
describes a transition or animation — motion can't be written down, only felt.

**Editor — yes.** Implements the export contract: exports the chosen transition
as CSS. Set `export_label:"Copy CSS"`, `export_format:"text"`.

### Template

```html
<div class="ctl"><label>Duration <output id="vd">400</output>ms</label>
  <input id="dur" type="range" min="100" max="1500" step="50" value="400"></div>
<div class="ctl"><label>Easing</label>
  <select id="ease"><option>ease</option><option>ease-in-out</option>
    <option>cubic-bezier(.34,1.56,.64,1)</option><option>linear</option></select></div>
<div class="track"><div id="ball" class="ball"></div></div>
<button id="play" class="play">Play</button>
```

```css
.ctl{display:flex;align-items:center;gap:var(--ds-space-2);margin-bottom:var(--ds-space-1);font:13px var(--ds-font-sans);color:var(--ds-muted)}
.ctl label{flex:1}.ctl input,.ctl select{flex:1;accent-color:var(--ds-accent)}
.track{height:48px;background:var(--ds-card);border:1px solid var(--ds-border);border-radius:var(--ds-radius);
  position:relative;overflow:hidden;margin:var(--ds-space-2) 0}
.ball{position:absolute;top:12px;left:8px;width:24px;height:24px;border-radius:50%;background:var(--ds-accent)}
.play{font:600 13px var(--ds-font-sans);padding:var(--ds-space-1) var(--ds-space-3);cursor:pointer;
  background:var(--ds-bg);color:var(--ds-fg);border:1px solid var(--ds-border);border-radius:var(--ds-radius)}
```

```js
var dur=document.getElementById('dur'),ease=document.getElementById('ease'),
  vd=document.getElementById('vd'),ball=document.getElementById('ball'),on=false;
function css(){return 'transition: transform '+dur.value+'ms '+ease.value+';';}
function apply(){ball.style.transition='transform '+dur.value+'ms '+ease.value;vd.textContent=dur.value;}
function play(){on=!on;ball.style.transform=on?'translateX(calc(100% + 200px))':'translateX(0)';}
dur.addEventListener('input',apply);ease.addEventListener('change',apply);
document.getElementById('play').addEventListener('click',play);
window.addEventListener('message',function(e){if(e.data&&e.data.type==='md2x:request-export'){
  parent.postMessage({type:'md2x:export',format:e.data.format,payload:css()},'*');}});
apply();
parent.postMessage({type:'md2x:resize',height:document.documentElement.scrollHeight},'*');
```
