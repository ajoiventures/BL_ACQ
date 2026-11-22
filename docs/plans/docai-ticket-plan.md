# Doc AI delivery plan under the existing master backlog

**Revision: November 22, 2026. Status: planned child work; no provider or production service enabled.**

Doc AI is the product in this plan. The existing builder swarm develops it through the established skills, agent roles and ticket workflow. The product contains an evidence engine, document application services and an optional provider connection. The builder swarm remains separate from product runtime.

The machine-readable source is `config/docai-ticket-plan.json`, using the existing `br.build-ticket-plan.v1` scheduler contract. Its 24 `BR-DOC-*` items are local delivery children of existing `BR-ENG-*` requirements in the master register. They do not create replacement epics, replace the existing agent roster or establish that external tracker issues were opened. Earlier acquisition-oriented 84-ticket work remains separate and supplies reusable evidence where appropriate; its completion states are not inherited here.

## What exists, and what still needs work

| Component | Observed reusable foundation | Remaining Doc AI responsibility |
| --- | --- | --- |
| Evidence engine | `pilot/document_evidence.py` has source hashes, typed manual/native claims, immutable history, review and conflict/supersession handling. | Document-neutral identity and scope, generalized intake, compatible provider-origin candidates, extraction runs, full metadata and tested migration. |
| Native ingestion | Earlier local `filing/inbox.py:file_document(path, root, destination=None)` has native readers, archived originals and receipts. | Audit the exact revision and adapt the contract; expose source coverage and partial/truncated parsing, safe resource limits and reproducible fixtures. |
| Application | `pilot/document_offer_layer.py` consumes reviewed financial fields. | A general Doc AI intake/status/source/review/export workflow. The existing offer layer remains a downstream consumer. |
| Provider interface | `CandidateProvider` exists; `NativeJsonProvider` copies structured claims; `DisabledAIProvider` rejects calls. | A truthful provider/result/error contract, supported store schema, compatible adapter and independently verified connection. Current stubs do not establish these. |
| Local model client | Earlier local code contains an Ollama client and an unverified tool exposure. | Registration, version compatibility, authentication, allowed data and end-to-end invocation are unverified. Code presence does not establish connection. |
| Builder coordination | The current offline scheduler and earlier durable `PROJECT_INTERNAL` ticket machinery supply useful contracts. | Reuse the existing skills/agent library and audited persistence patterns. Keep development tickets distinct from product ingestion jobs and business transaction states. |

Current planning evidence is already maintained in `docs/architecture/docai-current-state.md`, `docs/architecture/document-engine-layers.md` and `config/swarm-library-extension.json`. BR-DOC-001 extends these sources instead of creating a duplicate boundary or reuse inventory. Existing read-only audits are partial evidence; canonical execution workspace/provenance and reviewed selected-adapter ownership remain open acceptance.

A ChatGPT cloud connector being available does not prove that this application's backend is connected. No live endpoint, authenticated Doc AI inference, model download or production deployment is established by this plan.

## Engine, application and provider responsibilities

The **engine** owns document identity, immutable originals, versions, extraction runs, typed candidates, ACLs, idempotence, conflict handling, review history and accepted projections. Native parsing is an ordinary code path. It must work without AI credentials or model services.

The **application layer** manages intake, durable jobs, status, source display, candidate review, accepted output and operations visibility. It calls engine rules instead of duplicating them. Document processing stages are ordinary software queues; naming ingestion, extraction, indexing and action stages does not create runtime agents.

The **provider adapter** converts an explicitly configured service's response into unaccepted candidates. The generic seam and mock contract are built early in BR-DOC-007 and reviewed at B. BR-DOC-012 then implements one actual version-pinned client, registers it while disabled and independently checks recorded-response/contract fixtures through its injected transport. The selected implementation can wrap the audited existing Ollama client or implement the chosen NVIDIA service client; building every provider is outside this increment. Endpoint access, compatible deployed versions, permission to process specific data, bounded spend/time and measured output quality remain later conditions for the C live evaluation.

The **consumer boundary** publishes reviewed document facts. Acquisition economics, negotiation, offers and other workflows can consume those facts independently. They are not prerequisites for Doc AI extraction or its first provider experiment.

## Connection gates: when AI becomes appropriate

| Gate | Child | Required result | What it permits |
| --- | --- | --- | --- |
| A — local path | BR-DOC-010 | Native intake → source-linked candidates → human review → accepted export, with failures handled and AI disabled. | A usable inspectable local document slice. |
| B — adapter contract | BR-DOC-009 | Disabled generic seam and mock provider behavior, schema and error/provenance handling independently verified. | The generic interface is ready. BR-DOC-012 separately implements and independently checks the selected real client offline. |
| C — limited evaluation | BR-DOC-013, verdict BR-DOC-014 | A/B, the BR-DOC-012 version-pinned real adapter and independent offline conformance, reviewed fixture policy, adverse tests and verified endpoint/auth/version/data policy/cost/timeout/provenance. | One bounded synthetic or specifically permitted test-document run, followed by an independent quality/cost verdict. |
| D — production | BR-DOC-024, readiness BR-DOC-022 | Accepted release, supported scope, production data permissions, monitored rollout, budgets, stop conditions and rollback. | A separately enabled narrow production canary. |

A and B can proceed in parallel within resource and file ownership limits. The limited C test does not wait for all twelve parser classes, vector retrieval, acquisition finance, household segmentation or the earlier 84-ticket backlog. Hosted inference also does not require a local GPU; self-hosted inference has a separate verified hardware/runtime requirement. Optional R and CUDA measurements remain distinct tracks.

The current plan sets `ai_enabled`, `live_calls_enabled`, `model_downloads_enabled` and `production_enabled` to false. A phase appearing in an offline schedule cannot change those switches. C remains explicitly blocked; D and retrieval are deferred. This plan makes no model call and authorizes no document transfer or source-folder mutation.

## Builder coordination and resource manager

Reuse L1 for evidence and ontology, L2 for engineering and interoperability, L3 for error/cost/data-risk and independent analysis, and L4 for workflows and operations. SW-00 coordinates and integrates; SW-13 independently reviews implementation evidence. These labels route work within the existing organization. They do not add another agent roster.

The scheduler reserves **three worker slots plus one separate integrator**, with **CUDA = 0** and **R runtime = 0** until actual runtime evidence changes the profile. L1-L4 and SW-13 share the same three worker slots. One named owner cannot be booked twice. Overlapping file or ancestor-directory write scopes serialize. A worker count is not a CPU-core or GPU-capacity measurement.

