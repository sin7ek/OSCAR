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
<section><h2>Language &amp; names</h2><label for="name-display">Show names</label><select id="name-display"><option value="original_and_english">Original + English (when available)</option><option value="original">Original only</option><option value="english">English preferred (original preserved)</option></select><label for="alias-fallback">When no English alias exists</label><select id="alias-fallback"><option value="original">Use original</option><option value="sort_name">Allow artist sort-name as transliteration (not a translation)</option></select><p>English aliases are fetched on demand from MusicBrainz. Original names and entity IDs are always retained. These settings do not tag audio files.</p></section>
<section><h2>Optical drives</h2><div id="drives"></div><button id="probe" type="button">Check inserted discs</button><p id="media-status" aria-live="polite"></p><div id="toc-results"></div></section>
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
 document.getElementById('name-display').value=settings.name_display||'original_and_english';
 document.getElementById('alias-fallback').value=settings.english_alias_fallback||'original';
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
   if(disc.status==='disc_present' && disc.disc_type==='audio'){
     const button=document.createElement('button');button.type='button';
     button.textContent='Read TOC and MusicBrainz ID';
     button.onclick=()=>showToc(disc.stable_id);
     el.append(button);
   }
  }
 }catch(error){el.textContent='Probe unavailable: '+error.message}
};
async function showToc(stableId){
 const target=document.getElementById('toc-results');target.replaceChildren();
 const status=document.createElement('p');status.textContent='Reading disc TOC…';target.append(status);
 try{
  const r=await fetch('/api/toc?'+new URLSearchParams({stable_id:stableId}));
  if(!r.ok)throw new Error(await r.text());
  const toc=await r.json();
  status.textContent='MusicBrainz Disc ID: '+toc.musicbrainz_disc_id+' · '+toc.tracks.length+' tracks · Lead-out '+toc.leadout_sector;
  const note=document.createElement('p');note.textContent='INDEX 00, pregaps and hidden track-one audio are not checked by a standard TOC.';target.append(note);
  const table=document.createElement('table');table.style.width='100%';
  for(const track of toc.tracks){
    const tr=document.createElement('tr');
    for(const value of [track.number,track.start_sector,track.duration_seconds+' s']){
      const cell=document.createElement('td');cell.textContent=String(value);cell.style.padding='5px';tr.append(cell);
    }table.append(tr);
  }
  target.append(table);
  const lookup=document.createElement('button');lookup.type='button';
  lookup.textContent='Find release candidates on MusicBrainz';
  lookup.onclick=()=>showCandidates(stableId);target.append(lookup);
 }catch(error){status.textContent='TOC unavailable: '+error.message}
}
async function showCandidates(stableId){
 const target=document.getElementById('toc-results');
 const p=document.createElement('p');p.textContent='Looking up MusicBrainz candidates…';target.append(p);
 try{
  const r=await fetch('/api/releases?'+new URLSearchParams({stable_id:stableId}));
  if(!r.ok)throw new Error(await r.text());
  const result=await r.json();
  p.textContent=result.releases.length+' candidate(s) found — physical edition requires review';
  for(const release of result.releases){
    const entry=document.createElement('p');
    const link=document.createElement('a');
    link.href='https://musicbrainz.org/release/'+encodeURIComponent(release.id);
    link.target='_blank';link.rel='noopener noreferrer';
    link.textContent=(release.title||'Untitled')+' · '+(release.artist||'Unknown')+' · '+(release.date||'?')+
      ' · '+release.labels.map(x=>(x.name||'')+' '+(x.catalog_number||'')).join(', ');
    entry.append(link);
    const inspect=document.createElement('button');inspect.type='button';
    inspect.style.marginLeft='10px';inspect.textContent='Inspect disc & tracklist';
    inspect.onclick=()=>showMedium(stableId,release.id);entry.append(inspect);
    target.append(entry);
  }
 }catch(error){p.textContent='MusicBrainz unavailable: '+error.message}
}
const aliasCache=new Map();
async function aliasFor(type,id){
 const key=type+':'+id;
 if(!aliasCache.has(key)){
  const req=fetch('/api/name-aliases?'+new URLSearchParams({entity_type:type,entity_id:id}))
   .then(async r=>{if(!r.ok)throw new Error(await r.text());return r.json()})
   .catch(e=>{aliasCache.delete(key);throw e});
  aliasCache.set(key,req);
 }
 return aliasCache.get(key);
}
function nameValue(original,alias){
 const mode=settings.name_display||'original_and_english';
 const fallback=settings.english_alias_fallback||'original';
 const extra=alias.english||(fallback==='sort_name'&&alias.sort_name!==original?alias.sort_name:null);
 if(!extra||extra===original||mode==='original')return original;
 if(mode==='english')return extra;
 return original+' ('+extra+')';
}
function aliasNode(type,id,original){
 const span=document.createElement('span');
 const value=document.createElement('span');value.textContent=original||'—';span.append(value);
 if(!id)return span;
 const button=document.createElement('button');button.type='button';
 button.style.margin='4px';button.style.padding='4px 8px';button.style.fontSize='12px';
 button.textContent='EN';button.title='English alias automatically enriched';
 button.className='alias-enrichment';button.dataset.aliasType=type;button.dataset.aliasId=id;
 button.applyAlias=(alias)=>{
   value.textContent=nameValue(original||alias.original,alias);
   const source=alias.english?alias.english_source:
      (settings.english_alias_fallback==='sort_name'&&alias.sort_name?'sort name':'no English alias');
   button.title=source+'; original: '+alias.original;
   button.textContent=alias.english?'EN ✓':'EN —';
   button.disabled=true;
 };
 button.onclick=async()=>{
  button.disabled=true;button.textContent='…';
  try{
   const alias=await aliasFor(type,id);
   button.applyAlias(alias);
  }catch(e){button.disabled=false;button.textContent='EN';button.title=e.message}
 };
 span.append(button);return span;
}
async function enrichNamesAutomatically(area){
 const buttons=[...area.querySelectorAll('button.alias-enrichment')];
 const keys=new Map();
 for(const button of buttons){
  const key=button.dataset.aliasType+':'+button.dataset.aliasId;
  if(!keys.has(key))keys.set(key,{
   entity_type:button.dataset.aliasType,entity_id:button.dataset.aliasId
  });
  button.textContent='EN …';button.disabled=true;
 }
 const entities=[...keys.values()];
 if(!entities.length)return;
 const message=document.createElement('p');
 message.textContent='Automatically enriching '+entities.length+' unique artist/work names…';
 area.prepend(message);
 let completed=0, failed=0, cacheHits=0;
 for(let i=0;i<entities.length;i+=8){
  if(!area.isConnected)return;
  const batch=entities.slice(i,i+8);
  try{
   const r=await fetch('/api/name-aliases/batch',{
     method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(batch)
   });
   if(!r.ok)throw new Error(await r.text());
   const data=await r.json();
   for(const item of data.entities||[]){
    completed++;
    if(item.error)failed++;
    else if(item.cache_status==='hit')cacheHits++;
    const matching=buttons.filter(b=>b.dataset.aliasType===item.entity_type
       &&b.dataset.aliasId.toLowerCase()===item.id);
    for(const b of matching){
      if(item.error){b.textContent='EN !';b.title=item.error;b.disabled=false}
      else b.applyAlias(item);
    }
   }
  }catch(error){
   failed+=batch.length;
   completed+=batch.length;
   for(const b of buttons){
    if(batch.some(e=>e.entity_type===b.dataset.aliasType&&e.entity_id===b.dataset.aliasId)){
      b.textContent='EN !';b.title='Retry: '+error.message;b.disabled=false;
    }
   }
  }
  message.textContent='English names processed: '+Math.min(i+8,entities.length)+' / '+entities.length;
 }
 message.textContent='English name enrichment finished · '+(completed-failed)+' successful, '+failed+' failed, '+cacheHits+' cache hits. Failed names can be retried.';
}
async function showMedium(stableId, releaseId){
 const target=document.getElementById('toc-results');
 let area=document.getElementById('medium-results');
 if(!area){area=document.createElement('section');area.id='medium-results';target.append(area)}
 area.replaceChildren();
 const status=document.createElement('p');status.textContent='Loading exact medium…';area.append(status);
 try{
  const r=await fetch('/api/release-medium?'+new URLSearchParams({stable_id:stableId,release_id:releaseId}));
  if(!r.ok)throw new Error(await r.text());
  const info=await r.json();
  status.textContent=info.release_title+' · '+info.total_media+' discs · '+info.status;
  const warning=document.createElement('p');
  warning.textContent='Composer and performers are taken from explicit MusicBrainz relationships, not from the general artist credit. Missing information is shown as undocumented. Physical edition still requires review; nothing is written.';
  area.append(warning);
  if(!info.matched_media.length){
    const p=document.createElement('p');p.textContent='No medium has this exact Disc ID attached to MusicBrainz.';
    area.append(p);return;
  }
  for(const medium of info.matched_media){
    const title=document.createElement('h3');
    title.textContent='Disc '+medium.position+' of '+info.total_media+
       (medium.title?' · '+medium.title:'')+' ('+medium.track_count+' tracks)';
    area.append(title);
    if(!medium.track_count_matches){
      const mismatch=document.createElement('p');
      mismatch.textContent='Track count differs from the inserted disc; manual review required.';
      area.append(mismatch);
    }
    const label=document.createElement('p');
    label.textContent='Work groups only where MusicBrainz explicitly links a movement to a parent work. Otherwise tracks remain separate.';
    area.append(label);
    const tracksByNumber=new Map(medium.tracks.map(t=>[String(t.number||t.position),t]));
    for(const group of (medium.work_groups||[])){
      if(group.parent_work_id){
        const heading=document.createElement('h4');
        heading.textContent=group.parent_work_title||'Untitled work';
        area.append(heading);
        const source=document.createElement('small');
        source.textContent='Verified MusicBrainz work relationship · '+group.tracks.length+' track(s)';
        area.append(source);
      }
      const table=document.createElement('table');table.style.width='100%';
      for(const number of group.tracks){
        const track=tracksByNumber.get(String(number));
        if(!track)continue;
        const tr=document.createElement('tr');
        const composer=track.composers?.map(x=>x.name).join(', ')||'—';
        const performers=track.performers?.map(x=>x.name+(x.role?' ('+x.role+')':'')).join(', ')||'Not documented';
        const cols=[
          track.number||track.position,
          track.title||'Untitled',
          null,null,
          performers
        ];
        for(let i=0;i<cols.length;i++){
          const td=document.createElement('td');
          td.style.padding='6px';td.style.borderBottom='1px solid #324253';
          td.style.verticalAlign='top';
          if(i===2){
            const works=track.work_details||[];
            if(!works.length)td.textContent='Work not linked';
            for(const work of works){
              td.append(aliasNode('work',work.id,work.title||work.id));
            }
          }else if(i===3){
            if(!track.composers?.length)td.textContent='—';
            for(const composer of track.composers||[]){
              if(td.childNodes.length)td.append(document.createTextNode(', '));
              td.append(aliasNode('artist',composer.artist_id,composer.name));
            }
          }else{td.textContent=String(cols[i]??'')}
          tr.append(td);
        }
        table.append(tr);
      }
      area.append(table);
    }
  }
  enrichNamesAutomatically(area);
 }catch(error){status.textContent='Could not retrieve medium: '+error.message}
}
document.getElementById('save').onclick=async()=>{
 const status=document.getElementById('status');settings.profile=document.getElementById('profile').value;
 settings.name_display=document.getElementById('name-display').value;
 settings.english_alias_fallback=document.getElementById('alias-fallback').value;
 status.textContent='Saving…';
 try{const r=await fetch('/api/settings',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(settings)});
 if(!r.ok)throw new Error(await r.text());status.textContent='Settings saved. No rip started.';}
 catch(e){status.textContent='Could not save: '+e.message}
};
init().catch(e=>document.getElementById('status').textContent=e.message);
</script></body></html>"""


def settings_page() -> HTMLResponse:
    return HTMLResponse(PAGE, headers={"Cache-Control": "no-store"})
