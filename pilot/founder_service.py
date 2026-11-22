"""Serve the authenticated synthetic Founder review on loopback.

Run `python -m pilot.founder_service` and use the single-run access keys in
the terminal. Checkpoint and decision data survive a restart in the SQLite file.
"""

import argparse
import hashlib
import hmac
import json
import mimetypes
import re
import secrets
import sqlite3
import time
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from .contracts import Deal, Decision, Evidence, Parcel
from .storage import Store

ROOT = Path(__file__).resolve().parents[1]
RECORD = "orchard-01"
SCOPE = "commercial"
ROLES = {"reviewer": "commercial", "founder": "commercial", "civic-reader": "civic"}
STATIC = {
    "index.html",
    "style.css",
    "app.js",
    "fixtures.js",
    "connected.html",
    "connected.js",
    "valuation.html",
    "valuation.css",
    "valuation.js",
    "corporate.html",
    "corporate.js",
    "corporate.css",
}
SCHEMA = """
CREATE TABLE IF NOT EXISTS founder_active_evidence (
 scope TEXT, record TEXT, evidence TEXT NOT NULL, PRIMARY KEY(scope,record));
CREATE TABLE IF NOT EXISTS founder_drafts (
 scope TEXT, record TEXT, actor TEXT, evidence TEXT NOT NULL, version INTEGER NOT NULL,
 note TEXT NOT NULL, PRIMARY KEY(scope,record,actor));
CREATE TABLE IF NOT EXISTS founder_actions (
 scope TEXT, record TEXT, step INTEGER, actor TEXT NOT NULL, action TEXT NOT NULL,
 evidence TEXT NOT NULL, note TEXT NOT NULL, PRIMARY KEY(scope,record,step));
CREATE TABLE IF NOT EXISTS founder_receipts (
 scope TEXT, record TEXT, actor TEXT, request_id TEXT, fingerprint TEXT NOT NULL,
 response TEXT NOT NULL, PRIMARY KEY(scope,record,actor,request_id));
"""


