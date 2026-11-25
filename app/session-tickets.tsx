'use client';
import {useEffect,useState} from 'react';
import TicketReview from './ticket-review';
import TicketReleaseEvidence from './ticket-release-evidence';
type Ticket={id:string;version:number;title:string;area:string;status:string;effective_status?:string;owner:string;leader:string;acceptance:string;evidence:string;dependencies:string[];next_action?:string;blocker?:string;canonical_approval?:{authority:string;scope:string}};
export default function SessionTickets(){
 const [rows,setRows]=useState<Ticket[]>([]),[query,setQuery]=useState(''),[error,setError]=useState('');
 const [loaded,setLoaded]=useState(false);
 const [refreshVersion,setRefreshVersion]=useState(0);
 useEffect(()=>{
  const id=new URLSearchParams(window.location.search).get('ticket');
  if(id&&/^BR-(T\d{3}|P[a-f0-9]{16})$/.test(id))setQuery(id);
  const controller=new AbortController();
  let pending=false;
  async function refresh(){
   if(pending)return;
   pending=true;
   try{
    const res=await fetch('/api/tickets',{cache:'no-store',signal:controller.signal});
    if(!res.ok)throw Error('Ticket register unavailable');
    const tickets:Ticket[]=await res.json();
    if(!controller.signal.aborted){setRows(tickets);setLoaded(true);setError('');}
   }catch(error){
    if(!controller.signal.aborted)setError(error instanceof Error?error.message:'Ticket register unavailable');
   }finally{pending=false;}
  }
  void refresh();
  const timer=window.setInterval(refresh,15000);
  window.addEventListener('focus',refresh);
  return ()=>{controller.abort();window.clearInterval(timer);window.removeEventListener('focus',refresh);};
 },[refreshVersion]);
 const displayStatus=(ticket:Ticket)=>ticket.effective_status??ticket.status;
 const closed=rows.filter(ticket=>displayStatus(ticket)==='closed').length;
 const closedIds=new Set(rows.filter(ticket=>displayStatus(ticket)==='closed').map(ticket=>ticket.id));
 const awaitingReview=rows.filter(ticket=>displayStatus(ticket)==='review_required');
 const unmetPrerequisites=(ticket:Ticket)=>ticket.dependencies.filter(id=>!closedIds.has(id));
 const readyForReview=awaitingReview.filter(ticket=>unmetPrerequisites(ticket).length===0).length;
 const blocked=rows.filter(ticket=>displayStatus(ticket)==='blocked').length;
 const filtered=rows.filter(r=>[r.id,r.title,displayStatus(r),r.area,r.owner,r.leader].join(' ').toLowerCase().includes(query.toLowerCase()));
 return <section className="panel" style={{padding:'1.4rem',marginBottom:'1rem'}}><h2>Session tickets</h2>
 {loaded&&<p role="status"><strong>{rows.length-closed} remaining</strong> · {closed} closed · {rows.length} total · {readyForReview} review requested · {awaitingReview.length-readyForReview} with open prerequisites · {blocked} blocked</p>}
 <label>Find by workstream, owner, status or ID <input type="search" value={query} onChange={e=>setQuery(e.target.value)} placeholder="Acquisition"/></label>
 {error&&<p role="alert">{error}</p>}{loaded&&query&&<p>{filtered.length} matching tickets</p>}
 <div style={{maxHeight:'25rem',overflow:'auto'}}>{filtered.map(r=><details key={r.id} open={query===r.id} id={r.id} style={{padding:'.6rem 0',borderBottom:'1px solid #474440'}}>
 <summary>{r.id} · {r.title} · {displayStatus(r).replaceAll('_',' ')}</summary>
 <p>{r.area} · {r.leader} / {r.owner}</p>
 {r.canonical_approval&&<p><strong>Canonical approval</strong> {r.canonical_approval.authority} · {r.canonical_approval.scope}. Runtime review history is unchanged.</p>}
 {displayStatus(r)==='review_required'&&<p><strong>Completion</strong>{' '}
 {unmetPrerequisites(r).length>0?`Close ${unmetPrerequisites(r).join(', ')} first.`:'Prerequisites are closed. Record completion evidence to close.'}</p>}
 {displayStatus(r)!=='closed'&&<TicketReview id={r.id} version={r.version} review={r.status==='review_required'}
 prerequisites={unmetPrerequisites(r)} onChange={()=>setRefreshVersion(value=>value+1)}/>}
 {r.blocker&&<p><strong>Blocker</strong> {r.blocker}</p>}
 {r.next_action&&<p><strong>Next action</strong> {r.next_action}</p>}
 <p><strong>Acceptance</strong> {r.acceptance}</p><p><strong>Live evidence</strong> {r.evidence}</p><TicketReleaseEvidence ticketId={r.id}/>
 {r.dependencies.length>0&&<p>Depends on {r.dependencies.join(', ')}</p>}</details>)}</div></section>
}
