"""Minimal built-in settings UI; served without external CD/DVD privileges."""
from fastapi.responses import HTMLResponse

PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>OSCAR · Settings</title><style>
:root{color-scheme:dark}body{font-family:system-ui,-apple-system,sans-serif;background:#10151d;color:#eef2f6;max-width:900px;margin:32px auto;padding:0 18px}
h1{letter-spacing:.14em}p,small{color:#a9b6c4}section{background:#19222e;border:1px solid #324253;border-radius:14px;padding:20px;margin:16px 0}
.drive{border-top:1px solid #324253;padding:16px 0;display:grid;gap:8px}
label{display:block;margin:8px 0}input,select{background:#0c131b;color:white;border:1px solid #516376;border-radius:8px;padding:9px;font:inherit}
input[type=number]{width:120px}button{background:#bfd5ff;color:#091b35;border:0;border-radius:9px;padding:11px 18px;cursor:pointer;font-weight:700}
.note{padding:12px;background:#283342;border-radius:9px}#status{min-height:1.5em}
</style></head><body>
<h1>OSCAR</h1><p>Open Source CD Archiving &amp; Ripping · Device settings</p>
<div class="note">Configuration preview: no ripping, archiving or automatic deletion is implemented. Keep this UI on localhost or behind authentication.</div>
<section><h2>Ripping profile</h2>
<label for="profile">Default profile</label><select id="profile"><option value="archival">Archival / collectors</option><option value="classical">Classical / works &amp; performers</option></select>
<p>Profile selection is stored for future processing. Neither profile starts a rip.</p></section>
<section><h2>Optical drives</h2><div id="drives"></div><button id="probe" type="button">Check inserted discs</button><p id="media-status" aria-live="polite"></p></section>
<button id="save">Save settings</button><p id="status" aria-live="polite"></p>
<script>
let settings;
const area=document.getElementById('drives');
function safeText(node,value){node.textContent=value;}
async function init(){
 const [a,b]=await Promise.all([fetch('/api/settings'),fetch('/api/drives')]);
 if(!a.ok||!b.ok)throw new Error('Unable to load configuration');
 settings=await a.json();const live=await b.json();
 document.getElementById('profile').value=settings.profile;
 area.replaceChildren();
 for(const drive of settings.drives){
  const row=document.createElement('div');row.className='drive';
  const head=document.createElement('strong');safeText(head,drive.label);
  const device=document.createElement('small');
  const match=live.find(x=>x.stable_id===drive.stable_id);
  safeText(device,drive.stable_id+(match?(match.present?' · detected: ':' · missing: ')+match.device:' · not currently detected'));
  const label=document.createElement('label');const check=document.createElement('input');
  check.type='checkbox';check.checked=drive.enabled;check.onchange=()=>drive.enabled=check.checked;
  label.append(check,document.createTextNode(' Enable drive'));
  const offsetLabel=document.createElement('label');safeText(offsetLabel,' Read offset (samples; blank = unknown) ');
  const offset=document.createElement('input');offset.type='number';offset.min=-2000;offset.max=2000;
  offset.value=drive.offset_samples===null?'':drive.offset_samples;
  offset.oninput=()=>{drive.offset_samples=offset.value===''?null:Number(offset.value)};
  offsetLabel.append(offset);row.append(head,device,label,offsetLabel);area.append(row);
 }
}
document.getElementById('probe').onclick=async()=>{
 const el=document.getElementById('media-status');el.textContent='Checking drives…';
 try{
  const response=await fetch('/api/media');
  if(!response.ok)throw new Error(await response.text());
  const results=await response.json();
  el.replaceChildren();
  if(!results.length){el.textContent='No enabled drives detected. Enable and save a drive first.';return}
  for(const disc of results){
   const p=document.createElement('p');
   p.textContent=disc.label+' ('+disc.device+'): '+disc.status+
      (disc.disc_type?' · '+disc.disc_type:'')+(disc.error?' · '+disc.error:'');
   el.append(p);
  }
 }catch(error){el.textContent='Probe unavailable: '+error.message}
};
document.getElementById('save').onclick=async()=>{
 const status=document.getElementById('status');settings.profile=document.getElementById('profile').value;
 status.textContent='Saving…';
 try{const r=await fetch('/api/settings',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(settings)});
 if(!r.ok)throw new Error(await r.text());status.textContent='Settings saved. No rip started.';}
 catch(e){status.textContent='Could not save: '+e.message}
};
init().catch(e=>document.getElementById('status').textContent=e.message);
</script></body></html>"""


def settings_page() -> HTMLResponse:
    return HTMLResponse(PAGE, headers={"Cache-Control": "no-store"})