SW-00 dispatches only dependency-ready work, applies priority then remaining critical-path estimates, and replans after blockers, resources, ownership, revisions or evidence change. Use the existing durable `PROJECT_INTERNAL` tracker for approved development work with version/CAS checks and independent closure evidence. Do not route builder tasks through the business `Swarm.transition` lifecycle. Product extraction jobs have their own state and scope.

Each handoff contains child ID, parent references, source revision, changed paths, exact commands, acceptance-to-evidence mapping, actual results, unexecuted checks and residual limitations. SW-13 evaluates implementation independently; SW-00 promotes the reviewed result. A failed criterion preserves rework history and blocks dependent claims. The planner trusts supplied statuses; it neither authenticates reviewers nor executes those gates.

## Roadmap and bounded work list

Extend the existing current-state audit, layer architecture and library crosswalk with the remaining canonical workspace/provenance and ownership decisions; start fixture work alongside that coordination. Freeze document contracts, then build native parsing, vault identity, durable jobs and the disabled provider seam. Connect the local reviewable application, pass A/B and adverse tests, and implement and independently check one disabled real provider client plus its manifest/preflight. Only then resolve the specific C preconditions. Connector expansion, telemetry, reviewed consumer outputs and parser breadth can proceed independently where their actual dependencies permit.

Every range below is an assumption for active builder effort in minutes. It is not a promised elapsed delivery date, empirical speed or production capacity. Detailed write scopes, required resources, blockers and acceptance criteria are authoritative in the JSON; they are repeated below for review.

| Child | Scope | Master parents | Owner | Effort range |
| --- | --- | --- | --- | --- |
| BR-DOC-001 | Confirm canonical Doc AI execution workspace and reuse ownership | BR-ENG-281, BR-ENG-286, BR-ENG-311, BR-ENG-313, BR-ENG-314 | SW-00_integrator | 30–100 min |
| BR-DOC-002 | Version document, extraction, candidate and review contracts | BR-ENG-124, BR-ENG-175, BR-ENG-272, BR-ENG-282, BR-ENG-286 | L1_evidence | 60–180 min |
| BR-DOC-003 | Prepare synthetic golden files and predeclared evaluation metrics | BR-ENG-184, BR-ENG-291, BR-ENG-317, BR-ENG-319 | L3_quality | 80–240 min |
| BR-DOC-004 | Adapt the evidence store into a versioned Doc AI vault | BR-ENG-124, BR-ENG-179, BR-ENG-272, BR-ENG-286 | L1_evidence | 120–300 min |
| BR-DOC-005 | Reuse native filing behind a safe document parser plugin | BR-ENG-125, BR-ENG-180, BR-ENG-286 | L2_engineering | 100–320 min |
| BR-DOC-006 | Add durable intake jobs, leases and outbox recovery | BR-ENG-177, BR-ENG-178, BR-ENG-184 | L4_workflow | 120–300 min |
| BR-DOC-007 | Build the disabled provider seam and mock adapter contract | BR-ENG-282, BR-ENG-283, BR-ENG-286, BR-ENG-295 | L2_engineering | 80–220 min |
| BR-DOC-008 | Expose Doc AI intake, status, review and source trace | BR-ENG-127, BR-ENG-178, BR-ENG-182, BR-ENG-185, BR-ENG-294 | L4_workflow | 120–320 min |
| BR-DOC-009 | Gate B: independently verify the offline provider contract | BR-ENG-295, BR-ENG-313, BR-ENG-323 | SW-13_independent_review | 40–100 min |
| BR-DOC-010 | Gate A: verify the local native extraction and review path | BR-ENG-125, BR-ENG-127, BR-ENG-180, BR-ENG-182, BR-ENG-184, BR-ENG-324 | SW-13_independent_review | 60–180 min |
| BR-DOC-011 | Specify and dry-run a bounded source connector | BR-ENG-121, BR-ENG-123, BR-ENG-176, BR-ENG-177, BR-ENG-179, BR-ENG-295 | L4_workflow | 90–260 min |
| BR-DOC-012 | Implement one version-pinned disabled provider client and preflight | BR-ENG-282, BR-ENG-283, BR-ENG-286, BR-ENG-295 | L2_engineering | 140–420 min |
| BR-DOC-013 | Gate C: run a bounded live extraction on synthetic/test files | BR-ENG-283, BR-ENG-286, BR-ENG-291, BR-ENG-295, BR-ENG-319 | L2_engineering | 60–200 min |
| BR-DOC-014 | Independently score the live candidate quality and costs | BR-ENG-185, BR-ENG-291, BR-ENG-317, BR-ENG-319, BR-ENG-320, BR-ENG-324 | SW-13_independent_review | 80–220 min |
| BR-DOC-015 | Add document operations telemetry and cost visibility | BR-ENG-185, BR-ENG-320, BR-ENG-326, BR-ENG-328 | L4_workflow | 90–260 min |
| BR-DOC-016 | Publish reviewed document outputs to downstream consumers | BR-ENG-127, BR-ENG-182, BR-ENG-183, BR-ENG-282, BR-ENG-294 | L1_evidence | 60–180 min |
| BR-DOC-017 | Verify isolation, hostile inputs and recovery across the slice | BR-ENG-130, BR-ENG-184, BR-ENG-295, BR-ENG-323, BR-ENG-327 | L3_quality | 100–260 min |
| BR-DOC-018 | Expand typed parsers through the twelve-class coverage matrix | BR-ENG-175, BR-ENG-180, BR-ENG-286 | L2_engineering | 160–480 min |
| BR-DOC-019 | Later: add permission-aware retrieval and versioned embeddings | BR-ENG-181, BR-ENG-272, BR-ENG-286 | L2_engineering | 160–480 min |
| BR-DOC-020 | Run independent R diagnostics and calibration when available | BR-ENG-291, BR-ENG-317, BR-ENG-319, BR-ENG-328 | L3_quality | 100–280 min |
| BR-DOC-021 | Measure useful CUDA batches against the CPU reference | BR-ENG-286, BR-ENG-288, BR-ENG-317, BR-ENG-320 | L2_engineering | 120–360 min |
| BR-DOC-022 | Review a scoped production candidate and rollback evidence | BR-ENG-283, BR-ENG-295, BR-ENG-323, BR-ENG-324, BR-ENG-327 | SW-00_integrator | 60–200 min |
| BR-DOC-023 | Reconcile the unavailable original document-platform specification | BR-ENG-186, BR-ENG-313, BR-ENG-314 | L1_evidence | 60–200 min |
| BR-DOC-024 | Gate D: conduct a separately enabled monitored production pilot | BR-ENG-130, BR-ENG-185, BR-ENG-283, BR-ENG-320, BR-ENG-327, BR-ENG-328 | L4_workflow | 120–360 min |

