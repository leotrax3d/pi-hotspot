'use strict';
const $=s=>document.querySelector(s), reduce=matchMedia('(prefers-reduced-motion: reduce)').matches;
const ease='cubic-bezier(.23,1,.32,1)', sleep=ms=>new Promise(r=>setTimeout(r,ms));
const enter=el=>el.animate(reduce?[{opacity:0},{opacity:1}]:[{opacity:0,transform:'translateY(20px) scale(.98)'},{opacity:1,transform:'translateY(0) scale(1)'}],{duration:reduce?100:280,easing:ease});
const exit=el=>el.animate(reduce?[{opacity:1},{opacity:0}]:[{opacity:1,transform:'translateY(0)'},{opacity:0,transform:'translateY(-16px)'}],{duration:reduce?80:180,easing:ease}).finished;
let busy=false,codeMode=false;
function features(c){const f=c.features||{};for(const a of document.querySelectorAll('#community-actions a'))a.hidden=a.href.includes('view=chat')?f.chat===false:f.singleplayer===false&&f.multiplayer===false;}
enter($('main'));
async function access(){await exit($('#rules'));$('#rules').hidden=true;$('#access-form').hidden=false;$('.flow-track').setAttribute('aria-label','Schritt 2 von 2');$('.flow-track span:last-child').classList.add('active');enter($('#access-form'));(codeMode?$('input[name=code]'):$('#accept')).focus()}
function showCode(enabled){codeMode=enabled;$('#codelabel').hidden=!enabled;$('#redeem').hidden=!enabled;$('#accept').hidden=enabled;$('#code-choice').textContent=enabled?'Ohne Zugangscode verbinden':'Mit Zugangscode verbinden';if(enabled){enter($('#codelabel'));$('input[name=code]').focus()}}
fetch('/api/portal').then(r=>{if(!r.ok)throw Error();return r.json()}).then(c=>{
 features(c);
 for(const k of ['title','description','terms'])$('#'+k).textContent=c[k];
 $('#accepttext').textContent=c.accept_text;showCode(c.portal_mode==='code');$('#code-choice').hidden=c.portal_mode!=='both';
 $('#code-choice').onclick=()=>{if(!codeMode&&location.protocol!=='https:'){location.assign('https://'+location.host+'/?code=1');return}showCode(!codeMode)};
 if(c.session?.active){const s=c.session;$('#status').hidden=false;$('#status').textContent=`Verbunden\n${s.remaining_seconds===null?'Zeit unbegrenzt':Math.ceil(s.remaining_seconds/60)+' Minuten verbleibend'}\n${(s.used/1024**2).toFixed(1)} MB genutzt`;$('#rules').hidden=true;$('#access-form').hidden=true;$('.flow-track').hidden=true;$('#title').textContent='Verbunden';$('#connection-scene').hidden=false;$('.connection-art').hidden=true;$('#connection-title').textContent='Was möchtest du machen?';$('#connection-detail').textContent='Chatte mit anderen Geräten oder starte ein Spiel.';$('#community-actions').hidden=false;}
 else{$('#access-form').hidden=true;$('#rules-next').hidden=false;$('#rules-next').onclick=()=>{$('#rules-next').disabled=true;access()};if(c.session)$('#error').textContent=c.session.reason;if(new URLSearchParams(location.search).has('code')&&c.portal_mode!=='accept'){showCode(true);access()}}
}).catch(()=>$('#error').textContent='Portal derzeit nicht erreichbar. Bitte die Seite neu laden.');
$('#accept').onclick=()=>{$('input[name=code]').value=''};
$('#access-form').addEventListener('submit',async e=>{
 e.preventDefault();if(busy)return;
 if(codeMode&&!$('input[name=code]').value.trim()){$('#error').textContent='Bitte einen Zugangscode eingeben.';$('input[name=code]').focus();return}
 busy=true;$('#error').textContent='';const data=new FormData(e.currentTarget),start=performance.now();
 // Start the real request immediately, independently of the presentation.
 const request=fetch('/portal/activate',{method:'POST',body:data,credentials:'same-origin',signal:AbortSignal.timeout(20000)}).then(async r=>{if(!r.ok){const doc=new DOMParser().parseFromString(await r.text(),'text/html');throw Error(doc.querySelector('p')?.textContent||'Verbindung fehlgeschlagen. Bitte erneut versuchen.')}const status=await fetch('/api/portal',{cache:'no-store'}).then(r=>r.json());if(!status.session?.active)throw Error('Zugang noch nicht aktiv. Bitte erneut versuchen.');return status}).then(value=>({value}),error=>({error}));
 await exit($('#access-form'));$('#access-form').hidden=true;$('#title').hidden=true;$('#description').hidden=true;$('.flow-track').hidden=true;$('footer').hidden=true;
 const scene=$('#connection-scene');scene.hidden=false;scene.focus();enter(scene);
 const arrow=$('.flight-arrow');
 if(!reduce)await arrow.animate([{transform:'translateX(-90px) scale(.85)',opacity:0},{transform:'translateX(0) scale(1)',opacity:1,offset:.4},{transform:'translateX(150px) scale(1)',opacity:0}],{duration:850,easing:'cubic-bezier(.77,0,.175,1)',fill:'forwards'}).finished;
 arrow.hidden=true;$('.connection-spinner').hidden=false;$('#connection-title').textContent='Verbinden';
 const result=await request;
 await sleep(Math.max(0,(reduce?0:2500)-(performance.now()-start)));
 $('.connection-spinner').hidden=true;
 if(result.error){$('#connection-title').textContent='Noch nicht verbunden';$('#connection-detail').textContent=result.error.name==='TimeoutError'?'Zeitüberschreitung. Bitte erneut versuchen.':result.error.message;$('#connection-back').hidden=false;$('#connection-back').focus()}
 else{$('.connection-check').hidden=false;enter($('.connection-check'));$('#connection-title').textContent='Verbunden';$('#connection-detail').textContent='Du kannst jetzt surfen, chatten oder spielen.';$('#community-actions').hidden=false;$('footer').hidden=false;enter($('#connection-title'));enter($('#community-actions'));}
 busy=false;
});
$('#connection-back').onclick=()=>{location.assign('/')};
addEventListener('pageshow',e=>{if(e.persisted)location.reload()});
