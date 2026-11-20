# Black River product portfolio

**Black River** is the product family. **Machine of Machines** is the architecture that lets the products work together. Each product card names the customer, what they bring, what they receive, and how to verify the result. These offers use the current repository and a synthetic pilot. Commercial packaging, pricing and customer validation are open.

See the [capability and layer coverage map](architecture/capability-coverage.md) for the functions behind the offers, including engine dependencies and delivery evidence.

## Agents and services

### 1. Black River System Architect

**Buyer** A founder, CTO, or technical lead who needs an architecture the team can explain and test.

**Product form** A project-scoped Codex agent and reusable modeling skill. Give it a question, a repository revision, and the requirements or design constraints. Receive a system boundary, a focused architecture view, and a trace from the requirement to code and verification.

**Try it** Open the checkout in Codex and ask for `black_river_system_architect` to model the Orchard approval. The evaluation passes when an engineer can identify the owning component and reproduce the stale-evidence test from the citations. [Agent and workflow](architecture/swarm-learning.md) · [Worked model](architecture/modeling-black-river.md)

### 2. Black River Swarm Review

**Buyer** An engineering or operations lead who needs a defensible assessment before committing to a release or integration.

**Product form** A scoped, facilitated review. The lead frames the question, specialists inspect their lanes, an independent reviewer checks a material success and failure path, and the parent reconciles disagreements. The customer receives an evidence-linked grade, a list of gaps and suggested acceptance tests, and reviewed lessons when findings are reusable.

**Try it** Ask the swarm to review the acquisition-to-settlement workflow at a pinned revision. The review is accepted when each grade links to evidence, the mirror separately verifies a material claim, and unresolved gaps have a named next check. The existing review found the settlement conflict after reapproval. This offer currently runs as a coordinated engagement using Codex. [Swarm procedure](architecture/swarm-learning.md) · [Example technical review](architecture/technical-review.md)

### Individual specialist offers

These are the product forms for roles inside the swarm. The System Architect has a project-scoped Codex configuration. The other specialists have been exercised as assigned review roles. An operator can deliver each review separately today. A separately installable agent would also need its own configuration, sample task and independent acceptance test.

| Role offered individually | What the customer receives | Proof of a good handoff |
| --- | --- | --- |
| **Evidence Reviewer** | A source inventory and a finding on which claims have current evidence. | The reviewer can resolve a cited revision and explain why stale evidence changes the eligibility decision. |
| **Finance Reviewer** | A checked purchase ceiling or reconciliation with assumptions and evidence. | A second reviewer reproduces the binding ceiling or traces cash and receivables back to separate receipts and invoices. |
| **Experience Reviewer** | A reproducible founder workflow replay and a list of usability gaps. | The report records the browser and device coverage, exact failed step and conditions needed to recheck it. |
| **Independent Mirror Reviewer** | A separate replay of a material claim and failure case, with an agreement or discrepancy record. | Both reviews use the same revision and evidence, and the mirror records its own result before comparing conclusions. |

## Tools and knowledge products

| Product | Buyer and job | Independent deliverable and trial |
| --- | --- | --- |
| **Learning Index** | An agent lead needs to find and reuse a previously verified lesson. | A local SQLite index over tracked guides and reviewed lessons. Run the index and search commands to retrieve a passage with its original path, lines and Git blob. A useful trial retrieves the settlement correction lesson and resolves its cited source. [Learning Index](guides/learning_index.md) |
| **Source Inventory** | An engineering lead needs to establish which source files and historical variants exist. | A fingerprinted file and archive inventory with exact duplicates and stated scan limits. Run it on an authorized source tree and confirm that two identical copies share one digest. [Source Inventory](guides/inventory.md) |
| **Code Map and Walkthroughs** | A founder or new engineer needs to understand and teach the code. | A VS Code workspace, source-to-guide catalog, inline walkthroughs and running examples. Use `code-map.cmd teach` for the deal workflow or open the debugger lesson for the five-row asset example. The learner should be able to trace an input to its output and test. [Code map](code-map.md) · [Start Here](START_HERE.md) |
| **Guide Checker** | A maintainer needs to know whether new source is explained and the links still work. | A CLI that flags undocumented files, broken links and invalid guide mappings. An acceptance run catches a deliberately missing or shared guide in the test fixture. [Guide Checker](guides/check_guides.md) |
| **Founder Replay** | Product and QA need to repeat a review flow across browser configurations. | A runnable browser test covering the local workflows and connected review on Chromium and WebKit. The output identifies emulator coverage and keeps physical-device acceptance visible. [Founder Replay](../tools/replay_founder.md) · [Physical-device acceptance](physical-device-acceptance.md) |
| **Pilot Release Checks** | A technical lead needs to decide whether a given revision is ready for approval. | One command for lint, selected type checks, unit tests, guide coverage, recovery and the browser replay. Run `code-map.cmd verify` and use the first failed step to locate the release issue. This product combines the checker and replay. [Release checks](guides/check_pilot.md) |
| **CUDA Scenario Screen** | An underwriting or analytics lead needs to explore many downside assumptions. | A CPU or NVIDIA GPU sensitivity grid with an optional cell-by-cell parity check. Run `code-map.cmd cuda` on an eligible machine. Its output is a scenario result for analysis. The underwriting packet and human review set approval authority. [CUDA screen](guides/cuda_screen.md) |
| **Asset Reporting Demo** | An asset operator or learner needs to see how raw rows become a validated report. | A synthetic CSV, exception and summary reports, and a manifest linking output to its source. Run the VS Code example and confirm that an unknown cost stays distinct from zero. [Asset Reporting](guides/asset_reporting.md) |

