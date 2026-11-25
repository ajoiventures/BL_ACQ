"""Capture verified acquisition execution as episodic evidence."""

import hashlib
import json

from . import acquisition_runs as runs


def initialize(db):
    db.execute("""CREATE TABLE IF NOT EXISTS acquisition_learning_episodes(
        id TEXT PRIMARY KEY, run_id TEXT NOT NULL REFERENCES acq_runs(id),
        batch_start INTEGER NOT NULL, body TEXT NOT NULL, recorded_at TEXT NOT NULL,
        UNIQUE(run_id, batch_start)
    )""")
    for operation in ("UPDATE", "DELETE"):
        db.execute(f"""CREATE TRIGGER IF NOT EXISTS learning_episode_no_{operation.lower()}
            BEFORE {operation} ON acquisition_learning_episodes
            BEGIN SELECT RAISE(ABORT, 'Immutable learning episode'); END""")

    db.execute("""CREATE TABLE IF NOT EXISTS acquisition_learning_proposals(
        id TEXT PRIMARY KEY, body TEXT NOT NULL
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS acquisition_learning_reviews(
        proposal_id TEXT PRIMARY KEY REFERENCES acquisition_learning_proposals(id),
        body TEXT NOT NULL
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS acquisition_learning_outcomes(
        id TEXT PRIMARY KEY, episode_id TEXT NOT NULL REFERENCES acquisition_learning_episodes(id),
        body TEXT NOT NULL, recorded_at TEXT NOT NULL
    )""")
    db.execute("""CREATE INDEX IF NOT EXISTS learning_outcomes_episode
        ON acquisition_learning_outcomes(episode_id, recorded_at, id)""")
    db.execute("""CREATE TABLE IF NOT EXISTS acquisition_outcome_reviews(
        outcome_id TEXT PRIMARY KEY REFERENCES acquisition_learning_outcomes(id),
        body TEXT NOT NULL
    )""")
    for table in ("acquisition_learning_proposals", "acquisition_learning_reviews",
                  "acquisition_learning_outcomes", "acquisition_outcome_reviews"):
        for operation in ("UPDATE", "DELETE"):
            db.execute(f"""CREATE TRIGGER IF NOT EXISTS {table}_no_{operation.lower()}
                BEFORE {operation} ON {table}
                BEGIN SELECT RAISE(ABORT, 'Immutable learning record'); END""")


def capture_batch(db, run_id, batch_start):
    verification = runs.verify_batch(db, run_id, batch_start)
    receipt = json.loads(db.execute(
        "SELECT receipt FROM acq_batches WHERE run_id=? AND start=?", (run_id, batch_start),
    ).fetchone()[0])
    manifest = runs.snapshot_available(db, verification["snapshot_id"])
    episode = {
        "schema_version": 1,
        "memory": "EPISODIC",
        "kind": "ACQUISITION_BATCH_EXECUTION",
        "source": {**verification, "manifest_sha256": runs.sha(manifest),
                   "receipt_sha256": runs.sha(receipt)},
        "execution_receipt": receipt,
        "execution_outcome": "COMPLETED_VERIFIED",
        "acquisition_outcome": "UNKNOWN",
        "eligible_records": verification["records_verified"],
        "realized_cash_cents": None,
        "observed_cost_cents": None,
        "promotion_authorized": False,
    }
    digest = runs.sha(episode)
    existing = db.execute(
        "SELECT id FROM acquisition_learning_episodes WHERE run_id=? AND batch_start=?",
        (run_id, batch_start),
    ).fetchone()
    if existing and existing["id"] != digest:
        raise ValueError("Execution source changed after episode capture")
    if not existing:
        db.execute("INSERT INTO acquisition_learning_episodes VALUES(?,?,?,?,?)",
                   (digest, run_id, batch_start, runs.encode(episode), runs.now()))
    return {"id": digest, "episode": episode, "replay": existing is not None}


