'use client';
import {useEffect,useState} from 'react';
type Review={ticket_id:string|null;disposition:string;objective:string;theme?:string;workstream?:string;next_action:string;status:string};
export default function PromptIntake(){
 const [prompt,setPrompt]=useState(''),[ticket,setTicket]=useState(''),[result,setResult]=useState<Review|null>(null);
 const [ideas,setIdeas]=useState<{request_id:string;prompt:string;result:Review}[]>([]);
 async function fetchIdeas(){const r=await fetch('/api/prompt-review/ideas',{cache:'no-store'});if(r.ok)setIdeas(await r.json())}
 useEffect(()=>{fetchIdeas().catch(()=>{})},[]);
 const [busy,setBusy]=useState(false),[error,setError]=useState(''),[key,setKey]=useState('');
 useEffect(()=>{fetch('/api/prompt-review/current',{cache:'no-store'}).then(r=>r.ok?r.json():null).then(r=>{if(r?.disposition)setResult(r)}).catch(()=>{})},[]);
 async function submit(){
   setBusy(true);setError('');
   const requestId=key||crypto.randomUUID();setKey(requestId);
   try{
     const r=await fetch('/api/prompt-review',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({prompt,request_id:requestId,...(ticket.trim()?{ticket_id:ticket.trim()}: {})})});
     const data=await r.json();
     if(!r.ok)throw Error(typeof data.detail==='string'?data.detail:'Unable to record instruction');
     setResult(data);setPrompt('');setKey('');await fetchIdeas();
   }catch(e){setError((e as Error).message)}finally{setBusy(false)}
 }
 return <section className="panel" style={{padding:'1.2rem',marginBottom:'1rem'}}><h2>Founder intake</h2>
 <form onSubmit={e=>{e.preventDefault();void submit()}}>
 <label>Instruction <textarea required maxLength={8000} value={prompt} onChange={e=>{setPrompt(e.target.value);setKey('')}} placeholder="Continue the Asher property review…"/></label>
 <label>Ticket, if known <input value={ticket} onChange={e=>{setTicket(e.target.value);setKey('')}} placeholder="BR-T028"/></label>
 <button disabled={busy||!prompt.trim()}>Review instruction</button></form>
 {error&&<p role="alert">{error}</p>}
 {result&&<div aria-live="polite"><p><strong>{result.ticket_id||'Intake'}</strong> · {result.disposition.replaceAll('_',' ')}</p><p>{[result.workstream,result.theme].filter(Boolean).join(' · ')}</p><p>{result.objective}</p><p><strong>Next action</strong> {result.next_action}</p></div>}
 {ideas.length>0&&<details><summary>Private idea capture ({ideas.length})</summary>{ideas.map(i=><p key={i.request_id}><strong>{i.result.workstream}</strong> · {i.prompt}</p>)}</details>}</section>
}
