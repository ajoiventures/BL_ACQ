# Trace the sourced corporate case

Open [corporate_case.py](../../pilot/corporate_case.py). This adapter combines a
specific, manually sourced WD-40 dataset with the reusable
[statement engine](corporate_model.md) and [acquisition model](acquisition_finance.md).
It is not a general filing parser. The model version is `br-corporate-case-1`.

## Follow a calculation

1. `load_case` reads the versioned source facts and editable assumptions.
2. `evaluate_case` validates the selected case, source availability, source IDs
   and the common historical quote date. Filing dates cannot follow the cutoff.
   Later retrieval of price history is permitted only with its original market
   event date and its later retrieval date recorded separately.
3. `historical_checks` performs 23 identities for each of three reported years:
   69 controls in total. These include complete reported cash-flow components,
   the FX cash effect, equity movements and shares. They do not invent historical
   CFO from changes in two balance sheets.
4. `normalize_wdfc` converts USD thousands to absolute USD, preserving actual
   share counts. Current operating lease liabilities already contained in
   accrued liabilities move to frozen current liabilities once. Other current
   assets, goodwill, ROU assets, deferred taxes and selected liabilities remain
   explicitly frozen. The opening balance sheet still reconciles.
5. `project_statements` produces the five annual forecasts and reconciliation
   controls. `value_forecast` derives economic FCFF from those forecasts.
6. `compare_companies` constructs historical EV/operating-EBIT multiples from
   RPM and Clorox, including the source-specific adjustments in the dataset.
7. `evaluate_acquisition` uses the same operating forecast with a separate
   hypothetical transaction financing structure. Its financing cash flows are
   not the standalone company's dividends or old debt schedule.

## Units and dates

The adapter requires source schema `1.0`, currency USD, the documented source
unit string, and ticker WDFC. Its normalization cannot be reused for another
issuer merely by replacing the company name. The generic statement and
financing engines accept their own documented normalized contracts.

FY2025 balances are dated August 31, 2025. The case carries them unchanged into
a hypothetical October 31, 2025 opening, after the filing became public. This is
an **unverified closing-balance proxy**. Model-year forecasts end October 31,
2026–2030; they are not WD-40 fiscal-year guidance. Market price history was
retrieved in November 2026, so this is not a fully archived point-in-time backtest.

## Valuation conventions

The WACC build is:

`cost of equity = risk-free rate + beta × equity risk premium`

`WACC = cost of equity × (1 − debt weight) + debt cost × (1 − tax rate) × debt weight`

All inputs are explicit analyst assumptions. Forecast FCFF is EBIT less tax on
positive EBIT, plus D&A, less physical/intangible capex and the change in
operating NWC. Recurring share compensation remains an expense; it is not added
back. Levered NOL benefits are not inserted into this unlevered valuation.

Terminal NOPAT is final-year EBIT grown once and taxed at the terminal tax rate.
Terminal reinvestment equals NOPAT times growth divided by terminal ROIC. The
engine requires positive terminal NOPAT, positive ROIC at least equal to growth,
and WACC above nonnegative growth. A distressed or nonoperating terminal year
needs a different method.

The equity bridge adds full reported cash and deducts funded debt and declared
other claims, then divides by opening common shares. Full cash availability,
existing options/awards and claim completeness remain review items. Future SBC
is already retained as an expense and is not also charged as forecast dilution
in this particular DCF convention.

## Comparables

Both peers use October 31, 2025 reference prices but their selected FY2025
earnings and share-count dates differ. The denominator is constructed operating
EBIT, not normalized recurring earnings or latest LTM. Known peer raw operating
lines must agree with their stored derived EBIT. EV includes the documented
debt, minority interests and debt-like claims, less reported cash. Low, median
and high multiples are applied to WD-40's FY2025 operating income; its equity
bridge uses the same other-claims assumption as DCF.

The two-peer range is a limited cross-check. It does not justify a mechanical
average with DCF. See the [source audit](../corporate-source-audit.md) for Clorox
amortization, the Glad obligation, pensions, leases and retained unusual items.

## Reproducible output and review state

Every bundle includes the exact case, source facts and computed report. The
report records its model version, an input SHA-256 digest, Python version and
SHA-256 fingerprints of the three financial modules. Those fingerprints aid
reconstruction; they are not signatures, independent approval or a complete
dependency lock.

`status` remains `research_requires_review` and `execution_allowed` remains
false. A balanced statement or `modeled_feasible` financing result does not
establish attractive returns, data completeness, a lender commitment or
employer acceptance. A failed acquisition financing/exit check withholds sponsor
returns rather than returning a misleading zero.

Read the [case memo](../corporate-case.md), run the
[command-line exporter](run_corporate_case.md), or inspect the
[integration tests](test_corporate_case.md).