def read(db, episode_id):
    row = db.execute("SELECT body,recorded_at FROM acquisition_learning_episodes WHERE id=?",
                     (episode_id,)).fetchone()
    if row is None:
        raise LookupError("Learning episode not found")
    episode = json.loads(row["body"])
    if runs.sha(episode) != episode_id:
        raise ValueError("Learning episode digest mismatch")
    return {"id": episode_id, "episode": episode, "recorded_at": row["recorded_at"]}


def attempt_history(db, run_id, *, after, limit):
    """Project pending and unsuccessful states from the append-only run audit."""
    runs.get(db, run_id)
    events = db.execute("""SELECT seq,action,body,at,prev_hash,hash FROM audit
        WHERE domain='COMMERCIAL' AND object_id=? AND seq>?
          AND action IN ('ACQ_RUN_START','ACQ_RUN_STEP') ORDER BY seq LIMIT ?""",
        (run_id, after, limit + 1)).fetchall()
    episodes = []
    for row in events[:limit]:
        if hashlib.sha256((row["prev_hash"] + row["body"]).encode()).hexdigest() != row["hash"]:
            raise ValueError("Run attempt audit digest mismatch")
        domain, _, action, subject, detail = json.loads(row["body"])
        if (domain, action, subject) != ("COMMERCIAL", row["action"], run_id):
            raise ValueError("Run attempt audit scope mismatch")
        state = "READY" if action == "ACQ_RUN_START" else detail["state"]
        outcome = {"FAILED": "FAILED", "CANCELLED": "CANCELLED", "COMPLETED": "COMPLETED"}.get(state, "PENDING")
        episodes.append({
            "schema_version": 1, "memory": "EPISODIC", "kind": "ACQUISITION_RUN_ATTEMPT",
            "source": {"run_id": run_id, "audit_sequence": row["seq"], "audit_sha256": row["hash"],
                       "observed_at": row["at"]},
            "execution_outcome": outcome, "run_state": state, "execution_details": detail,
            "acquisition_outcome": "UNKNOWN", "realized_cash_cents": None,
            "observed_cost_cents": None, "promotion_authorized": False,
        })
    return {"episodes": episodes, "next_after": episodes[-1]["source"]["audit_sequence"] if len(events) > limit else None}


def _batch_completion_sequence(db, source):
    """Locate the audited advance that persisted this exact batch."""
    run_id = source["run_id"]
    events = db.execute("""SELECT seq,body,prev_hash,hash FROM audit
        WHERE domain='COMMERCIAL' AND object_id=? AND action='ACQ_RUN_STEP'
        ORDER BY seq""", (run_id,))
    for row in events:
        domain, _, action, subject, detail = json.loads(row["body"])
        if (domain, action, subject) != ("COMMERCIAL", "ACQ_RUN_STEP", run_id):
            raise ValueError("Batch completion audit scope mismatch")
        if detail["action"] != "advance" or detail["cursor"] != source["end"]:
            continue
        if detail["state"] not in {"RUNNING", "COMPLETED"}:
            continue
        if (detail.get("snapshot_id") != source["snapshot_id"]
                or hashlib.sha256((row["prev_hash"] + row["body"]).encode()).hexdigest() != row["hash"]):
            raise ValueError("Batch completion audit does not match the retained episode")
        return row["seq"]
    raise ValueError("Verified batch completion audit is unavailable")


