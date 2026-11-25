import sqlite3

import pytest

from backend.core import outreach_preview


def test_preview_recovers_without_duplicate_or_suppressed_delivery(tmp_path):
    dbpath = tmp_path / "outbox.sqlite"
    recipients = ["business:2", "business:1"]
    with sqlite3.connect(dbpath) as db:
        outreach_preview.initialize(db)
        first = outreach_preview.preview(db, "sample", "a" * 64, recipients, {"business:2"})
        assert first["delivery_state"] == "DISABLED" and first["deliveries"] == 0
        assert first["suppressed_ids"] == ["business:2"]
        assert not first["replay"]
    with sqlite3.connect(dbpath) as db:
        assert outreach_preview.preview(db, "sample", "a" * 64, recipients[::-1], {"business:2"}) == {
            **first, "replay": True,
        }
        with pytest.raises(ValueError, match="changed"):
            outreach_preview.preview(db, "sample", "a" * 64, recipients, set())
        assert db.execute("SELECT count(*) FROM outreach_previews").fetchone()[0] == 1
