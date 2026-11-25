'use client';

import {useEffect, useRef, useState} from 'react';

type Point = [number, number];
type Feature = {
  id: string;
  geometry: {type: 'Polygon'; coordinates: Point[][]} | {type: 'MultiPolygon'; coordinates: Point[][][]};
  properties: {address: string; reported_units: number; lawful_units: number | null; decision: string};
};
type View = {longitude: number; latitude: number; zoom: number};
type Result = {
  features: Feature[];
  revision: string;
  representation: 'parcel' | 'overview';
  geometry_crs: string;
  source_sha256: Record<string, string>;
};
const initial: View = {longitude: -81.3905, latitude: 28.5721, zoom: 15};
const dossierSnapshot = '2026-11-24';
const dossierParcels = new Set<string>();
const width = 800;
const height = 430;

function bounds(view: View) {
  const degrees = .048 * 2 ** (15 - view.zoom);
  const vertical = degrees * height / width * Math.cos(view.latitude * Math.PI / 180);
  return {
    west: view.longitude - degrees / 2,
    east: view.longitude + degrees / 2,
    south: view.latitude - vertical / 2,
    north: view.latitude + vertical / 2,
  };
}

export default function CollegeParkMap() {
  const [view, setView] = useState(initial);
  const [result, setResult] = useState<Result | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const revision = useRef('');
  const canvas = useRef<HTMLCanvasElement>(null);
  const hitAreas = useRef<{id: string; outline: Path2D}[]>([]);

  useEffect(() => {
    const request = new AbortController();
    const params = new URLSearchParams({zoom: String(view.zoom)});
    for (const [key, value] of Object.entries(bounds(view))) params.set(key, String(value));
    if (revision.current) params.set('revision', revision.current);
    fetch('/api/acquisition-map/college-park?' + params, {cache: 'no-store', signal: request.signal})
      .then(async response => {
        const data = await response.json();
        if (!response.ok) throw Error(typeof data.detail === 'string' ? data.detail : 'Map unavailable');
        return data as Result;
      })
      .then(data => {
        if (request.signal.aborted) return;
        revision.current = data.revision;
        setResult(data);
        setLoading(false);
      })
      .catch((cause: unknown) => {
        if (request.signal.aborted) return;
        setError(cause instanceof Error ? cause.message : 'Map unavailable');
        setLoading(false);
      });
    return () => request.abort();
  }, [view]);

  useEffect(() => {
    const context = canvas.current?.getContext('2d');
    if (!context) return;
    const {west, east, south, north} = bounds(view);
    context.clearRect(0, 0, width, height);
    hitAreas.current = [];
    for (const feature of result?.features ?? []) {
      const parts = feature.geometry.type === 'Polygon' ? [feature.geometry.coordinates] : feature.geometry.coordinates;
      const outline = new Path2D();
      for (const rings of parts) {
        for (const ring of rings) {
          ring.forEach(([lon, lat], index) => {
            const x = (lon - west) * width / (east - west);
            const y = (north - lat) * height / (north - south);
            if (index === 0) outline.moveTo(x, y);
            else outline.lineTo(x, y);
          });
          outline.closePath();
        }
      }
      const active = feature.id === selected;
      context.fillStyle = active ? '#fcd34d' : '#86d1bc';
      context.strokeStyle = active ? '#92400e' : '#134e4a';
      context.lineWidth = active ? 3 : 2;
      context.fill(outline, 'evenodd');
      context.stroke(outline);
      hitAreas.current.push({id: feature.id, outline});
    }
  }, [result, view, selected]);

  function move(next: View) {
    setError('');
    setLoading(true);
    setResult(null);
    setSelected(null);
    setView({...next});
  }

  function pan(east: number, north: number) {
    const frame = bounds(view);
    move({...view,
      longitude: Math.max(-81.55, Math.min(-81.25, view.longitude + east * (frame.east - frame.west) / 3)),
      latitude: Math.max(28.43, Math.min(28.72, view.latitude + north * (frame.north - frame.south) / 3))});
  }

  const parcel = result?.features.find(feature => feature.id === selected);
  return <section className="panel">
    <h2>College Park parcel map</h2>
    <p>Retained College Park research snapshot · November 24, 2026. Parcel outlines are assessor geometry. District membership, lawful unit counts, and program eligibility are pending.</p>
    <div aria-label="Map controls" role="group">
      <button disabled={view.zoom <= 13} onClick={() => move({...view, zoom: view.zoom - 1})}>Zoom out</button>{' '}
      <button disabled={view.zoom >= 19} onClick={() => move({...view, zoom: view.zoom + 1})}>Zoom in</button>{' '}
      <button onClick={() => pan(0, 1)}>North</button>{' '}
      <button onClick={() => pan(0, -1)}>South</button>{' '}
      <button onClick={() => pan(-1, 0)}>West</button>{' '}
      <button onClick={() => pan(1, 0)}>East</button>{' '}
      <button onClick={() => {revision.current = ''; move(initial);}}>Reset map</button>
    </div>
    <p role="status">{loading ? 'Loading parcels...' : result?.representation === 'overview' ?
      'Zoom in to see parcel outlines.' : result ? `${result.features.length} parcels in view` : ''}</p>
    {error && <p role="alert">{error}</p>}
    <canvas ref={canvas} width={width} height={height} aria-label="College Park parcel outlines"
      style={{display: 'block', width: '100%', maxWidth: width, background: '#eef4ef'}}
      onClick={event => {
        const frame = event.currentTarget.getBoundingClientRect();
        const context = event.currentTarget.getContext('2d');
        const x = (event.clientX - frame.left) * width / frame.width;
        const y = (event.clientY - frame.top) * height / frame.height;
        setSelected(hitAreas.current.find(area => context?.isPointInPath(area.outline, x, y, 'evenodd'))?.id ?? null);
      }} />
    {Boolean(result?.features.length) && <ul aria-label="Parcels in view">
      {result?.features.map(feature => <li key={feature.id}>
        <button aria-pressed={selected === feature.id} onClick={() => setSelected(feature.id)}>
          {feature.properties.address}
        </button>
      </li>)}
    </ul>}
    {parcel && <div>
      <h3>{parcel.properties.address}</h3>
      <p>Parcel {parcel.id} · {parcel.properties.reported_units} assessment-reported units · {parcel.properties.decision}</p>
      <p>Lawful units {parcel.properties.lawful_units ?? 'unknown'}</p>
      {dossierParcels.has(parcel.id) && <a href={`/api/acquisition-dossiers/college-park/${parcel.id}?as_of=${dossierSnapshot}`}>
        Open dated parcel evidence ({dossierSnapshot})
      </a>}
    </div>}
    {result && <details>
      <summary>Geometry and source records</summary>
      <p>Geometry CRS {result.geometry_crs}</p>
      <p>Selection revision <code>{result.revision}</code></p>
      <ul>{Object.entries(result.source_sha256).map(([source, digest]) =>
        <li key={source}>{source} <code style={{overflowWrap: 'anywhere'}}>{digest}</code></li>
      )}</ul>
    </details>}
  </section>;
}