def propose_comparison(db, *, pairs, rationale, expected_outcome, rollback, previous_proposal_id=None,
                       revision=None):
    if revision is not None and revision["baseline_sha256"] == revision["candidate_sha256"]:
        raise ValueError("Baseline and candidate revisions must differ")
    if previous_proposal_id is not None:
        read_proposal(db, previous_proposal_id)
    comparisons = []
    inputs = set()
    for pair in pairs:
        baseline = read(db, pair["baseline_id"])
        candidate = read(db, pair["candidate_id"])
        earlier, later = baseline["episode"], candidate["episode"]
        before, after = earlier["source"], later["source"]
        if (before["run_id"] == after["run_id"]
                or baseline["recorded_at"] >= candidate["recorded_at"]
                or before["snapshot_id"] != after["snapshot_id"]
                or before["manifest_sha256"] != after["manifest_sha256"]
                or before["input_sha256"] != after["input_sha256"]
                or earlier["eligible_records"] != later["eligible_records"]):
            raise ValueError("Require a later run and capture on identical retained inputs")
        if _batch_completion_sequence(db, before) >= _batch_completion_sequence(db, after):
            raise ValueError("Require a later run and capture on identical retained inputs")
        if before["input_sha256"] in inputs:
            raise ValueError("Comparison requires distinct input cases")
        inputs.add(before["input_sha256"])
        comparisons.append({
            **pair, "input_sha256": before["input_sha256"], "eligible_records": earlier["eligible_records"],
            "baseline_backend": earlier["execution_receipt"]["backend"],
            "candidate_backend": later["execution_receipt"]["backend"],
            "baseline_compute_s": earlier["execution_receipt"].get("compute_s"),
            "candidate_compute_s": later["execution_receipt"].get("compute_s"),
            "baseline_results_sha256": before["results_sha256"],
            "candidate_results_sha256": after["results_sha256"],
            "baseline_recorded_at": baseline["recorded_at"],
            "candidate_recorded_at": candidate["recorded_at"],
        })
    if len(comparisons) < 2:
        raise ValueError("At least two distinct comparison cases are required")
    proposal = {
        "schema_version": 1, "memory": "PROCEDURAL_PROPOSAL", "rationale": rationale,
        "expected_outcome": expected_outcome, "rollback": rollback,
        "observed_result": "OUTPUT_REGRESSION" if any(
            c["baseline_results_sha256"] != c["candidate_results_sha256"] for c in comparisons
        ) else "EXACT_OUTPUT_PARITY",
        "comparisons": sorted(comparisons, key=lambda case: case["input_sha256"]),
        "promotion_authorized": False,
    }
    if previous_proposal_id is not None:
        proposal["previous_proposal_id"] = previous_proposal_id
    if revision is not None:
        proposal["revision"] = {
            **revision, "evidence_status": "DECLARED_UNVERIFIED",
        }
    proposal_id = runs.sha(proposal)
    inserted = db.execute("INSERT OR IGNORE INTO acquisition_learning_proposals VALUES(?,?)",
                          (proposal_id, runs.encode(proposal))).rowcount
    return {"id": proposal_id, "proposal": proposal, "replay": inserted == 0}


def read_proposal(db, proposal_id):
    row = db.execute("""
        SELECT p.body AS proposal,r.body AS review
        FROM acquisition_learning_proposals p
        LEFT JOIN acquisition_learning_reviews r ON r.proposal_id=p.id
        WHERE p.id=?
    """, (proposal_id,)).fetchone()
    if row is None:
        raise LookupError("Learning proposal not found")
    proposal = json.loads(row["proposal"])
    if runs.sha(proposal) != proposal_id:
        raise ValueError("Learning proposal digest mismatch")
    review = json.loads(row["review"]) if row["review"] is not None else None
    if review is not None:
        audit = db.execute("""SELECT body,prev_hash,hash FROM audit
            WHERE domain='COMMERCIAL' AND object_id=? AND action='ACQ_LEARNING_PROPOSAL_REVIEWED'
            ORDER BY seq DESC LIMIT 1""", (proposal_id,)).fetchone()
        if (audit is None
                or hashlib.sha256((audit["prev_hash"] + audit["body"]).encode()).hexdigest() != audit["hash"]
                or json.loads(audit["body"]) != ["COMMERCIAL", "SW-13", "ACQ_LEARNING_PROPOSAL_REVIEWED", proposal_id, review]):
            raise ValueError("Learning review audit mismatch")
    return {"id": proposal_id, "proposal": proposal, "review": review}


