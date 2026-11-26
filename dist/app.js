(() => {
'use strict';
// Update status is separate from the immutable scientific release loaded above.
async function loadUpdateStatus(){
 const box=document.getElementById('update-status');
 try{
  const response=await fetch('data/update-status.json',{cache:'no-store'});
  if(!response.ok)throw new Error('status unavailable');
  const status=await response.json(),when=v=>v?new Date(v).toLocaleString(undefined,{dateStyle:'medium',timeStyle:'short'}):'awaiting first check';
  const schedule=status.schedule;
  const cadence=schedule?.is_enabled?`Daily checks at ${schedule.local_time||'08:00'} (${schedule.timezone||'America/Toronto'}). `:'';
  const issue=status.last_result==='prepared'?' GitHub upload and workflow activation are pending.':status.last_result==='held'?' The latest update is held for review; the validated release remains available.':status.source_errors?.length?' Some source checks need attention.':'';
  box.textContent=`${cadence}Last source check: ${when(status.last_checked_at_utc)}. Last accepted data release: ${when(status.last_data_update_at_utc)}.${issue}`;
 }catch{box.textContent='Update status is temporarily unavailable. The loaded data retain their source dates and provenance.';}
}
loadUpdateStatus();

const $ = id => document.getElementById(id);
const OXIDES = ['SiO2','TiO2','Al2O3','FeOT','MgO','CaO','Na2O','K2O','MnO'];
const LABELS = {SiO2:'SiO₂',TiO2:'TiO₂',Al2O3:'Al₂O₃',FeOT:'FeOₜ',MgO:'MgO',CaO:'CaO',Na2O:'Na₂O',K2O:'K₂O',MnO:'MnO',sol:'Mission sol'};
const NAMES = {SiO2:'silica',TiO2:'titania',Al2O3:'alumina',FeOT:'total iron as FeO',MgO:'magnesia',CaO:'lime',Na2O:'soda',K2O:'potash',MnO:'manganese oxide'};
const MISSIONS = {chemcam:{name:'Curiosity',instrument:'ChemCam',crater:'Gale crater'},supercam:{name:'Perseverance',instrument:'SuperCam',crater:'Jezero crater'}};
const state = {mission:'chemcam',data:null,points:[],filtered:[],byId:new Map(),selected:null,oxide:'SiO2',page:0,pageSize:25,rmi:null,groups:[],mapGeometry:null,scatterGeometry:null,colourMin:0,colourMax:1,cache:{},loadToken:0};
const isNum = v => typeof v === 'number' && Number.isFinite(v);
const fmt = (v,d=2) => isNum(v) ? v.toLocaleString('en-US',{minimumFractionDigits:d,maximumFractionDigits:d}) : '—';
const int = v => isNum(v) ? v.toLocaleString('en-US',{maximumFractionDigits:0}) : '—';
const esc = s => String(s ?? '').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const label = o => LABELS[o] || o;
const median = values => {const v=values.filter(isNum).sort((a,b)=>a-b), n=v.length;return n ? (n%2?v[(n-1)/2]:(v[n/2-1]+v[n/2])/2) : null;};
const archiveLabel = d => typeof d.archive_version==='object' ? [d.archive_version.dataset_id,d.archive_version.latest_moc_file].filter(Boolean).join(' · ') : String(d.archive_version||'');
const flagText = p => (p.quality_flags||[]).map(f=>typeof f==='string'?f:JSON.stringify(f));
const atlas=window.MarsAtlas.create({getState:()=>state,colour,label,onChooseGroup:chooseGroup,onSelectPoint:selectPoint,download,toast});
function toast(message){$('toast').textContent=message;$('toast').hidden=false;clearTimeout(state.toastTimer);state.toastTimer=setTimeout(()=>$('toast').hidden=true,4300);}
function colour(value){
 if(!isNum(value)) return '#8c9189';
 const t=Math.max(0,Math.min(1,(value-state.colourMin)/(state.colourMax-state.colourMin||1)));
 const stops=[[54,76,102],[81,139,152],[163,185,161],[215,192,128],[192,119,79]], j=Math.min(3,Math.floor(t*4)), f=t*4-j;
 return '#'+stops[j].map((v,i)=>Math.round(v+(stops[j+1][i]-v)*f).toString(16).padStart(2,'0')).join('');
}
function palette(){const s=getComputedStyle(document.documentElement);return{ink:s.getPropertyValue('--ink').trim(),muted:s.getPropertyValue('--muted').trim(),line:s.getPropertyValue('--line').trim(),paper:s.getPropertyValue('--plot').trim(),accent:s.getPropertyValue('--accent').trim()};}
function setTheme(theme){document.documentElement.dataset.theme=theme;document.querySelectorAll('.theme-switch button').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.theme===theme)));try{localStorage.setItem('mars-libs-theme',theme);}catch{} if(state.data){drawMap();drawScatter();atlas.refreshColours();}}
function normalise(data){
 data.points=Array.isArray(data.points)?data.points:[];
 for(const p of data.points){p.source_id=p.source_id||p.provenance?.source_table_id;p.source_row=p.source_row??p.provenance?.source_row;p.source_rows=p.source_rows??p.provenance?.source_rows;}
 data.sources=Array.isArray(data.sources)?data.sources:Object.entries(data.sources||{}).map(([id,v])=>({id,...(typeof v==='string'?{url:v}:v)}));
 data.oxides=(data.oxides||OXIDES).filter(x=>OXIDES.includes(x));
 data.rmi_targets=(data.rmi_targets||[]).map(r=>({...r,points:(r.points||[]).map(p=>({...p,point_id:p.point_id??p.id??null,point:p.point??p.number??null}))}));
 return data;
}
async function fetchJSON(path,gzip=false,expectedSha=null){
 const response=await fetch(path);if(!response.ok)throw new Error(`${path} returned HTTP ${response.status}`);
 const bytes=gzip?await new Response(response.body.pipeThrough(new DecompressionStream('gzip'))).arrayBuffer():await response.arrayBuffer();
 if(expectedSha&&crypto.subtle){const actual=[...new Uint8Array(await crypto.subtle.digest('SHA-256',bytes))].map(v=>v.toString(16).padStart(2,'0')).join('');if(actual!==expectedSha)throw new Error('The data release changed or a file is incomplete. Reload to load a consistent release');}
 return JSON.parse(new TextDecoder().decode(bytes));
}
async function loadData(mission){
 const data=await fetchJSON(`data/${mission}.json`);
 const useGzip=typeof DecompressionStream!=='undefined'&&Array.isArray(data.point_files_gzip)&&data.point_files_gzip.length;
 const paths=useGzip?data.point_files_gzip:data.point_files;
 if(paths?.length){
   const chunks=new Array(paths.length);let done=0;
   const workers=Array.from({length:Math.min(4,paths.length)},async(_,worker)=>{for(let i=worker;i<paths.length;i+=Math.min(4,paths.length)){const path=typeof paths[i]==='string'?paths[i]:paths[i].path;const plain=path.endsWith('.gz')?path.slice(0,-3):path,expected=data.packaging?.chunks?.find(c=>c.file===plain)?.sha256;chunks[i]=await fetchJSON(path,!!useGzip,expected);done++;if(state.mission===mission)$('load-status').textContent=`Loading ${MISSIONS[mission].instrument} archive · ${done} of ${paths.length} data files…`;}});
   await Promise.all(workers);data.points=chunks.flatMap(c=>Array.isArray(c)?c:(c.points||[]));
 }
 return normalise(data);
}
async function switchMission(mission){
 const token=++state.loadToken;state.mission=mission;
 document.querySelectorAll('[data-mission]').forEach(b=>{const active=b.dataset.mission===mission;b.classList.toggle('active',active);b.setAttribute('aria-pressed',String(active));});
 $('load-status').textContent=`Loading the archived ${MISSIONS[mission].instrument} measurements…`;$('error-box').hidden=true;
 document.querySelectorAll('#filters input,#filters select,#export-csv,#export-map,#export-scatter,#rmi-target,#rmi-oxide,#filter-rmi').forEach(e=>e.disabled=true);
 try{
  if(!state.cache[mission])state.cache[mission]=loadData(mission).catch(e=>{delete state.cache[mission];throw e;});
  const data=await state.cache[mission];if(token!==state.loadToken)return;
  state.data=data;state.points=data.points;state.byId=new Map(data.points.map(p=>[p.id,p]));state.selected=null;state.rmi=null;atlas.missionChanged();
  const validSols=data.points.map(p=>p.sol).filter(isNum);state.minSol=validSols.reduce((a,b)=>Math.min(a,b),Infinity);state.maxSol=validSols.reduce((a,b)=>Math.max(a,b),-Infinity);
  if(!validSols.length){state.minSol=0;state.maxSol=0;}
  state.oxide=data.oxides.includes(state.oxide)?state.oxide:'SiO2';
  $('oxide').innerHTML=data.oxides.map(o=>`<option value="${o}">${label(o)} · ${NAMES[o]||o}</option>`).join('');$('oxide').value=state.oxide;$('rmi-oxide').innerHTML=$('oxide').innerHTML;$('rmi-oxide').value=state.oxide;
  const axisOptions=data.oxides.map(o=>`<option value="${o}">${label(o)} (wt%)</option>`).join('');
  $('scatter-x').innerHTML=`<option value="sol">Mission sol</option>${axisOptions}`;$('scatter-y').innerHTML=axisOptions;
  $('scatter-x').value='SiO2';$('scatter-y').value='MgO';
  resetInputs();
  $('rmi-target').innerHTML=data.rmi_targets.length?data.rmi_targets.map(r=>`<option value="${esc(r.id)}">${esc(r.target||r.id)} · sol ${esc(r.sol)}</option>`).join(''):'<option value="">No image examples in this snapshot</option>';
  $('map-title').textContent=MISSIONS[mission].crater;
  document.querySelectorAll('#filters input,#filters select,#export-csv,#export-map,#export-scatter,#rmi-target,#rmi-oxide,#filter-rmi').forEach(e=>e.disabled=false);
  if(!data.rmi_targets.length){$('rmi-target').disabled=true;$('filter-rmi').disabled=true;}
  applyFilters();
  chooseRMI(data.rmi_targets[0]?.id,true);
  updateProvenance();
  const retrieved=data.generated_at_utc||data.retrieved_at_utc||'';
  $('load-status').textContent=`${MISSIONS[mission].instrument} · ${int(data.points.length)} archived records · sols ${int(state.minSol)}–${int(state.maxSol)}${data.archive_version?' · '+archiveLabel(data):''}${retrieved?' · snapshot '+retrieved.slice(0,10):''}`;
 }catch(error){if(token!==state.loadToken)return;$('load-status').textContent='The data snapshot could not be loaded.';$('error-box').hidden=false;$('error-box').textContent=`${error.message}. Please reload the page. If you downloaded this project, serve the folder over HTTP rather than opening index.html directly.`;}
}
function resetInputs(){
 $('sol-min').value=state.minSol;$('sol-max').value=state.maxSol;$('sol-min').min=state.minSol;$('sol-max').max=state.maxSol;
 $('search').value='';$('include-calibration').checked=false;$('exclude-flagged').checked=false;
}
function applyFilters(){
 if(!state.data)return;
 const query=$('search').value.trim().toLowerCase(), min=$('sol-min').value===''?state.minSol:Number($('sol-min').value), max=$('sol-max').value===''?state.maxSol:Number($('sol-max').value);
 const cal=$('include-calibration').checked, flags=$('exclude-flagged').checked;
 state.filtered=state.points.filter(p=>(cal||!p.is_calibration)&&(!flags||!p.quality_flags?.length)&&isNum(p.sol)&&p.sol>=min&&p.sol<=max&&(!query||String(p.target||'').toLowerCase().includes(query)||String(p.id||'').toLowerCase().includes(query)));
 state.filteredIds=new Set(state.filtered.map(p=>p.id));state.page=0;
 const values=state.filtered.map(p=>p.oxides?.[state.oxide]).filter(isNum);
 state.colourMin=values.reduce((a,b)=>Math.min(a,b),Infinity);state.colourMax=values.reduce((a,b)=>Math.max(a,b),-Infinity);
 if(!values.length){state.colourMin=0;state.colourMax=1;}
 $('legend-min').textContent=values.length?fmt(state.colourMin):'—';$('legend-max').textContent=values.length?fmt(state.colourMax):'—';$('legend-unit').textContent=`${label(state.oxide)} wt%`;['min','max','unit'].forEach(key=>$('rmi-legend-'+key).textContent=$('legend-'+key).textContent);$('rmi-oxide').value=state.oxide;
 buildGroups();
 $('stat-points').textContent=int(state.filtered.length);$('stat-targets').textContent=int(new Set(state.filtered.map(p=>p.target).filter(Boolean)).size);$('stat-locations').textContent=int(state.groups.length);
 const sols=state.filtered.map(p=>p.sol);$('stat-sols').textContent=sols.length?`${int(sols.reduce((a,b)=>Math.min(a,b),Infinity))}–${int(sols.reduce((a,b)=>Math.max(a,b),-Infinity))}`:'—';
 $('location-picker').hidden=true;
 if(!state.selected||!state.filteredIds.has(state.selected.id))state.selected=state.filtered.find(p=>isNum(p.oxides?.[state.oxide]))||state.filtered[0]||null;
 renderTable();updateSelected();drawMap();drawScatter();drawRMI();
}
function buildGroups(){
 const groups=new Map();
 for(const p of state.filtered){const loc=p.location;if(p.is_calibration||!loc||!isNum(loc.lat)||!isNum(loc.lon))continue;
 const key=`${loc.lat.toFixed(8)},${loc.lon.toFixed(8)}`;let group=groups.get(key);if(!group){group={key,lat:loc.lat,lon:loc.lon,points:[],site:p.site??loc.site,drive:p.drive??loc.drive};groups.set(key,group);}group.points.push(p);}
 state.groups=[...groups.values()].map(g=>({...g,value:median(g.points.map(p=>p.oxides?.[state.oxide]))}));
 const mapped=state.groups.reduce((n,g)=>n+g.points.length,0), ground=state.filtered.filter(p=>!p.is_calibration).length;
 $('map-caption').textContent=`${int(mapped)} of ${int(ground)} selected Mars-target measurements have matched rover positions. Each marker uses the median ${label(state.oxide)} of its measurements; marker size indicates count. Calibration records are kept off this map.`;
}
function canvasSetup(canvas){const r=canvas.getBoundingClientRect(),d=Math.min(2,devicePixelRatio||1);canvas.width=Math.round(r.width*d);canvas.height=Math.round(r.height*d);const ctx=canvas.getContext('2d');ctx.setTransform(d,0,0,d,0,0);return{ctx,w:r.width,h:r.height};}
function ticks(lo,hi,count=5){if(!isNum(lo)||!isNum(hi))return[];if(lo===hi)return[lo];return Array.from({length:count},(_,i)=>lo+(hi-lo)*i/(count-1));}
function drawMap(){atlas.draw();}
function plotAxisLabel(key){return key==='sol'?'Mission sol':`${label(key)} (wt%)`;}
function drawScatter(){
 const {ctx,w,h}=canvasSetup($('scatter-canvas')),p=palette();ctx.fillStyle=p.paper;ctx.fillRect(0,0,w,h);
 if(!state.data)return;
 const xkey=$('scatter-x').value,ykey=$('scatter-y').value;
 const get=(point,key)=>key==='sol'?point.sol:point.oxides?.[key];
 const data=state.filtered.filter(point=>isNum(get(point,xkey))&&isNum(get(point,ykey)));
 $('scatter-empty').hidden=data.length>0;
 if(!data.length){state.scatterGeometry=null;return;}
 let xmin=Infinity,xmax=-Infinity,ymin=Infinity,ymax=-Infinity;for(const point of data){const x=get(point,xkey),y=get(point,ykey);xmin=Math.min(xmin,x);xmax=Math.max(xmax,x);ymin=Math.min(ymin,y);ymax=Math.max(ymax,y);}
 let dx=(xmax-xmin)||Math.max(1,Math.abs(xmin)*.1),dy=(ymax-ymin)||Math.max(1,Math.abs(ymin)*.1);xmin-=dx*.045;xmax+=dx*.045;ymin-=dy*.045;ymax+=dy*.045;
 const left=62,right=26,top=25,bottom=54,pw=Math.max(1,w-left-right),ph=Math.max(1,h-top-bottom),xp=v=>left+(v-xmin)/(xmax-xmin)*pw,yp=v=>top+ph-(v-ymin)/(ymax-ymin)*ph;
 const xt=ticks(xmin,xmax,w<500?4:6),yt=ticks(ymin,ymax,5);
 ctx.font='10px ui-monospace,monospace';ctx.fillStyle=p.muted;ctx.strokeStyle=p.line;ctx.lineWidth=.6;
 const precision=(max,min)=>max-min<2?2:(max-min<30?1:0);
 xt.forEach(t=>{const x=xp(t);ctx.beginPath();ctx.moveTo(x,top);ctx.lineTo(x,top+ph);ctx.stroke();ctx.textAlign='center';ctx.fillText(t.toFixed(xkey==='sol'?0:precision(xmax,xmin)),x,top+ph+20);});
 yt.forEach(t=>{const y=yp(t);ctx.beginPath();ctx.moveTo(left,y);ctx.lineTo(left+pw,y);ctx.stroke();ctx.textAlign='right';ctx.fillText(t.toFixed(precision(ymax,ymin)),left-10,y+3);});
 ctx.textAlign='center';ctx.fillText(plotAxisLabel(xkey),left+pw/2,h-10);ctx.save();ctx.translate(14,top+ph/2);ctx.rotate(-Math.PI/2);ctx.fillText(plotAxisLabel(ykey),0,0);ctx.restore();
 const projected=new Array(data.length),radius=data.length>10000?1.7:data.length>1000?2.1:3;
 ctx.globalAlpha=data.length>10000?.38:.62;
 for(let i=0;i<data.length;i++){const point=data[i],x=xp(get(point,xkey)),y=yp(get(point,ykey));projected[i]={point,x,y};ctx.fillStyle=colour(point.oxides?.[state.oxide]);ctx.beginPath();ctx.arc(x,y,radius,0,Math.PI*2);ctx.fill();}
 ctx.globalAlpha=1;
 if(state.selected&&state.filteredIds.has(state.selected.id)&&isNum(get(state.selected,xkey))&&isNum(get(state.selected,ykey))){const x=xp(get(state.selected,xkey)),y=yp(get(state.selected,ykey));ctx.strokeStyle=p.ink;ctx.lineWidth=1.3;ctx.beginPath();ctx.arc(x,y,6,0,Math.PI*2);ctx.moveTo(x-10,y);ctx.lineTo(x-5,y);ctx.moveTo(x+5,y);ctx.lineTo(x+10,y);ctx.moveTo(x,y-10);ctx.lineTo(x,y-5);ctx.moveTo(x,y+5);ctx.lineTo(x,y+10);ctx.stroke();}
 state.scatterGeometry={projected,w,h,left,right,top,bottom,pw,ph,xmin,xmax,ymin,ymax,xt,yt,xkey,ykey,xp,yp};
 $('scatter-caption').textContent=`${int(data.length)} of ${int(state.filtered.length)} filtered records have values on both axes. Each point is one published composition estimate. Click to inspect; concentrations and totals are not renormalized.`;
}
function nearestMap(x,y){let found=null,best=Infinity;for(const g of state.mapGeometry?.projected||[]){const d=Math.hypot(x-g.x,y-g.y);if(d<Math.max(13,g.radius+5)&&d<best){found=g;best=d;}}return found;}
function nearestScatter(x,y){let found=null,best=100;for(const g of state.scatterGeometry?.projected||[]){const d=(x-g.x)**2+(y-g.y)**2;if(d<best){found=g;best=d;}}return found;}
function mousePoint(event,canvas){const r=canvas.getBoundingClientRect();return{x:event.clientX-r.left,y:event.clientY-r.top};}
function showTooltip(el,html,x,y,width){el.innerHTML=html;el.hidden=false;el.style.left=`${Math.max(8,Math.min(x+13,width-235))}px`;el.style.top=`${Math.max(8,y-56)}px`;}
function chooseGroup(g){
 if(!g)return;const points=g.points;
 $('location-picker').hidden=false;$('location-points').innerHTML=points.map(p=>`<option value="${esc(p.id)}">${esc(p.target)} · sol ${esc(p.sol)} · point/order ${esc(p.point)} · ${fmt(p.oxides?.[state.oxide])} wt%</option>`).join('');
 selectPoint(points.find(p=>isNum(p.oxides?.[state.oxide]))||points[0]);$('location-points').value=state.selected.id;
}
function selectPoint(point){if(!point)return;state.rmiMissingSpot=null;state.selected=point;updateSelected();renderTable();drawMap();drawScatter();drawRMI();}
function findSource(point){return state.data.sources.find(s=>s.id===point.source_id)||state.data.sources.find(s=>String(s.url||'').endsWith('/'+point.source_id))||state.data.sources.find(s=>/moc.*\.csv/i.test(s.url||''));}
function updateSelected(){
 const p=state.selected,o=state.oxide;
 $('table-oxide').textContent=`${label(o)} wt%`;
 if(!p){$('detail-target').textContent='No measurement selected';$('detail-sub').textContent='Adjust the filters to explore available records.';$('detail-value').textContent='—';$('detail-unit').textContent=`${label(o)} / wt%`;['detail-facts','mini-chemistry','detail-quality','detail-source','composition-body'].forEach(id=>$(id).innerHTML='');$('composition-target').textContent='Selected measurement';return;}
 $('detail-target').textContent=p.target||'Unnamed target';$('detail-sub').textContent=`${p.instrument||MISSIONS[state.mission].instrument} · sol ${p.sol} · point/order ${p.point??'—'}`;
 $('detail-value').textContent=fmt(p.oxides?.[o]);$('detail-unit').textContent=`${label(o)} / wt%`;
 const facts=[['Calibration RMSEP',`${fmt(p.uncertainty?.rmsep?.[o])} wt%`],['Shot SD',`${fmt(p.uncertainty?.shot_sd?.[o])} wt%`],['Reported total',`${fmt(p.total_wt_pct)} wt%`],['Target distance',`${fmt(p.distance_m,3)} m`],['Site / drive',`${p.site??p.location?.site??'—'} / ${p.drive??p.location?.drive??'—'}`]];
 if(p.location&&isNum(p.location.lat)&&isNum(p.location.lon)){facts.push(['Rover latitude',`${fmt(p.location.lat,6)}°`],['Rover longitude',`${fmt(p.location.lon,6)}°E`]);}else facts.push(['Rover position','No matched record']);
 $('detail-facts').innerHTML=facts.map(([a,b])=>`<dt>${esc(a)}</dt><dd>${esc(b)}</dd>`).join('');
 const max=Math.max(1,...state.data.oxides.map(k=>isNum(p.oxides?.[k])?p.oxides[k]:0));
 $('mini-chemistry').innerHTML=state.data.oxides.map(k=>`<div class="mini-row ${k===o?'active':''}"><span>${label(k)}</span><span class="mini-bar"><i style="width:${Math.max(0,Math.min(100,(p.oxides?.[k]||0)/max*100))}%"></i></span><span>${fmt(p.oxides?.[k])}</span></div>`).join('');
 const notes=[];if(p.is_calibration)notes.push('Onboard calibration target.');if(!state.filteredIds.has(p.id))notes.push('This image-example measurement is outside the current table filters.');
 if(p.point_index_kind&&!String(p.point_index_kind).includes('rmi')&&!String(p.point_index_kind).includes('raster'))notes.push(`Point/order is an observation order (${String(p.point_index_kind).replaceAll('_',' ')}), not an archived image-spot number.`);
 const flags=flagText(p);notes.push(flags.length?`Quality/review flags: ${flags.join('; ')}.`:'No quality/review flags recorded for this point.');const archiveNotes=[];if(p.archive_comment)archiveNotes.push(p.archive_comment);if(p.archive_saturation)archiveNotes.push('Saturation: '+p.archive_saturation);if(p.quality_notes)archiveNotes.push(...Object.entries(p.quality_notes).filter(([,v])=>v!==null&&v!=='').map(([k,v])=>k+': '+v));if(archiveNotes.length)notes.push('Archive notes: '+archiveNotes.join('; '));$('detail-quality').textContent=notes.join(' ');
 const source=findSource(p),sourceUrl=p.source_url||source?.url;
 $('detail-source').innerHTML=`${sourceUrl?`<a href="${esc(sourceUrl)}" target="_blank" rel="noopener">Open source table <svg class="arrow-icon" viewBox="0 0 14 14" width="12" height="12" aria-hidden="true"><path d="M2 12 12 2M3 2h9v9" fill="none" stroke="currentColor" stroke-width="1.3"/></svg></a>`:'Source table in bundled metadata'}${p.source_row?` · row ${esc(p.source_row)}`:''}<span class="record-id">${esc(p.id)}</span>`;
 $('composition-target').textContent=`${p.target||'Unnamed target'} · sol ${p.sol} · point/order ${p.point??'—'}`;
 $('composition-body').innerHTML=state.data.oxides.map(k=>`<tr class="${k===o?'selected-row':''}"><td>${label(k)}</td><td>${fmt(p.oxides?.[k])}</td><td>${fmt(p.uncertainty?.rmsep?.[k])}</td><td>${fmt(p.uncertainty?.shot_sd?.[k])}</td></tr>`).join('')+`<tr><td>Reported total</td><td>${fmt(p.total_wt_pct)}</td><td>—</td><td>—</td></tr>`;
}
function renderTable(){
 if(!state.data)return;const total=state.filtered.length,pages=Math.max(1,Math.ceil(total/state.pageSize));state.page=Math.max(0,Math.min(state.page,pages-1));const rows=state.filtered.slice(state.page*state.pageSize,(state.page+1)*state.pageSize),o=state.oxide;
 $('measurements').querySelector('tbody').innerHTML=rows.length?rows.map(p=>`<tr class="${p.id===state.selected?.id?'selected-row':''}"><td><button class="select-record" data-id="${esc(p.id)}">${esc(p.target||'Unnamed target')}</button>${p.is_calibration?'<span class="target-kind">CAL</span>':''}</td><td>${esc(p.sol)}</td><td>${esc(p.point??'—')}</td><td>${fmt(p.oxides?.[o])}</td><td>${fmt(p.uncertainty?.rmsep?.[o])}</td><td>${fmt(p.uncertainty?.shot_sd?.[o])}</td><td>${fmt(p.total_wt_pct)}</td><td>${fmt(p.distance_m,2)}</td></tr>`).join(''):'<tr><td colspan="8">No measurements match these filters. Try a wider sol range or clear the target search.</td></tr>';
 $('table-summary').textContent=`${int(total)} records · concentration and uncertainty in wt% · point/order as supplied or derived`;
 $('page-label').textContent=`Page ${state.page+1} of ${pages}`;$('prev-page').disabled=state.page===0;$('next-page').disabled=state.page===pages-1;
}
function rmiPath(r){return r.image_local||r.image_local_path||r.image_path||r.image_url;}
function chooseRMI(id,selectFirst=false){
 const r=state.data?.rmi_targets.find(r=>r.id===id)||null;state.rmi=r;state.rmiMissingSpot=null;
 if(!r){$('rmi-image').hidden=true;$('rmi-overlay').innerHTML='';$('rmi-empty').hidden=false;$('rmi-empty').textContent='No image examples in this snapshot.';$('rmi-selected-readout').textContent='No image example is available.';return;}
 $('rmi-target').value=r.id;$('rmi-empty').hidden=true;$('rmi-image').hidden=false;$('rmi-image').src=rmiPath(r);$('rmi-image').alt=`${r.instrument||MISSIONS[state.mission].instrument} Remote Micro-Imager mosaic of ${r.target}, sol ${r.sol}; coloured circles locate archived LIBS spots`;
 $('rmi-source').href=r.image_url||r.source_image_url||rmiPath(r);$('rmi-source').hidden=false;
 const matched=r.points.filter(s=>s.point_id&&state.byId.has(s.point_id)).length;
 $('rmi-summary').textContent=`${r.target} · sol ${r.sol} · ${matched} matched compositions / ${r.points.length} annotated spots`;
 let method=r.coordinate_method||r.annotation_method||'Spot positions follow the archived image annotations.';if(typeof method!=='string')method=JSON.stringify(method);if(method==='official_PDS_RMI_mosaic_label_annotations_joined_by_SCLK')method='Spot coordinates come from the official PDS mosaic label, matched to the chemistry by spacecraft clock.';else if(method==='centers_of_official_PDS_annotation_crosshairs')method='Spot coordinates were digitized from crosshairs on the official PDS annotated mosaic.';else method=method.replaceAll('_',' ');if(r.coordinate_note)method+=' '+r.coordinate_note;
 const precision=r.coordinate_uncertainty_px;
 $('rmi-method').textContent=`${method}${(r.notes||[]).length?' '+r.notes.join(' '):''}${isNum(precision)?` Digitization precision: approximately ${precision} image ${precision===1?'pixel':'pixels'}; this is not the physical laser-pointing uncertainty.`:''}`;
 if(selectFirst){const first=r.points.find(s=>s.point_id&&state.byId.has(s.point_id));if(first)selectPoint(state.byId.get(first.point_id));}drawRMI();
}
function updateRMILocalReadout(){
 const r=state.rmi;if(!r)return;const spot=state.rmiMissingSpot||r.points.find(s=>s.point_id===state.selected?.id),box=$('rmi-selected-readout');
 if(!spot){box.textContent='Select a numbered spot in this image to inspect its composition.';return;}
 const p=state.byId.get(spot.point_id),o=state.oxide;
 if(!p){box.innerHTML=`<strong>Spot ${esc(spot.point??'—')}</strong> · No matched composition in the published archive. ${label(o)}, calibration RMSEP and shot SD are unavailable.`;return;}
 box.innerHTML=`<strong>Spot ${esc(spot.point??'—')} · ${esc(p.target)}</strong><br><span class="rmi-value">${label(o)} ${fmt(p.oxides?.[o])} wt%</span><span class="rmi-uncertainties">Calibration RMSEP: ${fmt(p.uncertainty?.rmsep?.[o])} wt% · Shot SD: ${fmt(p.uncertainty?.shot_sd?.[o])} wt%</span>`;
}
function chooseRMISpot(index){const spot=state.rmi?.points[index];if(!spot)return;const point=state.byId.get(spot.point_id);if(point){selectPoint(point);}else{state.rmiMissingSpot=spot;drawRMI();}}
function drawRMI(){
 const r=state.rmi;if(!r)return;updateRMILocalReadout();const svg=$('rmi-overlay'),image=$('rmi-image');
 const width=r.width||image.naturalWidth,height=r.height||image.naturalHeight;if(!width||!height)return;
 svg.setAttribute('viewBox',`0 0 ${width} ${height}`);svg.setAttribute('preserveAspectRatio','xMidYMid meet');
 const bounds=svg.getBoundingClientRect(),scale=Math.min(bounds.width/width,bounds.height/height)||1;
 const radius=9/scale,hitRadius=14/scale,font=11/scale;
 svg.innerHTML=r.points.filter(s=>isNum(s.x)&&isNum(s.y)).map(s=>{
  const point=state.byId.get(s.point_id),value=point?.oxides?.[state.oxide],selected=state.rmiMissingSpot?s===state.rmiMissingSpot:point&&point.id===state.selected?.id;
  const tooltip=`Spot ${s.point??'—'} · ${point?`${label(state.oxide)} ${fmt(value)} wt%`:'composition unavailable'}`;
  return `<g tabindex="0" role="button" data-rmi-index="${r.points.indexOf(s)}" ${point?`data-point="${esc(point.id)}"`:''} aria-label="${esc(tooltip)}" class="${selected?'selected-spot':''}"><title>${esc(tooltip)}</title>${selected?`<circle class="halo" cx="${s.x}" cy="${s.y}" r="${13/scale}" style="fill:none;stroke:#fff;stroke-width:${1.2/scale};stroke-dasharray:${3/scale} ${2/scale};pointer-events:none"/>`:''}<circle cx="${s.x}" cy="${s.y}" r="${radius}" fill="${colour(value)}" fill-opacity=".96" style="stroke:#fff;stroke-width:${(selected?2:1)/scale};pointer-events:none"/><text x="${s.x}" y="${s.y}" text-anchor="middle" dominant-baseline="central" font-size="${font}" style="stroke-width:${1.2/scale};pointer-events:none">${esc(s.point??'')}</text><circle class="spot-hit-target" cx="${s.x}" cy="${s.y}" r="${hitRadius}" style="fill:transparent;stroke:none;pointer-events:all"/></g>`;
 }).join('');
}
function updateProvenance(){
 const d=state.data,sourceDate=d.generated_at_utc||d.retrieved_at_utc||'Not recorded',withGeo=d.points.filter(p=>p.location&&isNum(p.location.lat)&&isNum(p.location.lon)&&!p.is_calibration).length,cal=d.points.filter(p=>p.is_calibration).length;
 $('snapshot-details').innerHTML=`<p><strong>${esc(d.instrument||MISSIONS[state.mission].instrument)}</strong> · ${int(d.points.length)} archived records, including ${int(cal)} onboard calibration records. ${int(withGeo)} Mars-target records have matched rover positions. ${d.archive_version?`Archive: ${esc(archiveLabel(d))}.`:''} Prepared ${esc(sourceDate)}.</p>${(d.notes||[]).map(n=>`<p>${esc(typeof n==='string'?n:JSON.stringify(n))}</p>`).join('')}`;
 const src=d.sources||[];const mains=src.filter(s=>/moc|master|obs|waypoint|interp|userguide|release|archsis/i.test(`${s.id} ${s.url}`));
 const shown=(mains.length?mains:src).slice(0,8);
 $('source-links').innerHTML=`<ul class="source-list">${shown.map(s=>`<li><a href="${esc(s.url||s.source_url||'#')}" target="_blank" rel="noopener">${esc(s.title||s.id||String(s.url).split('/').pop())} <svg class="arrow-icon" viewBox="0 0 14 14" width="12" height="12" aria-hidden="true"><path d="M2 12 12 2M3 2h9v9" fill="none" stroke="currentColor" stroke-width="1.3"/></svg></a>${s.version?` · version ${esc(s.version)}`:''}</li>`).join('')}</ul>${src.length>shown.length?`<p>${src.length-shown.length} additional source entries, with URLs and checksums, are retained in <a href="data/${state.mission}.json" target="_blank" rel="noopener">the snapshot metadata</a>.</p>`:''}`;
}
function download(filename,content,type){const blob=new Blob([content],{type}),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=filename;document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),10000);}
function csvField(value){if(value===null||value===undefined)return '';let s=String(value);if(typeof value==='string'&&/^[=+@-]/.test(s))s="'"+s;return /[",\r\n]/.test(s)?'"'+s.replaceAll('"','""')+'"':s;}
function exportCSV(){
 if(!state.data)return;const oxides=state.data.oxides;
 const headers=['id','mission','instrument','sol','sequence','point_or_order','point_index_kind','target','target_type','is_calibration','distance_m',...oxides.map(o=>o+'_wt_pct'),...oxides.map(o=>o+'_rmsep_wt_pct'),...oxides.map(o=>o+'_shot_sd_wt_pct'),'reported_total_wt_pct','spectrum_total','rover_latitude','rover_east_longitude','rover_elevation_m','position_kind','position_source','site','drive','quality_flags','archive_notes','source_id','source_row','source_rows','source_url'];
 const lines=[headers.join(',')];for(const p of state.filtered){const l=p.location||{},source=findSource(p);const row=[p.id,p.mission,p.instrument,p.sol,p.sequence,p.point,p.point_index_kind,p.target,p.target_type,!!p.is_calibration,p.distance_m,...oxides.map(o=>p.oxides?.[o]),...oxides.map(o=>p.uncertainty?.rmsep?.[o]),...oxides.map(o=>p.uncertainty?.shot_sd?.[o]),p.total_wt_pct,p.spectrum_total,l.lat,l.lon,l.elevation_m,l.kind,l.source,p.site??l.site,p.drive??l.drive,flagText(p).join('; '),[p.archive_comment,p.archive_saturation,p.quality_notes?JSON.stringify(p.quality_notes):null].filter(Boolean).join('; '),p.source_id,p.source_row,(p.source_rows||[p.source_row]).filter(Boolean).join('; '),p.source_url||source?.url];lines.push(row.map(csvField).join(','));}
 download(`mars-libs-${state.mission}-filtered.csv`,'\uFEFF'+lines.join('\r\n'),'text/csv;charset=utf-8');toast(`Downloaded ${int(state.filtered.length)} records with all reported oxides and uncertainties.`);
}
function svgText(x,y,text,options=''){return `<text x="${x}" y="${y}" ${options}>${esc(text)}</text>`;}
function exportPlot(which){
 if(which==='map'){atlas.exportMap();return;}
 const g=which==='map'?state.mapGeometry:state.scatterGeometry;if(!g){toast('No plotted data to export.');return;}const p=palette(),extra=75,w=g.w,h=g.h+extra;
 const parts=[`<svg xmlns="http://www.w3.org/2000/svg" width="${w}" height="${h}" viewBox="0 0 ${w} ${h}"><title>${esc(MISSIONS[state.mission].instrument)} ${which==='map'?'rover-position map':'composition plot'}</title><rect width="100%" height="100%" fill="${p.paper}"/><g font-family="monospace" font-size="10" fill="${p.muted}">`];
 for(const v of g.xt){const x=g.xp(v);parts.push(`<path d="M${x},${g.top}V${g.top+g.ph}" fill="none" stroke="${p.line}" stroke-width=".6"/>`,svgText(x,g.top+g.ph+20,which==='map'?v.toFixed(4):fmt(v,g.xkey==='sol'?0:1),'text-anchor="middle"'));}
 for(const v of g.yt){const y=g.yp(v);parts.push(`<path d="M${g.left},${y}H${g.left+g.pw}" fill="none" stroke="${p.line}" stroke-width=".6"/>`,svgText(g.left-9,y+3,which==='map'?v.toFixed(4):fmt(v,1),'text-anchor="end"'));}
 parts.push(svgText(g.left+g.pw/2,g.h-10,which==='map'?'East longitude (°)':plotAxisLabel(g.xkey),'text-anchor="middle"'),`<text transform="translate(14 ${g.top+g.ph/2}) rotate(-90)" text-anchor="middle">${esc(which==='map'?'Latitude (°)':plotAxisLabel(g.ykey))}</text></g>`);
 for(const point of g.projected){const value=which==='map'?point.value:point.point.oxides?.[state.oxide];parts.push(`<circle cx="${point.x.toFixed(2)}" cy="${point.y.toFixed(2)}" r="${which==='map'?point.radius.toFixed(2):2}" fill="${colour(value)}" fill-opacity="${which==='map'?1:.55}"><title>${esc(which==='map'?`${point.points.length} measurements; median ${fmt(value)} wt%`:`${point.point.target}; sol ${point.point.sol}; ${fmt(value)} wt%`)}</title></circle>`);}
 parts.push(`<g fill="${p.ink}" font-family="monospace" font-size="10">`,svgText(15,g.h+18,`${MISSIONS[state.mission].instrument} · ${label(state.oxide)} colour scale: ${fmt(state.colourMin)}–${fmt(state.colourMax)} wt%`),svgText(15,g.h+35,which==='map'?'Rover-position proxies; marker colour = median. No spatial interpolation.':'One point per archived estimate. Totals and concentrations are not renormalized.'),svgText(15,g.h+52,`NASA PDS · snapshot ${String(state.data.generated_at_utc||'').slice(0,10)} · ${state.filtered.length} filtered records`),'</g></svg>');
 download(`mars-libs-${state.mission}-${which}-${state.oxide}.svg`,parts.join(''),'image/svg+xml');toast('Plot exported as an editable SVG.');
}
// Inputs and linked views.
document.querySelectorAll('.theme-switch button').forEach(b=>b.addEventListener('click',()=>setTheme(b.dataset.theme)));
document.querySelectorAll('[data-mission]').forEach(b=>b.addEventListener('click',()=>{if(b.dataset.mission!==state.mission)switchMission(b.dataset.mission);}));
function changeOxide(value){const selected=state.selected,missing=state.rmiMissingSpot;state.oxide=value;$('oxide').value=value;$('rmi-oxide').value=value;applyFilters();if(selected&&state.rmi?.points.some(s=>s.point_id===selected.id))selectPoint(selected);if(missing){state.rmiMissingSpot=missing;drawRMI();}}
$('oxide').addEventListener('change',()=>changeOxide($('oxide').value));$('rmi-oxide').addEventListener('change',()=>changeOxide($('rmi-oxide').value));
['sol-min','sol-max','include-calibration','exclude-flagged'].forEach(id=>$(id).addEventListener('change',applyFilters));
let searchTimer;$('search').addEventListener('input',()=>{clearTimeout(searchTimer);searchTimer=setTimeout(applyFilters,180);});
$('reset-filters').addEventListener('click',()=>{resetInputs();applyFilters();});
$('prev-page').addEventListener('click',()=>{state.page--;renderTable();});$('next-page').addEventListener('click',()=>{state.page++;renderTable();});
$('measurements').addEventListener('click',event=>{const b=event.target.closest('.select-record');if(b)selectPoint(state.byId.get(b.dataset.id));});
$('location-points').addEventListener('change',()=>selectPoint(state.byId.get($('location-points').value)));$('clear-location').addEventListener('click',()=>$('location-picker').hidden=true);
$('rmi-target').addEventListener('change',()=>chooseRMI($('rmi-target').value,true));$('rmi-image').addEventListener('load',drawRMI);
$('rmi-image').addEventListener('error',()=>{$('rmi-empty').hidden=false;$('rmi-empty').textContent='The image could not be loaded. Open the original archive image using the link below.';});
$('rmi-overlay').addEventListener('click',event=>{const g=event.target.closest('[data-rmi-index]');if(g)chooseRMISpot(Number(g.dataset.rmiIndex));});
$('rmi-overlay').addEventListener('keydown',event=>{if(event.key==='Enter'||event.key===' '){const g=event.target.closest('[data-rmi-index]');if(g){event.preventDefault();chooseRMISpot(Number(g.dataset.rmiIndex));}}});
$('filter-rmi').addEventListener('click',()=>{if(!state.rmi)return;const firstMatched=state.rmi.points.map(s=>state.byId.get(s.point_id)).find(Boolean);$('search').value=firstMatched?.target||state.rmi.target||'';$('sol-min').value=state.rmi.sol;$('sol-max').value=state.rmi.sol;applyFilters();$('measurements').scrollIntoView({behavior:'smooth',block:'start'});});
['scatter-x','scatter-y'].forEach(id=>$(id).addEventListener('change',drawScatter));
$('export-csv').addEventListener('click',exportCSV);$('export-map').addEventListener('click',()=>exportPlot('map'));$('export-scatter').addEventListener('click',()=>exportPlot('scatter'));
$('scatter-canvas').addEventListener('click',event=>{const {x,y}=mousePoint(event,$('scatter-canvas')),g=nearestScatter(x,y);if(g)selectPoint(g.point);});
let mapHoverFrame=0,scatterHoverFrame=0;
$('scatter-canvas').addEventListener('mousemove',event=>{cancelAnimationFrame(scatterHoverFrame);scatterHoverFrame=requestAnimationFrame(()=>{const {x,y}=mousePoint(event,$('scatter-canvas')),g=nearestScatter(x,y);if(g)showTooltip($('scatter-tooltip'),`<strong>${esc(g.point.target)}</strong><br>Sol ${esc(g.point.sol)} · point/order ${esc(g.point.point??'—')}<br>${label(state.oxide)}: ${fmt(g.point.oxides?.[state.oxide])} wt%`,x,y,state.scatterGeometry.w);else $('scatter-tooltip').hidden=true;});});
$('map-canvas').addEventListener('mouseleave',()=>$('map-tooltip').hidden=true);$('scatter-canvas').addEventListener('mouseleave',()=>$('scatter-tooltip').hidden=true);
let resizeTimer;new ResizeObserver(()=>{clearTimeout(resizeTimer);resizeTimer=setTimeout(()=>{if(state.data){drawMap();drawScatter();drawRMI();}},100);}).observe($('map-canvas').parentElement);
window.addEventListener('resize',()=>{clearTimeout(resizeTimer);resizeTimer=setTimeout(()=>{if(state.data){drawMap();drawScatter();drawRMI();}},100);});
try{const saved=localStorage.getItem('mars-libs-theme');if(['light','dark','auto'].includes(saved))setTheme(saved);}catch{}
window.matchMedia?.('(prefers-color-scheme: dark)').addEventListener('change',()=>{if(document.documentElement.dataset.theme==='auto'&&state.data){drawMap();drawScatter();}});
// A GitHub Pages export downloads its source from the actual hosting repository.
const githubHost=location.hostname.match(/^([a-z0-9-]+)\.github\.io$/i);
if(githubHost){
 const owner=githubHost[1],firstSegment=location.pathname.split('/').filter(Boolean)[0];
 const repository=!firstSegment||/\.html?$/i.test(firstSegment)?`${owner}.github.io`:decodeURIComponent(firstSegment);
 const projectLink=$('project-download');
 if(projectLink){projectLink.href=`https://github.com/${encodeURIComponent(owner)}/${encodeURIComponent(repository)}/archive/refs/heads/main.zip`;projectLink.removeAttribute('download');}
}
// Reassemble the complete portable project from verified static transport parts.
if(!githubHost){const link=$('project-download');link.href='docs/SCHEDULED_UPDATES.md';link.textContent='GitHub setup & updates ↗';link.removeAttribute('download');link.target='_blank';link.rel='noopener';}
switchMission('chemcam');
})();
