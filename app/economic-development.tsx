'use client';
import {useRef,useState} from 'react';
import Link from 'next/link';
import baselineFixture from '../docs/economic-development/fixtures/baseline.json';
import unknownFixture from '../docs/economic-development/fixtures/data-center-unknown.json';
import failFixture from '../docs/economic-development/fixtures/data-center-fail.json';
import hypotheticalFixture from '../docs/economic-development/fixtures/data-center-hypothetical.json';

type Ratio={value:string|null;numerator:number;denominator:number};
type Gate={status:string;criterion:string;missing_inputs:string[]};
type Report={status:string;kind:string;input_sha256:string;report_sha256:string;warnings:string[];storefront_metrics?:{survey_coverage:Ratio;known_vacancy_rate:Ratio;vacancy_rate_lower_bound:Ratio;vacancy_rate_upper_bound:Ratio};employment_location_quotient?:{status:string;value:string|null};gate_results?:Record<string,Gate>;failed_gates?:string[];unknown_gates?:string[];planning_load?:{requested_peak_facility_mw:string|null;supplied_deliverable_mw:string|null;capacity_margin_mw:string|null};next_action?:{action:string}};
type DCFields={it:string;basis:string;pue:string;peak:string;required:string;available:string;energization:string;stage:string};
const gateNames:Record<string,string>={demand_profile:'Customer load and ramp',reserve_redundancy_headroom:'Reserve and redundancy',utility_service_terms_reliability:'Service terms and reliability',utility_study_service_costs:'Utility studies and costs',fiber_route_diversity:'Physical fiber diversity',land_control_title:'Land control and title',land_use_permit_path:'Land use and permits',cooling_water:'Cooling and water',environmental_flood:'Environmental constraints',noise_air_generator_community:'Noise, air and community',customer_commercial_readiness:'Customer and commercial case'};
const stageNames=['PROXIMITY','PRELIMINARY_ASSESSMENT','ENGINEERING_STUDY','SERVICE_AGREEMENT','ENERGIZED'];
const moduleCards=[['Baseline','A defined district, dated inventory and visible data gaps.','BR-T097'],['Business retention','Needs, space, continuity and expansion opportunities.','BR-T098'],['Sector and workforce','Regional context tied to actual customer demand.','BR-T099'],['Sites and infrastructure','Use, utilities, access, hazards, cost and delivery dates.','BR-T100'],['Acquisition pipeline','Projects linked to the corridor plan and investment conditions.','BR-T102'],['Capital and fiscal review','Separate private returns, public costs and local outcomes.','BR-T101'],['Main Street ownership','Housing, business ownership, public realm and delivery.','BR-T055'],['Outcomes and learning','Comparable baselines, targets and observed results.','BR-T108']];
const pretty=(v:string)=>v.toLowerCase().replaceAll('_',' ').replace(/^./,c=>c.toUpperCase());
const percent=(r:Ratio)=>r.value===null?'Unknown':(Number(r.value)*100).toLocaleString(undefined,{maximumFractionDigits:2})+'%';
const observe=(value:unknown)=>({value,evidence_status:value===null?'UNKNOWN':'HYPOTHETICAL',source_ref:value===null?null:'urn:black-river:ui-synthetic-scenario',source_date:value===null?null:'2026-11-23',note:'Interactive hypothetical example; no real site evidence.'});

