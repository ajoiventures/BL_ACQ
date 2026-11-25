"""Founder-owned prompt ledger. Only scoped, fixed-vocabulary summaries enter shared records."""
import json
import re
import uuid
from fastapi import Depends, HTTPException
from pydantic import BaseModel, Field
from .core.tickets import canonical_register, get, is_canonically_closed, TicketError


class Intake(BaseModel):
    prompt: str = Field(min_length=1, max_length=16000)
    request_id: str = Field(min_length=1, max_length=120)
    ticket_id: str | None = Field(default=None, max_length=64)


STOP = set("a the to for and on or of in please can could you i we my our this that by with from me create build add update new work ticket make as is are at all each do an it into across have want would like need get".split())
REFERENCE = re.compile(r"\bBR-[TP][A-Z0-9]+\b", re.I)
DIGEST = re.compile(r"^(?:what(?:'s| is| are)? (?:left|remaining|pending|next|the status|the progress)|how (?:far|much is left|are (?:we|things)|is .*progress)|(?:show|give) (?:me )?(?:the |a )?(?:status|progress|summary|digest)|(?:status|progress|summary|digest|thanks|thank you|hello|hi|ok)\b)",re.I)
STANDING = re.compile(r"\b(?:every (?:time|prompt|instruction|request)|each (?:prompt|instruction|request)|standing instruction|all future prompts|from now on)\b",re.I)
STANDING_SCOPE = re.compile(r"ticket|prompt review|track|triage|organization",re.I)
FOLLOW_UP = re.compile(r"^(?:(?:please|yes)\s+)*(?:proceed|continue|next(?: batch(?: of tickets)?)?|resume|go ahead|do it|run tickets)[.!?\s]*$",re.I)
QUESTION = re.compile(r"^(?:what|why|when|where|which|who|how (?:does|did|can|do|should)|can i|is (?:this|that|it|there)|are (?:these|there)|tell me|explain|could i)\b",re.I)
ACTION = re.compile(r"\b(?:build|create|implement|add|fix|change|update|research|analyze|analyse|review|track|investigate|model|compare|find|file|design|schedule|calculate|run|document|collect|map|verify|draft|write|archive|upload|test|develop|prepare|integrate|evaluate|compile|generate|dissect|connect)\b",re.I)
ALIASES = {
    "BR-T004": ("gmail", "physical mail"),
    "BR-T014": ("postgis", "postgresql"),
    "BR-T017": ("local llm", "local model benchmarking"),
    "BR-T019": ("automatic filing", "document routing"),
    "BR-T020": ("legacy archiving",),
    "BR-T023": ("comprehensive plan",),
    "BR-T024": ("rhino sketch", "rhino model"),
    "BR-T027": ("buy box",),
    "BR-T028": ("asher",),
    "BR-T029": ("multifamily parcel inventory",),
    "BR-T033": ("daily funnel",),
    "BR-T035": ("lagro",),
    "BR-T039": ("o sullivan",),
}
IDEA = re.compile(r"\b(?:someday|sometime later|side idea|side thought|side note|distraction|separate thought|i have an idea|idea capture|idea for later|park (?:this|that|it|an? idea)|capture (?:this |an? )?idea|put (?:this|it) on the back burner)\b",re.I)
TOPICS = (
    ("Acquisition","COMMERCIAL","Acquisition research request","L4","SW-02",r"acquisition|multifamily|underwriting|commercial|parcel"),
    ("Atlas","MAIN_STREET_INSTITUTIONAL","District research request","L1","SW-00",r"district|main street|corridor|atlas"),
    ("Academy","PROJECT_INTERNAL","Academy development request","L1","SW-00",r"curriculum|skills|academy|course"),
    ("Integration","PROJECT_INTERNAL","Engineering integration request","L2","SW-00",r"software|integration|api|database|plugin"),
)
DEFAULT = ("System","PROJECT_INTERNAL","Founder work request","L1","SW-00")


def words(text):
    return re.findall(r"[a-z0-9]+",text.casefold())


