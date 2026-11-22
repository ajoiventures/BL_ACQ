# Doc AI: audited current state and reuse boundary

Reviewed: 2026-11-22. This is a source audit and a planning correction. It does not certify a running installation.

## What exists, and whether it is connected

The inspected work contains useful document intake, evidence, and review components. It does **not establish a connected NVIDIA Doc AI service or a complete general document application**. The recent `BL_ACQ` work implements an evidence foundation and a financial consumer of reviewed evidence. The existing Founder Command work also contains a real Ollama text client and an MCP wrapper; their running model, authenticated registration, and end-to-end connection remain unverified in this audit.

The builder swarm is a separate development capability. Its procedures, scheduling, and review help build these components. Installing builder skills or creating task profiles does not connect a document model, create product agents, or enable document processing in a deployed application.

Three source snapshots were inspected:

| Snapshot label | Relevant source paths, relative to that workspace | Audit qualification |
| --- | --- | --- |
| `BL_ACQ` | `pilot/document_evidence.py`, `pilot/document_offer_layer.py`, `pilot/founder_service.py`, `tools/run_document_offer.py`, `tools/schedule_builder_work.py`, `config/builder-skills.json`, `config/build-ticket-plan.json` | Implemented source was inspected. The document and provider source files were unchanged at the start of this correction. Planning and documentation changes during this correction are separate from runtime implementation. |
| Existing Founder Command workspace | `filing/`, `backend/`, `scripts/local_model.py`, `scripts/model_mcp.py`, `site_academy/runner.py`, `docs/session-tickets.json` | Recovered local source snapshot; Git revision metadata was not available in that copy. Conclusions apply to inspected source, not to a remotely running or another local installation. |
| Modular Founder Command workspace | `apps/api/black_river_api/main.py`, `apps/api/black_river_api/services.py`, `apps/api/black_river_api/workflows.py` | Recovered local source snapshot; Git revision metadata was not available in that copy. This is a reuse candidate, not evidence that all workspaces are integrated. |

Canonical organization references are `BR-SWARM-001`, `BR-SWARM-SKILLS-001`, and `BR-ENG-MASTER-001`. Their identities and applicable skill metadata support the crosswalk. They are specifications, not runtime evidence. This document does not reproduce private source bodies or private storage locators and does not certify completion of the engineering master.

## Status vocabulary

Use these statuses separately in tickets and release manifests:

| Status | Required meaning |
| --- | --- |
| Specified | An interface, skill, or acceptance condition is written down. |
| Implemented | Source code for the stated behavior exists in an identified snapshot. |
| Disabled | A code path explicitly refuses the operation, or an activation setting keeps it unavailable. |
| Tested | A named test or evaluation actually ran against an identified version and produced retained results. Test source alone is insufficient. |
| Connected | A successful invocation through the intended endpoint and identity boundary is evidenced. A URL, model name, environment-variable reference, or wrapper file is insufficient. |
| Deployed | The identified version is running in the intended environment with operating ownership and deployment evidence. |
| Unverified | The audit did not establish the relevant configuration, runtime, connection, or deployment fact. |

No model, provider, or connector was invoked for this audit. Credential values were not inspected. Existing test definitions and prior descriptions were reviewed where relevant; this audit did not rerun them and creates no new model-quality or deployment certification.

## Component inventory