def proposal_memory(revision):
    """Project the frozen proposal into distinct evidence and workflow views."""
    proposal = revision["proposal"]
    comparison = proposal["comparisons"]
    review = revision["review"]
    return {
        "working": {
            "review_state": review["decision"] if review else "PENDING_REVIEW",
            "next_action": "RETAIN_REVIEW" if review else "REVIEW_FROZEN_COMPARISON",
        },
        "semantic": {
            "frozen_input_sha256": [case["input_sha256"] for case in comparison],
            "verification_scope": "IDENTICAL_RETAINED_INPUTS_PER_PAIR",
        },
        "episodic": {
            "pairs": [
                {key: case[key] for key in ("baseline_id", "candidate_id", "eligible_records",
                                          "baseline_results_sha256", "candidate_results_sha256")}
                for case in comparison
            ],
            "observed_comparison": proposal["observed_result"],
        },
        "procedural": {
            "proposal_id": revision["id"], "rationale": proposal["rationale"],
            "previous_proposal_id": proposal.get("previous_proposal_id"),
            "rollback": proposal["rollback"], "promotion_authorized": False,
            "revision": proposal.get("revision"),
        },
        "predictive": {
            "expected_outcome": proposal["expected_outcome"],
            "classification": "SUPPLIED_EXPECTATION",
        },
    }


def review_comparison(db, proposal_id, *, reviewer, decision, rationale):
    if reviewer != "SW-13":
        raise ValueError("Independent review required")
    proposal = read_proposal(db, proposal_id)["proposal"]
    if decision == "VALIDATE_REHEARSAL" and proposal["observed_result"] != "EXACT_OUTPUT_PARITY":
        raise ValueError("Output regression cannot be validated")
    review = {"schema_version": 1, "proposal_id": proposal_id, "reviewer": reviewer,
              "decision": decision, "rationale": rationale, "promotion_authorized": False}
    body = runs.encode(review)
    previous = db.execute("SELECT body FROM acquisition_learning_reviews WHERE proposal_id=?", (proposal_id,)).fetchone()
    if previous and previous["body"] != body:
        raise ValueError("Learning proposal already has an immutable review")
    if not previous:
        db.execute("INSERT INTO acquisition_learning_reviews VALUES(?,?)", (proposal_id, body))
    return {"review": review, "replay": previous is not None}


def report_outcome(db, episode_id, *, parcel_key, outcome, observed_on, source_ref,
                   source_revision_sha256, excerpt, reported_cash_cents):
    from datetime import date

    source = read(db, episode_id)["episode"]["source"]
    recorded_date = date.fromisoformat(observed_on)
    if recorded_date.isoformat() != observed_on or recorded_date > date.today():
        raise ValueError("Use a current or historical ISO observation date")
    if not source_ref.strip() or not excerpt.strip():
        raise ValueError("Source locator and retained excerpt are required")
    if reported_cash_cents is not None and outcome != "CLOSED":
        raise ValueError("Cash may only be reported for a closed outcome")
    parcel = db.execute("""SELECT 1 FROM acq_parcels
        WHERE snapshot_id=? AND parcel_key=? AND ordinal>=? AND ordinal<?""",
        (source["snapshot_id"], parcel_key, source["start"], source["end"])).fetchone()
    if parcel is None:
        raise LookupError("Parcel is outside the frozen learning episode")
    observation = {
        "schema_version": 1, "episode_id": episode_id, "parcel_key": parcel_key,
        "reported_outcome": outcome, "observed_on": observed_on,
        "source": {"locator": source_ref.strip(), "revision_sha256": source_revision_sha256,
                   "excerpt": excerpt.strip(), "excerpt_sha256": runs.sha(excerpt.strip())},
        "reported_cash_cents": reported_cash_cents, "realized_cash_cents": None,
        "evidence_state": "SOURCE_REPORTED", "promotion_authorized": False,
    }
    outcome_id = runs.sha(observation)
    inserted = db.execute("INSERT OR IGNORE INTO acquisition_learning_outcomes VALUES(?,?,?,?)",
                          (outcome_id, episode_id, runs.encode(observation), runs.now())).rowcount
    return {"id": outcome_id, "observation": observation, "replay": inserted == 0}


