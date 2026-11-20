"""Exercise the credential and one-use approval boundary with synthetic requests."""

from dataclasses import replace
import unittest

from pilot.connectors import ConnectorGrant, ConnectorRequest, authorize_connector


class MemoryApprovals:
    def __init__(self, approved):
        self.approved = set(approved)

    def consume_allowed(self, request):
        if request not in self.approved:
            return False
        self.approved.remove(request)
        return True


class ConnectorChecks(unittest.TestCase):
    def test_credentials_scope_evidence_and_replay(self):
        request = ConnectorRequest("id1", "demo", "dispatch", "work1", "v1", "operator")
        grant = ConnectorGrant("demo", frozenset({"dispatch"}), "synthetic-key")
        journal = MemoryApprovals([request])
        # Each failed request leaves the real approval available for its intended action.
        for action, credentials in [
            (request, None),
            (request, replace(grant, credential=" ")),
            (replace(request, scope="other"), grant),
            (replace(request, operation="different"), grant),
            (replace(request, evidence_version="v2"), grant),
            (replace(request, actor_id="other"), grant),
        ]:
            with self.subTest(request=action):
                with self.assertRaises(PermissionError):
                    authorize_connector(action, credentials, journal)
        authorize_connector(request, grant, journal)
        with self.assertRaises(PermissionError):
            authorize_connector(request, grant, journal)
