"""Bounded source intelligence: immutable observations and real local preparation.

This module does not fetch URLs, call an AI provider, accept evidence, contact a
person, or create transaction authority. Existing project_tickets owns work.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
import tempfile
from urllib.parse import urlparse

from filing.inbox import file_document, read_capture
from . import tickets

POLICY_VERSION = "signal-flow-1.1"
DOMAINS = {"COMMERCIAL", "MAIN_STREET_INSTITUTIONAL"}
TOPICS = {"ECONOMIC_DEVELOPMENT", "DATA_CENTER", "MAIN_STREET", "ACQUISITION", "CAPITAL", "INFORMATIONAL", "TOWN_GROWTH", "MACRO_FINANCIAL"}
AUTHORITY = {"financial_authority": 0, "contractual_authority": 0, "external_execution": False, "accepted_evidence": False}
TOPIC_DOMAINS = {
    "MACRO_FINANCIAL": ["D01", "D05", "D06", "D07", "D10", "D13", "D15"],
    "ECONOMIC_DEVELOPMENT": ["D01", "D05", "D06", "D09", "D10"],
    "DATA_CENTER": ["D01", "D02", "D05", "D09", "D10"],
    "MAIN_STREET": ["D01", "D02", "D03", "D05", "D06", "D09"],
    "ACQUISITION": ["D02", "D03", "D04", "D07", "D08", "D11"],
    "CAPITAL": ["D07", "D08", "D15"],
    "TOWN_GROWTH": ["D01", "D03", "D05", "D06", "D09"],
    "INFORMATIONAL": ["D12"],
}

ROUTES = {
    "MACRO_FINANCIAL": [("BR-T113", "economic-development"), ("BR-T132", "profit-review"), ("BR-T135", "site-studies"), ("BR-T136", "acquisition-coach")],
    "ECONOMIC_DEVELOPMENT": [("BR-T097", "economic-development"), ("BR-T100", "economic-development")],
    "DATA_CENTER": [("BR-T100", "economic-development"), ("BR-T104", "economic-development")],
    "MAIN_STREET": [("BR-T102", "site-studies")],
    "ACQUISITION": [("BR-T076", "acquisition-coach")],
    "CAPITAL": [("BR-T074", "profit-review")],
    "TOWN_GROWTH": [("BR-T097", "economic-development"), ("BR-T098", "economic-development"), ("BR-T102", "site-studies")],
    "INFORMATIONAL": [],
}
HUMAN_ACTIONS = {
    "BR-T113": "Record dated macro observations and obtain regional exposure data before building conditional forecasts.",
    "BR-T132": "Separate common shocks from asset exposures; obtain debt, refinancing, liquidity and tenant demand data.",
    "BR-T135": "Prepare availability-dated macro features for pre-site strategy estimates; do not assign unsupported probabilities.",
    "BR-T136": "Stress cash flows with explicit lender quotes, costs and assumptions; do not equate policy rates with borrowing rates.",
    "BR-T097": "Assemble a dated population, jobs and housing baseline for the named place.",
    "BR-T098": "List local business needs and find source evidence for employer demand.",
    "BR-T100": "Resolve the reported locations to parcel IDs before adding candidate sites.",
    "BR-T102": "Name one Main Street corridor and map its businesses, housing and transport connections.",
    "BR-T104": "Prepare the customer load profile and a checklist of utility evidence needed for site review.",
    "BR-T076": "Compare a lawful 2–4 unit candidate with the current buy box and identify its first missing document.",
    "BR-T074": "Reconcile financial inputs to transaction records before changing the capital scenario.",
}
QUESTIONS = {
    "MACRO_FINANCIAL": ["Record observation period and first availability separately; retrieve point-in-time series and current vintages before prediction.", "Distinguish shocks from asset valuations, borrower debt, financial leverage and funding vulnerabilities; estimate local exposure with independent data.", "Treat policy rates as distinct from offered loan rates; no strategy probabilities, profit estimates or investment decisions without supported model inputs."],
    "ECONOMIC_DEVELOPMENT": ["Identify the geography, dated baseline and responsible public agency.", "Obtain source-defined jobs, wages and tax measures; keep announced investment separate from realized outcomes."],
    "DATA_CENTER": ["Obtain a customer load profile and dated utility capacity and delivery assessment.", "Verify tariff, interconnection conditions, water, fiber, environmental limits, zoning and site control; proximity is not serviceability."],
    "MAIN_STREET": ["Connect the announcement to a named corridor and documented local businesses, housing and transport links.", "Compare ownership, lawful uses, vacancy, displacement risk and infrastructure across the whole corridor before choosing parcels."],
    "ACQUISITION": ["Preserve the 2–4 unit buy box; verify lawful units, title, actual rents, expenses and acquisition basis.", "Keep the planned Ives disposition and intended exchange capital unverified until source documents and the qualified transaction team establish them."],
    "CAPITAL": ["Reconcile actual balances, owner identity, costs and capital restrictions using transaction records.", "Model financing and exit scenarios only with declared assumptions; an announcement establishes no available capital."],
    "TOWN_GROWTH": ["Compare dated aggregate city population, county migration flows, housing permits and jobs using compatible geographies and periods.", "Do not infer migration direction from immigrant stock; distinguish natural change, domestic migration and international migration where the source permits.", "Assess housing, infrastructure and business capacity for the town and corridor; do not profile individual households or target political groups."],
    "INFORMATIONAL": ["Retain the source and its limits; no operational action is required."],
}
IMPLICATIONS = {
    "MACRO_FINANCIAL": "Macro-financial observations can inform conditional risk scenarios and pre-site features, not parcel suitability, current loan terms or accepted training labels.",
    "ECONOMIC_DEVELOPMENT": "Potential research lead for the economic baseline and site inventory; local benefit remains unverified.",
    "DATA_CENTER": "A site-readiness announcement may justify utility diligence; it does not establish data-center suitability or available power.",
    "MAIN_STREET": "Investigate whether regional activity supports the Main Street ownership goal; the source itself does not establish corridor demand.",
    "ACQUISITION": "Compare the signal with the current buy box before adding acquisition work.",
    "CAPITAL": "Consider whether new evidence changes a declared capital scenario; no ledger balance is updated.",
    "TOWN_GROWTH": "Investigate aggregate growth, migration and housing trends before choosing a town or corridor; no population-direction conclusion is made.",
    "INFORMATIONAL": "Informational intake can remain a digest without generating work.",
}

class SignalError(Exception):
    def __init__(self, code, detail):
        super().__init__(detail)
        self.code = code


def stamp():
    return datetime.now(timezone.utc).isoformat()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def sha(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def initialize(db):
    statements = [
        """CREATE TABLE IF NOT EXISTS signal_sources(source_id TEXT PRIMARY KEY,
            security_domain TEXT NOT NULL, source_key TEXT NOT NULL,
            UNIQUE(security_domain,source_key))""",
        """CREATE TABLE IF NOT EXISTS signal_snapshots(source_id TEXT NOT NULL,
            revision INTEGER NOT NULL, snapshot_sha256 TEXT NOT NULL, observed_at TEXT NOT NULL,
            payload TEXT NOT NULL, digest TEXT NOT NULL,
            PRIMARY KEY(source_id,revision), FOREIGN KEY(source_id) REFERENCES signal_sources(source_id))""",
        """CREATE TABLE IF NOT EXISTS signal_plans(plan_id TEXT PRIMARY KEY,
            source_id TEXT NOT NULL, source_revision INTEGER NOT NULL,
            plan_sha256 TEXT NOT NULL UNIQUE, payload TEXT NOT NULL,
            FOREIGN KEY(source_id,source_revision) REFERENCES signal_snapshots(source_id,revision))""",
        """CREATE TABLE IF NOT EXISTS signal_runs(run_id TEXT PRIMARY KEY,plan_id TEXT NOT NULL,
            worker_id TEXT NOT NULL,attempt INTEGER NOT NULL,state TEXT NOT NULL,payload TEXT NOT NULL,
            UNIQUE(plan_id,worker_id,attempt), FOREIGN KEY(plan_id) REFERENCES signal_plans(plan_id))""",
        """CREATE TABLE IF NOT EXISTS signal_requests(operation TEXT NOT NULL,
            request_id TEXT NOT NULL,request_sha256 TEXT NOT NULL,result TEXT NOT NULL,
            PRIMARY KEY(operation,request_id))""",
    ]
    for sql in statements:
        db.execute(sql)
    for table in ("signal_sources", "signal_snapshots", "signal_plans", "signal_runs", "signal_requests"):
        for verb in ("UPDATE", "DELETE"):
            db.execute(f"CREATE TRIGGER IF NOT EXISTS no_{table}_{verb.lower()} BEFORE {verb} ON {table} BEGIN SELECT RAISE(ABORT,'Append-only intelligence records'); END")


def replay(db, operation, request_id, body):
    row = db.execute("SELECT request_sha256,result FROM signal_requests WHERE operation=? AND request_id=?", (operation,request_id)).fetchone()
    if row:
        if row["request_sha256"] != sha(body):
            raise SignalError(409, "Request ID was already used with different content")
        return json.loads(row["result"])
    return None


def remember(db, operation, request_id, body, result):
    db.execute("INSERT INTO signal_requests VALUES(?,?,?,?)", (operation,request_id,sha(body),canonical(result)))
    return result


def _date(value, name):
    if value is None:
        return None
    try:
        if len(value) == 10:
            datetime.strptime(value, "%Y-%m-%d")
        else:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                raise ValueError()
    except (TypeError, ValueError):
        raise SignalError(422, f"{name} requires an ISO date or timezone-aware timestamp")
    return value


def _validate(body):
    if body["security_domain"] not in DOMAINS:
        raise SignalError(422, "Unsupported source security domain")
    try:
        url = urlparse(body["source_url"])
        _ = url.port
    except ValueError:
        raise SignalError(422, "A valid HTTP(S) source locator is required")
    if url.scheme not in {"http", "https"} or not url.hostname or url.username or url.password or any(c.isspace() for c in body["source_url"]):
        raise SignalError(422, "A public HTTP(S) source locator without credentials is required")
    if not body["content"].strip() or not body["title"].strip() or not body["source_key"].strip():
        raise SignalError(422, "Source key, title and retained excerpt cannot be blank")
    if len(set(body["topic_tags"])) != len(body["topic_tags"]):
        raise SignalError(422, "Duplicate topic tags")
    if not set(body["topic_tags"]) <= TOPICS:
        raise SignalError(422, "Unknown topic tag")
    for item in body["source_claims"]:
        if not item["claim"].strip() or not item["quote"].strip() or item["quote"] not in body["content"]:
            raise SignalError(422, "Every supplied source claim needs a nonempty exact quote in the retained excerpt")
    for name in ("published_at", "event_at"):
        _date(body.get(name), name)


def _source_row(db, source_id, revision=None, as_of=None):
    where, args = "source_id=?", [source_id]
    if revision is not None:
        where += " AND revision=?"
        args.append(revision)
    if as_of:
        parsed = datetime.fromisoformat(as_of.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise SignalError(422, "as_of requires a timezone-aware timestamp")
        where += " AND observed_at<=?"
        args.append(parsed.astimezone(timezone.utc).isoformat())
    row = db.execute("SELECT * FROM signal_snapshots WHERE " + where + " ORDER BY revision DESC LIMIT 1", args).fetchone()
    if not row:
        raise SignalError(404, "Source revision not found")
    return row


def source_domain(db, source_id):
    row = db.execute("SELECT security_domain FROM signal_sources WHERE source_id=?", (source_id,)).fetchone()
    if row is None:
        raise SignalError(404, "Source not found")
    return row["security_domain"]


def source_revision_hash(db, source_id, revision):
    return _source_row(db, source_id, revision)["snapshot_sha256"]


def read_source_excerpt(db, source_id, revision, domain, archive_root):
    row = _source_row(db, source_id, revision)
    source = json.loads(row["payload"])
    receipt = source.get("evidence_receipt", {})
    capture_id = receipt.get("capture_id")
    if not capture_id:
        raise SignalError(404, "Archived source excerpt not found")
    try:
        capture = read_capture(Path(archive_root) / domain, capture_id)
    except (OSError, ValueError, sqlite3.Error) as exc:
        raise SignalError(409, "Archived source excerpt could not be verified") from exc
    if (capture["source_revision"] != row["snapshot_sha256"]
            or capture["sha256"] != source.get("content_sha256")):
        raise SignalError(409, "Archived source excerpt could not be verified")
    return capture["content"]


def _digest(source):
    result = {"digest_id": "BR-DIG-" + source["snapshot_sha256"][:20],
              "source_id": source["source_id"], "source_revision": source["revision"],
              "source_claims": source["source_claims"],
              "implications": [IMPLICATIONS[t] for t in source["topic_tags"]],
              "unknowns": list(dict.fromkeys(q for t in source["topic_tags"] for q in QUESTIONS[t])),
              "method": "DETERMINISTIC_LOCAL", "policy_version": POLICY_VERSION,
              "limits": ["Only the retained excerpt was captured; the full publisher page is not archived.",
                         "Claim descriptions were supplied by the operator. Exact quotes were located mechanically; entailment is not independently verified.",
                         "No ownership, capacity, legal status, profit or authority is established."]}
    result["digest_sha256"] = sha(result)
    return result


def capture(db, event, actor, body, archive_root):
    _validate(body)
    prior = replay(db, "capture", body["request_id"], body)
    if prior is not None:
        return prior
    domain, key = body["security_domain"], body["source_key"]
    source_id = "BR-SRC-" + sha({"domain":domain,"key":key})[:20]
    stored = db.execute("SELECT 1 FROM signal_sources WHERE source_id=?", (source_id,)).fetchone()
    if not stored:
        db.execute("INSERT INTO signal_sources VALUES(?,?,?)", (source_id,domain,key))
    snapshot_input = {k:v for k,v in body.items() if k != "request_id"}
    snapshot_hash = sha(snapshot_input)
    previous = db.execute("SELECT * FROM signal_snapshots WHERE source_id=? ORDER BY revision DESC LIMIT 1", (source_id,)).fetchone()
    if previous and previous["snapshot_sha256"] == snapshot_hash:
        result = {"source_id":source_id,"revision":previous["revision"],"status":"CAPTURED",
                  "source":json.loads(previous["payload"]),"digest":json.loads(previous["digest"]),"authority":AUTHORITY}
        return remember(db, "capture", body["request_id"], body, result)
    revision = previous["revision"] + 1 if previous else 1
    retained_bytes = body["content"].encode("utf-8")
    archive_root = Path(archive_root) / domain
    archive_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=archive_root) as directory:
        incoming = Path(directory) / (source_id + "-excerpt.txt")
        incoming.write_bytes(retained_bytes)
        locator = {"kind":"EXCERPT_SPAN","start":0,"end":len(body["content"])}
        receipt = file_document(incoming, archive_root, source_revision=snapshot_hash,
                                source_locator=locator)
    receipt["file"] = str(Path(receipt["file"]).relative_to(archive_root))
    receipt["scope"] = "RETAINED_EXCERPT_ONLY"
    receipt["bytes"] = len(retained_bytes)
    receipt["source_revision"] = snapshot_hash
    receipt["source_locator"] = locator
    now = stamp()
    claims = []
    for i, item in enumerate(body["source_claims"]):
        start = body["content"].index(item["quote"])
        claims.append({"claim_id":f"{source_id}-R{revision}-C{i+1}", **item,
                       "locator":{"start":start,"end":start+len(item["quote"]),"unit":"UNICODE_CODE_POINT"},
                       "filing_capture_id":receipt["capture_id"],
                       "evidence_state":"SOURCE_REPORTED", "verification_status":"UNVERIFIED",
                       "extraction_method":"OPERATOR_SUPPLIED_WITH_EXACT_QUOTE_CHECK"})
    source = {**snapshot_input, "source_id":source_id,"revision":revision,"source_claims":claims,
              "observed_at":now,"first_available_at":now,"system_recorded_at":now,
              "content_sha256":hashlib.sha256(retained_bytes).hexdigest(),"snapshot_sha256":snapshot_hash,
              "evidence_receipt":receipt,"verification_status":"UNVERIFIED","confidence":None,
              "data_domains":sorted({"D12", "D13", "D14"}.union(*(set(TOPIC_DOMAINS[t]) for t in body["topic_tags"])))}
    digest = _digest(source)
    db.execute("INSERT INTO signal_snapshots VALUES(?,?,?,?,?,?)", (source_id,revision,snapshot_hash,now,canonical(source),canonical(digest)))
    event(db,domain,actor,"SIGNAL_SOURCE_CAPTURED",source_id,
          {"revision":revision,"snapshot_sha256":snapshot_hash,"content_sha256":source["content_sha256"],"capture_kind":"EXCERPT_ONLY"})
    result = {"source_id":source_id,"revision":revision,"status":"CAPTURED","source":source,"digest":digest,"authority":AUTHORITY}
    return remember(db,"capture",body["request_id"],body,result)


def make_plan(db, event, actor, source_id, body):
    operation = "plan:" + source_id
    prior = replay(db, operation, body["request_id"], body)
    if prior is not None:
        return prior
    row = _source_row(db,source_id)
    if row["revision"] != body["revision"]:
        raise SignalError(409,"Source changed; create a plan from its current revision")
    source, digest = json.loads(row["payload"]), json.loads(row["digest"])
    links, seen, excluded = [], set(), []
    if body["disposition"] == "LINK_EXISTING":
        for tag in source["topic_tags"]:
            for ticket_id, module in ROUTES[tag]:
                if ticket_id in seen:
                    continue
                record = tickets.get(db,ticket_id)
                if record["domain"] not in ("PROJECT_INTERNAL",source["security_domain"]):
                    excluded.append({"ticket_id":ticket_id,"reason":"CROSS_DOMAIN_LINK_NOT_AUTHORIZED"})
                    continue
                seen.add(ticket_id)
                links.append({"ticket_id":ticket_id,"title":record["title"],"owner":record["owner"],
                              "leader":record["leader"],"status":record["status"],"version":record["version"],"module":module})
    workers = []
    actions = []
    if links:
        workers = [
            {"worker_id":"SOURCE_EVIDENCE_MAP","specialist":"SW-00","leader":"L1","description":"Verify retained excerpt integrity and map claim locators."},
            {"worker_id":"MODULE_READINESS","specialist":"SW-04","leader":"L2","description":"Generate source-linked evidence requests for the chosen modules."},
            {"worker_id":"ACTION_BRIEF","specialist":"SW-02","leader":"L4","description":"Prepare one bounded human action for each linked ticket."},
        ]
        actions = [{"action_id":source_id+f"-R{source['revision']}-"+x["ticket_id"],
                    "title":HUMAN_ACTIONS[x["ticket_id"]],
                    "ticket_id":x["ticket_id"],"proposed_role":x["owner"],"acknowledged_owner":None,
                    "state":"PROPOSED","external_action_executed":False} for x in links]
    plan = {"source_id":source_id,"source_revision":source["revision"],"source_sha256":source["snapshot_sha256"],
            "digest_sha256":digest["digest_sha256"],"security_domain":source["security_domain"],
            "disposition":body["disposition"],"state":"PREPARATION_ONLY","links":links,"excluded_links":excluded,
            "workers":workers,"human_actions":actions,"policy_version":POLICY_VERSION,"authority":AUTHORITY}
    scope_hash = sha(plan)
    existing = db.execute("SELECT payload FROM signal_plans WHERE source_id=? ORDER BY rowid DESC LIMIT 1",(source_id,)).fetchone()
    latest = json.loads(existing["payload"]) if existing else None
    if latest and latest.get("content_sha256") == scope_hash:
        plan = latest
    else:
        plan["content_sha256"] = scope_hash
        plan["plan_revision"] = latest.get("plan_revision", 1) + 1 if latest else 1
        plan_hash = sha(plan)
        plan["plan_id"] = "BR-PLAN-" + plan_hash[:20]
        plan["plan_sha256"] = plan_hash
        plan["created_at"] = stamp()
        db.execute("INSERT INTO signal_plans VALUES(?,?,?,?,?)",(plan["plan_id"],source_id,source["revision"],plan_hash,canonical(plan)))
        event(db,source["security_domain"],actor,"SIGNAL_PLAN_PREPARED",plan["plan_id"],
              {"source_id":source_id,"source_revision":source["revision"],"plan_revision":plan["plan_revision"],"plan_sha256":plan_hash,"ticket_ids":[x["ticket_id"] for x in links]})
    return remember(db,operation,body["request_id"],body,plan)


def execute_worker(worker_id, source, digest, plan, archive_root):
    if worker_id == "SOURCE_EVIDENCE_MAP":
        path = Path(archive_root)/source["security_domain"]/source["evidence_receipt"]["file"]
        content = path.read_bytes()
        if hashlib.sha256(content).hexdigest() != source["content_sha256"]:
            raise ValueError("Retained excerpt integrity check failed")
        text = content.decode("utf-8")
        receipt = source["evidence_receipt"]
        if "source_revision" in receipt and (
            receipt["source_revision"] != source["snapshot_sha256"]
            or receipt.get("source_locator") != {"kind":"EXCERPT_SPAN","start":0,"end":len(text)}
        ):
            raise ValueError("Filing capture revision or excerpt bounds do not match")
        checks = []
        for claim in source["source_claims"]:
            locator = claim["locator"]
            if "source_revision" in receipt and claim.get("filing_capture_id") != receipt["capture_id"]:
                raise ValueError("Claim filing capture does not match its source")
            exact = text[locator["start"]:locator["end"]] == claim["quote"]
            if not exact:
                raise ValueError("Claim locator integrity check failed")
            checks.append({"claim_id":claim["claim_id"],"quote_found":True,"source_sha256":source["content_sha256"],"evidence_state":"SOURCE_REPORTED","independently_verified":False})
        return {"artifact_type":"EVIDENCE_MAP","checks":checks,"verified_excerpt_bytes":len(content),"fact_acceptance":False}
    if worker_id == "MODULE_READINESS":
        return {"artifact_type":"READINESS_CHECKLIST","source_id":source["source_id"],"source_revision":source["revision"],
                "tickets":[x["ticket_id"] for x in plan["links"]],
                "requests":[{"topic":tag,"questions":QUESTIONS[tag],"status":"MISSING_EVIDENCE"} for tag in source["topic_tags"]],
                "disposition":"INVESTIGATE_ONLY","site_capacity_mw":None,"realized_profit":None}
    if worker_id == "ACTION_BRIEF":
        return {"artifact_type":"HUMAN_ACTION_BRIEF","actions":plan["human_actions"],
                "first_action":"Review the retained source and collect the first missing document for the linked ticket." if plan["human_actions"] else "No action required.",
                "focus":"Preserve the current acquisition and Main Street objective; this source does not replace it.","outbound_messages_sent":0}
    raise ValueError("Unknown local worker")


def release(db, event, actor, source_id, body, archive_root):
    operation = "release:" + source_id
    prior = replay(db,operation,body["request_id"],body)
    if prior is not None:
        return prior
    row = db.execute("SELECT payload FROM signal_plans WHERE plan_id=? AND source_id=?",(body["plan_id"],source_id)).fetchone()
    if not row:
        raise SignalError(404,"Routing plan not found")
    plan = json.loads(row["payload"])
    current = _source_row(db,source_id)
    latest_plan_id = db.execute("SELECT plan_id FROM signal_plans WHERE source_id=? ORDER BY rowid DESC LIMIT 1",(source_id,)).fetchone()["plan_id"]
    if body["plan_sha256"] != plan["plan_sha256"] or latest_plan_id != plan["plan_id"] or current["revision"] != plan["source_revision"] or current["snapshot_sha256"] != plan["source_sha256"]:
        raise SignalError(409,"Source or plan changed; prepare and release the current revision")
    for link in plan["links"]:
        ticket = tickets.get(db,link["ticket_id"])
        if ticket["version"] != link.get("version") or ticket["domain"] not in ("PROJECT_INTERNAL",plan["security_domain"]):
            raise SignalError(409,"Linked ticket changed; prepare a current routing plan")
    source,digest = json.loads(current["payload"]),json.loads(current["digest"])
    runs = []
    for worker in plan["workers"]:
        previous = db.execute("SELECT payload FROM signal_runs WHERE plan_id=? AND worker_id=? ORDER BY attempt DESC LIMIT 1",(plan["plan_id"],worker["worker_id"])).fetchone()
        last = json.loads(previous["payload"]) if previous else None
        if last and (last["state"] == "COMPLETED" or last["attempt"] >= 2):
            runs.append(last)
            if last["state"] == "FAILED":
                break
            continue
        attempt = last["attempt"] + 1 if last else 1
        work_id = "BR-WORK-" + sha({"plan":plan["plan_id"],"worker":worker["worker_id"]})[:20]
        run = {"run_id":work_id+f"-A{attempt}","work_id":work_id,"plan_id":plan["plan_id"],"worker_id":worker["worker_id"],
               "specialist":worker["specialist"],"leader":worker["leader"],"attempt":attempt,"state":"RUNNING","mode":"DETERMINISTIC_LOCAL",
               "input_revision_sha256":plan["plan_sha256"],"worker_version":POLICY_VERSION,"started_at":stamp(),"completed_at":None,
               "output":None,"output_sha256":None,"error":None}
        event(db,source["security_domain"],actor,"SIGNAL_WORK_STARTED",run["run_id"],{"worker_id":worker["worker_id"],"attempt":attempt,"plan_sha256":plan["plan_sha256"]})
        try:
            output = execute_worker(worker["worker_id"],source,digest,plan,archive_root)
            run.update(state="COMPLETED",output=output,output_sha256=sha(output))
        except (OSError, ValueError) as exc:
            run.update(state="FAILED",error=type(exc).__name__+": "+str(exc)[:300])
        run["completed_at"] = stamp()
        db.execute("INSERT INTO signal_runs VALUES(?,?,?,?,?,?)",(run["run_id"],plan["plan_id"],worker["worker_id"],attempt,run["state"],canonical(run)))
        event(db,source["security_domain"],actor,"SIGNAL_WORK_"+run["state"],run["run_id"],
              {"worker_id":worker["worker_id"],"output_sha256":run["output_sha256"],"error":run["error"]})
        runs.append(run)
        if run["state"] == "FAILED":
            break
    state = "FAILED" if any(r["state"] == "FAILED" for r in runs) else "COMPLETED"
    result = {"source_id":source_id,"plan_id":plan["plan_id"],"status":state,"runs":runs,"human_actions":plan["human_actions"],
              "execution_mode":"DETERMINISTIC_LOCAL","live_ai_provider":False,"authority":AUTHORITY}
    return remember(db,operation,body["request_id"],body,result)


def detail(db, source_id, as_of=None):
    row = _source_row(db,source_id,as_of=as_of)
    source,digest = json.loads(row["payload"]),json.loads(row["digest"])
    availability = {
        "system_recorded_at": source.get("system_recorded_at", row["observed_at"]),
        "reported_publication_at": source.get("published_at"),
        "verified_public_availability_at": None,
        "historical_basis": "RECORDED_CAPTURE",
    }
    plans = [json.loads(r["payload"]) for r in db.execute("SELECT payload FROM signal_plans WHERE source_id=? AND source_revision<=? ORDER BY rowid",(source_id,source["revision"]))]
    latest_plan_id = plans[-1]["plan_id"] if plans else None
    for plan in plans:
        plan["is_current"] = plan["source_revision"] == source["revision"] and plan["plan_id"] == latest_plan_id
    runs = [json.loads(r["payload"]) for r in db.execute("SELECT r.payload FROM signal_runs r JOIN signal_plans p ON p.plan_id=r.plan_id WHERE p.source_id=? AND p.source_revision<=? ORDER BY p.source_revision,r.run_id",(source_id,source["revision"]))]
    return {"source":source,"digest":digest,"plans":[] if as_of else plans,"runs":[] if as_of else runs,"authority":AUTHORITY,
            "availability":availability,
            "as_of_semantics":"Recorded source capture only. Reported publication dates do not enable public-information replay. Historical plan and run projections are unavailable."}


def listing(db):
    rows = db.execute("SELECT s.payload FROM signal_snapshots s JOIN (SELECT source_id,MAX(revision) revision FROM signal_snapshots GROUP BY source_id) latest ON s.source_id=latest.source_id AND s.revision=latest.revision ORDER BY s.observed_at DESC")
    return [{k:source[k] for k in ("source_id","title","revision","security_domain","topic_tags","observed_at")} for source in (json.loads(r["payload"]) for r in rows)]


def contract():
    return {"version":POLICY_VERSION,"security_domains":sorted(DOMAINS),"topic_tags":sorted(TOPICS),
            "maturity_layers":["RAW","NORMALIZED","CANONICAL","INTELLIGENCE","OPERATIONAL"],
            "data_domains":[f"D{i:02}" for i in range(1,16)],"fact_state":"SOURCE_REPORTED_UNVERIFIED",
            "operations":["capture","plan","release","read"],"workers":"Three bounded synchronous CPU preparation handlers",
            "model_provider":"NOT_CONNECTED","continuous_monitoring":False,"external_fetch":False,
            "ticket_authority":"project_tickets","independent_acceptance":"PENDING","authority":AUTHORITY}
