# Independent technical review

**Decision.** The local synthetic pilot earns **B** for repeatability. Its strongest claim is that an engineer can reconstruct which underwriting packet the founder approved, which settlement records followed it and what survived a database restore. The open engineering question is what should happen to an already posted obligation after a second, valid approval. The current pilot stops on that path. [Approval model](modeling-black-river.md) · [Acceptance source](../../pilot/acceptance.py)

**Boundary.** This review covers the committed source at `be51964c2f6c72eac94ee1c1891fc1adc9121adb` on Windows, the linked public architecture documents, and Draft PR #9 targeting `main`. Its units of evidence are source contracts, synthetic tests and observed runtime outputs. The grade applies to the local acquisition pilot. Production identity, live property sources and payments, live citation retrieval, physical-device acceptance and external agent orchestration require their own evidence. [Reviewed revision](https://github.com/ajoiventures/BL_ACQ/tree/be51964c2f6c72eac94ee1c1891fc1adc9121adb) · [PR #9](https://github.com/ajoiventures/BL_ACQ/pull/9)

## What you have created

Black River has an executable acquisition and operations pilot. It turns parcel and deal evidence into a reproducible price decision, records distinct review and approval actions, then verifies the downstream accounting records and restored database. The decision model has a stronger proof trail than a spreadsheet calculation alone. For example, the Orchard ceiling is the minimum of three independently testable limits. A reviewer can explain the binding limit and recover the precise packet that supported it. [Orchard fixture](../../pilot/scenario.py) · [Domain tests](../../tests/test_pilot_domain.py)

You have also created engineering tools that make the system learnable. The VS Code workspace and file map show where to begin in code. The portable verification runner exercises source checks, failure cases, browser behavior and recovery. The CUDA tool separates analytical exploration from approval authority. Alongside the reviewed revision, this batch adds a project-scoped architecture agent and a rebuilt-from-source learning library for reviewed lessons. [Code map](../code-map.md) · [Verification runner](../../tools/check_pilot.py) · [Swarm learning](swarm-learning.md)

## Rubric and results

**A** requires independent repetition across the representative operating environments specified for that claim, including failure and recovery. **B** requires an executable end-to-end local demonstration and checked negative paths. **C** means a component or contract works but a material handoff still lacks proof. **D** means the proposal has specifications or examples and awaits integrated verification. Grades follow the operating boundary of each row. The overall decision reflects the pilot’s critical path rather than an arithmetic average.

| Area | Grade | Evidence and limit |
| --- | --- | --- |
| Architecture and traceability | B | The CTO map identifies the connected review component, SQLite state and prospective providers. The worked sequence matches the service’s order of evidence validation, retry recognition and transaction commit. The broader system-of-systems model still needs provider-owned interface, identity and failure contracts. [CTO map](../CTO_ARCHITECTURE.md) · [System views](system-of-systems.md) |
| Domain model and decision authority | B | Qualification checks scope, dates and source references. Underwriting uses integer cents and the minimum of base, downside and available funding. Independent reviewer and founder actions bind to the persisted packet digest. Stale revisions, equal retries, competing submissions and revoked funding all have executable coverage. Evidence authenticity comes from synthetic fixtures in this run. [Underwriting](../../pilot/underwriting.py) · [Connected tests](../../tests/test_founder_service.py) |
| Storage and queue recovery | B | Scoped immutable records, transactional migrations, task leases and request receipts survive replay and an exercised SQLite restore. Concurrent claims and transactional rollback passed. The restore exercises one machine. Multi-host contention, checkpoint retention and recovery time objectives have yet to be measured. [Storage tests](../../tests/test_pilot_storage.py) · [Restore checks](../../pilot/acceptance.py) |
| Ledger and downstream integration | C | Distinct service, invoice and receipt evidence reconciled four synthetic entities to 205,000 cents cash and 80,000 cents receivable. The follow-up reapproval case below could not complete settlement. [Ledger](../../pilot/ledger.py) · [Settlement sequence](../../pilot/acceptance.py) |
| Founder UI and device coverage | B | A real Chromium and WebKit replay verified five local workflows and a connected browser workflow with independent sessions, retry after interrupted acknowledgement and a scoped decision. Phone viewport and touch profiles were emulated on Windows. Physical Safari and Chrome, screen reader and OS file transfer have pending evidence cells. [Replay](../../tools/replay_founder.py) · [Handset matrix](../physical-device-acceptance.md) |
| Analytical acceleration | B | The optional CUDA sensitivity screen reproduced every scalar result over 250,000 cases. Timing from this review was 0.403 seconds on the first call and 0.0083 seconds on the second. This evidence applies to this bounded synthetic grid and device. Benchmark realistic workload sizes and an optimized CPU comparator before a platform performance claim. [CUDA decision](cuda-screening.md) |
| External delivery and release assurance | C | The connector authorizer defines a scoped, independently approved request. Production provider delivery receipts and replay after uncertain external delivery still need a real integration test. The PR records a hosted CI billing block. Local lint and selected type checks have narrower scope than cross-platform CI and live connector acceptance. [Connector contract](../../pilot/connectors.py) · [Check suite](../../tools/check_pilot.py) |
| Broader engine portfolio | D | The engine inventory assigns inputs, outputs and backlog references to GIS, design, ML, communications and portfolio work. The independently executed evidence here covers the acquisition, review, queue, settlement and sensitivity paths. [Engine inventory](intelligence-engines.md) |

