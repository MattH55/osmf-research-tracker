const API='http://localhost:8000/api';
let cd=[],cs={field:'procedure_name',asc:true},map,mm={};
const LS=['Fully_Approved','Regulated_Therapy_Program','Decriminalized_Possession','Right_To_Try','Clinical_Trial_Only','Physician_Discretion_Gray','Prohibited'];
const OQ=['High','Medium','Low','Variable'];
const MOD=['Psychedelics','Gene_Therapy','Stem_Cell','Peptide','Repurposed_Drug','Reproductive_Tech','Assisted_Dying','Other'];
const JT=['Country','US_State','ZEDE','Province','Territory','Federal'];

document.addEventListener('DOMContentLoaded',()=>{
  map=L.map('map').setView([30,0],2);
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',{attribution:'&copy; OSM',maxZoom:18}).addTo(map);
  lfo();fd();pad();
  if(localStorage.getItem('mt')==='dark'){document.documentElement.setAttribute('data-theme','dark');document.getElementById('tb').textContent='☀️'}
});

function toggleTheme(){const h=document.documentElement,i=h.getAttribute('data-theme')==='dark';h.setAttribute('data-theme',i?'light':'dark');localStorage.setItem('mt',i?'light':'dark');document.getElementById('tb').textContent=i?'🌙':'☀️'}
function sv(v){document.getElementById('vp').classList.toggle('hidden',v!=='public');document.getElementById('va').classList.toggle('hidden',v!=='admin');if(v==='public'){map.invalidateSize();fd()}else lad()}
function tst(m,t='success'){const e=document.createElement('div');e.className='toast t'+(t==='success'?'s':'e');e.textContent=m;document.body.appendChild(e);setTimeout(()=>e.remove(),3000)}

function goc(q){const c={High:'#059669',Medium:'#d97706',Low:'#dc2626',Variable:'#7c3aed'};return c[q]||'#6b7280'}
function umm(d){
  Object.values(mm).forEach(m=>map.removeLayer(m));mm={};
  const g={};d.forEach(r=>{const j=r.jurisdiction_id;if(!g[j])g[j]={n:r.jurisdiction_name,la:r.jurisdiction_latitude,lo:r.jurisdiction_longitude,recs:[],os:new Set()};g[j].recs.push(r);if(r.oversight_quality)g[j].os.add(r.oversight_quality)});
  Object.entries(g).forEach(([jid,gr])=>{if(!gr.la||!gr.lo)return;const oa=[...gr.os];const c=oa.length===1?goc(oa[0]):'#6b7280';
    const m=L.circleMarker([gr.la,gr.lo],{radius:10,fillColor:c,color:'#fff',weight:1.5,fillOpacity:0.85}).addTo(map).bindTooltip('<b>'+esc(gr.n)+'</b><br>'+gr.recs.length+' record(s)',{direction:'top'});
    m.on('click',()=>{cd=gr.recs;rt(gr.recs);document.getElementById('ml').textContent=gr.n;document.getElementById('mb').classList.remove('hidden');map.setView([gr.la,gr.lo],5)});
    mm[jid]=m;
  });
}

async function fd(){
  document.getElementById('tbdy').innerHTML='<tr><td colspan="7" class="loading">Loading...</td></tr>';
  try{const r=await fetch(API+'/access-records/query',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({status:'active'})});
    cd=await r.json();rt(cd);umm(cd);document.getElementById('mb').classList.add('hidden')}
  catch(e){document.getElementById('tbdy').innerHTML='<tr><td colspan="7" class="empty">Error loading data. Is the backend running on port 8000?</td></tr>'}
}

