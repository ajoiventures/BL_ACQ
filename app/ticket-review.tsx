'use client';

import {FormEvent,useState} from 'react';

export default function TicketReview({id,version,prerequisites,review,onChange}:{
 id:string;version:number;prerequisites:string[];review:boolean;onChange:()=>void;
}){
 const [busy,setBusy]=useState(false);
 const [error,setError]=useState('');
 async function submit(event:FormEvent<HTMLFormElement>){
  event.preventDefault();
  const form=event.currentTarget;
  const fields=new FormData(form);
  const button=(event.nativeEvent as SubmitEvent).submitter;
  const target=button instanceof HTMLButtonElement?button.value:'';
  if(!['closed','review_required'].includes(target))return;
  setBusy(true);
  setError('');
  try{
   const response=await fetch('/api/tickets/'+encodeURIComponent(id)+'/transition',{
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify({target,version,evidence:fields.get('evidence'),source:fields.get('source')}),
   });
   if(!response.ok){
    const body=await response.json();
    throw Error(typeof body.detail==='string'?body.detail:'Review could not be recorded');
   }
   form.reset();
   onChange();
  }catch(error){
   setError(error instanceof Error?error.message:'Review could not be recorded');
  }finally{setBusy(false);}
 }
 return <form onSubmit={submit} aria-label={`Record ticket completion for ${id}`}>
  <label>Work evidence <textarea name="evidence" required maxLength={12000}/></label>
  <label>Evidence source <input name="source" required maxLength={2000}/></label>
  <button type="submit" value="closed" disabled={busy||prerequisites.length>0}>Mark complete</button>{' '}
  {!review&&<button type="submit" value="review_required" disabled={busy}>Request optional review</button>}
  {error&&<p role="alert">{error}</p>}
 </form>;
}