## Validated schedule snapshot

The actual repository scheduler accepted this JSON, including all phase gates, IDs and dependencies. The graph is acyclic; all 24 IDs are unique; all estimates fall within their supplied ranges; file ownership and resource capacity checks pass. The plan contains **18 planned, 4 explicitly blocked and 2 deferred** children, and **0 completed** children. After dependency propagation the scheduler produces **16 schedulable, 6 blocked and 2 excluded** items.

**Ready now:** `BR-DOC-001` (SW-00 canonical workspace/provenance and reuse ownership) and `BR-DOC-003` (L3 fixtures/evaluation policy). `BR-DOC-002` follows the reviewed boundary. The three worker lanes then share the engine/seam/application queue; no worker is duplicated to manufacture concurrency.

With the current assumed point durations, the schedulable-scope critical-path lower bound is **710 relative minutes** and the resource-constrained heuristic schedule is **930 relative minutes**. Substituting all low or all high per-ticket estimates gives **590–1,900 relative minutes** for this same schedulable scope. This excludes blocked/future work and external waiting, and is not a probabilistic confidence interval or delivery promise. In the point-estimate simulation, B completes at minute 510 and A at minute 610.

Observed peak allocation in the generated schedule is 3 workers and 1 integrator, with no CUDA or R allocated. The schedule has no overlapping writes or duplicate owner bookings. The next live-evaluation work remains held by selected-client conformance and its connection/test manifest; R and CUDA measurements remain held by unavailable runtimes; the original source-reconciliation task remains held by the missing specific source.

Reproduce the schedule without writing or executing product work:

```bash
python tools/schedule_builder_work.py --plan config/docai-ticket-plan.json
```

The exact `config/docai-ticket-plan.json` file-byte SHA-256 is `2269f4ce1dfc2edcb89dfbbd38d813cba62f71d2a330f3e7f4b385c8ad98fc26`. The scheduler canonicalizes JSON before hashing; its separate `plan_sha256` is `81843cd61e8d5ff14dba5733c55363fb3e8d82e0641d1f5a141a444f43ad4e75`. Both identify this validation input using their stated representations. A later edit or status change requires a new schedule. No implementation, provider test, R execution, GPU benchmark or deployment was performed by validating this plan.

## Specific reuse and correctness risks

The legacy parser's limits need explicit coverage metadata: TXT/MD/CSV reads cap at 150,000 bytes; DOCX has a 2 MB XML guard; PDF extraction caps at five pages and 20,000 characters per page. A successful bounded read is not proof of a complete document. An adapter must either extend a limit safely or report what it skipped, why and how much is known. Scans must produce a truthful OCR-needed/unsupported state until a separately enabled provider can process them.

The current evidence store accepts manual/native JSON methods and does not accept a general provider metadata record. A protocol declaration alone therefore does not make AI plug-compatible. The generic seam in BR-DOC-007 is separate from the selected real client implementation in BR-DOC-012; both its recorded-response/contract evidence and the later live evaluation are required before claiming compatibility. The new contract includes truthful extraction method, provider/model/API/run versions, source spans, raw-response reference/hash, structured errors and coverage; protected raw responses follow the same access and retention controls as the source.

Idempotence must compare the request payload as well as the key. Stale writes need version/CAS conflicts, and multiple document references must not collapse distinct revisions or purposes. Revocation, deletion and supersession propagate to projections and any later index. Provider confidence stays separate from source validity, human review and calibrated event probabilities.

The original document-platform PDF named in BR-ENG-186 remains a source gap. Unrelated reference PDFs cannot establish its exact twenty microtasks or SQL. Reconciliation is a separate child, and does not block useful implementation against the verified current contracts and this user correction.

## Complete child acceptance contracts

These are planned deliverables. Existing files named in write scopes are to be extended; other proposed paths do not imply implemented capabilities. All children retain empty completion-evidence arrays until their acceptance is independently reviewed.

### BR-DOC-001 — Confirm canonical Doc AI execution workspace and reuse ownership

**Parents:** BR-ENG-281, BR-ENG-286, BR-ENG-311, BR-ENG-313, BR-ENG-314. **Owner:** SW-00_integrator; SW-00 coordinates and SW-13 reviews independently. **Status:** planned. **Layer:** architecture.

**Dependencies:** none. **Resources:** integrator=1. **Effort:** 30–100 minutes (point assumption: 50).

**Write scopes:** `docs/architecture/docai-current-state.md`, `docs/architecture/document-engine-layers.md`, `config/swarm-library-extension.json`.

**Reuse basis:** pilot/document_evidence.py contains reusable provenance and review rules with acquisition-oriented scope. tools/schedule_builder_work.py already validates the bounded development DAG. Earlier local filing/inbox.py and backend/core/tickets.py are reuse candidates requiring revision and contract checks; folder names are not deployment evidence. The existing docs/architecture/docai-current-state.md, docs/architecture/document-engine-layers.md and config/swarm-library-extension.json capture current-state, product-boundary and library-mapping evidence; their contents are partial fulfillment, not closure of the remaining workspace/provenance and ownership decisions.

**Acceptance:**

1. Extend the current-state audit, engine/layer architecture and existing library crosswalk with the reviewed execution decision; preserve their existing findings instead of creating duplicate boundary or inventory documents.
2. Record the canonical execution repository/workspace, source revision/provenance and reviewed adapter ownership before migration. Verify interfaces for EvidenceStore, native filing, durable PROJECT_INTERNAL tickets and local-model client; distinguish code presence, tests, registration, connection and deployment.
3. Treat document_offer_layer.py as an optional downstream financial consumer. Initial extraction and provider evaluation have no finance, household-segment or all-84-ticket dependency.
4. Map every child to existing master requirements and L1-L4 ownership with SW-00 coordination and SW-13 independent review; no replacement master epic, agent roster or external issue is implied.
5. Record present provider compatibility gaps, including EvidenceStore rejecting provider metadata; do not describe NativeJsonProvider as document extraction or DisabledAIProvider as a working connection.
6. Select one initial provider backend and name the adapter owner using the audited reuse evidence; distinguish this implementation decision from endpoint activation and live connection permission.

### BR-DOC-002 — Version document, extraction, candidate and review contracts

**Parents:** BR-ENG-124, BR-ENG-175, BR-ENG-272, BR-ENG-282, BR-ENG-286. **Owner:** L1_evidence; SW-00 coordinates and SW-13 reviews independently. **Status:** planned. **Layer:** engine.