| Component | Evidence and implemented behavior | Present limit |
| --- | --- | --- |
| Native filing engine and local application entry point | Existing Founder Command `filing/inbox.py`: `extract` and `file_document(path, root, destination=None)` parse supported native text, choose a configured destination, archive original bytes, and issue SQLite receipts. | One-pass file/directory intake. No automatic chat connector, background watcher, OCR, or general extraction job service is established. |
| Mail and renewal review workflow | Existing Founder Command `backend/main.py`: `RenewalIntake` and `classify_renewal`; `POST /api/records/{rid}/renewal` accepts user-supplied text and a source-contained deadline quote, checks version/state, and records audit evidence. | User-reviewed text workflow. The route does not read a PDF or call a model. Its text evidence is labeled `SIMULATION`. |
| Local text model client | Existing Founder Command `scripts/local_model.py`: `extract`, `request`, and `grade` implement an Ollama chat request, a structured result, and four synthetic smoke cases. | Actual installed model, successful invocation, field accuracy, GPU execution, and current runtime are unverified. This is text extraction/classification, not an implemented NVIDIA document OCR deployment. |
| Local MCP model wrapper | Existing Founder Command `scripts/model_mcp.py`: `classify_mail` calls the local model client and labels the proposal `UNVERIFIED`. | Source binds to loopback and reads a configured model tag. Authenticated registration and a working ChatGPT-to-local connection are not established. Loopback binding is not authentication. |
| Deterministic evidence foundation | [`pilot/document_evidence.py`](../../pilot/document_evidence.py): `EvidenceStore` archives supplied bytes, validates typed claims, appends review decisions, and projects accepted inputs with provenance. | Scoped to the present document/deal contract. It is not a generic OCR, layout, or document orchestration engine. Caller identity must come from the application. |
| AI candidate seam | The same module defines `CandidateProvider`, `NativeJsonProvider`, and `DisabledAIProvider`. | AI operations are explicitly disabled. The present schema and dispatch require additional implementation before a provider can be connected truthfully. |
| Financial application consumer | [`pilot/document_offer_layer.py`](../../pilot/document_offer_layer.py): `evaluate_with_evidence` binds reviewed financial inputs into offer evaluation; `export_r_review` exports a research/review exchange. | A downstream consumer of document evidence. It is not the general Doc AI application layer or proof that an R runtime ran. |
| Existing subject-bound evidence API | Modular Founder Command `services.py`: `create_evidence`; `main.py`: `/api/v1/evidence` and associated object/work-item routes. | Existing operator, object, work-item, domain, and timestamp checks are reusable. No model extraction integration is established. |
| General Doc AI service and operator workflow | Filing, review, and evidence fragments exist across the inspected snapshots. | A unified binary upload, job/status, document preview, candidate review, provider management, and accepted-evidence delivery flow is not established by these fragments. |
| NVIDIA document service | No working service adapter, authenticated invocation, or deployed endpoint was evidenced in the inspected document interfaces. | Connection and deployment are unverified. CUDA compute dependencies elsewhere in the project do not establish document AI capability. |

The `BL_ACQ` [`pilot/founder_service.py`](../../pilot/founder_service.py) routes cover sessions, workspaces, valuation, and corporate operations. They do not expose document upload, extraction jobs, provider execution, or document review routes. The example in [`tools/run_document_offer.py`](../../tools/run_document_offer.py) consumes pretyped synthetic JSON claims; it does not demonstrate extraction from the source document.

## Preserve and extend the existing filing interface

The existing Founder Command `AGENTS.md` and `filing/README.md` explicitly direct future work to extend the filing module before introducing another intake service. Preserve `file_document(path, root, destination=None)`, stored originals, route behavior, permissions, receipts, and compatible callers. New chat, upload, or folder channels should be adapters around that boundary, with additive storage changes.

The current native extraction limits must be visible to the application:

| Input | Current extraction in `filing/inbox.py` | Consequence for Doc AI |
| --- | --- | --- |
| TXT, Markdown, CSV | First 150,000 bytes, decoded as UTF-8 with replacement for invalid sequences. | Content beyond the limit is not classified. Replacement decoding can alter source text. Record completeness and encoding warnings. |
| DOCX | Text from `word/document.xml`; returns empty text when that XML member exceeds 2,000,000 uncompressed bytes. | The current result does not distinguish an oversized document from missing readable text. It is not a layout-preserving document model. |
| PDF | Native text from the first five pages, limited to 20,000 characters per page. | Later pages and longer page content are omitted. No scan OCR is performed. |
| Unsupported format or extraction exception | Empty extraction; normally routes to `Review` through a generic reason. | Preserve specific error/completeness information so operators can distinguish unsupported, unreadable, truncated, and ambiguous inputs. |

Original bytes are copied into a temporary snapshot before classification and hashing. The destination archive uses the snapshot hash, and an existing destination is checked for matching bytes. An explicit configured destination takes precedence; otherwise exactly one keyword category must match. Zero or multiple matches go to `Review`. These are useful foundations to reuse, while explicit parsing outcomes and source locations are additional work.

Filing a document does not establish that a fact in it is true, that a payment occurred, or that a contract has legal effect. Reviewed claims and downstream actions remain separate decisions.

## Why the current provider seam is not plug-ready

`CandidateProvider` is a useful conceptual boundary, but four concrete constraints prevent simply adding a model URL:

1. `EvidenceStore.ingest_bundle` directly constructs `NativeJsonProvider`; it does not dispatch to an injected or configured provider. That native provider validates an already supplied claims array. It does not extract claims from document bytes.
2. `EvidenceStore.add_claim` only allows `method` values `manual` and `native_json`. It rejects unknown fields. Provider, model, version, execution identifier, confidence, and raw-response references are not part of the accepted claim schema.
3. Bundle documents require `content_utf8`. Although `register_document` can archive supplied binary bytes, the bundle envelope is not an arbitrary PDF/image intake contract.
4. `DisabledAIProvider.candidate_claims` always raises. This is an intentional boundary, not a configured service waiting for a key.

An additive, versioned candidate/run contract must preserve method and provenance honestly. Model output must not be relabeled `native_json` to bypass the disabled boundary. The revised contract needs source-artifact identity, extraction coverage, page/span or region references, provider/model versions where applicable, execution metadata, unsupported/error outcomes, and candidate status. Model confidence must remain separate from reviewer acceptance and measured field accuracy.