def matches(prompt, rows):
    normalized = " " + " ".join(words(prompt)) + " "
    terms = set(words(prompt)) - STOP
    candidates = []
    for row in rows:
        if row["id"].startswith("BR-P"):
            continue
        title = words(row["title"])
        common = terms.intersection(set(title) - STOP)
        phrases = [" ".join(title), *ALIASES.get(row["id"],())]
        if any(" " + phrase + " " in normalized for phrase in phrases):
            candidates.append(row["id"])
        elif len(common) >= 3 and len(common) / max(1,len(set(title)-STOP)) >= .55:
            candidates.append(row["id"])
    return candidates


def outcome(row, disposition):
    if row is None:
        return {"ticket_id":None,"disposition":disposition,"objective":"Clarify the intended work item",
                "next_action":"Identify one ticket ID or describe one specific deliverable.","status":"awaiting_clarification"}
    planning, _ = canonical_register()
    ticket_id = row["id"]
    closed = row["status"] == "closed" or is_canonically_closed(planning, ticket_id)
    if closed:
        next_action = "Open the register to select the next ticket."
    else:
        next_action = planning.get(ticket_id, {}).get("next_action") or row["acceptance"].split(";")[0].rstrip(".") + "."
    return {"ticket_id":ticket_id,"disposition":disposition,"objective":row["title"],
            "next_action":next_action,"status":"closed" if closed else row["status"]}


def active_assignment(db):
    """Restore the last actionable assignment, not the last intake event.

    Keep immutable intake receipts distinct from the current ticket state.
    A digest, side idea or ambiguous instruction must not replace this pointer.
    """
    row = db.execute("SELECT result FROM private_prompt_review WHERE disposition IN ('created','linked','resumed') ORDER BY seq DESC LIMIT 1").fetchone()
    if row is None:
        return None
    receipt = json.loads(row["result"])
    ticket = get(db, receipt["ticket_id"])
    return {**receipt, **outcome(ticket, receipt["disposition"]),
            "active_ticket_id": ticket["id"], "workstream": ticket["area"], "theme": ticket["title"]}