**Dependencies:** BR-DOC-001. **Resources:** agent_worker=1. **Effort:** 60–180 minutes (point assumption: 100).

**Write scopes:** `pilot/document_contracts.py`, `schemas/docai`, `tests/test_docai_contracts.py`.

**Acceptance:**

1. Define document-neutral identity plus optional typed asset links; preserve source revision, original hash, document version, run ID, schema version, actor and purpose/tenant scope.
2. Register the twelve existing document-class contracts and UNKNOWN; declare supported fields and parsers individually instead of claiming twelve implemented extractors.
3. Separate source observations, candidate claims, provider scores, human review decisions and accepted projections. A provider cannot submit its own review or authoritative status.
4. Define ExtractionRun and CandidateClaim metadata for truthful extraction method, parser/provider/model/API version, configuration hash, actual backend, evidence spans, input coverage, truncation/partial status, structured errors and protected raw-response reference/hash.
5. Define backward-compatible migration/version negotiation and reject unknown incompatible schemas; dates, currencies, units, decimals, missing values and page/row offsets have explicit types.

### BR-DOC-003 — Prepare synthetic golden files and predeclared evaluation metrics

**Parents:** BR-ENG-184, BR-ENG-291, BR-ENG-317, BR-ENG-319. **Owner:** L3_quality; SW-00 coordinates and SW-13 reviews independently. **Status:** planned. **Layer:** evaluation.

**Dependencies:** none. **Resources:** agent_worker=1. **Effort:** 80–240 minutes (point assumption: 120).

**Write scopes:** `tests/fixtures/docai`, `docs/validation/docai-evaluation-policy.md`, `tools/docai_metrics.py`, `tests/test_docai_metrics.py`.

**Acceptance:**

1. Create or inventory licensed synthetic/test-only originals, hashes, labels and independently checked source spans; include native text, a scan, tables, ambiguous values and malformed/truncated files.
2. Define field precision/recall, exact-value accuracy, span fidelity, abstention/coverage, critical false accepts, review time, latency and cost with explicit denominators and small-sample limitations.
3. Predeclare test split, supported document classes, acceptance thresholds, minimum evidence and baseline before live results are seen; unsupported classes remain unsupported.
4. Keep provider confidence separate from empirical correctness; plan held-out reliability, Brier score or other appropriate calibration only where labeled probability-like scores exist.
5. Golden values and scoring code are independently reviewed, immutable per fixture version and usable without an AI provider, R or CUDA.

### BR-DOC-004 — Adapt the evidence store into a versioned Doc AI vault

**Parents:** BR-ENG-124, BR-ENG-179, BR-ENG-272, BR-ENG-286. **Owner:** L1_evidence; SW-00 coordinates and SW-13 reviews independently. **Status:** planned. **Layer:** engine.

**Dependencies:** BR-DOC-002. **Resources:** agent_worker=1. **Effort:** 120–300 minutes (point assumption: 180).

**Write scopes:** `pilot/document_evidence.py`, `pilot/document_vault.py`, `tests/test_document_evidence.py`, `tests/test_docai_vault.py`.

**Reuse basis:** pilot/document_evidence.py: EvidenceStore, append-only reviews, source hashes, supersession and conflict rules.

**Acceptance:**

1. Preserve immutable original bytes separately from derived text, hashes, extraction runs and review events; preserve historical versions and explicit supersession.
2. Add typed provider-origin candidates and metadata through the reviewed contract, without relaxing accepted-input review or allowing a model to write decisions.
3. Enforce tenant/purpose ACLs on intake, source access, candidate reads, review and export; revoked access, deletion and retention changes invalidate derived visibility.
4. Replay identical document/claim requests idempotently; reject reused keys with a different payload and return explicit version/CAS conflicts for stale updates.
5. Keep ambiguous asset links in review, support multiple source references and asset links, and prevent stale/superseded/conflicting evidence from silently becoming accepted input.
6. Migration tests preserve current manual/native behavior and distinguish schema compatibility from a real provider connection.

### BR-DOC-005 — Reuse native filing behind a safe document parser plugin

**Parents:** BR-ENG-125, BR-ENG-180, BR-ENG-286. **Owner:** L2_engineering; SW-00 coordinates and SW-13 reviews independently. **Status:** planned. **Layer:** engine.

**Dependencies:** BR-DOC-002. **Resources:** agent_worker=1. **Effort:** 100–320 minutes (point assumption: 180).

**Write scopes:** `pilot/document_native.py`, `pilot/document_parsers`, `tests/test_docai_native.py`.

**Reuse basis:** Earlier local filing/inbox.py provides native extraction, routing, original preservation and receipts; exact migration compatibility is not yet established.

**Acceptance:**

1. Audit and adapt the existing file_document(path, root, destination=None) contract and native TXT/MD/CSV/DOCX/text-PDF behaviors; preserve originals and receipts without copying an unrelated application.
2. Ship one declared initial document-class vertical slice with native text extraction and manual candidate entry; recognize scanned/image-only input as needs_ocr rather than fabricate text.
3. Emit deterministic page/row/text-span provenance and parser version; record bytes/pages/rows covered, explicit truncation and partial failures, never label an incomplete parse complete.
4. Audit the legacy limits before reuse: TXT/MD/CSV reads capped at 150,000 bytes, DOCX XML guarded at 2 MB, and PDF extraction capped at five pages and 20,000 characters per page. Carry applied limits and detected incomplete coverage into explicit metadata; do not silently inherit completeness assumptions.
5. Bound file size, decompression, page count, parser time and memory; sanitize paths and quarantine malformed, unsupported or suspicious files without deleting the original.
6. Offline fixtures demonstrate native extraction and exact source references with provider imports, model downloads and network construction absent.

### BR-DOC-006 — Add durable intake jobs, leases and outbox recovery

**Parents:** BR-ENG-177, BR-ENG-178, BR-ENG-184. **Owner:** L4_workflow; SW-00 coordinates and SW-13 reviews independently. **Status:** planned. **Layer:** engine.

**Dependencies:** BR-DOC-002. **Resources:** agent_worker=1. **Effort:** 120–300 minutes (point assumption: 180).

**Write scopes:** `pilot/document_jobs.py`, `tests/test_docai_jobs.py`.

**Reuse basis:** Earlier local backend/core/tickets.py has durable PROJECT_INTERNAL jobs, version conflict checks and SW-13 closure patterns; do not reuse the business transaction lifecycle.

**Acceptance:**

