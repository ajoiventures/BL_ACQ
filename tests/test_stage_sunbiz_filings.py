import sqlite3

import pytest

from tools.stage_sunbiz_filings import LIMIT, stage_daily


def filing(status, document=b"L26000123456"):
    return document + b" " * 192 + status + b"FLAL".ljust(15) + b" " * 1220 + b"\r\n"


def test_stage_observations_and_replay(tmp_path):
    source = tmp_path / "20261123c.txt"
    source.write_bytes(filing(b"A") + filing(b"Z").replace(b"\r\n", b"\n") + b"bad\r\n" + filing(b"I", b" " * 12))
    database = tmp_path / "filings.sqlite"
    receipt = stage_daily(source, database)
    assert receipt["records"] == 4
    assert receipt["accepted"] == 2
    assert receipt["accepted_record_framing"] == {"CRLF": 1, "LF": 1}
    assert receipt["raw_status_hex_counts"] == {"41": 1, "5a": 1}
    assert receipt["quarantined"] == {"width_or_framing": 1, "document_number": 1}
    assert stage_daily(source, database) == {**receipt, "replay": True}
    source.write_bytes(filing(b"I"))
    with pytest.raises(ValueError, match="different bytes"):
        stage_daily(source, database)
    with sqlite3.connect(database) as db:
        assert db.execute("SELECT raw_status FROM filing_observations ORDER BY source_line").fetchall() == [(b"A",), (b"Z",)]
        assert db.execute("SELECT COUNT(*) FROM filing_quarantine").fetchone() == (2,)


def test_budget_failure_rolls_back_observations(tmp_path):
    source = tmp_path / "20261123c.txt"
    source.write_bytes(filing(b"A") + b"x" * LIMIT)
    database = tmp_path / "filings.sqlite"
    with pytest.raises(ValueError, match="byte budget"):
        stage_daily(source, database)
    with sqlite3.connect(database) as db:
        assert db.execute("SELECT COUNT(*) FROM filing_observations").fetchone() == (0,)
        assert db.execute("SELECT COUNT(*) FROM filing_manifest").fetchone() == (0,)


def test_short_crlf_record_cannot_pass_as_lf(tmp_path):
    source = tmp_path / "20261123c.txt"
    valid = filing(b"I")
    source.write_bytes(valid[:-3] + b"\r\n" + valid)
    receipt = stage_daily(source, tmp_path / "filings.sqlite")
    assert receipt["records"] == 2
    assert receipt["accepted"] == 1
    assert receipt["accepted_record_framing"] == {"CRLF": 1}
    assert receipt["quarantined"] == {"width_or_framing": 1}