## Operating products

| Product | Buyer and job | Independent deliverable and trial |
| --- | --- | --- |
| **Deal Qualification and Underwriting** | An acquisition analyst needs to explain why a proposed price is inside or outside policy. | A deterministic engine and synthetic deal showing eligibility and the base, downside and financing ceilings. Trial acceptance reproduces the Orchard ceiling and holds a packet with missing or expired evidence. [Underwriting](guides/underwriting.md) |
| **Founder Command** | A principal needs to review the exact packet and record a decision with accountability. | A local authenticated pilot with independent reviewer and founder roles, retained evidence and retry behavior. Start the connected service and demonstrate a stale revision rejection and one committed decision. Physical-device and production identity evidence remain open. [Connected Founder Command](../pilot/founder_service.md) |
| **Ledger and Reconciliation** | A controller needs to distinguish billed amounts from settled amounts and trace the underlying source. | A synthetic four-entity ledger and recovery replay. Compare invoices with independently evidenced receipts and confirm the same balances after restore. Settlement corrections after deal reapproval still require a defined accounting rule. [Ledger](guides/ledger.md) · [Pilot acceptance](guides/pilot_acceptance.md) |

## Seven product extensions

| Product | Buyer and trial deliverable | Current evidence and the next acceptance check |
| --- | --- | --- |
| **Deal Decision Packet** | An acquisition principal or investment committee gets one shareable file with the proposed price, binding ceiling, evidence revision, exceptions, and decision history. | The synthetic Orchard packet and founder decision exist. The shareable export needs implementation. Verify that an exported packet identifies the exact approved evidence, preserves all three ceilings, and includes no material outside the recipient's scope. [Underwriting](guides/underwriting.md) · [Founder review](../pilot/founder_service.md) |
| **Deal Exception Monitor** | An acquisition operations lead gets a queue of deals that need review because evidence expired, financing changed, or a prior decision is stale. | The pilot rejects stale revisions at review. A multi-deal queue and scheduled checks remain planned. Replay a batch containing a healthy deal, expired evidence, reduced financing, and superseded approval. Show the three exceptions once each, with their reasons. [Worked approval model](architecture/modeling-black-river.md) |
| **Parcel Feasibility Brief** | A developer or site acquisition team gets a brief on zoning, access, wetlands, and missing evidence before commissioning design. | The pilot uses synthetic parcel evidence. A usable trial requires licensed sources, coordinate validation, and dates. Compare one authorized parcel with an independent reference and show an unknown status for any constraint whose evidence is unavailable. [Parcel and GIS engine](architecture/intelligence-engines.md) |
| **Design-to-Economics Comparator** | A developer or architect gets a side-by-side comparison of two design alternatives, including quantities, costs, reserves, assumptions, and feasibility. | The finance engine works on synthetic inputs. Design adapters and their handoff remain planned. Run two independently measured alternatives through the same cost rules, trace each quantity to its design revision, and reject an incompatible unit or coordinate reference system. [Design and feasibility engines](architecture/intelligence-engines.md) |
| **Settlement Exceptions Desk** | A controller gets a case list and review workflow for missing receipts, conflicting receipt evidence, and corrections after reapproval. | The mirror reproduced the reapproval conflict and confirmed that prior records survive it. Verify that an unchanged paid obligation leaves cash and receipt counts unchanged, and that a legitimate adjustment has separate evidence, independent approval, and a link to the original posting. [Settlement revision lesson](learning/settlement-revision.md) |
| **Repository Recovery Audit** | A CTO inheriting a system gets a fixed-scope engagement with a source and archive inventory, a reproducible checkout, a restore result, and a handoff guide. | Black River has exercised the inventory and restore tools. A trial uses one authorized repository and one backup. A second engineer must reproduce the manifest and recover the agreed records on a clean checkout. Record any missing source separately. [Source inventory](guides/inventory.md) · [Restore walkthrough](guides/pilot_acceptance.md) |
| **Black River Academy** | A technical founder or onboarding lead gets an instructor-led lab using the VS Code workspace, source guides, and an architecture exercise. | The lessons and local walkthrough work. Course delivery still needs learner acceptance. A learner should explain the system boundary, trace Orchard from evidence to its purchase ceiling, reproduce a stale-evidence failure, and show the restored decision record. [Start Here](START_HERE.md) · [Architecture modeling lab](architecture/modeling-black-river.md) |

The recovery audit and Academy can be delivered with a facilitator using the existing tools. The Decision Packet can be evaluated as a manually assembled example while the export is built. The monitor, parcel brief, design comparator, and exceptions desk each need the implementation or integration checks above before a standalone trial.

## How the products fit together

- **Architecture and assurance engagement.** System Architect creates the model. Swarm Review challenges it. Learning Index captures checked lessons. Source Inventory, Code Map, Guide Checker and Pilot Release Checks make the result reproducible.
- **Acquisition operating pilot.** Deal Qualification and Underwriting produces the evidence packet. CUDA explores downside assumptions. Founder Command captures approval. Ledger and Reconciliation follows the operating evidence. Founder Replay verifies the experience.

A design partner can evaluate one product with a single workflow and a measurable result. A standalone product trial needs a reproducible entry point, clear input and output, and at least one independently checked failure case. A commercial release adds its own delivery package, license or service terms, access, and support. Record what the customer actually tried before treating interest as acceptance.

The wider GIS, design and intelligence engines remain in the [engine inventory](architecture/intelligence-engines.md). Promote each to the portfolio when it has a working contract, a repeatable trial and evidence for its failure path.