1. Register source identity and durable work before file movement or extraction; define ordinary ingestion/extraction/index/action processing stages without creating AI agents.
2. Provide atomic lease acquisition, expiry, bounded retries/backoff, dead letters, cancellation and explicit terminal/partial states with request/run trace IDs.
3. Use payload-bound idempotency keys and optimistic version checks; duplicate arrivals, changed payloads and concurrent edits have distinct tested outcomes.
4. Crash/restart tests prove no lost source, duplicate finalization or contradictory accepted completion, including failure between outbox commit and processing.
5. Reuse audited persistence patterns from existing PROJECT_INTERNAL tickets for builder tracking, while keeping product ingestion jobs separate from development tickets and business Swarm.transition states.

### BR-DOC-007 — Build the disabled provider seam and mock adapter contract

**Parents:** BR-ENG-282, BR-ENG-283, BR-ENG-286, BR-ENG-295. **Owner:** L2_engineering; SW-00 coordinates and SW-13 reviews independently. **Status:** planned. **Layer:** provider_connection.

**Dependencies:** BR-DOC-002. **Resources:** agent_worker=1. **Effort:** 80–220 minutes (point assumption: 120).

**Write scopes:** `pilot/document_providers.py`, `tests/test_docai_provider_contract.py`.

**Reuse basis:** CandidateProvider protocol and DisabledAIProvider are limited stubs; NativeJsonProvider only copies already structured claims.

**Acceptance:**

1. Implement a provider-neutral extraction request/result/error interface against the versioned contracts, with disabled-by-default construction and an offline mock adapter.
2. Carry endpoint profile ID, truthful extraction method, provider/model/API versions, schema version, run/config hash, raw-response reference/hash, structured errors, provenance, coverage and usage fields; unavailable provider metadata remains explicitly unknown.
3. Mock success, abstention, malformed output, incompatible schema, timeout, rate limit, partial parse and cancellation; candidates never import reviews or call financial actions.
4. A disabled profile fails explicitly before network or model loading. Mocks prove request/response behavior only, not compatibility with any NVIDIA, cloud or local service.
5. Keep potential NVIDIA and existing local-model clients behind adapters; selected actual service/model versions and authenticated reachability remain unverified until the later connection gate.

### BR-DOC-008 — Expose Doc AI intake, status, review and source trace

**Parents:** BR-ENG-127, BR-ENG-178, BR-ENG-182, BR-ENG-185, BR-ENG-294. **Owner:** L4_workflow; SW-00 coordinates and SW-13 reviews independently. **Status:** planned. **Layer:** application.

**Dependencies:** BR-DOC-004, BR-DOC-005, BR-DOC-006. **Resources:** agent_worker=1. **Effort:** 120–320 minutes (point assumption: 180).

**Write scopes:** `pilot/document_application.py`, `pilot/founder_service.py`, `tools/run_docai.py`, `tests/test_docai_application.py`.

**Acceptance:**

1. Provide a documented local/API vertical slice for upload or registered local-file intake, job status, source text, candidate list, review decisions and accepted export.
2. Use the engine for all invariants; application code must not duplicate parsing, identity, monetary conversions or evidence acceptance rules.
3. Show original source/version, exact evidence span, coverage/truncation, conflicts, missing fields and reviewer history so the operator can reconstruct every result.
4. Authorize review separately from extraction; conflicting or stale decisions require an explicit conflict response and refreshed version, with auditable compensating decisions.
5. Expose truthful provider state: disabled, configured, preflight-verified, test-evaluated or production-enabled; availability of a chat connector never changes backend connection state.

### BR-DOC-009 — Gate B: independently verify the offline provider contract

**Parents:** BR-ENG-295, BR-ENG-313, BR-ENG-323. **Owner:** SW-13_independent_review; SW-00 coordinates and SW-13 reviews independently. **Status:** planned. **Layer:** quality_gate.

**Dependencies:** BR-DOC-003, BR-DOC-007. **Resources:** agent_worker=1. **Effort:** 40–100 minutes (point assumption: 60).

**Write scopes:** `reports/validation/docai-provider-contract.json`, `docs/validation/docai-gate-b.md`.

**Acceptance:**

1. An independent reviewer checks the disabled and mock adapter against the frozen request/result/error schema, including provider metadata and rejected review injection.
2. Offline tests prove no model import, network client construction, credential access or provider invocation when disabled.
3. Record exact revision, fixture hashes, commands, failures and not-tested capabilities; no mock pass is described as live NVIDIA or local-model compatibility.
4. Allow this gate to run before the full application is complete; actual provider activation still depends on Gate A and the separate live preflight conditions.

### BR-DOC-010 — Gate A: verify the local native extraction and review path

**Parents:** BR-ENG-125, BR-ENG-127, BR-ENG-180, BR-ENG-182, BR-ENG-184, BR-ENG-324. **Owner:** SW-13_independent_review; SW-00 coordinates and SW-13 reviews independently. **Status:** planned. **Layer:** quality_gate.

**Dependencies:** BR-DOC-003, BR-DOC-004, BR-DOC-005, BR-DOC-006, BR-DOC-008. **Resources:** agent_worker=1. **Effort:** 60–180 minutes (point assumption: 100).

**Write scopes:** `reports/validation/docai-native-slice.json`, `docs/validation/docai-gate-a.md`.

**Acceptance:**

1. Demonstrate a synthetic native document from immutable intake through parsing, candidate review and accepted export with source/version/run provenance.
2. Exercise repeated intake, changed-key payload, stale review, conflicting value, revoked ACL, superseded document and truncated parse; fail visibly instead of silently accepting.
3. Demonstrate scanned input entering needs_ocr/manual review without an AI dependency; unsupported document classes are labeled and quarantined.
4. The complete local slice succeeds with providers disabled and no LLM/API credential/model download; no acquisition finance or household segment is needed.
5. SW-13 records independent evidence and SW-00 promotes the gate only after reviewing the reported revision and failures.

### BR-DOC-011 — Specify and dry-run a bounded source connector

**Parents:** BR-ENG-121, BR-ENG-123, BR-ENG-176, BR-ENG-177, BR-ENG-179, BR-ENG-295. **Owner:** L4_workflow; SW-00 coordinates and SW-13 reviews independently. **Status:** planned. **Layer:** application.

**Dependencies:** BR-DOC-002, BR-DOC-004, BR-DOC-006. **Resources:** agent_worker=1. **Effort:** 90–260 minutes (point assumption: 150).

**Write scopes:** `pilot/document_connectors.py`, `tests/test_docai_connectors.py`, `docs/guides/docai-source-connector.md`.

**Acceptance:**

