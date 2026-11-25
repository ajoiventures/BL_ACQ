'use client';

import {useState} from 'react';

type Metric = {
  name: string;
  value: number;
  unit: string;
  period: string | number;
  method?: string;
  denominator: number | null;
  denominator_unit?: string;
  limits: string;
};

type BaselineReadback = {
  revision_sha256: string;
  district_operations?: {
    entity: string;
    period_end: string;
    reported_amounts: Record<'CYTotalRevenueAmt' | 'CYTotalExpensesAmt' | 'CYRevenuesLessExpensesAmt', number>;
  } | null;
  district_residential_permits: {
    observed_date: string;
    worktypes: Record<string, {issued: number; final_date: number; coo_date: number; coc_date: number}>;
    scope: string;
  };
  edgewater_funding: {
    records: {
      phase: string;
      source: string;
      funding_state: string;
      published_project_cost?: string;
      programmed_bond_or_loan?: string;
      actual_expenditure?: string | null;
    }[];
    regional_tip_comparison: {
      source: string;
      difference_from_city_reported_lap: string;
    };
    scope: string;
  };
  citywide_comparators: {
    employment: {
      employment_year: number;
      boundary_vintage: number;
      measures: {wac: {jobs: number}; rac: {jobs: number}};
      limits: string;
      boundary_source: string;
    };
    assessor_housing: {
      assessment_year: number;
      reported_unit_sum: number;
      parcels_with_numeric_values: number;
      parcels_without_numeric_values: number;
      scope: string;
      authority_chart: string;
    };
  };
  baseline: {
    revision: number;
    metrics: Metric[];
    scope_gaps: Record<string, null>;
    transportation: {observed_centerline_us_survey_ft: number};
  };
};

const labels: Record<string, string> = {
  reported_housing_units: 'Assessor-reported housing',
  open_business_receipt_cases: 'Open business receipt cases',
  workplace_jobs: 'Jobs by workplace',
  residence_based_jobs: 'Jobs by residence',
};

const methods: Record<string, string> = {
  positive_overlap: 'Blocks touching the district with positive area',
  representative_point_inside: 'Blocks with a representative point inside',
};