def plan(db, event, body):
    text = body.prompt.strip()
    if not text or not body.request_id.strip():
        raise HTTPException(422,"Prompt and request ID must contain text")
    previous = db.execute("SELECT * FROM private_prompt_review WHERE request_id=?",(body.request_id,)).fetchone()
    if previous:
        if previous["prompt"] != body.prompt or previous["explicit"] != body.ticket_id:
            raise HTTPException(409,"Request ID already belongs to a different input")
        return json.loads(previous["result"])

    def lookup(key):
        try:
            return get(db,key.upper().strip())
        except TicketError as exc:
            raise HTTPException(422,"Ticket reference does not exist") from exc

    rows = db.execute("SELECT id,title FROM project_tickets ORDER BY id").fetchall()
    ids = list(dict.fromkeys(i.upper() for i in REFERENCE.findall(text)))
    last_active = active_assignment(db)
    active = last_active["ticket_id"] if last_active else None
    topic = next((item[:5] for item in TOPICS if re.search(item[5],text,re.I)),DEFAULT)
    if (IDEA.search(text) or re.match(r"^(?:distraction|side note|idea capture|idea for later)\s*[:—-]",text,re.I)) and not (STANDING.search(text) and STANDING_SCOPE.search(text)):
        candidates = [body.ticket_id] if body.ticket_id else (ids or matches(text,rows))
        linked = lookup(candidates[0]) if len(candidates) == 1 else None
        result = {"ticket_id":linked["id"] if linked else None,"disposition":"parked_idea",
                  "objective":"Capture a side idea for later review","next_action":"Resume the active assignment. Revisit this idea when prioritizing its workstream.",
                  "status":"parked","workstream":linked["area"] if linked else topic[0],
                  "theme":linked["title"] if linked else topic[2]}
    elif body.ticket_id:
        result = outcome(lookup(body.ticket_id),"linked")
    elif len(ids) > 1:
        result = outcome(None,"needs_clarification")
    elif len(ids) == 1:
        result = outcome(lookup(ids[0]),"linked")
    elif STANDING.search(text) and STANDING_SCOPE.search(text):
        result = outcome(lookup("BR-T043"),"linked")
    elif FOLLOW_UP.match(text):
        result = outcome(lookup(active),"resumed") if active else outcome(None,"needs_clarification")
    elif DIGEST.search(text) or QUESTION.search(text):
        planning, _ = canonical_register()
        remaining = sum(not is_canonically_closed(planning, row[0]) for row in
                        db.execute("SELECT id FROM project_tickets WHERE status != 'closed'"))
        result = {"ticket_id":None,"disposition":"informational","objective":"Review current project context",
                  "next_action":f"{remaining} tickets remain. Open the register to inspect their acceptance criteria.",
                  "status":"read_only"}
    else:
        candidates = matches(text,rows)
        if len(candidates) == 1:
            result = outcome(lookup(candidates[0]),"linked")
        elif candidates or not ACTION.search(text):
            result = outcome(None,"needs_clarification")
        else:
            # Exact rephrasing by punctuation or capitalization can resume a private intake.
            normalized = " ".join(words(text))
            existing = db.execute("SELECT result FROM private_prompt_review WHERE normalized=? AND disposition='created' ORDER BY seq DESC LIMIT 1",(normalized,)).fetchone()
            if existing:
                key = json.loads(existing["result"])["ticket_id"]
                result = outcome(lookup(key),"linked")
            else:
                area,domain,title,leader,owner = topic
                key = "BR-P" + uuid.uuid4().hex[:16].upper()
                criteria = "Prepare the requested deliverable with traceable sources and obtain independent review against the private founder brief."
                db.execute("""INSERT INTO project_tickets(id,area,domain,title,leader,owner,status,acceptance,
                    evidence,dependencies,source) VALUES(?,?,?,?,?,?,'open',?,?,'[]',?)""",
                    (key,area,domain,title,leader,owner,criteria,"Private instruction received","Founder intake"))
                event(db,domain,"FOUNDER","TICKET_CREATED",key,{"objective":title})
                result = outcome(lookup(key),"created")
    associated = lookup(result["ticket_id"]) if result["ticket_id"] else None
    result.setdefault("workstream",associated["area"] if associated else topic[0])
    result.setdefault("theme",associated["title"] if associated else topic[2])
    result["active_ticket_id"] = result["ticket_id"] if result["disposition"] in {"created","linked","resumed"} else active
    db.execute("""INSERT INTO private_prompt_review(request_id,prompt,explicit,normalized,disposition,result)
                  VALUES(?,?,?,?,?,?)""",(body.request_id,body.prompt,body.ticket_id," ".join(words(text)),result["disposition"],json.dumps(result)))
    event(db,"PROJECT_INTERNAL","FOUNDER","PROMPT_REVIEW",result["ticket_id"] or "PRIVATE_INTAKE",{"objective":result["objective"]})
    return result


def register(app,actor,conn,event):
    with conn() as db:
        db.execute("""CREATE TABLE IF NOT EXISTS private_prompt_review(
            seq INTEGER PRIMARY KEY, request_id TEXT UNIQUE NOT NULL,
            prompt TEXT NOT NULL, explicit TEXT, normalized TEXT NOT NULL,
            disposition TEXT NOT NULL,result TEXT NOT NULL,created TEXT DEFAULT CURRENT_TIMESTAMP)""")
    def founder(who=Depends(actor)):
        if who != "FOUNDER":
            raise HTTPException(403,"Founder credential required")
    @app.post("/api/prompt-review",dependencies=[Depends(founder)])
    def review(body:Intake):
        with conn() as db:
            db.execute("BEGIN IMMEDIATE")
            return plan(db,event,body)
    @app.get("/api/prompt-review/current",dependencies=[Depends(founder)])
    def current():
        with conn() as db:
            return active_assignment(db)
    @app.get("/api/prompt-review/ideas",dependencies=[Depends(founder)])
    def ideas():
        with conn() as db:
            rows = db.execute("""SELECT request_id,prompt,result,created FROM private_prompt_review
                WHERE disposition='parked_idea' ORDER BY seq DESC""")
            return [{"request_id":row["request_id"],"prompt":row["prompt"],
                     "result":json.loads(row["result"]),"created":row["created"]} for row in rows]