1. Define a source adapter for explicitly allowed folders/labels and stable source IDs/revisions, with scoped permissions, cursor pagination, quotas and retries.
2. Use synthetic event feeds and an offline dry-run to prove durable registration before any move, replay recovery, stale cursors, access revocation and duplicate cross-source references.
3. Keep source-provider credentials separate from inference-provider credentials and from ChatGPT connector availability; backend connectivity requires its own verified configuration.
4. Default live watches, mailbox scans, file moves and external writes to disabled; list the concrete source authorization and configuration needed for a later narrow pilot.
5. Initial local-file extraction and the limited provider test do not wait for a Drive/Gmail connector or whole-mailbox integration.

### BR-DOC-012 — Implement one version-pinned disabled provider client and preflight

**Parents:** BR-ENG-282, BR-ENG-283, BR-ENG-286, BR-ENG-295. **Owner:** L2_engineering; SW-00 coordinates and SW-13 reviews independently. **Status:** planned. **Layer:** provider_connection.

**Dependencies:** BR-DOC-003, BR-DOC-007. **Resources:** agent_worker=1. **Effort:** 140–420 minutes (point assumption: 240).

**Write scopes:** `config/document-providers.json`, `requirements-docai-provider.lock`, `pilot/document_provider_client.py`, `pilot/document_providers.py`, `pilot/document_provider_preflight.py`, `tests/test_docai_selected_provider.py`, `tests/test_docai_provider_preflight.py`, `tests/fixtures/docai/provider`, `reports/validation/docai-selected-adapter.json`, `docs/guides/docai-provider-connection.md`.

**Reuse basis:** The earlier local Ollama client is an implementation reuse candidate; registration, version compatibility and end-to-end invocation remain unverified. A selected NVIDIA client is an alternative implementation, not an additional required backend.

**Acceptance:**

1. Implement exactly one actual provider client/adapter selected under BR-DOC-001: wrap the audited existing Ollama client or implement the chosen NVIDIA service client. Record the choice, owner, compatible API/model versions and pinned client dependencies; do not build every provider.
2. Register that concrete adapter in the provider registry with enabled=false. Map real service request, response, partial coverage, provenance, raw-response reference/hash, usage and error fields into the BR-DOC-007 contract; do not substitute the generic mock for the client implementation.
3. Run offline recorded-response and contract tests through the actual adapter with injected transport: success, abstention, malformed response, version drift, timeout, rate limit, cancellation and partial extraction. Label fixture origin/version, use existing permitted recordings or documented examples, and report missing compatibility evidence rather than inventing a recording; no new live capture occurs in this ticket.
4. Have SW-13 independently review the selected adapter revision, request serialization, response parsing, output/store schema compatibility, pinned versions and offline evidence. BR-DOC-009 verifies the generic seam; its mock pass does not close this selected-adapter requirement.
5. Prove registry loading, disabled construction, tests and offline preflight make no network calls, access no live credentials and download/start no models. Enabled code reaches a transport only through the later explicitly permitted Gate C path.
6. Document the selected endpoint, authentication method/principal reference, permissions, supported service/model/API versions and required data-retention/residency/use policy without storing secrets. Manifest completeness is distinct from authenticated reachability or provider quality.
7. Declare test-only data scope, request/page/byte/token limits, spend ceiling, concurrency, timeout, bounded retries, cancellation and teardown; missing or incompatible fields keep the profile disabled.
8. Validate provenance, structured errors, output schemas and expected provider usage/cost fields, preserving unavailable values as unknown. Keep ai_enabled=false with no automatic health probe or model download.
9. Hosted inference does not require this build environment to own CUDA. Self-hosted inference requires separately verified hardware, runtime and model/license readiness before live execution; neither is executed by this offline ticket.

### BR-DOC-013 — Gate C: run a bounded live extraction on synthetic/test files

**Parents:** BR-ENG-283, BR-ENG-286, BR-ENG-291, BR-ENG-295, BR-ENG-319. **Owner:** L2_engineering; SW-00 coordinates and SW-13 reviews independently. **Status:** blocked. **Layer:** provider_connection.

**Dependencies:** BR-DOC-003, BR-DOC-009, BR-DOC-010, BR-DOC-012, BR-DOC-017. **Resources:** agent_worker=1. **Effort:** 60–200 minutes (point assumption: 100).

**Write scopes:** `tools/evaluate_docai_provider.py`, `reports/validation/docai-live-evaluation.json`.

**Current hold:** No selected provider adapter has independently reviewed offline conformance, and no endpoint, authenticated backend connection, verified service/model versions or approved test-data policy is recorded. A concrete bounded test manifest, spend ceiling and permitted activation have not been verified; this planning change does not call or enable a provider.

**Acceptance:**

1. Require the independently reviewed BR-DOC-012 selected-client implementation and recorded-response/contract evidence at the exact version to be evaluated; Gate B alone supplies only generic seam evidence.
2. Before the first request, verify the selected endpoint, authentication, service/model/API versions, data policy, explicit test-data permission, cost ceiling and timeout on the exact manifest.
3. Run only the declared synthetic or specifically permitted test corpus; record authenticated reachability separately from extraction success and quality acceptance.
4. Capture source/run/provider/model versions, truthful extraction method, protected raw-response reference/hash, full/partial coverage, response/error status, usage/cost, latency, retries and candidate source spans; redact secrets and sensitive content in logs.
5. Stop on a policy/version/schema mismatch, budget breach or safety-critical output; rejected/malformed candidates remain unaccepted and no outbound transaction or document movement is triggered.
6. Disable the test connection after the bounded run; a successful test does not enable production, retrieval, runtime agents or access to other documents.

### BR-DOC-014 — Independently score the live candidate quality and costs

**Parents:** BR-ENG-185, BR-ENG-291, BR-ENG-317, BR-ENG-319, BR-ENG-320, BR-ENG-324. **Owner:** SW-13_independent_review; SW-00 coordinates and SW-13 reviews independently. **Status:** planned. **Layer:** quality_gate.

**Dependencies:** BR-DOC-003, BR-DOC-013. **Resources:** agent_worker=1. **Effort:** 80–220 minutes (point assumption: 120).

**Write scopes:** `reports/validation/docai-provider-verdict.json`, `docs/validation/docai-provider-evaluation.md`.

**Acceptance:**

1. Evaluate the frozen holdout against the predeclared baseline, field/type thresholds and source-span requirements; report denominators, confidence intervals and unsupported classes.
2. Publish a pass, fail or insufficient-evidence verdict per supported scope, preserving errors, abstentions, truncation and all critical false accepts.
3. Measure per-document/page latency, throughput, review effort and actual usage/cost; do not extrapolate pilot samples into a two-million-household capacity claim.
4. Assess calibration only for appropriate labeled scores and adequate samples; provider confidence never becomes evidence validity or an acquisition probability.
5. An independent verdict can reject or narrow the provider; passed mock tests, code presence and endpoint reachability are insufficient to claim useful extraction.