export default function EconomicDevelopment(){
 const [tab,setTab]=useState<'baseline'|'data-center'>('baseline');
 const [counts,setCounts]=useState({eligible_count:'100',occupied_count:'70',vacant_count:'10',unknown_count:'20'});
 const [fields,setFields]=useState<DCFields>({it:'10',basis:'ANNUAL_AVERAGE',pue:'1.3',peak:'15',required:'2029-01-01',available:'',energization:'',stage:'PROXIMITY'});
 const [gates,setGates]=useState<Record<string,string>>({});
 const [report,setReport]=useState<Report|null>(null),[audit,setAudit]=useState(''),[error,setError]=useState(''),[busy,setBusy]=useState(false);
 const requestVersion=useRef(0);
 const clear=()=>{requestVersion.current+=1;setReport(null);setAudit('');setError('')};
 function preset(kind:'unknown'|'fail'|'hypothetical'){
  const p=(kind==='unknown'?unknownFixture:kind==='fail'?failFixture:hypotheticalFixture) as {program:Record<string,{value:unknown}>;utility:Record<string,{value:unknown}>;gates:Record<string,{value:unknown}>};
  const value=(section:Record<string,{value:unknown}>,key:string)=>section[key]?.value==null?'':String(section[key].value);
  setFields({it:value(p.program,'it_load_mw'),basis:value(p.program,'it_load_basis'),pue:value(p.program,'pue'),peak:value(p.program,'requested_peak_facility_mw'),required:value(p.program,'required_operation_date'),available:value(p.utility,'deliverable_mw'),energization:value(p.utility,'energization_date'),stage:value(p.utility,'evidence_stage')});
  setGates(Object.fromEntries(Object.keys(gateNames).map(k=>[k,value(p.gates,k)])));clear();
 }
 async function run(){
  const version=++requestVersion.current;
  setBusy(true);setError('');setReport(null);setAudit('');
  try{
   let packet:unknown;
   if(tab==='baseline'){
    const parsed=Object.fromEntries(Object.entries(counts).map(([key,value])=>{if(!/^\d+$/.test(value)||!Number.isSafeInteger(Number(value)))throw Error('Enter a nonnegative whole count for every storefront field.');return[key,Number(value)]}));
    packet={...baselineFixture,review_id:'UI-SYNTHETIC-BASELINE',storefronts:parsed};
   }else{
    const v=(s:string)=>s===''?null:s;
    packet={...unknownFixture,review_id:'UI-SYNTHETIC-DATA-CENTER',program:{it_load_mw:observe(v(fields.it)),it_load_basis:observe(v(fields.basis)),pue:observe(v(fields.pue)),requested_peak_facility_mw:observe(v(fields.peak)),required_operation_date:observe(v(fields.required))},utility:{deliverable_mw:observe(v(fields.available)),energization_date:observe(v(fields.energization)),evidence_stage:observe(v(fields.stage))},gates:Object.fromEntries(Object.keys(gateNames).map(k=>[k,observe(gates[k]==='true'?true:gates[k]==='false'?false:null)]))};
   }
   const res=await fetch('/api/economic-development/'+tab,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(packet)});
   const body=await res.json();if(!res.ok)throw Error(typeof body.detail==='string'?body.detail:JSON.stringify(body.detail));if(version===requestVersion.current){setReport(body.report);setAudit(body.audit_hash);}
  }catch(e){if(version===requestVersion.current)setError((e as Error).message)}finally{setBusy(false)}
 }
 const edit=(key:keyof DCFields,value:string)=>{setFields({...fields,[key]:value});clear()};
 return <div className="economic-suite">
  <section className="panel econ-goal"><div className="panel-head"><h2>The Main Street goal</h2><span className="tag">TARGETS TO DEFINE</span></div><p>Build and sustain complete corridors where households can access housing and ownership, local businesses can remain and grow, and streets, buildings and infrastructure work as a coherent town.</p><p className="econ-mandate"><strong>Current acquisition path:</strong> lawful 2–4 unit acquisition followed by Main Street ownership and development.</p><p>Set the corridor boundary, dated baseline and numerical targets before measuring success. The data-center track adds regional opportunities; its capital and local benefits need their own evidence.</p><Link className="text-link" href="/swarm">Open the work tickets</Link></section>
  <div className="econ-module-grid">{moduleCards.map(([title,description,ticket],i)=><section className="panel" key={title}><span className="bronze">{String(i+1).padStart(2,'0')} / {ticket}</span><h3>{title}</h3><p>{description}</p></section>)}</div>
  <section className="panel econ-workbench"><div className="panel-head"><h2>Scenario workbench</h2><span className="tag">HYPOTHETICAL INPUTS</span></div><p>Explore the screening logic with invented inputs. Results describe these assumptions and do not verify a property, utility commitment or available capital.</p>
   <div className="econ-tabs" role="group" aria-label="Analysis type"><button aria-pressed={tab==='baseline'} onClick={()=>{setTab('baseline');clear()}}>Corridor baseline</button><button aria-pressed={tab==='data-center'} onClick={()=>{setTab('data-center');clear()}}>Data center site</button></div>
   <form onSubmit={e=>{e.preventDefault();run()}}>
   {tab==='baseline'?<><div className="econ-fields">{Object.entries(counts).map(([key,value])=><label key={key}>{pretty(key)}<input required inputMode="numeric" pattern="[0-9]+" value={value} onChange={e=>{setCounts({...counts,[key]:e.target.value});clear()}}/></label>)}</div><p>Occupied + vacant + unknown must equal eligible premises. The example also includes a hypothetical employment location quotient and ownership sample, visible in the full report.</p></>:<>
    <div className="econ-presets"><span>Load example</span><button type="button" onClick={()=>preset('unknown')}>Capacity unknown</button><button type="button" onClick={()=>preset('fail')}>Power / date shortfall</button><button type="button" onClick={()=>preset('hypothetical')}>All assumptions meet</button></div>
    <div className="econ-fields">
     <label>IT load (MW)<input inputMode="decimal" value={fields.it} onChange={e=>edit('it',e.target.value)}/></label>
     <label>IT load basis<select value={fields.basis} onChange={e=>edit('basis',e.target.value)}><option value="">Unknown</option><option value="ANNUAL_AVERAGE">Annual average</option><option value="NAMEPLATE">Nameplate</option><option value="PEAK">Peak</option></select></label>
     <label>Annual PUE assumption<input inputMode="decimal" value={fields.pue} onChange={e=>edit('pue',e.target.value)}/></label>
     <label>Requested peak facility load (MW)<input inputMode="decimal" value={fields.peak} onChange={e=>edit('peak',e.target.value)}/></label>
     <label>Required operation date<input type="date" value={fields.required} onChange={e=>edit('required',e.target.value)}/></label>
     <label>Supplied utility capacity (MW)<input inputMode="decimal" placeholder="Unknown" value={fields.available} onChange={e=>edit('available',e.target.value)}/></label>
     <label>Supplied energization date<input type="date" value={fields.energization} onChange={e=>edit('energization',e.target.value)}/></label>
     <label>Utility evidence stage — assumed<select value={fields.stage} onChange={e=>edit('stage',e.target.value)}><option value="">Unknown</option>{stageNames.map(s=><option value={s} key={s}>{pretty(s)}</option>)}</select></label>
    </div><p>PUE describes annual energy efficiency. Peak facility demand is a separate input. Blank entries remain unknown; the proximity example includes 500 acres and a nearby substation without established utility capacity.</p>
    <details><summary>Customer, site and infrastructure requirements</summary><div className="econ-fields">{Object.entries(gateNames).map(([key,label])=><label key={key}>{label}<select value={gates[key]||''} onChange={e=>{setGates({...gates,[key]:e.target.value});clear()}}><option value="">Unknown</option><option value="true">Meets assumption</option><option value="false">Fails assumption</option></select></label>)}</div></details>
   </>}
   <button className="primary" disabled={busy}>{busy?'Calculating…':'Run hypothetical screen'}</button></form>
   {error&&<p role="alert" className="alert error">{error}</p>}
   {report&&<section className="econ-result" aria-live="polite"><div className="panel-head"><h3>Screening result</h3><span className={'badge '+(report.status==='FAIL'?'amber':'')}>{pretty(report.status)}</span></div>
    {report.storefront_metrics&&<div className="econ-result-grid"><div><small>Survey coverage</small><strong>{percent(report.storefront_metrics.survey_coverage)}</strong></div><div><small>Vacancy among known premises</small><strong>{percent(report.storefront_metrics.known_vacancy_rate)}</strong></div><div><small>All-premises vacancy bounds</small><strong>{percent(report.storefront_metrics.vacancy_rate_lower_bound)} – {percent(report.storefront_metrics.vacancy_rate_upper_bound)}</strong></div></div>}
    {report.planning_load&&<div className="econ-result-grid"><div><small>Requested peak load</small><strong>{report.planning_load.requested_peak_facility_mw??'Unknown'} MW</strong></div><div><small>Supplied capacity</small><strong>{report.planning_load.supplied_deliverable_mw??'Unknown'} MW</strong></div><div><small>Capacity margin</small><strong>{report.planning_load.capacity_margin_mw??'Unknown'} MW</strong></div></div>}
    {report.gate_results&&<div className="econ-gate-table"><table><caption>Mandatory requirements — unknowns cannot pass</caption><thead><tr><th>Requirement</th><th>Supplied result</th></tr></thead><tbody>{Object.entries(report.gate_results).map(([key,g])=><tr key={key}><td>{g.criterion}</td><td>{pretty(g.status)}</td></tr>)}</tbody></table></div>}
    {report.next_action&&<p><strong>Next evidence action:</strong> {report.next_action.action}</p>}
    <p>All results use supplied assumptions. Acquisitions, utility reservations and financial commitments remain unapproved.</p>
    <details><summary>Inspect report and audit receipt</summary><pre>{JSON.stringify({report,audit_hash:audit},null,2)}</pre></details>
   </section>}
  </section>
  <section className="panel econ-links"><h2>Connect the site to the town</h2><div className="econ-three"><div><h3>Private project</h3><p>Customer demand, land control, costs, operating cash and acquisition conditions.</p></div><div><h3>Community outcomes</h3><p>Business continuity, housing access, permanent jobs and verified local procurement.</p></div><div><h3>Public fiscal effects</h3><p>Incremental revenues, incentives, infrastructure and ongoing service costs.</p></div></div><p>Construction activity and permanent demand use different periods. A viable data-center scenario alone does not establish Main Street rents, housing absorption or household wealth.</p></section>
 </div>
}