export default function CollegeParkBaseline({
  domain,
}: {domain: 'COMMERCIAL' | 'MAIN_STREET_INSTITUTIONAL'}) {
  const [data, setData] = useState<BaselineReadback | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  async function refresh() {
    setBusy(true);
    setError('');
    setData(null);
    try {
      const query = new URLSearchParams({domain});
      const response = await fetch('/api/cities-planning/research/college-park-baseline?' + query, {cache: 'no-store'});
      const body = await response.json();
      if (!response.ok) throw Error(typeof body.detail === 'string' ? body.detail : 'Baseline unavailable');
      setData(body);
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : 'Baseline unavailable');
    } finally {
      setBusy(false);
    }
  }

  return <section className="panel" aria-busy={busy}>
    <h2>College Park district baseline</h2>
    <button type="button" disabled={busy} onClick={refresh}>
      {busy ? 'Checking source receipts…' : data ? 'Refresh baseline' : 'Load baseline'}
    </button>
    {error && <p role="alert">{error}</p>}
    {data && <div aria-live="polite">
      <p>District baseline revision {data.baseline.revision}. Measures use different dates and geographic selections.</p>
      <dl>{data.baseline.metrics.map(metric => <div key={metric.name + (metric.method ?? '')}>
        <dt>{labels[metric.name] ?? metric.name} · {metric.period}</dt>
        <dd>
          <strong>{metric.value.toLocaleString('en-US')}</strong> {metric.unit}
          {metric.method && <p>{methods[metric.method] ?? metric.method}</p>}
          {metric.denominator !== null && <p>{metric.denominator} {metric.denominator_unit}</p>}
          <p>{metric.limits}</p>
        </dd>
      </div>)}</dl>
      <p>Observed Edgewater Drive centerline inside the district: {Math.round(data.baseline.transportation.observed_centerline_us_survey_ft).toLocaleString('en-US')} US survey feet.</p>
      <details>
        <summary>Orlando citywide comparison</summary>
        <h3>Employment · {data.citywide_comparators.employment.employment_year}</h3>
        <p>{data.citywide_comparators.employment.measures.wac.jobs.toLocaleString('en-US')} workplace jobs · {data.citywide_comparators.employment.measures.rac.jobs.toLocaleString('en-US')} residence-based jobs</p>
        <p>{data.citywide_comparators.employment.limits}</p>
        <h3>Assessor housing · {data.citywide_comparators.assessor_housing.assessment_year}</h3>
        <p>{data.citywide_comparators.assessor_housing.reported_unit_sum.toLocaleString('en-US')} units reported on {data.citywide_comparators.assessor_housing.parcels_with_numeric_values.toLocaleString('en-US')} parcels. {data.citywide_comparators.assessor_housing.parcels_without_numeric_values.toLocaleString('en-US')} parcels lack numeric values.</p>
        <p>{data.citywide_comparators.assessor_housing.scope}</p>
        <p><a href={data.citywide_comparators.assessor_housing.authority_chart}>Property Appraiser rate chart</a></p>
      </details>
      <details>
        <summary>Residential permit milestones</summary>
        <p>City-tagged cohort since January 2024, observed {data.district_residential_permits.observed_date}.</p>
        <dl>{Object.entries(data.district_residential_permits.worktypes).map(([kind, counts]) =>
          <div key={kind}><dt>{kind}</dt>
            <dd>{counts.issued} issued, {counts.final_date} final dates, {counts.coc_date} completion certificates, {counts.coo_date} occupancy certificates</dd>
          </div>
        )}</dl>
        <p>{data.district_residential_permits.scope}</p>
      </details>
      <details>
        <summary>Edgewater Drive funding</summary>
        <dl>{data.edgewater_funding.records.map(record =>
          <div key={record.phase}>
            <dt>{record.phase}</dt>
            <dd>
              {record.funding_state === 'CITY_REPORTS_COUNCIL_LAP_APPROVAL' ? 'City-reported council approval' : 'Programmed planning amount'}
              {' · '}
              {(record.published_project_cost ?? record.programmed_bond_or_loan) == null
                ? 'Amount unavailable'
                : Number(record.published_project_cost ?? record.programmed_bond_or_loan).toLocaleString('en-US', {style: 'currency', currency: 'USD'})}
              {' · '}<a href={record.source}>Source</a>
            </dd>
          </div>
        )}</dl>
        <p>For the roundabout, the regional program lists {Number(data.edgewater_funding.regional_tip_comparison.difference_from_city_reported_lap).toLocaleString('en-US', {style: 'currency', currency: 'USD'})} more in fiscal 2026 than the city-reported FDOT amount. <a href={data.edgewater_funding.regional_tip_comparison.source}>Regional program</a></p>
        <p>{data.edgewater_funding.scope}</p>
      </details>
      {data.district_operations && <details>
        <summary>District nonprofit finances</summary>
        <p>{data.district_operations.entity} · Form 990 for the year ended {data.district_operations.period_end}</p>
        <dl>{([
          ['Revenue', 'CYTotalRevenueAmt'],
          ['Expenses', 'CYTotalExpensesAmt'],
          ['Revenue less expenses', 'CYRevenuesLessExpensesAmt'],
        ] as const).map(([label, key]) => <div key={key}>
          <dt>{label}</dt>
          <dd>{data.district_operations?.reported_amounts[key].toLocaleString('en-US', {
            style: 'currency', currency: 'USD', maximumFractionDigits: 0,
          })}</dd>
        </div>)}</dl>
      </details>}
      <details><summary>Unverified measures</summary>
        <ul>{Object.entries(data.baseline.scope_gaps).filter(([, value]) => value === null)
          .map(([name]) => <li key={name}>{name.replaceAll('_', ' ')}</li>)}</ul>
      </details>
      <details style={{overflowWrap: 'anywhere'}}><summary>Source revision checksum</summary>
        <code>{data.revision_sha256}</code>
      </details>
    </div>}
  </section>;
}
