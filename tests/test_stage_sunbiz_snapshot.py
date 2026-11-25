import sqlite3
from types import SimpleNamespace

import numpy as np
import pytest

from tools import stage_sunbiz_snapshot as staging


def test_snapshot_reconciles_and_rolls_back(tmp_path, monkeypatch):
    source = tmp_path / "cordata.zip"
    source.write_bytes(b"fixture")
    database = tmp_path / "snapshot.sqlite"
    profile = {"member": "cordata0.txt", "records": 2, "status": {"I": 1, "other": 1}}
    verification = {
        "all_member_crcs_verified": True,
        "archive_sha256": staging.digest(source),
        "archive_bytes": 7,
        "members": [profile],
        "records": 2,
        "status": profile["status"],
        "artifact": "doc/Quarterly/Cor/cordata.zip",
        "portal": "https://sftp.floridados.gov/",
    }
    rows = np.full((2, 1442), ord(" "), dtype=np.uint8)
    rows[0, :12] = list(b"L26000000000")
    rows[0, 204:209] = list(b"IFLAL")
    rows[1, 204] = ord("Z")
    monkeypatch.setattr(staging, "archive_members", lambda _: [SimpleNamespace(filename="cordata0.txt")])

    def profile_member(_source, _member, consume):
        consume(0, rows)
        return {**profile, "lowercase_document_key_rows": 0}

    monkeypatch.setattr(staging, "profile_member", profile_member)
    with pytest.raises(ValueError, match="member differs"):
        staging.stage_snapshot(source, {
            **verification, "members": [{**profile, "lowercase_document_key_rows": 1}],
        }, database)
    with pytest.raises(ValueError, match="totals differ"):
        staging.stage_snapshot(source, {**verification, "records": 3}, database)
    with sqlite3.connect(database) as db:
        assert db.execute("SELECT count(*) FROM snapshot_observations").fetchone() == (0,)
        assert db.execute("SELECT count(*) FROM snapshot_manifest").fetchone() == (0,)
    result = staging.stage_snapshot(source, verification, database)
    assert result["accepted"] == result["quarantined"] == 1
    assert staging.stage_snapshot(source, verification, database) == {**result, "replay": True}
    with sqlite3.connect(database) as db:
        assert db.execute("SELECT document, raw_status, filing_type FROM snapshot_observations").fetchone() == (
            "L26000000000", b"I", b"FLAL".ljust(15)
        )
        assert db.execute("SELECT source_line, reason FROM snapshot_quarantine").fetchone() == (2, "document_number")
