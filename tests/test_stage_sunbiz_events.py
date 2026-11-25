import sqlite3

import pytest

from tools.audit_sunbiz_event_order import summarize_order
from tools.stage_sunbiz_events import stage


def test_event_staging_order_identity_and_replay(tmp_path):
    source = tmp_path / "20261123ce.txt"
    database = tmp_path / "events.sqlite"

    def event(key, sequence):
        prefix = key.ljust(12) + sequence + b"EVENT".ljust(20)
        return prefix.ljust(77) + b"20261124" + b"20261123" + b" " * 569

    payload = b"\r\n".join([
        event(b"L01234567890", b"00002"),
        event(b"L01234567890", b"00001"),
        event(b"l01234567890", b"00001"),
        b"incomplete",
        b"",
    ])
    source.write_bytes(payload)
    receipt = stage(source, database)
    assert receipt["accepted"] == 2
    assert receipt["quarantined"] == {"document_number": 1, "width_or_framing": 1}
    assert receipt["registry_updates"] == 0
    assert stage(source, database) == {**receipt, "replay": True}
    source.write_bytes(payload + b"x")
    with pytest.raises(ValueError, match="different bytes"):
        stage(source, database)
    with sqlite3.connect(database) as db:
        assert db.execute(
            "SELECT sequence, line, effective_raw, filed_raw FROM event_observation ORDER BY sequence"
        ).fetchall() == [(1, 2, b"20261124", b"20261123"), (2, 1, b"20261124", b"20261123")]


def test_review_receipt_publish_failure_preserves_previous_bytes(tmp_path, monkeypatch):
    from pathlib import Path

    import pytest

    from tools.review_sunbiz_event_order import publish_receipt

    output = tmp_path / "receipt.json"
    original = b'{"rows": 1}\n'
    output.write_bytes(original)
    with monkeypatch.context() as scoped:
        def interrupted_replace(*args):
            raise OSError("simulated interrupted publication")

        scoped.setattr(Path, "replace", interrupted_replace)
        with pytest.raises(OSError, match="interrupted publication"):
            publish_receipt(output, {"rows": 2})

    assert output.read_bytes() == original
    assert list(tmp_path.iterdir()) == [output]
    publish_receipt(output, {"rows": 2})
    assert output.read_bytes() == b'{\n  "rows": 2\n}\n'
def test_cross_file_order_retains_conflicting_repeated_sequences():
    rows = [('20261124ce.txt', '000001', 2, 'new'),
            ('20261120ce.txt', '000001', 2, 'old'),
            ('20261120ce.txt', '000002', 1, 'first'),
            ('20261124ce.txt', '000002', 2, 'second')]
    assert summarize_order(rows) == {
        'documents_in_multiple_files': 2,
        'nonincreasing_sequence_documents': 1,
        'cross_file_repeated_document_sequence': 1,
        'cross_file_conflicting_document_sequence': 1,
    }
