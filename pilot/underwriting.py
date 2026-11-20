"""Deterministic, review-only qualification and underwriting for the synthetic pilot."""

from dataclasses import asdict, dataclass
from datetime import date
import hashlib
import json
import math


@dataclass(frozen=True)
class Evidence:
    kind: str
    subject: str
    source: str
    observed: date
    expires: date
    confirmed: bool
    reference: str


@dataclass(frozen=True)
class Candidate:
    deal_id: str
    parcel_id: str
    district: str
    thesis: str
    property_family: str
    latitude: float
    longitude: float
    evidence: tuple[Evidence, ...]
    landlocked: bool | None = None
    wetlands_bps: int | None = None
    surviving_liens_cents: int | None = None


@dataclass(frozen=True)
class Economics:
    resale_cents: int
    renovation_cents: int
    carrying_cents: int
    selling_bps: int
    stress_price_drop_bps: int
    stress_extra_cents: int
    base_profit_cents: int
    stress_profit_cents: int
    financing_cap_cents: int | None

    def __post_init__(self):
        for name, value in asdict(self).items():
            if name == "financing_cap_cents" and value is None:
                continue
            if type(value) is not int or value < 0:
                raise ValueError(f"{name} must be a nonnegative integer")
        if self.selling_bps > 10000 or self.stress_price_drop_bps > 10000:
            raise ValueError("Rates must be between 0 and 10000 basis points")


@dataclass(frozen=True)
class Approval:
    reviewer: str
    packet_digest: str
    reviewed_on: date


def _check_evidence(candidate, as_of, required):
    checks = []
    for kind, subject, count in required:
        records = [e for e in candidate.evidence if e.kind == kind and e.subject == subject]
        current = [e for e in records if e.source.strip() and e.reference.strip()
                   and e.observed <= as_of <= e.expires]
        supported = {e.reference for e in current if e.confirmed is True}
        # Any current contrary evidence keeps the gate open for human resolution.
        passed = len(supported) >= count and all(e.confirmed is True for e in current)
        reason = "confirmed" if passed else "missing, expired or incomplete evidence"
        if any(e.confirmed is not True for e in current):
            reason = "contrary evidence"
        checks.append({"gate": kind, "passed": passed, "reason": reason, "required": count,
                       "evidence": [asdict(e) | {"observed": e.observed.isoformat(),
                                                "expires": e.expires.isoformat()} for e in records]})
    return checks


def qualify(candidate: Candidate, as_of: date) -> dict:
    checks = _check_evidence(candidate, as_of, (
        ("district_demand", candidate.district, 1), ("coordinates", candidate.parcel_id, 1),
        ("legal_use", candidate.parcel_id, 1), ("closed_comp", candidate.deal_id, 3),
        ("costs", candidate.deal_id, 1), ("financing", candidate.deal_id, 1)))
    def coordinate_ok(value, limit):
        return type(value) in (int, float) and math.isfinite(value) and abs(value) <= limit

    checks.extend([
        {"gate": "identity", "passed": all(s.strip() for s in (
            candidate.deal_id, candidate.parcel_id, candidate.district, candidate.thesis))},
        {"gate": "coordinate_range", "passed": coordinate_ok(candidate.latitude, 90)
         and coordinate_ok(candidate.longitude, 180)},
        {"gate": "property_family", "passed": candidate.property_family in ("single_family", "duplex")}
    ])
    return {"deal_id": candidate.deal_id, "parcel_id": candidate.parcel_id,
            "district": candidate.district, "thesis": candidate.thesis,
            "property_family": candidate.property_family,
            "coordinates": [candidate.latitude if coordinate_ok(candidate.latitude, 90) else None,
                            candidate.longitude if coordinate_ok(candidate.longitude, 180) else None],
            "as_of": as_of.isoformat(),
            "state": "eligible" if all(c["passed"] for c in checks) else "review_required",
            "checks": checks}


def purchase_limits(economics: Economics) -> dict:
    """Return conservative purchase ceilings in cents. Round proceeds down."""
    e = economics
    stressed_resale = e.resale_cents * (10000 - e.stress_price_drop_bps) // 10000
    base_net = e.resale_cents * (10000 - e.selling_bps) // 10000
    downside_net = stressed_resale * (10000 - e.selling_bps) // 10000
    costs = e.renovation_cents + e.carrying_cents
    return {"base": base_net - costs - e.base_profit_cents,
            "downside": downside_net - costs - e.stress_extra_cents - e.stress_profit_cents,
            "financing": e.financing_cap_cents}


def underwrite(candidate: Candidate, economics: Economics, proposed_cents: int, as_of: date,
               preparer: str, approval: Approval | None = None) -> dict:
    """Recompute the packet at review. A changed input invalidates its prior approval."""
    if type(proposed_cents) is not int or proposed_cents <= 0 or not preparer.strip():
        raise ValueError("A positive proposed bid and a named preparer are required")
    qualification = qualify(candidate, as_of)
    gates = _check_evidence(candidate, as_of, (
        ("title", candidate.parcel_id, 1), ("spatial", candidate.parcel_id, 1)))
    gates.extend([
        {"gate": "road_access", "passed": candidate.landlocked is False,
         "landlocked": candidate.landlocked},
        {"gate": "wetlands", "passed": type(candidate.wetlands_bps) is int
         and 0 <= candidate.wetlands_bps <= 5000, "wetlands_bps": candidate.wetlands_bps},
        {"gate": "surviving_liens", "passed": candidate.surviving_liens_cents == 0
         and type(candidate.surviving_liens_cents) is int,
         "liens_cents": candidate.surviving_liens_cents}])
    limits = purchase_limits(economics)
    ceiling = min(limits.values()) if None not in limits.values() else None
    packet = {"qualification": qualification, "economics": asdict(economics), "limits": limits,
              "gates": gates, "proposed_cents": proposed_cents, "preparer": preparer}
    digest = hashlib.sha256(json.dumps(packet, sort_keys=True, separators=(",", ":"),
                                       allow_nan=False).encode()).hexdigest()
    allowed = (qualification["state"] == "eligible" and all(g["passed"] for g in gates)
               and ceiling is not None and proposed_cents <= ceiling)
    signed = bool(approval and approval.reviewer.strip()
                  and approval.reviewer.strip().casefold() != preparer.strip().casefold()
                  and approval.packet_digest == digest and approval.reviewed_on == as_of)
    state = "review_required"
    if allowed:
        state = "bid_ready_simulation" if signed else "awaiting_manual_review"
    return {**packet, "packet_digest": digest, "ceiling_cents": ceiling,
            "binding_limits": [key for key, value in limits.items() if ceiling is not None and value == ceiling],
            "within_ceiling": ceiling is not None and proposed_cents <= ceiling,
            "approval": ({"reviewer": approval.reviewer, "reviewed_on": approval.reviewed_on.isoformat(),
                          "packet_digest": approval.packet_digest, "valid": signed} if approval else None),
            "state": state}