### BR-DOC-015 — Add document operations telemetry and cost visibility

**Parents:** BR-ENG-185, BR-ENG-320, BR-ENG-326, BR-ENG-328. **Owner:** L4_workflow; SW-00 coordinates and SW-13 reviews independently. **Status:** planned. **Layer:** application.

**Dependencies:** BR-DOC-006, BR-DOC-008. **Resources:** agent_worker=1. **Effort:** 90–260 minutes (point assumption: 150).

**Write scopes:** `pilot/document_observability.py`, `tests/test_docai_observability.py`, `docs/guides/docai-operations.md`.

**Acceptance:**

1. Expose queue age/depth, retries, dead letters, parse coverage, review backlog, accepted/rejected rates, supported class coverage and provider configuration state.
2. One trace reconstructs intake, version, extraction, review and export; tenant-scoped logs omit secrets and sensitive document content by default.
3. Report CPU/GPU/backend actually used, provider latency and measured usage/cost; unknown, unavailable and not-tested values must not appear as zeros or success.
4. Enforce the configured request/spend/time budgets before dispatch and test cancellation, exhausted quotas and partial provider failures with mocks.
5. Document alert thresholds, recovery ownership and operational bottlenecks without creating a second swarm dashboard or claiming production SLAs.

### BR-DOC-016 — Publish reviewed document outputs to downstream consumers

**Parents:** BR-ENG-127, BR-ENG-182, BR-ENG-183, BR-ENG-282, BR-ENG-294. **Owner:** L1_evidence; SW-00 coordinates and SW-13 reviews independently. **Status:** planned. **Layer:** consumer_interface.

**Dependencies:** BR-DOC-010. **Resources:** agent_worker=1. **Effort:** 60–180 minutes (point assumption: 100).

**Write scopes:** `pilot/document_exports.py`, `pilot/document_offer_layer.py`, `tests/test_docai_exports.py`, `docs/guides/docai-consumer-contract.md`.

**Acceptance:**

1. Export only authorized, reviewed, current fields through a versioned document-neutral contract with typed values, evidence references and explicit missing/conflict states.
2. Preserve retraction, expiry, supersession and ACL changes in consumer refresh; never treat a cached previously accepted field as permanently valid.
3. Keep document_offer_layer.py as one optional acquisition consumer that maps reviewed fields to existing finance rules; do not make it the Doc AI application layer.
4. Review tasks for consequential findings remain separate from external actions; no automated offers, messages, payment, legal status or transaction advancement occurs.
5. A simple nonfinancial consumer fixture demonstrates Doc AI usability without any underwriting or negotiation engine.

### BR-DOC-017 — Verify isolation, hostile inputs and recovery across the slice

**Parents:** BR-ENG-130, BR-ENG-184, BR-ENG-295, BR-ENG-323, BR-ENG-327. **Owner:** L3_quality; SW-00 coordinates and SW-13 reviews independently. **Status:** planned. **Layer:** quality_gate.

**Dependencies:** BR-DOC-003, BR-DOC-004, BR-DOC-006, BR-DOC-007, BR-DOC-008. **Resources:** agent_worker=1. **Effort:** 100–260 minutes (point assumption: 150).

**Write scopes:** `tests/test_docai_adversarial.py`, `reports/validation/docai-adversarial.json`.

**Acceptance:**

1. Inject cross-tenant access, revoked ACL, malicious file paths, hostile document instructions, mismatched identity and forbidden review/action fields; no unintended authority or external call is granted.
2. Exercise changed payload with reused idempotency key, concurrent writes, stale version/CAS updates, lost leases, partial parsing, dead letters and crash recovery.
3. Mock provider timeout, quota, cancellation, malformed metadata, schema drift, missing provenance and truncated responses; all failures remain traceable and recoverable.
4. Check canonical source identity and review projection across supersession, deletion/retention and conflicting claims; permission changes invalidate derived access.
5. Record meaningful failure evidence for the local vertical slice independently of optional connector, full twelve-parser or retrieval completion.

### BR-DOC-018 — Expand typed parsers through the twelve-class coverage matrix

**Parents:** BR-ENG-175, BR-ENG-180, BR-ENG-286. **Owner:** L2_engineering; SW-00 coordinates and SW-13 reviews independently. **Status:** planned. **Layer:** engine.

**Dependencies:** BR-DOC-002, BR-DOC-005. **Resources:** agent_worker=1. **Effort:** 160–480 minutes (point assumption: 240).

**Write scopes:** `pilot/document_parsers`, `tests/test_docai_parser_coverage.py`, `docs/validation/docai-parser-coverage.md`.

**Acceptance:**

1. Implement and review one bounded parser increment at a time against all twelve registered class contracts; track implemented/tested/unsupported field coverage explicitly.
2. Provide page/row evidence, unit/date/currency normalization, abstention and UNKNOWN quarantine; parser availability is separate from validated field coverage.
3. Keep OCR/model extraction behind the provider contract and activation gates; installing a parser must not download or start a model.
4. Use reviewed fixtures and adversarial partial/truncated documents per class; publish residual gaps and migration/version compatibility.
5. Initial local extraction and the first bounded live provider evaluation do not wait for all twelve classes.

### BR-DOC-019 — Later: add permission-aware retrieval and versioned embeddings

**Parents:** BR-ENG-181, BR-ENG-272, BR-ENG-286. **Owner:** L2_engineering; SW-00 coordinates and SW-13 reviews independently. **Status:** deferred. **Layer:** application.

**Dependencies:** BR-DOC-004, BR-DOC-018. **Resources:** agent_worker=1. **Effort:** 160–480 minutes (point assumption: 240).

**Write scopes:** `pilot/document_retrieval.py`, `tests/test_docai_retrieval.py`, `docs/guides/docai-retrieval.md`.

**Acceptance:**

1. Design a revision-specific chunk/embedding/index contract with embedding model/version, typed metadata filters and full source citations.
2. Enforce tenant/purpose authorization at ingestion and query and propagate source deletion, revocation, supersession and retention to derived indexes.
3. Evaluate retrieval quality, index memory, latency and cost against a baseline before selecting an embedding or vector backend.
4. Embedding-provider activation has its own endpoint/data/budget/quality checks; extraction-provider success does not authorize it.
5. Retrieval remains an optional later feature and is never a dependency of first-page extraction, manual review or the initial provider evaluation.