## Review of the linked architecture documents

| Document | Grade | What it proves and where to improve |
| --- | --- | --- |
| [CTO Architecture](../CTO_ARCHITECTURE.md) | B | Teaches the full operating story in terms a buyer and engineer can share. Add named external interface owners and acceptance measurements when those integrations are assigned. |
| [Machine of Machines](system-of-systems.md) | B | Distinguishes product terminology from architecture and deployment terminology. A target deployment view still needs the identity, network and data-retention decisions for external integrations. |
| [How to model Black River](modeling-black-river.md) | B | The approval example and its failure traces correspond to code and tests. Use a repeatable requirement-to-test link and record the selected revision for each subsequent model. |
| [Intelligence Engine Inventory](intelligence-engines.md) | B as an inventory | States what the engine does and points to evidence or work in the master backlog. A documented engine earns an implementation grade only after its integration and acceptance cases pass. |
| [CUDA decision](cuda-screening.md) | B | Records the portable comparison and verified synthetic parity. State the GPU, workload and timing conditions when quoting results. |
| [Physical acceptance](../physical-device-acceptance.md) | B as a procedure | Names the paths, devices and evidence required. Physical completion stays open while native results are unavailable. |

## Follow a packet through success and failure

The founder’s question is whether two people reviewed the same packet. The local HTTP boundary resolves the authenticated actor and commercial scope. A stale evidence digest returns a conflict before the server reuses an earlier receipt. An eligible request enters a transaction that records a decision with an evidence foreign key and an idempotency receipt. The settlement runner finds the approved digest, links source records and rebuilds the balances after restoration. The replayed final request leaves the restored history unchanged. [Service](../../pilot/founder_service.py) · [Storage](../../pilot/storage.py) · [Recovery test](../../tests/test_acceptance.py)

**Observed boundary at the reviewed revision.** A second still-eligible packet can be independently reviewed and approved after the original settlement. The next settlement then fails with `ValueError: Conflicting replay for evidence_id`. Service and invoice keys use deal plus entity, while the stored payload includes the approval decision and packet digest. This protects the prior accounting evidence against being overwritten. Operations needs a rule for recognizing an unchanged obligation, a new obligation and an authorized adjustment. [Service-event identity and payload](../../pilot/acceptance.py)

To reproduce with fictional records, run `acceptance(temp_directory)`. Increase the funding cap on the fixture by 10,000 cents while leaving the binding base ceiling unchanged, then invoke `prepare` against the same database with the revised fixture. Use the new digest to send a reviewer decision followed by founder approval. The packet reaches `bid_ready_simulation` and there are four recorded decisions across revisions. Calling `settle` exposes the identity conflict. The normal fresh-database acceptance exercises the first approved revision.

## Verification and next acceptance

| Check rerun on Windows | Result |
| --- | --- |
| Python unit suites in the pilot, reporting demo and guide checker | 23 + 9 + 1 tests passed |
| `python -m pilot.acceptance` | Two review events, two settled invoices, reconciliation and restore passed |
| `python tools/replay_founder.py --engine both` | Chromium 157.0.4341.60 with Pixel 7 emulation and WebKit 27.2 with iPhone 13 emulation passed |
| `python -m pilot.cuda_screen --backend cuda --compare --repeat 2` | Full CPU parity. Result SHA-256 `d11c109eab73e405f041bbdc4e1c93c39098176e6809100e8c06d078de0c2077` |

1. **Engineering and finance** should decide which business event identifies an obligation across underwriting revisions. The next regression must prove that an unchanged service already paid is acknowledged exactly once, a genuine adjustment has its own authorization and source, and both posting histories survive restore. [Finance ticket #7](https://github.com/ajoiventures/BL_ACQ/issues/7) · [Acceptance ticket #8](https://github.com/ajoiventures/BL_ACQ/issues/8)
2. **Product development and the independent reviewer** should gather native iPhone Safari and Android Chrome results for the four named journeys, including accessible validation messages and cross-scope and stale file handoffs. [Physical acceptance #12](https://github.com/ajoiventures/BL_ACQ/issues/12)
3. **Release engineering** should reproduce the pinned suite in hosted CI for the exact proposed revision. For future provider integration, test delivery acknowledgement, uncertain delivery, retry and reconciliation against a provider-approved test environment. [Delivery index](https://github.com/ajoiventures/BL_ACQ/issues/10)