The present evidence store also requires `deal_id` and operates within the current `commercial`, `family`, and `civic` scopes. General mail and household documents need an explicit subject/context mapping rather than an artificial property deal. Existing financial callers should remain compatible through a versioned adapter or migration. The modular Founder Command subject/work-item/domain checks are an existing design to evaluate before creating another identity system.

Named actors in `EvidenceStore` are recorded attestations supplied by the caller. Application authentication and authorization must establish who can propose, review, and accept. A stored name is not proof of independent review. Similarly, the current business-date projection should not be described as a complete reconstruction of what the system knew at every historical instant without a separate knowledge-time design.

## Engine, application layer, and future AI activation

The Doc AI engine should combine preserved originals, native parsing, optional model execution, candidate normalization, provenance, review state, and accepted-evidence projection. The application layer should expose intake, document/job status, previews, source-linked review, corrections, and delivery to authorized consumers. Acquisition offers are one consumer; mail, filing, and other document workflows are also consumers.

AI compatibility belongs in the design now. Provider execution can follow a narrow document milestone; it need not wait for all acquisition economics, R research, a two-million-household rollout, or the whole engineering master.

| Gate | Concrete completion evidence | What it permits |
| --- | --- | --- |
| Contract and preservation | Original bytes/receipts remain recoverable; versioned artifacts, candidates, runs, review authority, and error/completeness contracts are defined. | Implement provider-neutral interfaces, disabled adapters, and offline fixtures in parallel with the native workflow. |
| Native end-to-end workflow | One authorized representative document enters through the existing filing boundary, retains its source, yields visible parsing outcomes, and reaches review and an accepted-evidence consumer. | Validate the application path independently of a model. |
| Bounded provider connection | Correct endpoint/model/configuration, the intended authenticated access boundary, allowed document scope, time/cost limits, and a successful traceable smoke invocation are recorded. Candidate-only output and failure recovery are demonstrated. | Describe that particular provider and environment as connected for the bounded test. It does not establish production accuracy. |
| Evaluated document pilot | Representative held-out documents cover the chosen formats and critical fields; source citations, missing values, invalid output, false acceptance, latency, and failure cases meet stated acceptance conditions. Review and rollback are exercised. | Enable the selected provider for the measured pilot scope. |
| Operating release | Identified deployment, ownership, observability, storage/retention behavior, recovery, and versioned evaluation evidence are present. | Claim deployment for that environment and scope. Expansion requires evidence for the additional workload. |

A hosted provider test does not require a locally installed CUDA device. Self-hosted GPU inference requires a verified compatible runtime and measured resource use. Batch processing, memory limits, and CUDA optimization should be based on the document workload and measured bottlenecks; CUDA availability alone is not a document accuracy or connection test. Product agents that autonomously select or execute actions remain a separate later capability. They are not enabled by using agents to build this software.

## Reuse the existing swarm library and execution authority

[`config/swarm-library-extension.json`](../../config/swarm-library-extension.json) maps all 14 builder skills into a `software_builders` collection under the existing `BR-SWARM-SKILLS-001` capabilities and L1–L4/SW roster. It maps each of the four existing builder configurations as a temporary task profile, creates no new leaders, and does not claim a live library import. L4/SW-09 retains document operating accountability; L2 owns engineering integration; L3/SW-05 and SW-04 own financial and acquisition/probability responsibilities; SW-00 coordinates and SW-13 independently reviews.

Documentation registration in `BR-SWARM-001` and `BR-SWARM-SKILLS-001`, updates to the 14 installed personal procedures, and integration into the `BL_ACQ` learning index are separate publication channels. Their delivery evidence belongs to each channel. They do not by themselves import an organizational application database or establish a live worker/provider connection.

The existing Founder Command `backend/core/tickets.py` and `backend/ticket_routes.py` already implement an authoritative project-ticket engine, including `PROJECT_INTERNAL` work, version checks, evidence/source requirements, and audit events. `FOUNDER` submits work for review. `SW-13` may accept or return a submitted ticket; closure requires an independent finding/source and closed dependencies. Preserve these transitions and their history.

The `BL_ACQ` [`tools/schedule_builder_work.py`](../../tools/schedule_builder_work.py) is an offline advisory list scheduler. It can help project ready work and resource demand. It cannot launch workers, close canonical tickets, or grant approval. Its `completed` fields must never be imported as canonical `closed` status without the existing review transition.

Existing Founder Command `site_academy/runner.py` already implements `load_skills`, `start`, `act`, and `status`, with site, urban, and planning registries. It preserves studies, tasks, and append-only events, separates founder submission from audit acceptance, and requires a distinct review source and artifact. Extend its registry/curriculum boundary for builder qualification rather than creating another Academy database. A builder curriculum was not established by the inspected source.

