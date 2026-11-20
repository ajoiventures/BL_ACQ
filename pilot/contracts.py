"""Immutable records used by the synthetic pilot storage API."""
from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class Parcel:
    parcel_id: str
    jurisdiction: str
    apn: str


@dataclass(frozen=True)
class Deal:
    deal_id: str
    parcel_id: str
    title: str


@dataclass(frozen=True)
class Evidence:
    evidence_id: str
    deal_id: str
    kind: str
    source: str
    observed_on: str
    value: str


@dataclass(frozen=True)
class Decision:
    decision_id: str
    deal_id: str
    outcome: str
    rationale: str
    evidence_id: str


@dataclass(frozen=True)
class Task:
    """One lease attempt. Pass this exact result to complete or retry."""
    task_id: str
    deal_id: str
    kind: str
    state: Literal["queued", "claimed", "completed"]
    attempt: int
    claimed_by: str | None
    lease_until: int | None
    scope: str
