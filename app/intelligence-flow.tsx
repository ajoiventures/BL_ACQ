'use client';
import {useEffect,useRef,useState} from 'react';
import Link from 'next/link';
import haines from '../docs/intelligence-flow/haines-source.json';
import duke from '../docs/intelligence-flow/duke-source.json';

type Claim={claim:string;quote:string;claim_id?:string;evidence_state?:string};
type Packet={request_id:string;source_key:string;security_domain:string;source_url:string;title:string;content:string;capture_kind:string;published_at:string|null;event_at:string|null;topic_tags:string[];source_claims:Claim[]};
type Source=Packet&{source_id:string;revision:number;observed_at:string;content_sha256:string};
type Digest={source_claims:Claim[];implications:string[];unknowns:string[];method:string};
type Action={action_id:string;title:string;proposed_role:string;state:string;acknowledged_owner:string|null};
type Plan={plan_id:string;plan_sha256:string;source_revision:number;state:string;is_current?:boolean;links:{ticket_id:string;title:string;owner:string;leader:string;module:string;status:string}[];workers:{worker_id:string;specialist:string;leader:string;description:string}[];human_actions:Action[]};
type Run={run_id:string;plan_id:string;worker_id:string;attempt:number;state:string;mode:string;output:unknown;output_sha256:string;error:string|null};
type View={source:Source;digest:Digest;plans:Plan[];runs:Run[]};
type Summary={source_id:string;title:string;revision:number;security_domain:string;topic_tags:string[]};
const topics=['ECONOMIC_DEVELOPMENT','TOWN_GROWTH','MAIN_STREET','ACQUISITION','DATA_CENTER','CAPITAL','MACRO_FINANCIAL','INFORMATIONAL'];
const names:Record<string,string>={ECONOMIC_DEVELOPMENT:'Economic development',TOWN_GROWTH:'Town growth & migration',MAIN_STREET:'Main Street',ACQUISITION:'Acquisitions',DATA_CENTER:'Data center sites',CAPITAL:'Capital planning',MACRO_FINANCIAL:'Macro-financial intelligence',INFORMATIONAL:'Information only'};
const label=(s:string)=>s.toLowerCase().replaceAll('_',' ').replace(/^./,c=>c.toUpperCase());
const request=()=>crypto.randomUUID();
async function api(path:string,body?:unknown){
 const res=await fetch('/api/intelligence-flow'+path,body===undefined?{cache:'no-store'}:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
 const data=await res.json();if(!res.ok)throw Error(typeof data.detail==='string'?data.detail:JSON.stringify(data.detail));return data;
}

export default function IntelligenceFlow(){
 const [packet,setPacket]=useState<Packet>(haines);
 const [view,setView]=useState<View|null>(null),[sources,setSources]=useState<Summary[]>([]),[error,setError]=useState(''),[notice,setNotice]=useState(''),[busy,setBusy]=useState(false);
 const generation=useRef(0);
 const current=view?.plans.filter(p=>p.is_current!==false).at(-1);
 const currentRuns=view?.runs.filter(r=>r.plan_id===current?.plan_id)||[];
 const latestRuns=new Map<string,Run>();for(const run of currentRuns){if(!latestRuns.has(run.worker_id)||run.attempt>latestRuns.get(run.worker_id)!.attempt)latestRuns.set(run.worker_id,run);}
 const completedCurrent=Boolean(current?.workers.length)&&current!.workers.every(w=>latestRuns.get(w.worker_id)?.state==='COMPLETED');
 useEffect(()=>{api('').then(setSources).catch(e=>setError(e.message));},[]);
 function edit(next:Packet){generation.current++;setPacket(next);setView(null);setError('');setNotice('');}
 async function load(id:string){
  const token=++generation.current;setBusy(true);setError('');setNotice('');
  try{const data=await api('/'+encodeURIComponent(id));if(token===generation.current){setView(data);setPacket(data.source);}}
  catch(e){if(token===generation.current)setError((e as Error).message)}finally{setBusy(false)}
 }
 async function work(step:'capture'|'plan'|'release'){
  const token=++generation.current;setBusy(true);setError('');setNotice('');
  try{
   let id=view?.source.source_id;let releaseStatus:string|null=null;
   if(step==='capture'){
    const body={request_id:request(),source_key:packet.source_key,security_domain:packet.security_domain,source_url:packet.source_url,title:packet.title,content:packet.content,capture_kind:'EXCERPT_ONLY',published_at:packet.published_at||null,event_at:packet.event_at||null,topic_tags:packet.topic_tags,source_claims:packet.source_claims.map(({claim,quote})=>({claim,quote}))};
    const saved=await api('/capture',body);id=saved.source_id;
   }else if(step==='plan'&&view){
    await api('/'+id+'/plan',{request_id:request(),revision:view.source.revision,disposition:packet.topic_tags.every(t=>t==='INFORMATIONAL')?'INFORMATIONAL':'LINK_EXISTING'});
   }else if(step==='release'&&current){
    const released=await api('/'+id+'/release',{request_id:request(),plan_id:current.plan_id,plan_sha256:current.plan_sha256});releaseStatus=released.status;
   }
   if(id){const updated=await api('/'+id);if(token===generation.current){setView(updated);setNotice(step==='capture'?'Source excerpt captured. Its claims remain source reported.':step==='plan'?'Work linked to the existing ticket plan. Preparation is ready.':releaseStatus==='COMPLETED'?'Preparation completed. Review the results and proposed human actions below.':'Preparation needs attention. Inspect the failed run before continuing.');}}
   const list=await api('');if(token===generation.current)setSources(list);
  }catch(e){if(token===generation.current)setError((e as Error).message)}finally{setBusy(false)}
 }
 function claimEdit(index:number,key:'claim'|'quote',value:string){edit({...packet,source_claims:packet.source_claims.map((c,i)=>i===index?{...c,[key]:value}:c)});}
 return <div className="signal-flow">
  <section className="panel signal-intro"><div><span className="eyebrow">INFORMATION INTO ACTION</span><h2>One source. Connected work.</h2><p>Capture an article or research excerpt, preserve what it says, and connect it to the right projects. Run bounded preparation and see exactly what still needs a person.</p></div><Link href="/cities-planning">Open Cities & Planning →</Link></section>
  <div className="signal-steps" aria-label="Workflow"><span className={view?'complete':''}>1 · Capture source</span><span className={current?'complete':''}>2 · Prepare work</span><span className={completedCurrent?'complete':''}>3 · Run preparation</span><span>4 · Human action & review</span></div>
  <div className="signal-columns">
   <section className="panel signal-editor"><div className="panel-head"><h2>Source intake</h2><span className="tag">EXCERPT ONLY</span></div>
    <div className="signal-presets"><span>Try a real public source</span><button disabled={busy} onClick={()=>edit(haines)}>Haines City growth</button><button disabled={busy} onClick={()=>edit(duke)}>Florida site readiness</button></div>
    <form onSubmit={e=>{e.preventDefault();work('capture')}}>
     <label>Title<input required value={packet.title} disabled={busy} onChange={e=>edit({...packet,title:e.target.value})}/></label>
     <label>Source URL<input required type="url" value={packet.source_url} disabled={busy} onChange={e=>edit({...packet,source_url:e.target.value})}/></label>
     <div className="signal-fields"><label>Published on<input type="date" value={packet.published_at?.slice(0,10)||''} disabled={busy} onChange={e=>edit({...packet,published_at:e.target.value||null})}/></label><label>Event or observation date<input type="date" value={packet.event_at?.slice(0,10)||''} disabled={busy} onChange={e=>edit({...packet,event_at:e.target.value||null})}/></label></div>
     <label>Retained excerpt<textarea required rows={6} value={packet.content} disabled={busy} onChange={e=>edit({...packet,content:e.target.value})}/></label>
     <p className="muted">This saves supplied text and its receipt. The app does not fetch the whole article or verify every claim.</p>
     <fieldset className="signal-topics"><legend>Relevant workstreams</legend>{topics.map(t=><label key={t}><input type="checkbox" checked={packet.topic_tags.includes(t)} disabled={busy} onChange={e=>edit({...packet,topic_tags:e.target.checked?[...packet.topic_tags,t]:packet.topic_tags.filter(v=>v!==t)})}/>{names[t]}</label>)}</fieldset>
     <details><summary>Source claims and exact supporting passages</summary>{packet.source_claims.map((c,i)=><div className="signal-claim-edit" key={i}><label>Source-reported statement<textarea value={c.claim} disabled={busy} onChange={e=>claimEdit(i,'claim',e.target.value)}/></label><label>Exact passage in retained excerpt<textarea value={c.quote} disabled={busy} onChange={e=>claimEdit(i,'quote',e.target.value)}/></label><button type="button" disabled={busy} onClick={()=>edit({...packet,source_claims:packet.source_claims.filter((_,j)=>j!==i)})}>Remove statement</button></div>)}<button type="button" disabled={busy} onClick={()=>edit({...packet,source_claims:[...packet.source_claims,{claim:'',quote:''}]})}>Add statement</button><p>Passage matching confirms the text exists. It does not independently establish the statement’s meaning or accuracy.</p></details>
     <details><summary>Record and access settings</summary><label>Stable source reference<input required value={packet.source_key} disabled={busy} onChange={e=>edit({...packet,source_key:e.target.value})}/></label><label>Workspace domain<select value={packet.security_domain} disabled={busy} onChange={e=>edit({...packet,security_domain:e.target.value})}><option value="COMMERCIAL">Commercial</option><option value="MAIN_STREET_INSTITUTIONAL">Main Street institutional</option></select></label></details>
     <button className="primary" disabled={busy||packet.topic_tags.length===0}>{busy?'Working…':'Capture source'}</button>
    </form>
   </section>
   <section className="panel signal-digest"><div className="panel-head"><h2>Digest & next work</h2><span className="tag">LOCAL PREPARATION</span></div>
    {!view?<div className="signal-empty"><h3>Start with an evidence trail</h3><p>The town-growth example contains a Census table excerpt. It can trigger research into housing, migration and businesses while keeping the actual causes of growth unresolved.</p><p>Sources create research work within your chosen scope. They cannot change your acquisition budget or authorize an offer.</p></div>:<>
     <p className="muted">Revision {view.source.revision} · Captured {new Date(view.source.observed_at).toLocaleDateString()}</p>
     <h3>What the source reports</h3><ul>{view.digest.source_claims.map((c,i)=><li key={c.claim_id||i}>{c.claim}<small>Source reported · review pending</small></li>)}</ul>
     <h3>Potential relevance</h3><ul>{view.digest.implications.map((s,i)=><li key={i}>{s}</li>)}</ul>
     <h3>Evidence still needed</h3><ul>{view.digest.unknowns.map((s,i)=><li key={i}>{s}</li>)}</ul>
     <button className="primary" disabled={busy} onClick={()=>work('plan')}>Prepare linked work</button>
     {current&&<div className="signal-plan"><h3>Existing tickets</h3>{current.links.map((t,i)=><div className="signal-ticket" key={t.ticket_id+':'+i}><Link href={'/swarm?ticket='+t.ticket_id}>{t.ticket_id} · {t.title}</Link><small>{t.leader} / {t.owner} · {label(t.status)}</small></div>)}
      <h3>Bounded team assignments</h3>{current.workers.map(w=><p key={w.worker_id}><strong>{w.specialist}</strong> · {w.description}</p>)}
      <button className="primary" disabled={busy||current.workers.length===0} onClick={()=>work('release')}>Run preparation</button><p className="muted">Runs local evidence and readiness checks. Live AI research and continuous monitoring are not connected.</p>
     </div>}
    </>}
   </section>
  </div>
  {error&&<p className="alert error" role="alert">{error}</p>}{notice&&<p className="signal-notice" role="status">{notice}</p>}
  {view&&current&&<section className="panel signal-outcomes"><div className="panel-head"><h2>Results and human actions</h2><span className="badge">{currentRuns.length} current-plan runs</span></div><div className="signal-columns"><div><h3>Preparation receipts</h3>{currentRuns.length===0?<p>Preparation has not run for this source revision and plan.</p>:currentRuns.map(r=><details key={r.run_id}><summary>{label(r.worker_id)} · {label(r.state)} · attempt {r.attempt}</summary><p>{label(r.mode)}. Ticket acceptance and business execution remain separate.</p>{r.error&&<p className="alert error">{r.error}</p>}<pre>{JSON.stringify(r.output,null,2)}</pre><small className="signal-hash">Output receipt: {r.output_sha256}</small></details>)}</div><div><h3>Proposed human next actions</h3>{current.human_actions.map(a=><div className="signal-action" key={a.action_id}><strong>{a.title}</strong><small>{a.proposed_role} · {label(a.state)} · owner acknowledgment pending</small></div>)}<p>These are preparation actions. Sending messages, committing capital and approving transactions require their own authorization.</p></div></div><details><summary>Inspect complete history, including superseded plans and runs</summary><pre>{JSON.stringify(view,null,2)}</pre></details></section>}
  <section className="panel signal-history"><div className="panel-head"><h2>Captured sources</h2><span className="muted">Preserved across app reloads</span></div>{sources.length===0?<p>No sources captured yet.</p>:sources.map(s=><button key={s.source_id} disabled={busy} onClick={()=>load(s.source_id)}><strong>{s.title}</strong><small>Revision {s.revision} · {s.topic_tags.map(t=>names[t]||label(t)).join(' · ')}</small></button>)}</section>
 </div>
}
