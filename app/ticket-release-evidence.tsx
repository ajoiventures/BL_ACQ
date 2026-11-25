'use client';

import {useEffect, useState} from 'react';

type ReleaseEvidence = {
  release_sha256: string;
  evidence: string;
  source: string;
  reviewed_execution_links?: {
    assessment_id: string;
    operation_id: string;
    skill_id: string;
    receipt_sha256: string;
  }[];
};

type Result =
  | {status: 'idle' | 'loading' | 'error'}
  | {status: 'loaded'; evidence: ReleaseEvidence | null};

export default function TicketReleaseEvidence({ticketId}: {ticketId: string}) {
  const [attempt, setAttempt] = useState(0);
  const [result, setResult] = useState<Result>({status: 'idle'});

  useEffect(() => {
    if (!attempt) return;
    const controller = new AbortController();

    async function load() {
      try {
        const response = await fetch(
          `/api/tickets/${encodeURIComponent(ticketId)}/release-evidence`,
          {cache: 'no-store', signal: controller.signal},
        );
        if (!response.ok) throw new Error('Release evidence unavailable');
        const data: {release_evidence: ReleaseEvidence | null} = await response.json();
        if (!controller.signal.aborted) {
          setResult({status: 'loaded', evidence: data.release_evidence});
        }
      } catch {
        if (!controller.signal.aborted) setResult({status: 'error'});
      }
    }

    void load();
    return () => controller.abort();
  }, [attempt, ticketId]);

  function requestEvidence() {
    setResult({status: 'loading'});
    setAttempt(value => value + 1);
  }

  if (result.status === 'loaded') {
    if (!result.evidence) return <p role="status">No installed release evidence for this ticket.</p>;
    return (
      <div aria-label="Installed release evidence">
        <p style={{whiteSpace: 'pre-wrap', overflowWrap: 'anywhere'}}>
          <strong>Installed release evidence</strong>{' '}{result.evidence.evidence}
        </p>
        <p style={{overflowWrap: 'anywhere'}}>
          <strong>Source</strong> {result.evidence.source}<br />
          <strong>Release digest</strong> <code>{result.evidence.release_sha256}</code>
        </p>
        {!!result.evidence.reviewed_execution_links?.length && <details>
          <summary>Reviewed Academy simulations</summary>
          <ul>{result.evidence.reviewed_execution_links.map(link =>
            <li key={JSON.stringify([link.assessment_id, link.operation_id])} style={{overflowWrap: 'anywhere'}}>
              <strong>{link.skill_id}</strong><br />
              Assessment <code>{link.assessment_id}</code><br />
              Execution <code>{link.operation_id}</code><br />
              Receipt digest <code>{link.receipt_sha256}</code>
            </li>
          )}</ul>
        </details>}
      </div>
    );
  }

  return (
    <div>
      <button type="button" disabled={result.status === 'loading'} onClick={requestEvidence}>
        {result.status === 'error' ? 'Retry release evidence' : 'Show release evidence'}
      </button>
      {result.status === 'loading' && <p role="status">Loading release evidence…</p>}
      {result.status === 'error' && <p role="alert">Release evidence unavailable.</p>}
    </div>
  );
}