async function af(){
  const body={status:'active'};
  const m=document.getElementById('fm').value;if(m)body.modality=[m];
  const t=document.getElementById('ft').value;if(t)body.therapeutic_area=t;
  const l=document.getElementById('fl').value;if(l)body.legal_status=[l];
  const o=document.getElementById('fo').value;if(o)body.oversight_quality=[o];
  const s=document.getElementById('si').value.trim();if(s)body.search=s;
  try{const r=await fetch(API+'/access-records/query',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
    cd=await r.json();rt(cd);umm(cd)}
  catch(e){tst('Filter error','error')}
}

async function lfo(){
  try{const r=await fetch(API+'/filters/options'),o=await r.json();
    const fls=(id,it,vf,nf)=>{const s=document.getElementById(id);s.innerHTML='<option value="">All</option>';it.forEach(i=>{const op=document.createElement('option');op.value=vf(i);op.textContent=nf(i);s.appendChild(op)})};
    fls('fm',o.modalities||[],x=>x,x=>x.replace(/_/g,' '));
    fls('ft',o.therapeutic_areas||[],x=>x,x=>x.replace(/_/g,' '));
    fls('fl',o.legal_statuses||[],x=>x,x=>x.replace(/_/g,' '));
    fls('fo',o.oversight_qualities||[],x=>x,x=>x);
  }catch(e){}
}
function cf(){['fm','ft','fl','fo'].forEach(i=>document.getElementById(i).value='');document.getElementById('si').value='';fd()}

function rt(d){
  const s=[...d].sort((a,b)=>{const v=(a[cs.field]||'').toString().toLowerCase(),w=(b[cs.field]||'').toString().toLowerCase();return cs.asc?v.localeCompare(w):w.localeCompare(v)});
  document.getElementById('rc').textContent=s.length+' record'+(s.length!==1?'s':'');
  const t=document.getElementById('tbdy');
  if(!s.length){t.innerHTML='<tr><td colspan="7" class="empty">No results match your filters.</td></tr>';return}
  t.innerHTML=s.map(r=>'<tr class="ptr" onclick="sd(\''+r.id+'\')"><td>'+esc(r.procedure_name)+'</td><td>'+esc(r.jurisdiction_name)+'</td><td><span class="badge bg-'+r.legal_status+'">'+(r.legal_status||'').replace(/_/g,' ')+'</span></td><td>'+(r.oversight_quality?'<span class="badge bg-'+r.oversight_quality+'">'+r.oversight_quality+'</span>':'—')+'</td><td>'+esc(r.estimated_cost_range_usd||'—')+'</td><td><span class="badge bg-'+r.modality+'">'+(r.modality||'').replace(/_/g,' ')+'</span></td><td><button class="btnsm btn2" onclick="event.stopPropagation();sd(\''+r.id+'\')">📋</button></td></tr>').join('');
}
function st(f){if(cs.field===f)cs.asc=!cs.asc;else{cs.field=f;cs.asc=true}rt(cd)}

function sd(id){const r=cd.find(d=>d.id===id);if(!r){tst('Record not found','error');return}
  const fs=v=>v?v.replace(/_/g,' '):'';
  document.getElementById('dc').innerHTML='<h3>'+esc(r.procedure_name)+'<br><small style="color:var(--txt2);font-size:.875rem">in '+esc(r.jurisdiction_name)+'</small></h3><div class="mgrid"><div class="ms"><strong>Legal Status</strong><p><span class="badge bg-'+r.legal_status+'">'+fs(r.legal_status)+'</span></p></div><div class="ms"><strong>Oversight</strong><p>'+(r.oversight_quality?'<span class="badge bg-'+r.oversight_quality+'">'+r.oversight_quality+'</span>':'—')+'</p></div><div class="ms"><strong>Modality</strong><p><span class="badge bg-'+r.modality+'">'+fs(r.modality)+'</span></p></div><div class="ms"><strong>Cost (USD)</strong><p>'+esc(r.estimated_cost_range_usd||'—')+'</p></div></div>'+
  (r.access_pathway_details?'<h4>Access Pathway</h4><p style="font-size:.875rem">'+esc(r.access_pathway_details)+'</p>':'')+
  (r.eligibility_requirements?'<h4>Eligibility</h4><p style="font-size:.875rem">'+esc(r.eligibility_requirements)+'</p>':'')+
  (r.provider_requirements?'<h4>Provider Requirements</h4><p style="font-size:.875rem">'+esc(r.provider_requirements)+'</p>':'')+
  (r.residency_travel_notes?'<h4>Residency/Travel</h4><p style="font-size:.875rem">'+esc(r.residency_travel_notes)+'</p>':'')+
  (r.risk_notes?'<h4>Risk Notes</h4><p style="font-size:.875rem;color:var(--danger)">'+esc(r.risk_notes)+'</p>':'')+
  (r.arbitrage_summary?'<h4>💡 Arbitrage Summary</h4><p style="font-size:.875rem;background:var(--bg2);padding:.75rem;border-radius:var(--rad)">'+esc(r.arbitrage_summary)+'</p>':'')+
  (r.oversight_notes?'<h4>Oversight Notes</h4><p style="font-size:.875rem">'+esc(r.oversight_notes)+'</p>':'')+
  (r.cost_notes?'<h4>Cost Notes</h4><p style="font-size:.875rem">'+esc(r.cost_notes)+'</p>':'')+
  (r.last_verified?'<div class="ms"><strong>Last Verified</strong><p>'+r.last_verified+'</p></div>':'')+
  (r.sources&&r.sources.length?'<div class="msrc"><strong>Sources:</strong><ul style="margin:.25rem 0 0 1.25rem;font-size:.8125rem">'+r.sources.map(s=>'<li><a href="'+esc(s.url)+'" target="_blank" rel="noopener">'+esc(s.title)+'</a></li>').join('')+'</ul></div>':'');
  document.getElementById('dm').classList.remove('hidden');
}
function cd2(){document.getElementById('dm').classList.add('hidden')}
document.getElementById('dm').addEventListener('click',function(e){if(e.target===this)cd2()});

function expCSV(){
  const hd=['Procedure','Jurisdiction','Legal Status','Oversight','Cost (USD)','Modality','Access Pathway','Eligibility','Provider','Residency/Travel','Risk','Last Verified','Arbitrage Summary'];
  const rows=cd.map(r=>[r.procedure_name,r.jurisdiction_name,(r.legal_status||'').replace(/_/g,' '),r.oversight_quality||'',r.estimated_cost_range_usd||'',(r.modality||'').replace(/_/g,' '),r.access_pathway_details||'',r.eligibility_requirements||'',r.provider_requirements||'',r.residency_travel_notes||'',r.risk_notes||'',r.last_verified||'',r.arbitrage_summary||''].map(v=>'"'+String(v).replace(/"/g,'""')+'"'));
  dlBlob([hd.join(','),...rows.map(r=>r.join(','))].join('\n'),'medfreedom.csv','text/csv');
}
function expJSON(){dlBlob(JSON.stringify(cd,null,2),'medfreedom.json','application/json')}
function dlBlob(c,f,m){const b=new Blob([c],{type:m}),u=URL.createObjectURL(b),a=document.createElement('a');a.href=u;a.download=f;a.click();URL.revokeObjectURL(u)}

function pad(){
  document.getElementById('rls').innerHTML=LS.map(s=>'<option value="'+s+'">'+s.replace(/_/g,' ')+'</option>').join('');
  document.getElementById('roq').innerHTML='<option value="">—</option>'+OQ.map(s=>'<option value="'+s+'">'+s+'</option>').join('');
  document.getElementById('pm').innerHTML=MOD.map(m=>'<option value="'+m+'">'+m.replace(/_/g,' ')+'</option>').join('');
  document.getElementById('jty').innerHTML=JT.map(t=>'<option value="'+t+'">'+t.replace(/_/g,' ')+'</option>').join('');
  lrd();
}
async function lrd(){
  try{const[pr,jr]=await Promise.all([fetch(API+'/procedures'),fetch(API+'/jurisdictions')]);
    const p=await pr.json(),j=await jr.json();
    document.getElementById('rpid').innerHTML=p.map(i=>'<option value="'+i.id+'">'+i.name+'</option>').join('');
    document.getElementById('rjid').innerHTML=j.map(i=>'<option value="'+i.id+'">'+i.name+'</option>').join('');
  }catch(e){}
}
async function lad(){Promise.all([lar(),lap(),laj()])}
async function lar(){
  try{const r=await fetch(API+'/access-records'),d=await r.json();
    document.getElementById('atb').innerHTML=d.length?d.map(r=>'<tr><td>'+esc(r.procedure_name)+'</td><td>'+esc(r.jurisdiction_name)+'</td><td><span class="badge bg-'+r.legal_status+'">'+(r.legal_status||'').replace(/_/g,' ')+'</span></td><td>'+(r.oversight_quality?'<span class="badge bg-'+r.oversight_quality+'">'+r.oversight_quality+'</span>':'—')+'</td><td>'+esc(r.estimated_cost_range_usd||'—')+'</td><td><div class="actb"><button class="btnsm btn2" onclick="er(\''+r.id+'\')">Edit</button><button class="btnsm btn3" onclick="delR(\''+r.id+'\')">Del</button></div></td></tr>').join(''):'<tr><td colspan="6" class="empty">No records</td></tr>'}
  catch(e){tst('Failed to load records','error')}
}
async function lap(){
  try{const r=await fetch(API+'/procedures'),d=await r.json();
    document.getElementById('apb').innerHTML=d.length?d.map(p=>'<tr><td>'+esc(p.name)+'</td><td><span class="badge bg-'+p.modality+'">'+(p.modality||'').replace(/_/g,' ')+'</span></td><td>'+esc(p.subcategory||'—')+'</td><td>'+(p.therapeutic_areas||[]).join(', ')+'</td><td><div class="actb"><button class="btnsm btn2" onclick="ep(\''+p.id+'\')">Edit</button><button class="btnsm btn3" onclick="delP(\''+p.id+'\')">Del</button></div></td></tr>').join(''):'<tr><td colspan="5" class="empty">No procedures</td></tr>'}
  catch(e){tst('Failed to load procedures','error')}
}
async function laj(){
  try{const r=await fetch(API+'/jurisdictions'),d=await r.json();
    document.getElementById('ajb').innerHTML=d.length?d.map(j=>'<tr><td>'+esc(j.name)+'</td><td>'+esc(j.type)+'</td><td>'+esc(j.country_code)+'</td><td>'+(j.latitude!=null?j.latitude.toFixed(2):'—')+', '+(j.longitude!=null?j.longitude.toFixed(2):'—')+'</td><td><div class="actb"><button class="btnsm btn2" onclick="ej(\''+j.id+'\')">Edit</button><button class="btnsm btn3" onclick="delJ(\''+j.id+'\')">Del</button></div></td></tr>').join(''):'<tr><td colspan="5" class="empty">No jurisdictions</td></tr>'}
  catch(e){tst('Failed to load jurisdictions','error')}
}

async function saveR(e){e.preventDefault();
  const id=document.getElementById('rid').value;
  const body={procedure_id:document.getElementById('rpid').value,jurisdiction_id:document.getElementById('rjid').value,legal_status:document.getElementById('rls').value,oversight_quality:document.getElementById('roq').value||null,estimated_cost_range_usd:document.getElementById('rcr').value||null,last_verified:document.getElementById('rlv').value||null,access_pathway_details:document.getElementById('rap').value||null,eligibility_requirements:document.getElementById('rel').value||null,provider_requirements:document.getElementById('rpr').value||null,residency_travel_notes:document.getElementById('rrn').value||null,risk_notes:document.getElementById('rrk').value||null,arbitrage_summary:document.getElementById('ras').value||null,oversight_notes:document.getElementById('ron').value||null,cost_notes:document.getElementById('rcn').value||null,sources:[]};
  const url=id?API+'/access-records/'+id:API+'/access-records',m=id?'PUT':'POST';
  try{const r=await fetch(url,{method:m,headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});if(!r.ok)throw new Error();tst(id?'Record updated':'Record created');resetRF();lar();fd()}catch(e){tst('Failed','error')}
}
async function er(id){
  try{const r=await fetch(API+'/access-records/'+id),d=await r.json();
    document.getElementById('rt').textContent='Edit Access Record';document.getElementById('rid').value=d.id;
    document.getElementById('rpid').value=d.procedure_id;document.getElementById('rjid').value=d.jurisdiction_id;
    document.getElementById('rls').value=d.legal_status;document.getElementById('roq').value=d.oversight_quality||'';
    document.getElementById('rcr').value=d.estimated_cost_range_usd||'';document.getElementById('rlv').value=d.last_verified||'';
    document.getElementById('rap').value=d.access_pathway_details||'';document.getElementById('rel').value=d.eligibility_requirements||'';
    document.getElementById('rpr').value=d.provider_requirements||'';document.getElementById('rrn').value=d.residency_travel_notes||'';
    document.getElementById('rrk').value=d.risk_notes||'';document.getElementById('ras').value=d.arbitrage_summary||'';
    document.getElementById('ron').value=d.oversight_notes||'';document.getElementById('rcn').value=d.cost_notes||'';
    sat('records');
  }catch(e){tst('Failed to load','error')}
}
async function delR(id){if(!confirm('Delete?'))return;try{await fetch(API+'/access-records/'+id,{method:'DELETE'});tst('Deleted');lar();fd()}catch(e){tst('Failed','error')}}
function resetRF(){document.getElementById('rt').textContent='Add Access Record';document.getElementById('rid').value='';document.getElementById('rf').reset()}

async function saveP(e){e.preventDefault();
  const id=document.getElementById('pid').value,tas=document.getElementById('pta').value;
  const body={name:document.getElementById('pn').value,modality:document.getElementById('pm').value,subcategory:document.getElementById('ps').value||null,therapeutic_areas:tas?tas.split(',').map(s=>s.trim()).filter(Boolean):[],description:document.getElementById('pd').value||null,typical_us_cost_range:document.getElementById('pc').value||null,indications:document.getElementById('pin').value||null,sources:[]};
  const url=id?API+'/procedures/'+id:API+'/procedures',m=id?'PUT':'POST';
  try{const r=await fetch(url,{method:m,headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});if(!r.ok)throw new Error();tst(id?'Updated':'Created');resetPF();lap();lrd();fd()}catch(e){tst('Failed','error')}
}
async function ep(id){try{const r=await fetch(API+'/procedures/'+id),p=await r.json();document.getElementById('pt').textContent='Edit Procedure';document.getElementById('pid').value=p.id;document.getElementById('pn').value=p.name;document.getElementById('pm').value=p.modality;document.getElementById('ps').value=p.subcategory||'';document.getElementById('pc').value=p.typical_us_cost_range||'';document.getElementById('pta').value=(p.therapeutic_areas||[]).join(', ');document.getElementById('pd').value=p.description||'';document.getElementById('pin').value=p.indications||'';sat('procedures')}catch(e){tst('Failed','error')}}
async function delP(id){if(!confirm('Delete procedure and ALL its access records?'))return;try{await fetch(API+'/procedures/'+id,{method:'DELETE'});tst('Deleted');lap();fd()}catch(e){tst('Failed','error')}}
function resetPF(){document.getElementById('pt').textContent='Add Procedure';document.getElementById('pid').value='';document.getElementById('pf').reset()}

async function saveJ(e){e.preventDefault();
  const id=document.getElementById('jid').value;
  const body={name:document.getElementById('jn').value,type:document.getElementById('jty').value,country_code:document.getElementById('jcc').value,latitude:document.getElementById('jla').value?parseFloat(document.getElementById('jla').value):null,longitude:document.getElementById('jlo').value?parseFloat(document.getElementById('jlo').value):null,general_notes:document.getElementById('jno').value||null};
  const url=id?API+'/jurisdictions/'+id:API+'/jurisdictions',m=id?'PUT':'POST';
  try{const r=await fetch(url,{method:m,headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});if(!r.ok)throw new Error();tst(id?'Updated':'Created');resetJF();laj();lrd();fd()}catch(e){tst('Failed','error')}
}
async function ej(id){try{const r=await fetch(API+'/jurisdictions/'+id),j=await r.json();document.getElementById('jt').textContent='Edit Jurisdiction';document.getElementById('jid').value=j.id;document.getElementById('jn').value=j.name;document.getElementById('jty').value=j.type;document.getElementById('jcc').value=j.country_code;document.getElementById('jla').value=j.latitude!=null?j.latitude:'';document.getElementById('jlo').value=j.longitude!=null?j.longitude:'';document.getElementById('jno').value=j.general_notes||'';sat('jurisdictions')}catch(e){tst('Failed','error')}}
async function delJ(id){if(!confirm('Delete jurisdiction and ALL its records?'))return;try{await fetch(API+'/jurisdictions/'+id,{method:'DELETE'});tst('Deleted');laj();fd()}catch(e){tst('Failed','error')}}
function resetJF(){document.getElementById('jt').textContent='Add Jurisdiction';document.getElementById('jid').value='';document.getElementById('jf').reset()}

function sat(t){['records','procedures','jurisdictions','import'].forEach(x=>{document.getElementById('a'+x.charAt(0)).classList.toggle('hidden',x!==t);document.getElementById('t'+x.charAt(0)).classList.toggle('active',x===t)})}

async function bi(){const tx=document.getElementById('bit').value.trim();if(!tx){tst('Paste JSON first','error');return}
  try{const d=JSON.parse(tx);const r=await fetch(API+'/bulk-import',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(d)});const res=await r.json();document.getElementById('bir').innerHTML='<span style="color:var(--success)">✓ Imported: '+res.created.jurisdictions+' jurisdictions, '+res.created.procedures+' procedures, '+res.created.access_records+' records</span>';lad();lrd();fd()}catch(e){document.getElementById('bir').innerHTML='<span style="color:var(--danger)">Error: '+e.message+'</span>'}
}

function esc(s){if(!s)return'';const d=document.createElement('div');d.textContent=s;return d.innerHTML}