### BR-DOC-020 — Run independent R diagnostics and calibration when available

**Parents:** BR-ENG-291, BR-ENG-317, BR-ENG-319, BR-ENG-328. **Owner:** L3_quality; SW-00 coordinates and SW-13 reviews independently. **Status:** blocked. **Layer:** evaluation.

**Dependencies:** BR-DOC-003, BR-DOC-010. **Resources:** agent_worker=1, r_runtime=1. **Effort:** 100–280 minutes (point assumption: 150).

**Write scopes:** `research/docai`, `reports/validation/docai-r-validation.json`.

**Current hold:** No executable R runtime is verified in the present resource profile.

**Acceptance:**

1. Pin an executable R environment with renv and preserve typed document/run/provider/version identifiers and numeric missingness in the Python-to-R exchange.
2. Independently reproduce held-out accuracy/coverage/error interval metrics and reliability/calibration only when appropriate labeled provider scores exist.
3. Avoid leakage between versions of the same source across splits and report small/imbalanced samples and uncertainty instead of inventing calibrated probabilities.
4. Record R version, package lock, exact data hashes and executed commands; an export artifact or unexecuted script is not a completed R validation.
5. R execution is an optional independent measurement track; lack of R does not block the native product or a bounded provider experiment.

### BR-DOC-021 — Measure useful CUDA batches against the CPU reference

**Parents:** BR-ENG-286, BR-ENG-288, BR-ENG-317, BR-ENG-320. **Owner:** L2_engineering; SW-00 coordinates and SW-13 reviews independently. **Status:** blocked. **Layer:** compute.

**Dependencies:** BR-DOC-005, BR-DOC-007, BR-DOC-010. **Resources:** agent_worker=1, cuda_device=1. **Effort:** 120–360 minutes (point assumption: 180).

**Write scopes:** `tools/benchmark_docai_cuda.py`, `tests/test_docai_cuda_contract.py`, `reports/benchmarks/docai-cuda.json`.

**Current hold:** No CUDA device is verified in the present resource profile.

**Acceptance:**

1. Identify sufficiently parallel preprocessing, tensor inference or scoring workloads; retain serial metadata/ACL/provenance transactions on CPU with the reason recorded.
2. Benchmark bounded batch sizes, device residence, pinned/reused buffers where appropriate, memory limits and host/device transfer overhead with a readable CPU reference.
3. Report actual device/runtime/provider/model versions, precision, parity/tolerances, cold/warm latency, throughput, peak memory and end-to-end transfer/synchronization time.
4. An explicit CUDA request fails visibly when unavailable; never report a speedup from mocks, utilization percentage alone, CPU fallbacks or remote hardware assumptions.
5. Optimize measured useful throughput within quality/cost limits. Hosted provider evaluation remains possible without local CUDA; self-hosted GPU execution is a distinct resource gate.

### BR-DOC-022 — Review a scoped production candidate and rollback evidence

**Parents:** BR-ENG-283, BR-ENG-295, BR-ENG-323, BR-ENG-324, BR-ENG-327. **Owner:** SW-00_integrator; SW-00 coordinates and SW-13 reviews independently. **Status:** planned. **Layer:** quality_gate.

**Dependencies:** BR-DOC-014, BR-DOC-015, BR-DOC-017. **Resources:** integrator=1. **Effort:** 60–200 minutes (point assumption: 100).

**Write scopes:** `docs/operations/docai-release-gate.md`, `reports/validation/docai-release-verdict.json`.

**Acceptance:**

1. Assemble an immutable release manifest of code/schema/provider versions, supported classes, permitted data, ACLs, budgets, operational owners and independent SW-13 verdicts.
2. Verify migrations, backup/restore, revocation, rollback/disable, alert routing and failure containment against the exact release candidate.
3. A failed or insufficient-evidence quality/security verdict blocks release or narrows supported scope; twelve-class expansion, R and GPU claims require their own evidence.
4. Name the actual deployment target and accepted production scope before promotion; this review does not activate a provider or authorize external document access.
5. Do not gate Doc AI on acquisition finance or commercial transaction readiness; downstream consumers have independent release responsibilities.

### BR-DOC-023 — Reconcile the unavailable original document-platform specification

**Parents:** BR-ENG-186, BR-ENG-313, BR-ENG-314. **Owner:** L1_evidence; SW-00 coordinates and SW-13 reviews independently. **Status:** blocked. **Layer:** requirements.

**Dependencies:** none. **Resources:** agent_worker=1. **Effort:** 60–200 minutes (point assumption: 100).

**Write scopes:** `docs/plans/docai-source-reconciliation.md`.

**Current hold:** The original referenced document-platform PDF required by BR-ENG-186 has not been inspected; other unrelated PDFs do not satisfy that provenance requirement.

**Acceptance:**

1. When the original referenced document-platform PDF is available, record its hash/version and compare the exact task, schema and review contracts to existing master requirements.
2. List supported, contradictory, missing and already satisfied requirements with precise source provenance; do not invent the unavailable twenty microtasks or SQL.
3. Dedupe any needed changes against existing BR-ENG parents and this child plan; retain provenance gaps as explicit evidence states.
4. Current verified contracts and the latest user instruction are sufficient to begin the local Doc AI slice; this historical source gap is not a blanket prerequisite.

### BR-DOC-024 — Gate D: conduct a separately enabled monitored production pilot

**Parents:** BR-ENG-130, BR-ENG-185, BR-ENG-283, BR-ENG-320, BR-ENG-327, BR-ENG-328. **Owner:** L4_workflow; SW-00 coordinates and SW-13 reviews independently. **Status:** deferred. **Layer:** deployment.

**Dependencies:** BR-DOC-022. **Resources:** agent_worker=1. **Effort:** 120–360 minutes (point assumption: 180).

**Write scopes:** `docs/operations/docai-pilot-runbook.md`, `reports/operations/docai-pilot.json`.

**Current hold:** No production deployment target, approved release manifest or monitored rollout scope is verified.

**Acceptance:**

1. Enable only the approved release, deployment target, document classes, users/data sources and provider manifest; verify effective authorization and budgets before live production traffic.
2. Start at a small bounded canary with human review, traceable usage/cost, error/coverage thresholds, alerts, stop controls and a demonstrated rollback.
3. Track actual extraction quality, review workload, latency, failure recovery and cost using production denominators; expand only with reviewed evidence.
4. Report connection state, supported scope and deployment evidence accurately; no automatic negotiation, messages, property acquisition or runtime agent swarm is introduced.
5. Production activation is a distinct later step. This plan and any synthetic test do not enable production or establish two-million-household capacity.