class Rejected(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status


def validate_target(actor, scope, record):
    if ROLES.get(actor) != scope:
        raise Rejected(403, "This account has no access to that workspace.")
    if (scope, record) != (SCOPE, RECORD):
        raise Rejected(404, "Record unavailable in this workspace.")


def fixture():
    from .scenario import deal_fixture
    from .underwriting import underwrite

    candidate, economics, as_of = deal_fixture()
    packet = underwrite(candidate, economics, 23_500_000, as_of, "analyst")
    return {
        "ready": packet["state"] in ("awaiting_manual_review", "bid_ready_simulation"),
        "state": packet["state"],
        "ceiling_cents": packet["ceiling_cents"],
        "packet_digest": packet["packet_digest"],
        "checks": packet["qualification"]["checks"] + packet["gates"],
        "as_of": as_of.isoformat(),
    }


def prepare(path):
    from .valuation_store import initialize

    frozen = fixture()
    revision = frozen["packet_digest"]
    with Store(path, scope=SCOPE, actor="fixture-loader") as store:
        store.connection.executescript(SCHEMA)
        initialize(store.connection)
        with store.transaction():
            store.save(Parcel("orchard-parcel", "Synthetic County", "DEMO-001"))
            store.save(Deal(RECORD, "orchard-parcel", "Orchard parcel"))
            store.save(
                Evidence(
                    revision,
                    RECORD,
                    "underwriting",
                    "Synthetic founder review fixture",
                    frozen["as_of"],
                    json.dumps(frozen, sort_keys=True),
                )
            )
            store.connection.execute(
                "INSERT INTO founder_active_evidence VALUES(?,?,?) ON CONFLICT(scope,record) DO UPDATE SET evidence=excluded.evidence",
                (SCOPE, RECORD, revision),
            )
            # Early development databases used a label. Preserve these notes and actions
            # by resolving the digest from the original stored evidence, never today's fixture.
            legacy = store.connection.execute(
                "SELECT value FROM pilot_evidence WHERE scope=? AND deal_id=? AND evidence_id=?",
                (SCOPE, RECORD, "orchard-review-v1"),
            ).fetchone()
            if legacy:
                original = json.loads(legacy[0])["packet_digest"]
                for table in ("founder_actions", "founder_drafts"):
                    store.connection.execute(
                        f"UPDATE {table} SET evidence=? WHERE scope=? AND record=? AND evidence=?",
                        (original, SCOPE, RECORD, "orchard-review-v1"),
                    )


def read_record(connection, actor):
    active = connection.execute(
        """SELECT p.evidence_id,p.value FROM founder_active_evidence a
        JOIN pilot_evidence p ON p.scope=a.scope AND p.deal_id=a.record AND p.evidence_id=a.evidence
        WHERE a.scope=? AND a.record=?""",
        (SCOPE, RECORD),
    ).fetchone()
    if active is None:
        raise Rejected(409, "The record has no active evidence packet.")
    revision, raw = active
    packet = json.loads(raw)
    if packet["packet_digest"] != revision:
        raise Rejected(409, "Evidence identity mismatch. Review the stored packet.")
    row = connection.execute(
        "SELECT note,version,evidence FROM founder_drafts WHERE scope=? AND record=? AND actor=?",
        (SCOPE, RECORD, actor),
    ).fetchone()
    history = connection.execute(
        "SELECT actor,action,evidence,note FROM founder_actions WHERE scope=? AND record=? ORDER BY step",
        (SCOPE, RECORD),
    ).fetchall()
    history = [
        dict(zip(("actor", "action", "evidence", "note"), item)) for item in history
    ]
    events = [event for event in history if event["evidence"] == revision]
    if events and events[-1]["action"] == "approve" and packet["ready"]:
        packet["state"] = "bid_ready_simulation"
    return {
        "actor": actor,
        "scope": SCOPE,
        "record": RECORD,
        "evidence": revision,
        "underwriting": packet,
        "draft": {"note": row[0], "version": row[1], "evidence": row[2]}
        if row
        else {"note": "", "version": 0, "evidence": revision},
        "events": events,
        "history": history,
    }


def mutate(store, actor, body):
    """Reserve the idempotency key and commit core + checkpoint changes together."""
    request_id = body.get("request_id")
    if not isinstance(request_id, str) or not re.fullmatch(
        r"[a-zA-Z0-9-]{8,80}", request_id
    ):
        raise Rejected(400, "A valid operation ID is required.")
    operation, note, expected = (
        body.get("action"),
        body.get("note"),
        body.get("version"),
    )
    if (
        operation not in ("draft", "review", "approve")
        or not isinstance(note, str)
        or len(note) > 1500
        or type(expected) is not int
        or expected < 0
    ):
        raise Rejected(400, "Invalid checkpoint action, version or note.")
    digest = hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    key = (SCOPE, RECORD, actor, request_id)
    with store.transaction():
        conn = store.connection
        snapshot = read_record(conn, actor)
        revision = snapshot["evidence"]
        if body.get("evidence") != revision:
            raise Rejected(409, "Evidence changed. Reload the current review.")
        prior = conn.execute(
            "SELECT fingerprint,response FROM founder_receipts WHERE scope=? AND record=? AND actor=? AND request_id=?",
            key,
        ).fetchone()
        if prior:
            if prior[0] != digest:
                raise Rejected(
                    409, "Operation ID is already bound to a different request."
                )
            return json.loads(prior[1])
        if operation == "draft":
            if expected != snapshot["draft"]["version"]:
                raise Rejected(
                    409, "Draft changed on another device. Reload before saving."
                )
            conn.execute(
                """INSERT INTO founder_drafts VALUES(?,?,?,?,?,?) ON CONFLICT(scope,record,actor)
                            DO UPDATE SET evidence=excluded.evidence,version=excluded.version,note=excluded.note""",
                (SCOPE, RECORD, actor, revision, expected + 1, note),
            )
        else:
            role, stage = ("reviewer", 0) if operation == "review" else ("founder", 1)
            if actor != role:
                raise Rejected(403, "This account cannot perform this decision.")
            if expected != len(snapshot["events"]) or expected != stage:
                raise Rejected(
                    409,
                    "Decision history changed or the independent review is still pending.",
                )
            if operation == "approve" and not snapshot["underwriting"]["ready"]:
                raise Rejected(409, "Underwriting is on hold.")
            if not note.strip():
                raise Rejected(400, "Enter a decision rationale.")
            conn.execute(
                "INSERT INTO founder_actions VALUES(?,?,?,?,?,?,?)",
                (
                    SCOPE,
                    RECORD,
                    len(snapshot["history"]),
                    actor,
                    operation,
                    revision,
                    note,
                ),
            )
            store.save(
                Decision(
                    f"{RECORD}-{revision}-{operation}",
                    RECORD,
                    operation,
                    note,
                    revision,
                )
            )
        reply = read_record(conn, actor)
        conn.execute(
            "INSERT INTO founder_receipts VALUES(?,?,?,?,?,?)",
            (*key, digest, json.dumps(reply)),
        )
        return reply


class Server(ThreadingHTTPServer):
    def __init__(self, path, port=0):
        self.db = Path(path)
        self.db.parent.mkdir(parents=True, exist_ok=True)
        prepare(self.db)
        self.keys = {name: secrets.token_urlsafe(32) for name in ROLES}
        self.signing_key = secrets.token_bytes(32)
        super().__init__(("127.0.0.1", port), Handler)

    def session(self, actor):
        # HMAC binds the signed actor, nonce and expiry. Restarting invalidates issued cookies.
        payload = f"{actor}.{int(time.time()) + 3600}.{secrets.token_hex(16)}"
        sig = hmac.new(self.signing_key, payload.encode(), hashlib.sha256).hexdigest()
        return payload + "." + sig

    def identify(self, token):
        try:
            actor, expiry, nonce, sig = token.split(".")
            payload = f"{actor}.{expiry}.{nonce}"
            expected = hmac.new(
                self.signing_key, payload.encode(), hashlib.sha256
            ).hexdigest()
            if (
                actor in ROLES
                and hmac.compare_digest(expected, sig)
                and int(expiry) >= int(time.time())
            ):
                return actor
        except (ValueError, TypeError):
            pass
        raise Rejected(401, "Sign in with a current local access key.")


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def respond(self, status, body, content_type="application/json", cookie=None):
        raw = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        if cookie:
            self.send_header("Set-Cookie", cookie)
        self.end_headers()
        self.wfile.write(raw)

    def route(self, method):
        parsed = urlsplit(self.path)
        host = self.headers.get("Host", "")
        port = self.server.server_address[1]
        if host not in (f"127.0.0.1:{port}", f"localhost:{port}"):
            raise Rejected(403, "Loopback host required.")
        path = parsed.path
        if method == "GET" and not path.startswith("/api/"):
            name = path.lstrip("/") or "index.html"
            if name not in STATIC:
                raise Rejected(404, "Resource unavailable.")
            self.respond(
                200,
                (ROOT / "web" / name).read_bytes(),
                mimetypes.guess_type(name)[0] or "text/plain",
            )
            return
        if method == "POST":
            if (
                self.headers.get("Origin") not in (None, "http://" + host)
                or self.headers.get("Content-Type", "").split(";")[0]
                != "application/json"
            ):
                raise Rejected(403, "Same-origin JSON requests required.")
            try:
                length = int(self.headers.get("Content-Length", 0))
                maximum = 65536 if path.startswith(("/api/valuation/", "/api/corporate/")) else 16384
                if not 1 <= length <= maximum:
                    raise ValueError
                body = json.loads(self.rfile.read(length))
                if not isinstance(body, dict):
                    raise ValueError
            except (ValueError, UnicodeError, RecursionError):
                raise Rejected(400, "Invalid JSON request.") from None
        if path == "/api/session" and method == "POST":
            actor, token = body.get("actor"), body.get("token")
            if (
                not isinstance(actor, str)
                or actor not in ROLES
                or not isinstance(token, str)
                or not token.isascii()
                or not hmac.compare_digest(self.server.keys[actor], token)
            ):
                raise Rejected(401, "Invalid local account or access key.")
            self.respond(
                200,
                {"actor": actor},
                "application/json",
                "br_session="
                + self.server.session(actor)
                + "; Path=/; HttpOnly; SameSite=Strict; Max-Age=3600",
            )
            return
        if path == "/api/logout" and method == "POST":
            self.respond(
                200,
                {},
                "application/json",
                "br_session=; Path=/; HttpOnly; SameSite=Strict; Max-Age=0",
            )
            return
        if path.startswith("/api/valuation/"):
            self.valuation_route(method, path, body if method == "POST" else None)
            return
        if path.startswith("/api/corporate/"):
            self.corporate_route(method, path, body if method == "POST" else None)
            return
        matches = re.fullmatch(r"/api/workspaces/([\w-]+)/records/([\w-]+)", path)
        if not matches:
            raise Rejected(404, "Resource unavailable.")
        cookie = SimpleCookie()
        cookie.load(self.headers.get("Cookie", ""))
        actor = self.server.identify(
            cookie["br_session"].value if "br_session" in cookie else ""
        )
        validate_target(actor, *matches.groups())
        with Store(self.server.db, scope=SCOPE, actor=actor) as store:
            if method == "POST":
                result = mutate(store, actor, body)
            else:
                with store.transaction():
                    result = read_record(store.connection, actor)
        self.respond(200, result)

    def valuation_route(self, method, path, body):
        from .valuation_layer import evaluate
        from .valuation_store import Conflict, get_run, list_runs, save_run

        if path == "/api/valuation/examples" and method == "GET":
            examples = [json.loads(p.read_text(encoding="utf-8"))
                        for p in sorted((ROOT / "data" / "valuation").glob("*.json"))]
            self.respond(200, {"examples": examples})
            return
        cookie = SimpleCookie()
        cookie.load(self.headers.get("Cookie", ""))
        actor = self.server.identify(cookie["br_session"].value if "br_session" in cookie else "")
        if actor not in ("reviewer", "founder"):
            raise Rejected(403, "Valuation research requires the commercial workspace.")
        try:
            if path == "/api/valuation/evaluate" and method == "POST":
                self.respond(200, evaluate(body))
                return
            with Store(self.server.db, scope=SCOPE, actor=actor) as store:
                if path == "/api/valuation/runs" and method == "POST":
                    if set(body) != {"request_id", "packet"}:
                        raise ValueError("Saving a run requires request_id and packet")
                    self.respond(200, save_run(store, body["request_id"], body["packet"]))
                    return
                if path == "/api/valuation/runs" and method == "GET":
                    self.respond(200, {"runs": list_runs(store)})
                    return
                match = re.fullmatch(r"/api/valuation/runs/(VR-[a-f0-9]{24})", path)
                if match and method == "GET":
                    result = get_run(store, match[1])
                    if result is None:
                        raise Rejected(404, "Valuation run not found")
                    self.respond(200, result)
                    return
        except Conflict as error:
            raise Rejected(409, str(error)) from None
        except (ValueError, OverflowError) as error:
            raise Rejected(400, str(error)) from None
        raise Rejected(404, "Valuation resource unavailable")

    def corporate_route(self, method, path, body):
        from .corporate_case import evaluate_case, load_case

        cookie = SimpleCookie()
        cookie.load(self.headers.get("Cookie", ""))
        actor = self.server.identify(cookie["br_session"].value if "br_session" in cookie else "")
        if actor not in ("reviewer", "founder"):
            raise Rejected(403, "Corporate research requires the commercial workspace.")
        if self.headers.get("Origin") not in (None, "http://" + self.headers.get("Host", "")):
            raise Rejected(403, "Same-origin requests required.")
        if (method, path) not in (("GET", "/api/corporate/case"), ("POST", "/api/corporate/evaluate")):
            raise Rejected(404, "Corporate research resource unavailable.")
        try:
            default_case, facts = load_case()
        except (OSError, ValueError, UnicodeError):
            raise Rejected(503, "Corporate source case is unavailable.") from None
        if method == "GET":
            self.respond(200, {"case": default_case, "facts": facts, "actor": actor})
            return
        try:
            report = evaluate_case(body, facts)
            # Return the exact facts used, not a client copy from an earlier GET.
            # This route intentionally has no Store transaction or saved run.
            self.respond(200, {"case": body, "facts": facts, "report": report})
        except (ValueError, TypeError, KeyError, OverflowError, RecursionError) as error:
            raise Rejected(400, "Invalid corporate case: " + str(error)) from None

    def dispatch(self, method):
        try:
            self.route(method)
        except Rejected as error:
            self.respond(error.status, {"error": str(error)})
        except sqlite3.Error:
            self.respond(
                503, {"error": "Storage unavailable. Retry the same operation."}
            )

    def do_GET(self):
        self.dispatch("GET")

    def do_POST(self):
        self.dispatch("POST")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument(
        "--database", type=Path, default=ROOT / ".runs" / "founder.sqlite3"
    )
    args = parser.parse_args()
    with Server(args.database, args.port) as server:
        print(f"Open http://127.0.0.1:{server.server_port}/connected.html")
        print(f"Valuation http://127.0.0.1:{server.server_port}/valuation.html")
        print(f"Corporate case http://127.0.0.1:{server.server_port}/corporate.html")
        print("Synthetic local access keys expire on server restart.")
        for name, key in server.keys.items():
            print(f"{name}  {key}")
        server.serve_forever()
