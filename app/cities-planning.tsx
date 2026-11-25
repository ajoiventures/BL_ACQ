'use client';
import {useEffect,useRef,useState} from 'react';
import Link from 'next/link';
import CollegeParkBaseline from './college-park-baseline';
import EconomicDevelopment from './economic-development';
import SitePathDiscovery from './site-path-discovery';

type Projection={security_domain:string;forecast_id:string;forecast_revision:number;classification:string;accuracy_status:string;created_at:string;target_date:string;baseline:{place_id:string;title:string;population:number;reference_date:string;vintage:string;source_url:string;evidence_status:string};horizon_years:number;scenarios:{name:string;annual_growth_rate:string;projected_population:number;net_population_change:number;total_change_pct:string|null}[];output_sha256:string};
type ResearchForecast = {
 sha256:string;
 planning_context_sha256:string;
 planning_context:{
  boundary_reference:{vintage:string;scope:string;members:{fips:string;name:string}[]};
 };
 payload:{
  state:string;
  source:{release_date:string;url:string};
  target:{quarter:string;geography:string};
  primary_method:string;
  predictions:Record<string,{prediction_pct:string}>;
  observation:null;
 };
};
const researchMethods = [
 ['florida_growth','Florida growth persistence'],
 ['orlando_growth','Orlando growth persistence'],
 ['no_change','No change'],
] as const;
import pillarCatalog from '../docs/cities-planning/urban-pillars.json';
async function api(path:string,body?:unknown){const res=await fetch('/api/cities-planning'+path,body===undefined?{cache:'no-store'}:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});const result=await res.json();if(!res.ok)throw Error(typeof result.detail==='string'?result.detail:JSON.stringify(result.detail));return result;}
export default function CitiesPlanning(){
 const [tab,setTab]=useState('systems'),[horizon,setHorizon]=useState('5'),[rates,setRates]=useState(['0.005','0.02','0.04']);
 const [securityDomain,setSecurityDomain]=useState('COMMERCIAL'),[scenarioNames,setScenarioNames]=useState(['Lower growth assumption','Middle growth assumption','Higher growth assumption']);
 const [result,setResult]=useState<Projection|null>(null),[saved,setSaved]=useState<Projection[]>([]),[busy,setBusy]=useState(false),[error,setError]=useState('');const version=useRef(0);
 const [forecast,setForecast]=useState<ResearchForecast|null>(null);
 const [forecastLoading,setForecastLoading]=useState(false);
 const [forecastError,setForecastError]=useState('');
 async function loadResearchForecast(){
  setForecastLoading(true);setForecastError('');
  try{setForecast(await api('/research/orlando-hpi'));}
  catch(e){setForecastError((e as Error).message);}
  finally{setForecastLoading(false);}
 }
 const [baseline,setBaseline]=useState({place_id:'US:place:1228400',title:'Haines City, Florida',population:'45973',reference_date:'2025-07-01',vintage:'Census PEP Vintage 2025',source_url:'https://www.census.gov/newsroom/press-releases/2026/vintage-2025-city-town-pop-estimates.html',evidence_status:'SOURCE_REPORTED'});
 useEffect(()=>{api('').then(setSaved).catch(e=>setError(e.message));},[]);
 const invalidate=()=>{version.current++;setResult(null);setError('');};
 async function project(){const token=++version.current;setBusy(true);setError('');try{
  if(!/^\d+$/.test(baseline.population)||!Number.isSafeInteger(Number(baseline.population)))throw Error('Population must be a whole nonnegative count.');
  if(!/^\d+$/.test(horizon))throw Error('Enter a whole-year horizon.');
  const output=await api('/project',{request_id:crypto.randomUUID(),security_domain:securityDomain,baseline:{...baseline,population:Number(baseline.population)},horizon_years:Number(horizon),scenarios:rates.map((rate,i)=>({name:scenarioNames[i],annual_growth_rate:rate}))});
  if(token===version.current)setResult(output);const rows=await api('');if(token===version.current)setSaved(rows);
 }catch(e){if(token===version.current)setError((e as Error).message)}finally{setBusy(false)}}
 async function load(id:string){const token=++version.current;setBusy(true);setError('');try{const r=await api('/'+id);if(token===version.current){setResult(r);setTab('projections');setBaseline({...r.baseline,population:String(r.baseline.population)});setHorizon(String(r.horizon_years));setRates(r.scenarios.map((s:Projection['scenarios'][number])=>s.annual_growth_rate));setScenarioNames(r.scenarios.map((s:Projection['scenarios'][number])=>s.name));setSecurityDomain(r.security_domain);}}catch(e){if(token===version.current)setError((e as Error).message)}finally{setBusy(false)}}
 return <div className="cities-layer">
  <section className="panel cities-intro"><div><span className="eyebrow">ONE PLANNING LAYER · CONNECTED SPECIALIST ENGINES</span><h2>Understand the city. Plan its next chapter.</h2><p>Connect regional change to streets, homes, businesses and ownership. Keep one place record, one plan history and a clear account of assumptions, evidence and results.</p></div><Link href="/intelligence-flow">Bring in a source →</Link></section>
  <div className="econ-tabs cities-tabs" role="group" aria-label="Cities and planning views">{[['systems','City systems'],['method','Site analysis & synthesis'],['projections','Growth scenarios'],['engines','Specialist screens'],['delivery','Plans & outcomes']].map(([id,name])=><button key={id} aria-pressed={tab===id} onClick={()=>setTab(id)}>{name}</button>)}</div>
  {tab==='systems'&&<><section className="panel"><h2>18 urban planning pillars</h2><p>One shared planning catalog. These are research requirements, not completed district studies. Specialist calculations remain separate; findings require accepted place, source and review evidence.</p></section>{pillarCatalog.domains.map(domain=><section key={domain} className="panel"><h3>{domain} systems</h3><div className="cities-system-grid">{pillarCatalog.pillars.filter(p=>p.domain===domain).map(p=><section className="panel" key={p.id}><small>{p.id} · {p.owner}</small><h3>{p.name}</h3><p>{p.output}</p><details><summary>Required evidence and method</summary><p>{p.required_evidence}</p><p>{p.method_reference}</p><p>Coverage: specified; district acceptance not established.</p></details><Link href={'/swarm?ticket='+p.primary_ticket}>{p.primary_ticket} · Inspect work</Link></section>)}</div></section>)}<section className="panel cities-chain"><h3>Regional change → town capacity → corridor plan → property decision</h3><p>A growing population can create opportunities, but housing, services, infrastructure, employment and capital determine which projects can work. The complete Main Street corridor remains the base planning template.</p><p><strong>Current acquisition mandate:</strong> prepare the intended Ives sale and capital redeployment, develop the lawful 2–4-unit buy box, and connect that first acquisition to durable Main Street ownership.</p></section></>}
  {tab==='systems'&&<CollegeParkBaseline domain="MAIN_STREET_INSTITUTIONAL"/>}
  {tab==='method'&&<SitePathDiscovery/>}
  {tab==='projections'&&<section className="panel cities-projections"><div className="panel-head"><h2>Population scenario workbench</h2><span className="tag">CONDITIONAL PROJECTIONS</span></div><p>The example starts with Census-reported Haines City population. Growth rates below are illustrative assumptions, not an estimated probability or a calibrated forecast. Historical 10.0% growth is not automatically extended.</p>
   <form onSubmit={e=>{e.preventDefault();project()}}><div className="econ-fields"><label>Place<input value={baseline.title} disabled={busy} onChange={e=>{setBaseline({...baseline,title:e.target.value,evidence_status:'HYPOTHETICAL'});invalidate();}}/></label><label>Baseline population<input inputMode="numeric" value={baseline.population} disabled={busy} onChange={e=>{setBaseline({...baseline,population:e.target.value,evidence_status:'HYPOTHETICAL'});invalidate();}}/></label><label>Baseline date<input type="date" value={baseline.reference_date} disabled={busy} onChange={e=>{setBaseline({...baseline,reference_date:e.target.value,evidence_status:'HYPOTHETICAL'});invalidate();}}/></label><label>Projection horizon (years)<input type="number" min="1" max="20" value={horizon} disabled={busy} onChange={e=>{setHorizon(e.target.value);invalidate();}}/></label></div>
    <div className="econ-fields">{rates.map((rate,i)=><label key={i}>{scenarioNames[i]} — annual rate<input inputMode="decimal" value={rate} disabled={busy} onChange={e=>{setRates(rates.map((v,j)=>j===i?e.target.value:v));invalidate();}}/><small>Decimal fraction: 0.02 means 2% per year.</small></label>)}</div>
    <details><summary>Baseline identity and source</summary><div className="econ-fields"><label>Workspace domain<select value={securityDomain} disabled={busy} onChange={e=>{setSecurityDomain(e.target.value);invalidate();}}><option value="COMMERCIAL">Commercial</option><option value="MAIN_STREET_INSTITUTIONAL">Main Street institutional</option></select></label><label>Place identifier<input value={baseline.place_id} disabled={busy} onChange={e=>{setBaseline({...baseline,place_id:e.target.value,evidence_status:'HYPOTHETICAL'});invalidate();}}/></label><label>Source vintage<input value={baseline.vintage} disabled={busy} onChange={e=>{setBaseline({...baseline,vintage:e.target.value});invalidate();}}/></label><label>Source URL<input type="url" value={baseline.source_url} disabled={busy} onChange={e=>{setBaseline({...baseline,source_url:e.target.value});invalidate();}}/></label></div><p>Editing a count or geography changes the baseline to a hypothetical input. Source-reported information still requires review.</p></details>
    <button className="primary" disabled={busy}>{busy?'Calculating…':'Calculate and save scenarios'}</button></form>
   {result&&<div className="cities-result" aria-live="polite"><h3>{result.baseline.title} · {result.target_date}</h3><p><strong>{result.baseline.evidence_status==='HYPOTHETICAL'?'Hypothetical baseline':'Source-reported baseline · unverified'}</strong> · {result.baseline.population.toLocaleString()} residents at {result.baseline.reference_date} · {result.horizon_years}-year horizon · forecast accuracy unassessed.</p><div className="econ-gate-table"><table><caption>Projected totals conditional on supplied annual growth</caption><thead><tr><th>Scenario</th><th>Annual rate</th><th>Projected population</th><th>Change</th></tr></thead><tbody>{result.scenarios.map(s=><tr key={s.name}><td>{s.name}</td><td>{(Number(s.annual_growth_rate)*100).toLocaleString(undefined,{maximumFractionDigits:6})}%</td><td>{s.projected_population.toLocaleString()}</td><td>{s.net_population_change.toLocaleString()}</td></tr>)}</tbody></table></div><p>These paths do not identify migration causes, guarantee housing demand or establish an acquisition return. Connect a supported scenario to housing, jobs and infrastructure constraints before changing a plan.</p><details><summary>Inspect saved calculation and receipt</summary><pre>{JSON.stringify(result,null,2)}</pre></details></div>}
   <div className="cities-result">
    <h3>Orlando housing-price research forecast</h3>
    {!forecast&&<button type="button" disabled={forecastLoading} onClick={loadResearchForecast}>
     {forecastLoading?'Loading forecast…':'Load saved forecast'}
    </button>}
    {forecastError&&<p role="alert">{forecastError}</p>}
    {forecast&&<div aria-live="polite">
     <p>{forecast.payload.target.geography} · {forecast.payload.target.quarter} · outcome pending</p>
     <p>Annual growth in the seasonally adjusted purchase-only house-price index.</p>
     <dl>{researchMethods.map(([key,label])=><div key={key}>
      <dt>{label}{forecast.payload.primary_method===key?' (primary)':''}</dt>
      <dd>{forecast.payload.predictions[key].prediction_pct}%</dd>
     </div>)}</dl>
     <p><a href={forecast.payload.source.url}>FHFA release · {forecast.payload.source.release_date}</a></p>
     <details>
      <summary>Forecast geography and evidence</summary>
      <p>Reference boundary · {forecast.planning_context.boundary_reference.vintage}</p>
      <p>{forecast.planning_context.boundary_reference.members.map(member=>member.name).join(', ')}</p>
      <p>{forecast.planning_context.boundary_reference.scope}</p>
      <p style={{overflowWrap:'anywhere'}}>Forecast checksum <code>{forecast.sha256}</code></p>
      <p style={{overflowWrap:'anywhere'}}>Context checksum <code>{forecast.planning_context_sha256}</code></p>
     </details>
    </div>}
   </div>
   <h3>Saved scenario history</h3><p>Each run retains the supplied baseline, assumptions, revision and output receipt. Outcome comparison and forecast calibration remain in BR-T113.</p><div className="cities-saved">{saved.length===0?<p>No saved projections.</p>:saved.map(p=><button disabled={busy} key={p.forecast_id} onClick={()=>load(p.forecast_id)}><strong>{p.baseline.title} · {p.target_date}</strong><small>Revision {p.forecast_revision} · {p.created_at.slice(0,10)} · scenarios, accuracy unassessed</small></button>)}</div>
  </section>}
  {tab==='engines'&&<><section className="panel cities-engine-note"><h3>Shared planning context, separate calculations</h3><p>Economic baselines and data-center screens retain their own inputs and requirements. Town growth, corridor planning, finance and acquisition connect through the same evidence and ticket records.</p></section><EconomicDevelopment/></>}
  {tab==='delivery'&&<section className="panel cities-delivery"><h2>Track plans, delivery and outcomes</h2><p>The layer contract connects these records. Full adopted-plan tracking, interventions and forecast evaluation are planned work; the source-to-work flow and saved scenario registry are the local increments now available.</p><div className="cities-system-grid">{[['Plan revisions','Scope, geometry, objectives, alternatives, owner and adoption state.'],['Scenario assumptions','Population, housing, jobs, infrastructure and time-bound constraints.'],['Delivery phases','Entitlements, utilities, acquisition, construction and dependencies.'],['Observed results','Homes, occupied premises, jobs, cash, public costs and ownership.'],['Prediction error','Vintage, target date, observed value and honest uncertainty.'],['Strategy revision','What changed, which assumption failed and what action follows.']].map(([title,body])=><div key={title}><h3>{title}</h3><p>{body}</p></div>)}</div><h3>Three distinct measures of benefit</h3><p><strong>Private:</strong> supported risk-adjusted cash and ownership value. <strong>Community:</strong> housing access, business continuity and durable local ownership. <strong>Public:</strong> incremental revenue, infrastructure and ongoing service cost.</p><p><Link href="/swarm?ticket=BR-T112">Planning layer work</Link> · <Link href="/swarm?ticket=BR-T113">Forecast and outcome work</Link> · <Link href="/swarm?ticket=BR-T076">Current 2–4-unit action</Link></p></section>}
  {error&&<p role="alert" className="alert error">{error}</p>}
 </div>
}
