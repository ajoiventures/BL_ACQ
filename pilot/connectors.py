"""Check scoped credentials and consume one reviewed action through a durable adapter."""

from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class ConnectorGrant:
    scope: str
    operations: frozenset[str]
    credential: str = field(repr=False)


@dataclass(frozen=True)
class ConnectorRequest:
    key: str
    scope: str
    operation: str
    resource_id: str
    evidence_version: str
    actor_id: str


class ApprovalJournal(Protocol):
    def consume_allowed(self, request: ConnectorRequest) -> bool:
        """Atomically consume a separate reviewer approval for the exact request once."""
        ...


def authorize_connector(
    request: ConnectorRequest, grant: ConnectorGrant | None, journal: ApprovalJournal,
) -> None:
    # Validate the workspace and operation before looking up an approval.
    if grant is None or not grant.credential.strip():
        raise PermissionError("Connector credentials are required")
    if request.scope != grant.scope or request.operation not in grant.operations:
        raise PermissionError("Connector operation is outside the credential scope")
    if not all((request.key, request.resource_id, request.evidence_version, request.actor_id)):
        raise PermissionError("Action and evidence identity are required")
    if not journal.consume_allowed(request):
        raise PermissionError("A current, independent approval is required")
