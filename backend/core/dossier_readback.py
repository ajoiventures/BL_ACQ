"""Read a dated College Park dossier from bounded, retained public evidence."""

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from .spatial_constraints import screen_walkable_main_street

COVERAGE = Path(__file__).resolve().parents[2] / "docs/acquisition/college-park-coverage"
AS_OF = "2026-11-24"


class ParcelOutsideSample(LookupError):
    """The requested parcel is absent from the retained snapshot."""


def load(name):
    raw = (COVERAGE / name).read_bytes()
    return json.loads(raw), hashlib.sha256(raw).hexdigest()


def read_dossier(parcel_id, as_of, *, context_path=None):
    if as_of != AS_OF:
        raise ValueError("No retained dossier snapshot for that date")
    cards, cards_hash = load("candidate-property-card-review.json")
    permits, _ = load("candidate-permit-review.json")
    screen, screen_hash = load("candidate-screen.json")
    if {source["as_of"] for source in (cards, permits, screen)} != {as_of}:
        raise RuntimeError("Dossier source dates disagree")
    card = next((row for row in cards["cards"] if row["county_parcel_id"] == parcel_id), None)
    if card is None:
        raise ParcelOutsideSample(parcel_id)
    permit = next((row for row in permits["results"] if row["county_parcel_id"] == parcel_id), None)
    candidate = next((row for row in screen["matches"] if row["county_parcel_id"] == parcel_id), None)
    if not permit or not candidate or permit["response"] != f"orlando-permits-{parcel_id}.json":
        raise RuntimeError("Dossier evidence is incomplete")
    rows, permits_hash = load(permit["response"])
    if (permits_hash != permit["sha256"] or len(rows) != permit["rows"]
            or any(row["parcel_number"] != parcel_id for row in rows)):
        raise RuntimeError("Permit evidence integrity check failed")
    if (card["address"] != candidate["assessment_address"]
            or card["roll_reported_units"] != candidate["reported_units"]):
        raise RuntimeError("Parcel evidence conflicts")

    dossier = {
        "as_of": as_of,
        "parcel_id": parcel_id,
        "address": card["address"],
        "reported_units": card["roll_reported_units"],
        "permit_rows": len(rows),
        "occupancy_date_rows": sum(bool(row.get("coo_date")) for row in rows),
        "district_labels": sorted({row["mainstreet_district"] for row in rows if row.get("mainstreet_district")}),
        "provisional_overlap_fraction": candidate["provisional_overlap_fraction"],
        "lawful_units": None,
        "accepted_district_membership": None,
        "walkability": screen_walkable_main_street(
            parcel_id=parcel_id,
            district_membership=None,
            lawful_units=None,
        ),
        "utility_capacity": None,
        "decision": "HOLD",
        "recommendation": "Obtain city documentation of lawful unit count and district membership.",
        "sources": [
            {"url": card["source_url"], "sha256": cards_hash, "span": "Property Features"},
            {"url": permit["source_url"], "sha256": permits_hash, "span": "All retained permit rows"},
            {"artifact": "candidate-screen.json", "sha256": screen_hash, "span": f"matches for {parcel_id}"},
        ],
        "provider": "Local retained public evidence",
        "external_provider_calls": 0,
        "external_provider_cost_cents": 0,
    }

    permit_fields = ("permit_number", "application_type", "worktype", "application_status",
                     "issue_permit_date", "final_date", "coo_date", "coc_date")
    dossier["permits"] = sorted(
        ({field: row.get(field) for field in permit_fields} for row in rows),
        key=lambda row: (row["issue_permit_date"] or "", row["permit_number"] or ""),
    )
    dossier["building"] = {
        "assessor_land_use": card["land_use"],
        "assessor_building_use_subtype": card["building_use_subtype"],
        "observed_condition": None,
        "verified_rents": None,
    }
    dossier["ownership"] = {"verified_owner": None, "lineage": None}
    dossier["transactions"] = []
    if context_path:
        with Path(context_path).open("rb") as stream:
            raw = stream.read(262_145)
        if len(raw) > 262_144:
            raise RuntimeError("Dossier context exceeds the retained evidence limit")
        packet = json.loads(raw)
        if packet["as_of"] != as_of:
            raise RuntimeError("Dossier context date disagrees with the snapshot")
        parcels = packet["parcels"]
        if not isinstance(parcels, dict):
            raise RuntimeError("Dossier context parcel index is invalid")
        records = parcels.get(parcel_id)
        if records is not None:
            dossier["context"] = resolve_context(records, parcel_id, as_of=as_of)
            dossier["context"]["artifact_sha256"] = hashlib.sha256(raw).hexdigest()
    dossier["revision_sha256"] = hashlib.sha256(
        json.dumps(dossier, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()
    return dossier


def resolve_context(records, parcel_id, *, as_of):
    """Resolve visible revisions and keep source excerpts outside decision logic."""
    from datetime import date

    from .owner_entity_candidates import reconcile

    cutoff = date.fromisoformat(as_of)
    visible = {}
    for record in records["revisions"]:
        effective = date.fromisoformat(record["effective_date"])
        observed = date.fromisoformat(record["observed_date"])
        if effective <= cutoff and observed <= cutoff:
            visible.setdefault(record["series"], []).append(record)

    current = {}
    for series, versions in sorted(visible.items()):
        versions.sort(key=lambda row: (row["effective_date"], row["revision"]))
        latest = versions[-1]
        current[series] = {
            "value": latest["value"],
            "source_ref": latest["source_ref"],
            "span": latest["span"],
            "historical_sources": [row["source_ref"] for row in versions[:-1]],
        }

    filings = [
        row for row in records["registry_filings"]
        if date.fromisoformat(row["observed_date"]) <= cutoff
    ]
    identity = reconcile(parcel_id, records["assessor_name"], filings, [], cutoff=as_of)
    return {
        "revisions": current,
        "entity_candidates": identity["candidates"],
        "accepted_owner_id": identity["accepted_owner_id"],
        "signing_authority": identity["signing_authority"],
        "external_actions": [],
    }


def initialize_history(db):
    db.execute("""
        CREATE TABLE IF NOT EXISTS acquisition_dossier_revisions (
            parcel_id TEXT NOT NULL,
            revision TEXT NOT NULL,
            payload TEXT NOT NULL,
            PRIMARY KEY (parcel_id, revision)
        )
    """)
    for operation in ("UPDATE", "DELETE"):
        db.execute(f"""
            CREATE TRIGGER IF NOT EXISTS acquisition_dossier_no_{operation.lower()}
            BEFORE {operation} ON acquisition_dossier_revisions
            BEGIN SELECT RAISE(ABORT, 'Immutable dossier revision'); END
        """)


def retain_revision(db, dossier):
    payload = json.dumps(dossier, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return bool(db.execute("""
        INSERT INTO acquisition_dossier_revisions VALUES (?, ?, ?)
        ON CONFLICT(parcel_id, revision) DO NOTHING
    """, (dossier["parcel_id"], dossier["revision_sha256"], payload)).rowcount)


def retained_revision(db, parcel_id, revision):
    row = db.execute("""
        SELECT payload FROM acquisition_dossier_revisions WHERE parcel_id=? AND revision=?
    """, (parcel_id, revision)).fetchone()
    if row is None:
        return None
    dossier = json.loads(row[0])
    stored = dossier.pop("revision_sha256")
    canonical = json.dumps(dossier, sort_keys=True, separators=(",", ":"), allow_nan=False)
    if (stored != revision or dossier["parcel_id"] != parcel_id
            or hashlib.sha256(canonical.encode()).hexdigest() != revision):
        raise RuntimeError("Retained dossier revision digest mismatch")
    return {**dossier, "revision_sha256": revision}


def list_revisions(db, parcel_id, *, limit, offset):
    """Return capture-ordered revision locators without loading complete dossiers."""
    if not db.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='acquisition_dossier_revisions'"
    ).fetchone():
        return []
    rows = db.execute("""
        SELECT revision, json_extract(payload, '$.as_of') AS as_of
        FROM acquisition_dossier_revisions WHERE parcel_id=?
        ORDER BY rowid DESC LIMIT ? OFFSET ?
    """, (parcel_id, limit, offset))
    return [{"revision_sha256": row["revision"], "as_of": row["as_of"]} for row in rows]