### Planned library integration work

These six items are local planning records in the crosswalk. They are not external tickets, deployments, or completed executions. Each has acceptance criteria, dependencies, ownership, and reuse targets in the JSON.

Each also has narrow proposed write scopes, a single worker or integrator execution lane, zero required CUDA/R capacity, and low/point/high active-effort estimates. Those estimates are planning assumptions, excluding external provisioning and review queues. They are not measured throughput or delivery promises. Shared-file implementation requires an exclusive scope lease, and independent review remains a separate responsibility. The ticket bridge must reject an idempotency-key replay with a different actor or changed evidence and preserve the documented response type on an exact authorized replay before adopting existing business-engine patterns.

| Plan item | Existing parent | Existing capabilities | Purpose |
| --- | --- | --- | --- |
| `SWLIB-01` | `BR-T012` | `SK-28`, `SK-29` | Register the builder collection additively, preserving the existing skill and agent identities. |
| `SWLIB-02` | `BR-T012` | `SK-28`, `SK-29` | Bridge the advisory plan to existing ticket IDs, versions, transitions, and evidence history. |
| `SWLIB-03` | `BR-T012` | `SK-28`, `SK-29` | Add bounded resource projections to the existing coordinator, separating estimates from observed execution. |
| `SWLIB-04` | `BR-T012` | `SK-28` | Qualify builder procedures through the existing Academy runner and independent review. |
| `SWLIB-05` | `BR-T016` | `SK-28`, `SK-29` | Add authenticated private dispatch through the existing connector boundary with stable job identity and bounded scope. |
| `SWLIB-06` | `BR-T043` | `SK-28`, `SK-29` | Preserve corrections and handoffs; route document work to `BR-T004`/`BR-T019` and library work to `BR-T012`. |

`BR-T012` is recorded as `delivered_local` in the inspected existing manifest. Adding an extension does not erase that accomplishment or reopen it by implication. `BR-T016` remains the existing connection workstream. A connector is needed where a new invocation channel is needed, not as a blanket prerequisite for local Doc AI design or testing.

### Preserve the earlier 84-item plan as history

The crosswalk covers all 84 stable ticket IDs and capability IDs from `config/build-ticket-plan.json`, preserving their original statuses. It reclassifies scope without certifying that old implementation claims satisfy the corrected Doc AI acceptance criteria:

| Corrected category | Existing work items | Treatment |
| --- | ---: | --- |
| Doc AI foundations | 15 | Reuse relevant evidence and document components; add the missing general document contracts and workflow. |
| Shared builder tooling | 17 | Place in the existing software-builder collection and coordinator interfaces. |
| Downstream acquisition | 25 | Keep as consumers and domain work, separate from Doc AI readiness. |
| General platform | 22 | Reuse infrastructure where justified; do not make every platform feature a provider-connection prerequisite. |
| Future AI | 5 | Preserve deferred execution status. Bring interface/offline design forward where useful; gate actual provider and product-agent execution separately. |

## SWOT and concrete risks

| Area | Finding | Resulting planning decision |
| --- | --- | --- |
| Strength | Original preservation, filing receipts, domain-aware evidence, review paths, ticket transitions, and an Academy runner already exist. | Integrate and extend these boundaries before introducing replacement services or catalogs. |
| Weakness | Relevant code is distributed across snapshots; a shared deployment and storage migration are not established. | Select the integration target explicitly and record source/version provenance before implementation. |
| Weakness | Native parsing can silently truncate or collapse errors; the new claim schema excludes truthful model provenance. | Make completeness/error states and the additive provider contract early Doc AI work. |
| Opportunity | A narrow document-to-review workflow can demonstrate value before completing unrelated finance features. | Use the native workflow and bounded provider pilot as the next product milestones. |
| Opportunity | The existing ticket and Academy engines can absorb builder procedures and resource projections. | Implement bridges and qualification, preserving established IDs and review authority. |
| Risk | Specifications, installed skills, client files, or a scheduler can be mistaken for a live service or completed swarm execution. | Report specified, implemented, tested, connected, and deployed evidence separately. |
| Risk | A model proposal or named reviewer can be mistaken for independently accepted truth. | Enforce actual review identity, source linkage, and measured field quality in the application boundary. |
| Risk | New collections or generic document contexts can duplicate authority or cross private domain boundaries. | Preserve canonical skill/ticket ownership and authorize document/subject mappings explicitly. |

The next review should establish one integrated document workflow and its target runtime, then demonstrate a bounded provider connection when its contracts and controls are ready. This audit establishes the reusable source and remaining gaps; it does not establish a live provider, canonical library import, ticket closure, or production deployment.
