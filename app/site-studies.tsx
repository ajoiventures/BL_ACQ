'use client';
import {useEffect, useState} from 'react';

type Study = {id:number; name:string; curriculum:string};
type Packet = {study:number; counts:Record<string,number>; ready:{id:string;title:string;owner:string}[]};
async function request(path:string, name?:string, curriculum="site") {
  const res=await fetch('/api/site-studies'+path, name===undefined?{cache:'no-store'}:{
    method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name,curriculum})
  });
  const data=await res.json();
  if(!res.ok) throw new Error(typeof data.detail==='string'?data.detail:'Study request failed');
  return data;
}
export default function SiteStudies(){
  const [studies,setStudies]=useState<Study[]>([]);
  const [curriculum,setCurriculum]=useState('site');
  const [packet,setPacket]=useState<Packet|null>(null);
  const [name,setName]=useState('');
  const [error,setError]=useState('');
  const [task,setTask]=useState('');
  const [source,setSource]=useState('');
  const [evidence,setEvidence]=useState('');
  const [reason,setReason]=useState('');
  const [receipt,setReceipt]=useState('');
  const [busy,setBusy]=useState(false);
  useEffect(()=>{request('').then(setStudies).catch(e=>setError(e.message))},[]);
  async function open(id?:number){
    setBusy(true);setError('');setTask('');setReceipt('');
    try{
      setPacket(id?await request('/'+id):await request('',name.trim(),curriculum));
      setStudies(await request(''));
    }catch(e){setError((e as Error).message)}finally{setBusy(false)}
  }
  async function submit(){
    if(!packet || !task)return;
    setBusy(true);setError('');
    try{
      const res=await fetch('/api/site-studies/'+packet.study+'/tasks/'+encodeURIComponent(task),{
        method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({action:'submit',source,text:evidence,reason})
      });
      const result=await res.json();
      if(!res.ok)throw new Error(typeof result.detail==='string'?result.detail:'Evidence submission failed');
      setReceipt(task+' submitted for independent review.');setTask('');setSource('');setEvidence('');setReason('');
      setPacket(await request('/'+packet.study));
    }catch(e){setError((e as Error).message)}finally{setBusy(false)}
  }
  return <section className="panel" style={{padding:'1.3rem',marginBottom:'1rem'}}>
    <h2>District studies</h2>
    <form className="toolbar" onSubmit={e=>{e.preventDefault();void open()}}>
      <label>Curriculum <select value={curriculum} onChange={e=>{setCurriculum(e.target.value);setPacket(null);setReceipt('')}}><option value="site">Site analysis</option><option value="urban">Urban economics</option><option value="planning">Community planning</option><option value="acquisition">Acquisition and town development</option></select></label>
      <label>Study name <input value={name} onChange={e=>{setName(e.target.value);setPacket(null)}} maxLength={160} placeholder="College Park · Edgewater corridor"/></label>
      <button disabled={busy || name.trim().length<2}>Open study</button>
      {studies.length>0&&<select aria-label="Resume a study" value="" onChange={e=>{const s=studies.find(x=>x.id===Number(e.target.value));if(s){setName(s.name);setCurriculum(s.curriculum);void open(s.id)}}}><option value="">Resume existing…</option>{studies.map(s=><option key={s.id} value={s.id}>{s.name} · {s.curriculum}</option>)}</select>}
    </form>
    {error&&<p role="alert">{error}</p>}
    {packet&&<><p>{Object.entries(packet.counts).map(([k,v])=>v+' '+k.replaceAll('_',' ')).join(' · ')}</p><h3>Ready for evidence</h3>{packet.ready.map(t=><p key={t.id}><strong>{t.owner}</strong> · {t.title} <button type="button" disabled={busy} onClick={()=>{setTask(t.id);setReceipt('')}}>{t.id} · Submit evidence</button></p>)}</>}
    {task&&packet&&<form onSubmit={e=>{e.preventDefault();void submit()}}><h3>Evidence for {task}</h3>
      <label>Source and date <input value={source} onChange={e=>setSource(e.target.value)} required maxLength={500}/></label>
      <label>Work product <textarea value={evidence} onChange={e=>setEvidence(e.target.value)} required maxLength={150000}/></label>
      <label>How it meets the criteria <input value={reason} onChange={e=>setReason(e.target.value)} required maxLength={1500}/></label>
      <button disabled={busy}>Send to independent review</button>
    </form>}
    {receipt&&<p role="status">{receipt}</p>}
  </section>
}
