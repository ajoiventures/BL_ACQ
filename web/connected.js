// Render only server responses. A local filename or dropdown grants no authority.
const $ = (id) => document.getElementById(id);
const route = "/api/workspaces/commercial/records/orchard-01";
let snapshot = null;
let retryBody = null;
let busy = false;
function say(text) { $("feedback").textContent = text; }
async function request(path, body) {
  const response = await fetch(path, body ? {
    method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(body)
  } : {cache:"no-store"});
  if (!response.headers.get("Content-Type")?.includes("application/json"))
    throw Error("The local founder service is unavailable. Start python -m pilot.founder_service.");
  const data = await response.json();
  if (!response.ok) {
    const error = Error(data.error || "The request failed."); error.status = response.status; throw error;
  }
  return data;
}
function reset() {
  snapshot=null; retryBody=null; $("review").hidden=true; $("login").hidden=false;
  $("note").value=""; $("events").replaceChildren(); $("gates").replaceChildren();
  $("source").textContent=""; $("identity").textContent=""; $("summary").textContent="";
}
function setSnapshot(data) {
  snapshot=data; $("login").hidden=true; $("review").hidden=false; $("retry").hidden=true;
  $("identity").textContent=data.actor+" · "+data.scope+" · "+data.record;
  const cents = data.underwriting.ceiling_cents;
  const ceiling = cents === null ? "unverified" : new Intl.NumberFormat("en-US",{style:"currency",currency:"USD",maximumFractionDigits:0}).format(cents/100);
  $("summary").textContent="Synthetic purchase ceiling " + ceiling + ". " + data.underwriting.state.replaceAll("_"," ") + ".";
  $("source").textContent="Evidence "+data.evidence+" · "+data.underwriting.as_of+" · "+data.underwriting.packet_digest;
  $("gates").replaceChildren(...data.underwriting.checks.map(check=>{
    const li=document.createElement("li");
    const references=(check.evidence||[]).map(e=>e.reference+" ("+e.source+")");
    li.textContent=check.gate.replaceAll("_"," ")+(check.passed?" — confirmed":" — on hold")+(references.length?" · "+references.join(", "):"");return li;
  }));
  $("events").replaceChildren(...data.history.map(e=>{
    const li=document.createElement("li");li.textContent=e.actor+" · "+e.action+" · "+e.note+" · "+(e.evidence===data.evidence?"Current packet":"Superseded packet")+" "+e.evidence;return li;
  }));
  $("note").value=data.draft.note;
  $("draftSource").textContent=data.draft.evidence===data.evidence ? "" : "This draft was saved against an earlier packet. Inspect the current evidence before saving or deciding.";
  const action = data.actor==="reviewer" ? "review" : "approve";
  $("decision").dataset.action=action;
  $("decision").textContent=action==="review"?"Record independent review":"Approve simulated decision";
  $("decision").disabled=action==="review" ? data.events.length!==0 : (data.events.length!==1 || !data.underwriting.ready);
}
async function refresh() {
  try {setSnapshot(await request(route));retryBody=null;say("Checkpoint loaded.");}
  catch(error) {reset();say(error.message);}
}
$("login").addEventListener("submit",async event=>{
  event.preventDefault();
  try {
    await request("/api/session",{actor:$("actor").value,token:$("token").value});
    $("token").value="";await refresh();
    if(snapshot) $("review").querySelector("button").focus();
  } catch(error){say(error.message);}
});
$("logout").addEventListener("click",async()=>{
  try {await request("/api/logout",{});reset();say("Signed out.");$("actor").focus();}
  catch(error){say(error.message);}
});
$("refresh").addEventListener("click",refresh);
async function submit(action, previous=null) {
  if (!snapshot || busy) return;
  busy=true;
  const body=previous || {action,note:$("note").value,evidence:snapshot.evidence,
    version:action==="draft"?snapshot.draft.version:snapshot.events.length,request_id:crypto.randomUUID()};
  try {
    setSnapshot(await request(route,body));retryBody=null;
    say(action==="draft"?"Checkpoint saved.":"Decision recorded.");
  } catch(error) {
    if(error.status===401||error.status===403) reset();
    retryBody=(!error.status||error.status===503)?body:null;
    $("retry").hidden=!retryBody;say(error.message);
  } finally {busy=false;}
}
$("save").addEventListener("click",()=>submit("draft"));
$("decision").addEventListener("click",()=>submit($("decision").dataset.action));
$("retry").addEventListener("click",()=>{if(retryBody)submit(retryBody.action,retryBody);});
refresh();
