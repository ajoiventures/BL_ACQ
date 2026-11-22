# Black River capability and layer coverage

Black River has **338 master requirements across 34 epics**. The [product portfolio](../PRODUCT_PORTFOLIO.md) describes what a customer receives. This map describes the functions those products depend on. A single product can use several layers, and a layer can serve several products.

## What runs and what remains

### Document and probability increment

The November 22, 2026 [builder ticket plan](../plans/document-engine-tickets.md)
adds a bounded 84-ticket work breakdown alongside the 338-requirement master.
The current increment implements immutable document claims/reviews, exact
conditional offer economics, a reviewed-input application layer and an offline
builder scheduler. It reuses the existing underwriting and finance context;
it does not replace the ledger, workflow authority or corporate models.

The [verification record](../plans/document-engine-verification.md) distinguishes
executed CPU behavior, broader open capabilities, unavailable R/CUDA execution,
browser limitations and later AI. The [code map](../code-map.md) links each new
source and agent profile to its guide. The earlier coverage table below remains
the wider portfolio inventory; historical runtime claims there are not new
execution claims for this increment.

| Layer | Working evidence in the checkout | Remaining scope |
| --- | --- | --- |
| **Intake and evidence** | Synthetic parcel and comparable records, source references, freshness, coordinate validation, scoped immutable evidence. The UI rehearses document intake. | Authorized county and parcel ingestion, live document parsing and retrieval, consent, trusted communication and CRM sources. **E03, E08, E15, E17, E22** |
| **Deal, capital, and strategy** | The fictional Orchard deal qualifies, calculates base/downside/funding ceilings and holds for missing material evidence. CPU and CUDA run the same synthetic downside grid. | Live underwriting inputs, strategy breadth across property and debt families, entitlement, refinance and capital routing, portfolio analytics and robust optimization. **E05, E06, E09–E13, E16, E19, E34** |
| **Founder workspace and authority** | Browser review, independent reviewer and founder roles, versioned drafts, audited decisions and idempotent retries for the same request. Chromium and WebKit on Windows exercised the workflows, including emulated phone profiles. | Production identity, live map and service connections, native iPhone and Android evidence, and the planned founder workspace beyond the pilot. **E01, E25** |
| **Operations and reconciliation** | Durable tasks, synthetic maintenance and service flows, distinct invoice and receipt evidence, four-entity reconciliation and restore. | Live work orders, contractor dispatch, takeoffs and roof economics, banking and tax workflows, and a correction path when a settled obligation is reapproved. **E04, E07, E14, E18, E21** |
| **Foundation and assurance** | SQLite migrations and leases, role and scope checks, connector approval contract, local verification suite, source inventory, learning index, system architect and independent swarm review. | Hosted CI proof, production observability, deployment and recovery targets, and a governed plugin and agent runtime. **E02, E20, E23–E24, E26–E30, E32–E33** |
| **Integrated intelligence** | Standalone deterministic acquisition finance, a CUDA sensitivity screen, and a connected synthetic review and settlement path. | GIS-to-Rhino/Grasshopper-to-SketchUp interchange, licensed parcel and design data, spatial ML, model governance, and full parcel-to-profit verification. **E31** |

The testable flow is **synthetic intake → qualification → underwriting → review → approval → settlement → recovery**. The full target flow adds licensed parcel inputs, design exchange, provider delivery and settlement evidence. The [engine inventory](intelligence-engines.md) shows what comes into each engine and what goes out. The [independent review](technical-review.md) links the working claims to tests and limitations.

## Product dependencies

| Product or extension | Functions it depends on |
| --- | --- |
| Deal Decision Packet and Deal Exception Monitor | Versioned evidence, the deterministic underwriting packet, approval history, and change detection. Shareable export and multi-deal monitoring are extensions. |
| Parcel Feasibility Brief and Design-to-Economics Comparator | Parcel provenance, zoning and access constraints, unit and coordinate contracts, design quantities, and finance. Live GIS and design adapters are dependencies. |
| Settlement Exceptions Desk | Scoped invoices and receipts, independent accounting review, and a correction policy linked to original postings. A reproduced evidence-ID conflict remains the acceptance case to resolve. [Settlement revision lesson](../learning/settlement-revision.md) |
| System Architect, Swarm Review, Recovery Audit, and Academy | Source and revision inventory, model-to-test traceability, independent verification, learning retrieval, and documented replay. Product packaging can follow the existing artifact workflow. |

The private engineering master owns the detailed acceptance criteria. Its requirement crosswalk accounts for every master ticket. A related GitHub issue can supply partial evidence. Mark a master requirement complete only after checking its own acceptance criteria. The [delivery tracker](https://github.com/ajoiventures/BL_ACQ/issues/10) covers the current pilot execution queue.
