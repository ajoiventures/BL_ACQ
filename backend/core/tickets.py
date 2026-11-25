"""Scoped project commitments and independently reviewable delivery claims."""
import hashlib
import json
from pathlib import Path

SEED = Path(__file__).resolve().parents[2] / "docs/session-tickets.json"
DOMAIN = {"Acquisition": "COMMERCIAL", "Atlas": "MAIN_STREET_INSTITUTIONAL"}
WORK_STATES = {"open", "partial", "delivered_local", "in_progress", "blocked"}

class TicketError(Exception):
    def __init__(self, code, detail):
        super().__init__(detail)
        self.code = code

def import_manifest(db, event, source=SEED):
    rows = json.loads(source.read_text(encoding="utf-8"))
    db.execute("""CREATE TABLE IF NOT EXISTS project_tickets(
        id TEXT PRIMARY KEY, area TEXT NOT NULL, domain TEXT NOT NULL,
        title TEXT NOT NULL, leader TEXT NOT NULL, owner TEXT NOT NULL,
        status TEXT NOT NULL, acceptance TEXT NOT NULL, evidence TEXT NOT NULL,
        dependencies TEXT NOT NULL, version INTEGER NOT NULL DEFAULT 1,
        source TEXT NOT NULL)""")
    identifiers = {r["id"] for r in rows}
    if len(identifiers) != len(rows) or any(set(r["dependencies"]) - identifiers for r in rows):
        raise ValueError("Invalid or duplicated ticket reference in manifest")
    for item in rows:
        # A release claim cannot substitute for a review recorded in this runtime.
        status = "review_required" if item["status"] == "closed" else item["status"]
        domain = DOMAIN.get(item["area"], "PROJECT_INTERNAL")
        receipt = db.execute("""INSERT INTO project_tickets
            (id,area,domain,title,leader,owner,status,acceptance,evidence,dependencies,source)
            VALUES(?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO NOTHING""",
            (item["id"],item["area"],domain,item["title"],item["leader"],item["owner"],
             status,item["acceptance"],item["evidence"],json.dumps(item["dependencies"]),
             "docs/session-tickets.json#" + item["id"]))
        if receipt.rowcount:
            detail = item if status == item["status"] else {**item, "status": status, "manifest_status": item["status"]}
            event(db,domain,"SYSTEM","TICKET_IMPORT",item["id"],detail)

def canonical_register():
    manifest = SEED.read_bytes()
    planning = {item["id"]: item for item in json.loads(manifest)}
    path = SEED.parent / "acquisition" / "independent-review-queue.json"
    approvals = {}
    if path.is_file():
        queue = json.loads(path.read_bytes())
        if queue.get("manifest_sha256") == hashlib.sha256(manifest).hexdigest():
            approvals = {
                item["ticket_id"]: item for item in queue.get("canonical_approvals", [])
                if planning.get(item["ticket_id"], {}).get("status") == "closed"
            }
    return planning, approvals


def is_canonically_closed(planning, ticket_id):
    return planning.get(ticket_id, {}).get("status") == "closed"


def unpack(row):
    record = dict(row)
    record["dependencies"] = json.loads(record["dependencies"])
    return record

def get(db, ticket_id):
    row = db.execute("SELECT * FROM project_tickets WHERE id=?", (ticket_id,)).fetchone()
    if row is None:
        raise TicketError(404, "Ticket not found")
    return unpack(row)

def listing(db, area="", status="", owner="", q=""):
    predicates = []
    values = []
    for key,value in (("area", area), ("status",status), ("owner",owner)):
        if value:
            predicates.append(key + " = ?")
            values.append(value)
    if q:
        predicates.append("instr(lower(id || ' ' || title || ' ' || acceptance),lower(?)) > 0")
        values.append(q)
    clause = " WHERE " + " AND ".join(predicates) if predicates else ""
    return [unpack(row) for row in db.execute("SELECT * FROM project_tickets" + clause + " ORDER BY id",values)]

def history(db, ticket_id):
    rows = db.execute("""SELECT seq,actor,action,body,at,hash FROM audit
        WHERE object_id=? AND action IN ('TICKET_IMPORT','TICKET_TRANSITION','TICKET_METADATA_SYNC') ORDER BY seq""",(ticket_id,))
    return [{"seq":r["seq"],"actor":r["actor"],"action":r["action"],"at":r["at"],
             "hash":r["hash"],"detail":json.loads(r["body"])[4]} for r in rows]

def transition(db, event, actor, record, target, version, evidence, source):
    current = record["status"]
    if version != record["version"]:
        raise TicketError(409,"Ticket changed. Reload its current version")
    if actor == "SW-13" and not (current == "review_required" and target in ("closed","in_progress")):
        raise TicketError(403,"Auditor may accept or return a submitted ticket")
    if actor not in ("FOUNDER","SW-13"):
        raise TicketError(403,"Project role required")
    valid = current in WORK_STATES and target in {"in_progress","blocked","review_required"} and actor == "FOUNDER"
    valid |= current == "review_required" and actor == "SW-13" and target in {"closed","in_progress"}
    valid |= actor == "FOUNDER" and current in WORK_STATES | {"review_required"} and target == "closed"
    if not valid or current == target:
        raise TicketError(409,"Transition unavailable from current state")
    evidence, source = evidence.strip(), source.strip()
    if not evidence or not source:
        raise TicketError(422,"Evidence and its source locator are required")
    if target == "closed":
        if source.casefold() == record["source"].casefold() or evidence.casefold() == record["evidence"].casefold():
            raise TicketError(422,"Record a completion finding with a distinct evidence source")
        planning, _ = canonical_register()
        unresolved = [key for key in record["dependencies"]
                      if not is_canonically_closed(planning, key) and get(db,key)["status"] != "closed"]
        if unresolved:
            raise TicketError(409,"Close prerequisite tickets first: " + ", ".join(unresolved))
    updated = db.execute("""UPDATE project_tickets SET status=?,source=?,evidence=?,version=version+1
        WHERE id=? AND version=?""", (target,source,evidence,record["id"],version))
    if updated.rowcount != 1:
        raise TicketError(409,"Ticket changed. Reload its current version")
    event(db,record["domain"],actor,"TICKET_TRANSITION",record["id"],
          {"from":current,"to":target,"version":version+1,"evidence":evidence,"source":source})
    return get(db,record["id"])
