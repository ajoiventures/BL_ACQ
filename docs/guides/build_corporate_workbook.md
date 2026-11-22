# Corporate case workbook

`tools/build_corporate_workbook.mjs` creates the formula-driven WD-40 valuation and acquisition workbook from the corporate case bundle. It uses the primary runtime's `@oai/artifact-tool` package. The financial formulas are independently assembled in Excel; Python outputs are authoring-time comparison evidence rather than workbook calculation inputs.

## Build

Run `python tools/run_corporate_case.py --output /absolute/path/corporate_case_bundle.json` from the repository to refresh the sourced case bundle.

Create a temporary working directory and link its `node_modules` to the directory identified by `CODEX_PRIMARY_RUNTIME_NODE_MODULES`. Copy the builder into that directory. Run the copy with `CODEX_PRIMARY_RUNTIME_NODE` and three positional arguments: the absolute bundle path, the output directory, and the absolute repository path. The repository argument allows the builder to evaluate the Python case for independent comparisons. `CODEX_PRIMARY_RUNTIME_PYTHON` selects the Python executable when set.

The main output is `wdfc_corporate_acquisition.xlsx`. Supporting outputs are `workbook_validation.json`, `workbook_inspection.ndjson`, and PNG previews for visual review. Keep generated artifacts outside the repository.

## Workbook structure

| Sheet | Purpose |
| --- | --- |
| Summary | Current-case DCF, historical price reference, selected peer range, sponsor return, cash-flow and debt chart, and outstanding review items. |
| Assumptions | One numeric case selector: 1 Base, 2 Downside, 3 Upside. Each operating driver has one active row followed by the three editable case inputs. WACC and transaction assumptions are editable below. |
| Statements | Linked income statement, balance sheet, cash flow, working capital, assets, debt, NOL, equity and share schedules for five model years. |
| Valuation | FCFF, WACC, terminal ROIC and reinvestment, DCF, and enterprise-to-equity claims bridge. |
| Acquisition | Sources and uses, annual debt and cash waterfall, covenants, maturity timing, exit proceeds and conditional sponsor MOIC/annual IRR. |
| Comps | Two peers built from sourced operating lines, debt and claims components; live EV/EBIT and target value bridge. |
| Actuals | Three source fiscal years of income, balance sheet, cash flow and equity data, selected disclosures, the opening mapping, and source registry/locators. |
| Review | Terminal reconciliation evidence and unresolved review requirements. Business calculations do not depend on this sheet. |

Amounts display in USD millions and shares in millions; per-share values are USD. Source statements are supplied in USD thousands and the Python engine uses absolute dollars. Source actuals remain fixed across case changes. Blue values are editable inputs, black formulas calculate within a sheet, and green formulas link to other sheets.

## Model conventions

The historical analysis cutoff is October 31, 2025. Reported August 31, 2025 balances are carried unchanged into an explicitly hypothetical October 31 opening proxy. Model Years 1–5 end October 31; they are not the issuer's fiscal-year forecasts. A verified interim closing rollforward remains outstanding.

SBC remains an EBITDA expense. Standalone cash flow adds it back and the equity/share schedule models dilution at an assumed issuance price. DCF and acquisition cash flow treat recurring compensation as a cash-equivalent expense. Other current/noncurrent balances held fixed are disclosed. The $1.1 million other-claim proxy appears in the DCF and comparable bridges and is separately settled in acquisition uses.

Peer operating EBIT is calculated from raw source expense lines. RPM financing debt already includes finance leases. Clorox's separately disclosed finance leases are added once, and its $21 million intangible amortization reported in other expense is deducted in operating EBIT.

Acquisition interest uses beginning balances. A maturity before the modeled exit is payable in the annual operating waterfall. When maturity coincides with the year-five sale, scheduled amortization remains an annual obligation and the residual balloon is settled once in the exit debt payoff. Returns are unavailable following funding, mandatory-principal, covenant or exit-debt-repayment failure. Annual IRR uses equal annual periods with one initial contribution, no interim distributions and one terminal receipt.

## Verification and limitations

The builder recalculates each case and compares statement, financing, DCF and peer outputs with the Python implementation. It also changes a later-year growth input, a later-year tax input and the term borrowing rate; tests missing inactive and active case inputs, missing scalar/source/peer values and an invalid margin; and verifies return withholding after an unfunded early maturity and insufficient sale proceeds. It restores Base and requires a zero-result formula-error scan before export. The JSON file records those checks. The PNGs must be inspected after building; render success alone is not a visual review.

The workbook has been calculated with Artifact Tool. A separate native Microsoft Excel application-engine check is not part of this workflow. Numerical cash-boundary tolerance is documented separately from accounting materiality. Analyst assumptions, the opening balance proxy, annual liquidity resolution, source-vintage limits and independent human financial review remain material qualifications. The workbook is a research and training case, not institutional approval or a lender commitment.
