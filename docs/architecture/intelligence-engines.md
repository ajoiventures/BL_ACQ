# Black River intelligence engines

The platform pairs specialized engines around one parcel or deal. Each engine should hand the next layer a result with an input version, scope and provenance. A model or simulation can prepare evidence and recommend a next step. The recorded review determines whether an operator may proceed.

## Deal and spatial intelligence

| Engine | Input → output | Delivery evidence and backlog |
| --- | --- | --- |
| Parcel and GIS | Parcel IDs, coordinates, geometry, zoning and permits → normalized parcel context, overlays and uncertainty. | The pilot validates coordinates and uses synthetic parcel evidence. Licensed county ingestion, CRS validation and actual overlays remain on BR-ENG-285 and 300. |
| Parcel-to-design constraints | Parcel geometry, legal use and site constraints → a versioned design envelope with units and assumptions. | The pilot checks legal use, access and wetlands through evidence. The shared spatial-to-design contracts remain BR-ENG-299. |
| Rhino and Grasshopper | A buildable envelope and parameters → reproducible massing, geometry, quantities and constraint failures. | Planned. BR-ENG-301 requires coordinate, unit, tolerance and area round trips. |
| SketchUp | Design geometry and quantities → named components, materials, model states and reviewed scenes. | Planned. BR-ENG-302 requires object identity, scale and scenario exchange. |
| Spatial interchange and digital twin | GIS, design and portfolio artifacts → linked representations with transform, version and geometry fingerprint. | A sibling TWIN prototype has a selection bridge. Integrated interchange and reversible links remain BR-ENG-303. |
| Strategy eligibility | District thesis, property family, current legal use, comps, costs and capacity → eligible, held or excluded with reasons. | The Orchard fixture is executable. Additional property strategies and independent buy, fund and exit evidence remain BR-ENG-331–333. [Qualification and underwriting](../guides/underwriting.md) |
| Finance and feasibility | Price, costs, financing capacity, downside assumptions and evidence → base, downside and funding ceilings with an auditable packet. | The cent-precise acquisition calculation is executable. Construction quantities, reserve schedules, capital stacks and development-finance scenarios extend BR-ENG-305. [Worked calculation](../guides/scenario.md) |
| Simulation and optimization | Resale assumptions, stress rates and design alternatives → sensitivities and ranked options. | CPU and CUDA downside grids are executable. Monte Carlo, robust optimization and multi-objective ranking remain BR-ENG-306. [CUDA decision](cuda-screening.md) |
| ML and spatial decision science | Versioned historical features and observed outcomes → calibrated estimates, uncertainty, feature lineage and model evaluation. | Planned integrated model service. BR-ENG-304 requires baseline comparisons, leakage-safe evaluation, abstention and model cards. BR-ENG-310 closes the forecast-to-outcome loop. |

## Evidence, operations, and assurance

| Engine | Input → output | Delivery evidence and backlog |
| --- | --- | --- |
| Documents, search and retrieval | Source files and authorized messages → classified documents, versioned extracts, citations and scoped retrieval. | The UI demonstrates synthetic intake. Historical code was inventoried. Integrated parsing, retrieval and permissions remain BR-ENG-181, 272, 286 and 334. |
| Network and communications | Authorized relationships, messages and contact context → corridor intelligence, correspondence and proposed follow-up. | Roadmap scope in E08, E15 and BR-ENG-334. A send action requires a separate authorized integration. |
| Operations, maintenance and capital planning | Condition records, service evidence, work orders, quotes and quantities → prioritized actions, dispatch decisions and reserve inputs. | Synthetic operations examples and durable task claims are executable. Full field dispatch, takeoffs, roof assessment and maintenance economics belong to E18, E21 and BR-ENG-165. |
| Ledger, portfolio and family office | Independently reviewed service, invoice and receipt evidence → entity journals, consolidated balances and reconciliation. | The pilot reconciles four synthetic entities. Live payment reconciliation, tax treatment, portfolio forecasting and family-office operations remain E07 and E16. [Ledger walkthrough](../guides/ledger.md) |
| Founder and agent coordination | Evidence-backed opportunities, roles, scopes and work requests → queue, draft, reviewed decision, task assignment and receipt. | The connected pilot checks role, scope, evidence version, retry and concurrent decisions. Production tool orchestration and authority remain BR-ENG-307 and 337. [Connected service](../../pilot/founder_service.md) |
| Capability, benchmark and outcome intelligence | Source inventory, check runs, failure evidence and realized performance → prioritized gaps, repeatable benchmarks and outcomes feedback. | Source and guide checkers, review records and synthetic acceptance are executable. Continuous cost, quality, model drift and outcome measurement remain E32–E33 and BR-ENG-310. [Release checks](../guides/check_pilot.md) |

## The walkthrough to teach

1. Identify which engine owns the next question. A parcel source can establish location and provenance. It cannot supply a verified purchase ceiling without evidence from the deal and finance layers.
2. Follow one exact Orchard packet through eligibility, the binding price limit and a separate founder review. Then trace the recorded decision to the settlement and recovery demonstration.
3. Show the CUDA screen as a sensitivity exercise. Use the output to explore assumptions and retain the deterministic underwriting packet for the actual review.
4. Explain how the full design is tested. BR-ENG-308 calls for a licensed parcel progressing through GIS, Rhino, SketchUp, finance, optional ML, a reviewed dossier and reconciled payment. The executable synthetic pilot exercises its deal, decision, settlement and recovery segments.

Return to the [CTO guide](../CTO_ARCHITECTURE.md), the [Machine of Machines terminology reference](system-of-systems.md), the [file map](../code-map.md) or the [delivery index](https://github.com/ajoiventures/BL_ACQ/issues/10).
