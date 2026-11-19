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
<div class="note">Configuration preview. Experimental ripping requires explicit opt-in and writes only to staging; archiving and automatic deletion are not implemented. Keep this UI on localhost or behind authentication.</div>
<section><h2>Ripping profile</h2>
<label for="profile">Default profile</label><select id="profile"><option value="archival">Archival / collectors</option><option value="classical">Classical / works &amp; performers</option></select>
<p>Profile selection is stored for future processing. Neither profile starts a rip.</p></section>
<section><h2>Language &amp; names</h2><label for="name-display">Show names</label><select id="name-display"><option value="original_and_english">Original + English (when available)</option><option value="original">Original only</option><option value="english">English preferred (original preserved)</option></select><label for="alias-fallback">When no English alias exists</label><select id="alias-fallback"><option value="original">Use original</option><option value="sort_name">Allow artist sort-name as transliteration (not a translation)</option></select><p>English aliases are fetched on demand from MusicBrainz. Original names and entity IDs are always retained. These settings do not tag audio files.</p></section>
<section><h2>Optical drives</h2><div id="drives"></div><button id="probe" type="button">Check inserted discs</button><p id="media-status" aria-live="polite"></p><div id="toc-results"></div></section>
<section><h2>Staging verification (experimental)</h2>
<p>Review an already completed OSCAR rip. Reads cyanrip AccurateRip evidence, checks saved SHA-256, decodes each FLAC and validates CUE references. No tagging, archiving or cleanup.</p>
<label for="verify-job">Staging rip job ID (32 hexadecimal characters)</label>
<input id="verify-job" placeholder="f41806152a614b1a9006b10456b9bbd4" maxlength="32" style="width:340px;max-width:90%">
<button id="verify-start" type="button">Verify staged rip</button>
<div id="verify-output" aria-live="polite"></div></section>
<section><h2>Metadata &amp; tagging (experimental)</h2>
<p>Only for a previously verified staging rip. Preview an explicitly selected MusicBrainz physical release, including its classical work/performer relationships. Review label/catalog details before copying. Original FLACs are never modified.</p>
<label for="metadata-job">Verified staging job ID</label>
<input id="metadata-job" maxlength="32" placeholder="Paste 32-character rip job ID" style="width:340px;max-width:90%">
<label for="metadata-release">MusicBrainz release UUID (exact physical edition, not release group)</label>
<input id="metadata-release" maxlength="36" placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx" style="width:360px;max-width:90%">
<button type="button" id="metadata-preview-btn">Preview MusicBrainz tags</button>
<div id="metadata-output" aria-live="polite"></div></section>
<section><h2>Inspect saved FLAC metadata</h2>
<p>Read the actual tags from the new copies, compare with the saved MusicBrainz preview, and verify the tagged file hashes. No files are modified.</p>
<label for="inspect-job">Rip job ID</label>
<input id="inspect-job" maxlength="32" placeholder="32-character rip job ID" style="width:340px;max-width:90%">
<label for="inspect-copy">Tagged copy ID</label>
<input id="inspect-copy" maxlength="32" placeholder="32-character tagged copy ID" style="width:340px;max-width:90%">
<button type="button" id="inspect-start">Inspect saved tags</button>
<div id="inspect-result" aria-live="polite"></div></section>
<section><h2>Classical metadata v2 — review</h2>
<p>Separate the physical CD's suite/section order from MusicBrainz's canonical work relationships. This creates only a NEW tagged staging copy, leaving both earlier copies and the rip untouched.</p>
<label for="v2-job">Rip job ID</label><input id="v2-job" maxlength="32" style="width:340px;max-width:90%">
<label for="v2-source">Completed tagged-copy ID</label><input id="v2-source" maxlength="32" style="width:340px;max-width:90%">
<label for="v2-sections">Reviewed physical-CD sections (one per line: start-end | section title)</label>
<textarea id="v2-sections" rows="4" style="width:95%;background:#0c131b;color:white;border:1px solid #516376;border-radius:8px;padding:9px">1-12 | Water Music — Suite I (as issued)
13-22 | Water Music — Suite II (as issued)
23-28 | Music for the Royal Fireworks</textarea>
<p>This is a suggested layout for the first Händel CD; check the physical booklet before approving. Nothing is inferred from the HWV number.</p>
<label for="v2-movements">Optional manually reviewed movement labels (one per line: track number | movement text; leave blank to preserve unknown)</label>
<textarea id="v2-movements" rows="2" style="width:95%;background:#0c131b;color:white;border:1px solid #516376;border-radius:8px;padding:9px"></textarea>
<button id="v2-preview" type="button">Preview classical v2 tags</button>
<div id="v2-output" aria-live="polite"></div></section>
<button id="save">Save settings</button><p id="status" aria-live="polite"></p>
<script>
let settings;
let trustedLocalUI=false;
fetch('/api/ui/access').then(r=>r.ok?r.json():{}).then(data=>{
 trustedLocalUI=!!data.trusted_local_ui;
}).catch(()=>{trustedLocalUI=false});
function requestAuthHeaders(description){
 if(trustedLocalUI)return {'X-OSCAR-UI-ACTION':'confirmed'};
 const token=window.prompt(description+' (OSCAR rip token)');
 return token?{'X-OSCAR-RIP-TOKEN':token}:null;
}
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
  offsetLabel.append(offset);row.append(head,device,label,offsetLabel);
  const assist=document.createElement('div');
  const link=document.createElement('a');link.href='https://www.accuraterip.com/driveoffsets.htm';
  link.target='_blank';link.rel='noopener noreferrer';link.textContent='AccurateRip drive offset database';
  link.style.color='#bfd5ff';
  const hint=document.createElement('small');hint.style.display='block';
  hint.textContent=drive.offset_samples===null?'Offset not yet set.':'Saved offset: '+drive.offset_samples+' samples (never automatically overwritten).';
  const lookup=document.createElement('button');lookup.type='button';
  lookup.style.marginRight='8px';lookup.textContent='Look up offset';
  lookup.onclick=async()=>{
   hint.textContent='Checking AccurateRip drive-offset database…';
   try{
    const r=await fetch('/api/drive-offset/lookup?'+new URLSearchParams({stable_id:drive.stable_id}));
    if(!r.ok)throw new Error(await r.text());
    const data=await r.json();
    if(data.suggested_offset!==null){
     hint.textContent='Database suggests '+data.suggested_offset+' samples. Review before saving.';
     if(drive.offset_samples===null){
       offset.value=String(data.suggested_offset);
       drive.offset_samples=data.suggested_offset;
       hint.textContent+=' Suggested value filled in; click Save settings to persist.';
     }
    }else{
     hint.textContent=data.status==='conflict'?'Conflicting reported offsets for this model: '+
      [...new Set(data.matches.map(x=>x.offset_samples))].join(', ')+
      '. Do not guess; calibrate with a known disc or review the database.':
      'No reliable matching database offset. Try CD calibration or manual lookup.';
    }
   }catch(e){hint.textContent='Lookup unavailable; use the linked database manually. '+e.message}
  };
  const detect=document.createElement('button');detect.type='button';
  detect.style.marginRight='8px';detect.textContent='Detect from CD (experimental)';
  detect.onclick=async()=>{
    if(!confirm('Use the inserted CD to detect a drive offset with cyanrip? It must be known to AccurateRip. No audio is archived, and your settings will not be saved automatically.'))return;
    const access=requestAuthHeaders('Confirm CD offset calibration');
    if(!access)return;
    detect.disabled=true;hint.textContent='Reading offset from reference CD…';
    try{
      const r=await fetch('/api/drive-offset/from-disc',{method:'POST',
        headers:{...access,'Content-Type':'application/json'},
        body:JSON.stringify({stable_id:drive.stable_id,confirmation:'CALIBRATE_OFFSET'})});
      if(!r.ok)throw new Error(await r.text());
      const data=await r.json();
      if(data.suggested_offset!==null){
       hint.textContent='CD suggests '+data.suggested_offset+
        ' samples (experimental; review). Click Save settings to persist.';
       if(drive.offset_samples===null){
        offset.value=String(data.suggested_offset);drive.offset_samples=data.suggested_offset;
       }else hint.textContent+=' Existing saved offset left untouched.';
      }else hint.textContent=data.message;
    }catch(e){hint.textContent='CD calibration failed: '+e.message}
    finally{detect.disabled=false}
  };
  assist.append(lookup,detect,link,hint);row.append(assist);area.append(row);
  if(drive.offset_samples===null)lookup.click();
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
     const rip=document.createElement('button');rip.type='button';
     rip.style.marginLeft='8px';
     rip.textContent='Test rip to staging (experimental)';
     rip.onclick=()=>startTestRip(disc.stable_id,disc.label);
     el.append(rip);
   }
  }
 }catch(error){el.textContent='Probe unavailable: '+error.message}
};
async function startTestRip(stableId,label){
 const headers=requestAuthHeaders('Start experimental staging rip');
 if(!headers)return;
 const status=document.createElement('p');
 status.textContent='Checking test-rip plan for '+label+'…';
 document.getElementById('media-status').append(status);
 try{
  const planResponse=await fetch('/api/rip/plan?'+new URLSearchParams({stable_id:stableId}),{headers});
  if(!planResponse.ok)throw new Error(await planResponse.text());
  const plan=await planResponse.json();
  const accepted=window.confirm('EXPERIMENTAL RIP: '+plan.track_count+
    ' tracks from '+plan.device+' (offset '+plan.offset_samples+
    ') into a NEW folder below '+plan.output_root+
    '. No archive publication or cleanup. Continue?');
  if(!accepted){status.textContent='Test rip cancelled before starting';return}
  const response=await fetch('/api/rip/start',{
    method:'POST',
    headers:{...headers,'Content-Type':'application/json'},
    body:JSON.stringify({stable_id:stableId,confirmation:'RIP_TO_STAGING'})
  });
  if(!response.ok)throw new Error(await response.text());
  const job=await response.json();
  status.textContent='Rip job '+job.id+' started. Checking status…';
  const poll=async()=>{
    try{
      const r=await fetch('/api/rip/jobs/'+encodeURIComponent(job.id),{headers});
      if(!r.ok)throw new Error(await r.text());
      const state=await r.json();
      status.textContent='Rip '+job.id+': '+state.status+
        (state.flac_count?' · '+state.flac_count+' FLAC files':'')+
        (state.error?' · '+state.error:'')+
        (state.warning?' · '+state.warning:'');
      if(state.status==='needs_verification'){
        document.getElementById('verify-job').value=job.id;
        const hint=document.createElement('button');hint.type='button';
        hint.textContent='Open verification for this rip';
        hint.onclick=()=>{document.getElementById('verify-job').scrollIntoView({behavior:'smooth'});
          document.getElementById('verify-job').focus();};
        status.append(document.createTextNode(' '),hint);
      }
      if(state.status==='queued'||state.status==='running')setTimeout(poll,3000);
    }catch(error){status.textContent='Rip status unavailable: '+error.message}
  };
  poll();
 }catch(error){status.textContent='Test rip not started: '+error.message}
}
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
   button.title=(alias.cache_status==='stale'?'Cached name; MusicBrainz temporarily unavailable. ':'')+source+'; original: '+alias.original;
   button.textContent=alias.cache_status==='stale'?'EN ~':(alias.english?'EN ✓':'EN —');
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
 message.textContent='Automatically enriching '+entities.length+' unique composer, performer and work names…';
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
      if(item.error){
        const temporary=/503|502|500|504|429|cooldown|temporarily unavailable|Could not obtain MusicBrainz/.test(item.error);
        b.textContent=temporary?'EN ↻':'EN !';
        b.title=temporary?(item.queued_for_retry?
          'Automatically queued for retry. Reopen this disc later to refresh the displayed alias. ':
          'MusicBrainz temporarily unavailable; retry was not persisted. ')+item.error:item.error;
        b.disabled=false;
      }
      else b.applyAlias(item);
    }
   }
  }catch(error){
   failed+=batch.length;
   completed+=batch.length;
   for(const b of buttons){
    if(batch.some(e=>e.entity_type===b.dataset.aliasType&&e.entity_id===b.dataset.aliasId)){
      b.textContent='EN ↻';b.title='Lookup failed; click to retry later. '+error.message;b.disabled=false;
    }
   }
  }
  message.textContent='English names processed: '+Math.min(i+8,entities.length)+' / '+entities.length;
 }
 message.textContent='English names checked · '+(completed-failed)+' resolved, '+failed+' pending/error, '+cacheHits+' fresh cache hits. EN — = no English alias, EN ↻ = retry later, EN ~ = stale cached alias, EN ! = other lookup error.';
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
        const cols=[
          track.number||track.position,
          track.title||'Untitled',
          null,null,null
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
          }else if(i===4){
            if(!track.performers?.length)td.textContent='Not documented';
            for(const performer of track.performers||[]){
              if(td.childNodes.length)td.append(document.createTextNode(', '));
              td.append(aliasNode('artist',performer.artist_id,performer.name));
              if(performer.role){
                const role=document.createElement('span');
                role.textContent=' ('+performer.role+
                  (performer.attributes?.length?', '+performer.attributes.join(', '):'')+')';
                td.append(role);
              }
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
async function verifyExistingJob(){
 const target=document.getElementById('verify-output');
 const job=document.getElementById('verify-job').value.trim().toLowerCase();
 if(!/^[a-f0-9]{32}$/.test(job)){target.textContent='Enter an OSCAR rip job ID (32 hexadecimal characters).';return}
 const headers=requestAuthHeaders('Verify staged rip');
 if(!headers)return;
 target.textContent='Starting verification (FLAC decoding may take some time)…';
 try{
  const r=await fetch('/api/rip/jobs/'+job+'/verification',{method:'POST',headers});
  if(!r.ok)throw new Error(await r.text());
  async function poll(){
   const response=await fetch('/api/rip/jobs/'+job+'/verification',{headers});
   if(!response.ok)throw new Error(await response.text());
   const data=await response.json();
   if(data.status==='running'||data.status==='not_started'){
    target.textContent='Verification: '+data.status+' (reading stored FLAC files; no optical drive needed).';
    if(data.status==='running')setTimeout(()=>poll().catch(e=>target.textContent=e.message),2500);
    return;
   }
   target.replaceChildren();
   const summary=document.createElement('p');
   summary.textContent='Report: '+data.status+' · '+(data.flac_count??'?')+
      '/'+(data.expected_tracks??'?')+' FLAC · ripping errors: '+(data.ripping_errors??'?')+
      ' · CUE references match: '+(data.cue?.references_match?'yes':'no')+
      (data.error?' · '+data.error:'');
   target.append(summary);
   if(data.tracks?.length){
    const table=document.createElement('table');table.style.width='100%';
    const header=document.createElement('tr');
    for(const h of ['Track','AR v1','AR v2','SHA-256','FLAC decode','Result']){
     const cell=document.createElement('th');cell.textContent=h;cell.style.textAlign='left';
     cell.style.padding='6px';header.append(cell);
    }table.append(header);
    for(const track of data.tracks){
     const tr=document.createElement('tr');
     const ar=v=>{const a=track.accuraterip?.[v];
       return !a?'—':a.status==='accurately_ripped'?'Matched ('+a.confidence+')':a.status};
     for(const value of [track.number,ar('v1'),ar('v2'),
                         track.sha256_matches?'✓':'✗',track.flac_decodes?'✓':'✗',
                         track.checks_passed?'Passed':'Review']){
      const td=document.createElement('td');td.textContent=String(value);
      td.style.padding='6px';td.style.borderBottom='1px solid #324253';tr.append(td);
     }table.append(tr);
    }
    target.append(table);
   }
   const note=document.createElement('p');
   note.textContent=(data.notes||[]).join(' ');
   target.append(note);
  }
  await poll();
 }catch(e){target.textContent='Verification unavailable: '+e.message}
}
document.getElementById('verify-start').onclick=verifyExistingJob;

let reviewedMetadata=null;
function metadataElement(tag,text){const e=document.createElement(tag);e.textContent=String(text??'—');return e;}
document.getElementById('metadata-preview-btn').onclick=async()=>{
 const output=document.getElementById('metadata-output');output.replaceChildren();
 reviewedMetadata=null;
 const job=document.getElementById('metadata-job').value.trim().toLowerCase();
 const release=document.getElementById('metadata-release').value.trim().toLowerCase();
 if(!/^[a-f0-9]{32}$/.test(job)||!/^[a-f0-9-]{36}$/.test(release)){
  output.textContent='Enter a valid staging job ID and MusicBrainz release UUID.';return;
 }
 const access=requestAuthHeaders('Inspect MusicBrainz metadata preview');
 if(!access)return;
 output.textContent='Checking completed rip, exact MusicBrainz medium and relationships…';
 try{
  const r=await fetch('/api/rip/jobs/'+job+'/metadata/preview',{
    method:'POST',headers:{'Content-Type':'application/json',...access},
    body:JSON.stringify({release_id:release})
  });
  if(!r.ok)throw new Error(await r.text());
  const result=await r.json();reviewedMetadata=result;
  output.replaceChildren();
  output.append(metadataElement('h3',result.album.title));
  output.append(metadataElement('p','Album artist: '+result.album.artist+
   ' · Release date: '+(result.album.date||'unknown')+
   ' · Disc '+result.disc_number+'/'+result.disc_total));
  output.append(metadataElement('p','Labels: '+(result.album.labels||[]).map(x=>
    (x.name||'?')+' ['+(x.catalog_number||'no catalogue number')+']').join(', ')+
    ' · Barcode: '+(result.album.barcode||'unknown')));
  const link=document.createElement('a');
  link.href='https://musicbrainz.org/release/'+encodeURIComponent(result.release_id);
  link.rel='noopener noreferrer';link.target='_blank';link.textContent='Review exact MusicBrainz release';
  link.style.color='#bfd5ff';output.append(link);
  const table=document.createElement('table');table.style.width='100%';
  const head=document.createElement('tr');
  for(const v of ['#','Track title','Composer / work','Conductor / performers']){
   const th=metadataElement('th',v);th.style.padding='6px';th.style.textAlign='left';head.append(th);
  }table.append(head);
  for(const track of result.tracks){
   const tr=document.createElement('tr');
   const names=(track.composers||[]).map(x=>x.name).join(', ')||'Not documented';
   const works=(track.works||[]).map(x=>x.title).filter(Boolean).join(' / ')||'No work linked';
   const roles=(track.performers||[]).map(x=>x.name+(x.role?' ('+x.role+')':'')).join(', ')||'Not documented';
   for(const value of [track.number,track.tags.TITLE,names+' · '+works,roles]){
    const td=metadataElement('td',value);td.style.padding='6px';
    td.style.verticalAlign='top';td.style.borderBottom='1px solid #324253';tr.append(td);
   }table.append(tr);
  }output.append(table);
  output.append(metadataElement('p',(result.warnings||[]).join(' ')));
  const button=document.createElement('button');button.type='button';
  button.textContent='I reviewed this release — create separate tagged copies';
  button.onclick=async()=>{
   if(!reviewedMetadata||reviewedMetadata.fingerprint!==result.fingerprint)return;
   const confirmText='Create a NEW staging copy of '+result.track_count+' verified FLACs tagged as '+
     result.album.title+' ('+result.release_id+')? This does not publish or modify originals.';
   if(!confirm(confirmText))return;
   const copyAccess=requestAuthHeaders('Create reviewed FLAC copies');
   if(!copyAccess)return;
   button.disabled=true;
   const status=metadataElement('p','Copying and validating tagged FLACs…');output.append(status);
   try{
    const response=await fetch('/api/rip/jobs/'+job+'/metadata/copy',{
      method:'POST',headers:{'Content-Type':'application/json',...copyAccess},
      body:JSON.stringify({release_id:release,fingerprint:result.fingerprint,
                           confirmation:'COPY_TAGGED_TO_STAGING'})
    });
    if(!response.ok)throw new Error(await response.text());
    const started=await response.json();
    async function poll(){
      const r=await fetch('/api/rip/jobs/'+job+'/metadata/copies/'+started.copy_id,
                          {headers:copyAccess});
      if(!r.ok)throw new Error(await r.text());
      const task=await r.json();
      if(task.status==='running'){
       status.textContent='Tagging in progress; original FLACs remain unchanged…';
       setTimeout(()=>poll().catch(e=>status.textContent=e.message),3000);
      }else{
       if(task.status==='tagged_copy_ready_for_review'){
        document.getElementById('inspect-job').value=job;
        document.getElementById('inspect-copy').value=started.copy_id;
       }
       status.textContent=task.status+' · '+(task.count??'?')+' tagged FLAC copies'+
        (task.error?' · '+task.error:'')+
        ' · copy ID '+started.copy_id+'. No archive promotion.';
      }
    }await poll();
   }catch(e){status.textContent='Tagged-copy request failed: '+e.message}
   finally{button.disabled=false}
  };
  output.append(button);
 }catch(e){output.textContent='Metadata preview failed: '+e.message}
};


document.getElementById('inspect-start').onclick=async()=>{
 const job=document.getElementById('inspect-job').value.trim().toLowerCase();
 const copy=document.getElementById('inspect-copy').value.trim().toLowerCase();
 const target=document.getElementById('inspect-result');
 target.replaceChildren();
 if(!/^[a-f0-9]{32}$/.test(job)||!/^[a-f0-9]{32}$/.test(copy)){
  target.textContent='Enter both 32-character IDs.';return;
 }
 const headers=requestAuthHeaders('Read actual tagged FLAC metadata');
 if(!headers)return;
 target.textContent='Reading the actual FLAC Vorbis comments and comparing saved preview…';
 try{
  const r=await fetch('/api/rip/jobs/'+job+'/metadata/copies/'+copy+'/inspect',{headers});
  if(!r.ok)throw new Error(await r.text());
  const result=await r.json();
  target.replaceChildren();
  const title=document.createElement('h3');title.textContent=result.album.title||'Unknown album';target.append(title);
  const overview=document.createElement('p');
  overview.textContent=result.track_count+' tracks · '+result.status+
    ' · source: actual saved FLAC tags (not a MusicBrainz lookup)';
  target.append(overview);
  const table=document.createElement('table');table.style.width='100%';
  const h=document.createElement('tr');
  for(const v of ['Track','Title','Composer','Work / grouping','Conductor','Orchestra','Checks']){
   const th=document.createElement('th');th.textContent=v;th.style.textAlign='left';
   th.style.padding='6px';h.append(th);
  }table.append(h);
  for(const track of result.tracks){
   const t=track.tags||{};
   const value=(k)=>Array.isArray(t[k])?t[k].join(', '):'—';
   const row=document.createElement('tr');
   for(const txt of [track.track,value('TITLE'),value('COMPOSER'),
       [value('WORK'),value('GROUPING')].filter(x=>x!=='—').join(' / ')||'—',
       value('CONDUCTOR'),value('ORCHESTRA'),track.status]){
    const td=document.createElement('td');td.textContent=String(txt);
    td.style.padding='6px';td.style.verticalAlign='top';
    td.style.borderBottom='1px solid #324253';row.append(td);
   }
   table.append(row);
   const expanded=document.createElement('tr');
   const cell=document.createElement('td');cell.colSpan=7;
   const details=document.createElement('details');
   const summary=document.createElement('summary');
   summary.textContent='Track '+track.track+' — all stored Vorbis tags and preview differences ('+
    Object.keys(track.differences||{}).length+' differences)';
   details.append(summary);
   const pre=document.createElement('pre');pre.style.whiteSpace='pre-wrap';
   pre.style.overflowWrap='anywhere';pre.textContent=JSON.stringify({
      tags:track.tags,differences:track.differences,
      sha256_matches:track.sha256_matches,
      audio_streaminfo_md5_matches:track.audio_streaminfo_md5_matches
   },null,2);
   details.append(pre);cell.append(details);expanded.append(cell);table.append(expanded);
  }
  target.append(table);
  const footer=document.createElement('p');footer.textContent=(result.notes||[]).join(' ');
  target.append(footer);
 }catch(error){target.textContent='Inspection failed: '+error.message}
};


let v2Current=null;
function parseV2Lines(value,isMovement){
 const result=isMovement?{}:[];
 for(const raw of value.split(/\r?\n/)){
  const line=raw.trim();if(!line)continue;
  const pos=line.indexOf('|');
  if(pos<0)throw new Error('Missing | separator: '+line);
  const left=line.slice(0,pos).trim(),name=line.slice(pos+1).trim();
  if(!name)throw new Error('Missing name: '+line);
  if(isMovement){
   if(!/^\d+$/.test(left))throw new Error('Invalid track number: '+left);
   result[String(Number(left))]=name;
  }else{
   const m=/^(\d+)\s*-\s*(\d+)$/.exec(left);
   if(!m)throw new Error('Use start-end | title for every section');
   result.push({start:Number(m[1]),end:Number(m[2]),name});
  }
 }
 return result;
}
document.getElementById('v2-preview').onclick=async()=>{
 const target=document.getElementById('v2-output');target.replaceChildren();v2Current=null;
 const job=document.getElementById('v2-job').value.trim().toLowerCase();
 const source=document.getElementById('v2-source').value.trim().toLowerCase();
 if(!/^[a-f0-9]{32}$/.test(job)||!/^[a-f0-9]{32}$/.test(source)){
  target.textContent='Enter both 32-character IDs.';return;
 }
 let sections,movements;
 try{
  sections=parseV2Lines(document.getElementById('v2-sections').value,false);
  movements=parseV2Lines(document.getElementById('v2-movements').value,true);
 }catch(e){target.textContent=e.message;return}
 const access=requestAuthHeaders('Preview reviewed Classical v2 tags');
 if(!access)return;
 target.textContent='Checking completed tagged source and reviewing work identity…';
 try{
  const response=await fetch('/api/rip/jobs/'+job+'/metadata/copies/'+source+'/classical-v2/preview',{
   method:'POST',headers:{'Content-Type':'application/json',...access},
   body:JSON.stringify({sections,movements})
  });
  if(!response.ok)throw new Error(await response.text());
  const data=await response.json();v2Current=data;
  target.replaceChildren();
  const caption=document.createElement('p');caption.textContent=data.track_count+
    ' tracks · '+data.sections.map(x=>x.name+' ('+x.start+'–'+x.end+')').join(' · ');
  target.append(caption);
  const table=document.createElement('table');table.style.width='100%';
  const head=document.createElement('tr');
  for(const key of ['#','Release section','CD title','MusicBrainz work','Parent work','Movement','EN aliases']){
   const th=document.createElement('th');th.textContent=key;th.style.textAlign='left';
   th.style.padding='5px';head.append(th);
  }table.append(head);
  for(const t of data.tracks){
   const tr=document.createElement('tr');
   for(const value of [t.number,t.release_section,t.title,
    (t.work||[]).join('; ')||'—',(t.work_parent||[]).join('; ')||'—',
    t.movement||'Not documented',Object.entries(t.aliases||{}).map(x=>x[0]+': '+x[1].join(', ')).join('; ')||'—']){
    const td=document.createElement('td');td.textContent=String(value);
    td.style.padding='5px';td.style.borderBottom='1px solid #324253';tr.append(td);
   }table.append(tr);
  }target.append(table);
  const notes=document.createElement('p');notes.textContent=data.warnings.join(' ');target.append(notes);
  const button=document.createElement('button');button.textContent='I reviewed sections — create separate Classical v2 FLAC copies';
  button.type='button';
  button.onclick=async()=>{
   if(!v2Current||v2Current.fingerprint!==data.fingerprint)return;
   if(!confirm('Create a NEW tagged copy of '+data.track_count+' FLACs using the reviewed CD sections? Original files and previous copies stay unchanged.'))return;
   const copyAccess=requestAuthHeaders('Confirm Classical v2 staging copy');if(!copyAccess)return;
   button.disabled=true;
   const note=document.createElement('p');note.textContent='Creating new FLAC copies…';target.append(note);
   try{
    const response=await fetch('/api/rip/jobs/'+job+'/metadata/classical-v2/copy',{
      method:'POST',headers:{'Content-Type':'application/json',...copyAccess},
      body:JSON.stringify({preview:data,confirmation:'COPY_CLASSICAL_V2_TO_STAGING'})
    });
    if(!response.ok)throw new Error(await response.text());
    const started=await response.json();
    async function poll(){
     const r=await fetch('/api/rip/jobs/'+job+'/metadata/classical-v2/copies/'+started.copy_id,
                         {headers:copyAccess});
     if(!r.ok)throw new Error(await r.text());
     const state=await r.json();
     if(state.status==='running'){
      note.textContent='Tagging Classical v2 copy, originals untouched…';
      setTimeout(()=>poll().catch(e=>note.textContent=e.message),2500);
     }else{
      note.textContent=state.status+' · '+(state.count??'?')+' FLAC copies · copy ID '+started.copy_id+
       (state.error?' · '+state.error:'')+'. No archive publication.';
      if(state.status==='classical_v2_ready_for_review'){
       const inspect=document.createElement('button');inspect.type='button';
       inspect.textContent='Inspect actual Classical v2 FLAC tags';
       inspect.onclick=async()=>{
        const readAccess=requestAuthHeaders('Inspect actual Classical v2 tags');
        if(!readAccess)return;
        note.textContent='Reading saved Classical v2 FLAC tags and hashes…';
        try{
         const response=await fetch('/api/rip/jobs/'+job+'/metadata/classical-v2/copies/'+started.copy_id+'/inspect',
          {headers:readAccess});
         if(!response.ok)throw new Error(await response.text());
         const results=await response.json();
         note.textContent='Classical v2 inspection: '+results.status+' · '+results.track_count+' tracks';
         const table=document.createElement('table');table.style.width='100%';
         const head=document.createElement('tr');
         for(const label of ['#','Release section','Title','Work parent','Movement','Aliases','Result']){
          const th=document.createElement('th');th.textContent=label;
          th.style.padding='5px';th.style.textAlign='left';head.append(th);
         }table.append(head);
         for(const t of results.tracks){
          const tr=document.createElement('tr');
          for(const val of [t.number,t.release_section,t.title,
              (t.work_parent||[]).join(', ')||'—',(t.movement||[]).join(', ')||'—',
              Object.entries(t.english_aliases||{}).map(x=>x[0]+': '+x[1].join(', ')).join('; ')||'—',t.status]){
           const td=document.createElement('td');td.textContent=String(val);
           td.style.padding='5px';td.style.borderBottom='1px solid #324253';tr.append(td);
          }table.append(tr);
         }target.append(table);
        }catch(err){note.textContent='Inspection error: '+err.message}
       };target.append(inspect);
      }
     }
    }await poll();
   }catch(e){note.textContent='Classical v2 copy failed: '+e.message}
   finally{button.disabled=false}
  };target.append(button);
 }catch(e){target.textContent='Classical metadata preview failed: '+e.message}
};

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
