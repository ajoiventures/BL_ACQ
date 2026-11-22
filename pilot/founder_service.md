# Authenticated local review

Run `python -m pilot.founder_service` from the repository root. Open the printed loopback address in two separate browser profiles. Copy a role's access key from the terminal to sign in. Each start generates new high-entropy role keys and signs one-hour session cookies with a fresh process secret. The SQLite file defaults to `.runs/founder.sqlite3`. It preserves checkpoints and decisions across restarts.

Follow `validate_target`, `mutate` and `read_record`. The service derives the actor from the cookie and compares the requested scope and record against the account's assignment. A commercial review holds a synthetic Orchard parcel, evidence from the underwriting model and an independent decision trail. The civic example identity has no commercial access. The frozen fixture has its own evaluation date, evidence ID, source references and packet hash.

A save supplies its expected version, evidence ID and operation ID. Within the core store transaction, a conflicting stale write receives HTTP 409. An identical retry returns the stored response. The reviewer records the independent decision first. A distinct founder can then approve the eligible synthetic parcel. Both the receipt and the core decision commit in the same SQLite transaction.

The HTTP service binds to 127.0.0.1 and serves an explicit static-file list. Use separate browser profiles to exercise session boundaries on one machine. Production identity, TLS termination, physical-device connectivity, live orders, and external payment services are outside this local acceptance run.

Publishing a changed fixture stores another immutable evidence row keyed by the underwriting packet digest. The UI reads the stored snapshot and marks earlier decisions as superseded. A prior approval carries no authority over a new packet. Old draft or decision submissions return a conflict.

## Corporate research case

The same service serves `/corporate.html`. Its two API routes require a current
reviewer or founder session in the commercial workspace. Civic identities have
no access. A supplied Origin must match the loopback host, and POSTs require
JSON with a maximum body of 65,536 bytes.

- `GET /api/corporate/case` returns `{case, facts, actor}` from the checked-in
  historical case and source-fact files.
- `POST /api/corporate/evaluate` accepts the editable case object directly. It
  always reloads source facts on the server and returns `{case, facts, report}`
  together so a downloaded research packet contains the exact facts evaluated.
  Additional client fact fields do not replace the server's evidence.

These routes calculate research outputs only. They do not insert a saved run,
record an approval, place an order or change the acquisition ledger. Their
results remain `research_requires_review` with execution disabled. Malformed
case objects return HTTP 400; unavailable source files return HTTP 503. The
interface distinguishes reported August fiscal periods from the hypothetical
October opening and model years. See the [page guide](../web/corporate_html.md)
and [service tests](../docs/guides/test_corporate_service.md).
