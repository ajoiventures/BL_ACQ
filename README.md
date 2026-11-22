# Black River acquisition workspace

Open [the learning workspace](black-river.code-workspace) in VS Code. Start with a five-row asset report, then follow a simulated parcel through underwriting and founder review.

On Windows, run `code-map.cmd` for the architecture, a live teaching demo, a CTO pitch, and the file map. The [CTO guide](docs/CTO_ARCHITECTURE.md) explains the platform and its current evidence.

The [System Architect and swarm workflow](docs/architecture/swarm-learning.md) covers model review, lessons and search. The [technical review](docs/architecture/technical-review.md) grades the work against its source and verification evidence.

The [product portfolio](docs/PRODUCT_PORTFOLIO.md) describes the agent, swarm service, individual tools, and operating products. Open it on Windows with `code-map.cmd products`.

- [Start Here](docs/START_HERE.md) — run the examples, set a breakpoint, and inspect the output.
- [Code map](docs/code-map.md) — find the file guide for each maintained source.
- [Founder review](web/index.html) — serve this page locally using the instructions in Start Here.

The public examples use synthetic records. Domain selection and review actions in the browser demonstrate the workflow on a local device.

## Valuation & Risk

The [valuation workspace](docs/valuation.md) adds corporate and property discounted cash flow, event scenarios, reverse valuation, source checks, entry-price policy and immutable research runs. Start `python -m pilot.founder_service`, then open `http://127.0.0.1:8765/valuation.html` with a local reviewer or founder key.

The dated Nvidia example reproduces its source workbook numerically while keeping conflicting dates and the unverified price visible. Existing acquisition approvals and settlement remain separate from valuation research.

The feature is a research prototype. The [institutional readiness assessment](docs/valuation-institutional-readiness.md) defines the financial coverage and validation evidence required for a professional-use target.

## Corporate valuation and acquisition case

The [WD-40 case memo](docs/corporate-case.md) connects three years of sourced financial statements to a five-year linked forecast, DCF, two historical peer comparisons, acquisition funding, debt schedules and sponsor returns. It includes a formula-based Excel builder and a separate authenticated workspace at `http://127.0.0.1:8765/corporate.html`.

Run `python tools/run_corporate_case.py --case Base --output .runs/wdfc-base.json` to reproduce the complete case without an AI service or network connection. The historical cutoff is October 31, 2025; assumptions and unresolved closing-balance, data-vintage and professional-review limits remain explicit. This is a bounded research case, not a claim of institutional approval.
