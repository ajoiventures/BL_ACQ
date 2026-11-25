"""Persist internal outreach previews without a delivery adapter."""
import json
import re

from .acquisition_runs import sha


def initialize(db):
    db.execute("""CREATE TABLE IF NOT EXISTS outreach_previews (
        request_id TEXT PRIMARY KEY, request_hash TEXT NOT NULL, body TEXT NOT NULL
    )""")


def preview(db, request_id, packet_sha256, recipient_ids, suppressed_ids):
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", request_id):
        raise ValueError("Invalid preview request ID")
    if not re.fullmatch(r"[0-9a-f]{64}", packet_sha256):
        raise ValueError("Expected an exact packet SHA-256")
    if not 1 <= len(recipient_ids) <= 50 or len(set(recipient_ids)) != len(recipient_ids):
        raise ValueError("Expected between 1 and 50 distinct business record IDs")
    if any(not re.fullmatch(r"business:[A-Za-z0-9_-]{1,64}", key) for key in recipient_ids):
        raise ValueError("Expected opaque business record IDs")
    recipients = sorted(recipient_ids)
    suppressed = sorted(set(recipients).intersection(suppressed_ids))
    body = {"request_id": request_id, "packet_sha256": packet_sha256, "recipient_ids": recipients,
            "suppressed_ids": suppressed, "delivery_state": "DISABLED", "deliveries": 0}
    digest = sha(body)
    inserted = db.execute("""INSERT INTO outreach_previews VALUES (?,?,?)
                             ON CONFLICT(request_id) DO NOTHING""",
                          (request_id, digest, json.dumps(body, sort_keys=True))).rowcount
    stored_hash, stored_body = db.execute(
        "SELECT request_hash,body FROM outreach_previews WHERE request_id=?", (request_id,)
    ).fetchone()
    if stored_hash != digest:
        raise ValueError("Preview ID reused with changed packet, recipients or suppression")
    return {**json.loads(stored_body), "replay": not inserted}


def read_preview(db, request_id):
    row = db.execute("SELECT request_hash, body FROM outreach_previews WHERE request_id=?",
                     (request_id,)).fetchone()
    if row is None:
        raise LookupError("Preview not found")
    stored_hash, encoded = row
    body = json.loads(encoded)
    if sha(body) != stored_hash:
        raise ValueError("Stored preview differs from its recorded hash")
    return body