def outcome_history(db, episode_id, *, offset, limit):
    read(db, episode_id)
    rows = db.execute("""SELECT o.id,o.body,o.recorded_at,r.body AS review FROM acquisition_learning_outcomes o
        LEFT JOIN acquisition_outcome_reviews r ON r.outcome_id=o.id
        WHERE o.episode_id=? ORDER BY o.recorded_at,o.id LIMIT ? OFFSET ?""",
        (episode_id, limit + 1, offset)).fetchall()
    observations = []
    for row in rows[:limit]:
        body = json.loads(row["body"])
        if runs.sha(body) != row["id"] or body["episode_id"] != episode_id:
            raise ValueError("Learning outcome digest mismatch")
        observations.append({"id": row["id"], "observation": body, "recorded_at": row["recorded_at"],
                             "review": json.loads(row["review"]) if row["review"] else None})
    return {"observations": observations, "next_offset": offset + limit if len(rows) > limit else None}


def reconcile_outcome(db, episode_id, outcome_id, *, reviewer, ledger_ref, ledger_sha256, ledger_cash_cents):
    if reviewer != "SW-13":
        raise ValueError("Independent reviewer required")
    read(db, episode_id)
    row = db.execute("SELECT body FROM acquisition_learning_outcomes WHERE id=? AND episode_id=?",
                     (outcome_id, episode_id)).fetchone()
    if row is None:
        raise LookupError("Outcome not found in this episode")
    observation = json.loads(row["body"])
    if runs.sha(observation) != outcome_id:
        raise ValueError("Outcome digest mismatch")
    origin = observation["source"]
    ledger_ref = ledger_ref.strip()
    if (observation["reported_outcome"] != "CLOSED" or observation["reported_cash_cents"] is None
            or not ledger_ref or ledger_ref.casefold() == origin["locator"].casefold()
            or ledger_sha256 == origin["revision_sha256"]):
        raise ValueError("A closed outcome and distinct ledger evidence are required")
    ledger_scope = "REVIEWER_SUPPLIED_REFERENCE"
    if ledger_ref.startswith("app-ledger:"):
        ledger_id = ledger_ref.removeprefix("app-ledger:")
        ledger = db.execute("SELECT * FROM ledger WHERE id=? AND domain='COMMERCIAL'", (ledger_id,)).fetchone()
        if ledger is None:
            raise LookupError("Commercial ledger entry not found")
        entry = dict(ledger)
        cash = (entry["cents"] if entry["debit_account"] == "Cash"
                else -entry["cents"] if entry["credit_account"] == "Cash" else None)
        if (runs.sha(entry) != ledger_sha256 or cash != ledger_cash_cents
                or f"outcome_sha256:{outcome_id}" not in entry["evidence"].splitlines()):
            raise ValueError("Ledger entry does not match the supplied revision, cash amount and outcome")
        ledger_scope = "VERIFIED_APP_SIMULATION_JOURNAL"
    matches = ledger_cash_cents == observation["reported_cash_cents"]
    review = {"schema_version": 1, "episode_id": episode_id, "outcome_id": outcome_id,
              "reviewer": reviewer, "settlement_revision_sha256": origin["revision_sha256"],
              "ledger_locator": ledger_ref, "ledger_revision_sha256": ledger_sha256,
              "ledger_reported_cash_cents": ledger_cash_cents,
              "disposition": "AMOUNTS_MATCH" if matches else "AMOUNTS_CONFLICT",
              "reconciled_reported_cash_cents": ledger_cash_cents if matches else None,
              "scope": "LOCAL_RESEARCH_RECONCILIATION", "ledger_evidence_scope": ledger_scope,
              "promotion_authorized": False}
    body = runs.encode(review)
    existing = db.execute("SELECT body FROM acquisition_outcome_reviews WHERE outcome_id=?", (outcome_id,)).fetchone()
    if existing and existing["body"] != body:
        previous = json.loads(existing["body"])
        if "ledger_evidence_scope" not in previous and previous == {
                key: value for key, value in review.items() if key != "ledger_evidence_scope"
        } and ledger_scope == "REVIEWER_SUPPLIED_REFERENCE":
            return {"review": previous, "replay": True}
        raise ValueError("Outcome already reviewed; retain any new source revision as a new observation")
    if not existing:
        db.execute("INSERT INTO acquisition_outcome_reviews VALUES(?,?)", (outcome_id, body))
    return {"review": review, "replay": existing is not None}
