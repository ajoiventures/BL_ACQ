# WD-40 corporate valuation and acquisition-finance case

Prepared November 22, 2026. Historical analysis cutoff and hypothetical model
start: **October 31, 2025**. Status: **research case requiring qualified review**.

## Decision shown by the case

The operating forecast generates cash, but the illustrative acquisition price
produces weak sponsor returns. At a 20% premium to the historical $194.28
reference share price, the case requires approximately **$2.943 billion of
sponsor equity**. The Base case returns **0.951× invested equity and −0.99% a
year over five equal annual periods**. Even the specified Upside case returns
only **1.143× and 2.71% a year**. These are outputs of the supplied assumptions,
not a current trading recommendation, lender quotation or forecast of realized
investment results.

The case is intended to demonstrate a defensible path from reported statements
through operating drivers, valuation, transaction funding and investor cash
flows. It uses a nonfinancial operating company with public financial statements
so each transformation can be examined. It does not establish coverage of every
finance desk or constitute an employer-approved model.

## Reported evidence and date discipline

WD-40's [FY2025 Form 10-K](https://www.sec.gov/Archives/edgar/data/105132/000010513225000067/wdfc-20250831.htm)
provides the principal historical evidence. The
[FY2024 filing](https://www.sec.gov/Archives/edgar/data/105132/000010513224000064/wdfc-20240831.htm)
supplies the earlier comparative balance sheet. The versioned
[source facts](../data/corporate/wdfc_source_facts.json) preserve three years of
income statements, balance sheets, cash-flow statements and equity movements,
with source locations, publication dates, units and transformations.

| WD-40 FY2025 reported measure | USD millions |
| --- | ---: |
| Revenue | 619.985 |
| Operating income | 103.793 |
| Net income | 90.994 |
| Operating cash flow | 87.925 |
| Cash | 58.130 |
| Funded debt | 86.995 |
| Shareholders' equity | 268.152 |

Source balance sheets are dated **August 31, 2025**. The model carries those
balances unchanged into a hypothetical October 31 opening after publication of
the filing. No two-month interim statement has been fabricated. This proxy must
be replaced with verified closing balances for real transaction use. Forecast
columns are model years ending October 31, 2026–2030, not issuer fiscal-year
guidance.

The three reference quotes all use October 31, 2025:
[WDFC $194.28](https://chartexchange.com/symbol/nasdaq-wdfc/historical/),
[RPM $109.28](https://chartexchange.com/symbol/nyse-rpm/historical/), and
[CLX $112.46](https://chartexchange.com/symbol/nyse-clx/historical/).
Their tables were retrieved November 22, 2026; an archived vendor publication
vintage was not obtained. The data therefore supports a reproducible historical
case, not a claim of a fully point-in-time historical investment decision.

The historical engine checks 69 accounting identities, including complete CFO
components, FX cash movements and equity rollforwards. Source arithmetic is a
necessary control; it does not prove that every economic adjustment is complete.

## Accounting decisions a reviewer should examine

**Taxes.** Reported FY2025 earnings include an $11.929 million benefit associated
with the release of an uncertain tax position. The forecast uses an explicit
23% recurring tax assumption rather than mechanically extending the reported
effective rate. The simplified NOL model has no jurisdiction, expiry, tax-basis
or ownership-change analysis. Its utilization cap is an input, not a legal
conclusion.

**Working capital and frozen balances.** Operating receivables, inventory,
payables and selected accruals have explicit drivers. Current lease liabilities
already included in accrued liabilities are classified once. Other current
assets include tax receivables and assets held for sale; the adapter keeps that
balance separate instead of treating all of it as recurring operating NWC.
Deferred taxes, leases, goodwill and other identified accounts are frozen and
need additional schedules for a complete live-company forecast.

**Depreciation and presentation.** The forecast shows COGS and gross margin
before D&A, then deducts depreciation and intangible amortization below EBITDA.
Historical reported gross margin retains its original accounting basis. The
model does not assert that those presentations are directly identical. PPE
depreciation and finite-lived intangible amortization roll forward explicitly.

**Share compensation.** The standalone statements include the noncash CFO
addback, an equity credit and assumed share issuance. Economic DCF retains
recurring compensation as an expense without adding it back; future award
dilution is not charged a second time in that DCF. The acquisition assumes the
same compensation cost is paid in cash and has no SBC cash addback. Existing
award claims and option valuation remain unmodeled review items.

**Cash and claims.** DCF adds full reported cash and deducts funded debt and a
declared $1.1 million debt-like tax-claim proxy. The acquisition separately
settles existing debt and this claim at closing. The hypothetical settlement
does not establish what an authority would actually collect. Cash availability
and completeness of other claims require diligence.

The [source audit](corporate-source-audit.md) records the reported facts,
normalization judgments, peer adjustments and unresolved items in more detail.

## Forecast and valuation

All growth, margin, tax, capital structure and transaction inputs are editable
analyst assumptions in [the case file](../data/corporate/wdfc_2025_case.json).
They are not WD-40 management guidance or market-calibrated estimates.

| Assumption | Base convention |
| --- | --- |
| Revenue growth | 5% in each of five model years |
| EBITDA margin | 18%, 18.5%, 19%, 19.5%, 19.5% |
| Receivables / inventory / payables | 71 / 105 / 50 days |
| PPE cash capex | 1.5% of sales |
| Recurring tax | 23% |
| WACC | 8.517% |
| WACC inputs | Risk-free 4%; beta 0.9; ERP 5.5%; debt cost 6%; debt weight 10% |
| Perpetual growth / terminal ROIC | 2.5% / 18% |
| Annual valuation timing | End of each equal annual period |

Terminal reinvestment equals terminal NOPAT times growth divided by terminal
ROIC. Thus growth requires explicit reinvestment. About **75.6% of Base
enterprise value comes from discounted terminal value**, making terminal
economics a material review focus. The WACC assumptions have not been estimated
from a live market dataset.

| Scenario | DCF enterprise value, USD m | DCF per common share | Sponsor MOIC | Sponsor annual IRR |
| --- | ---: | ---: | ---: | ---: |
| Downside | 952.202 | $68.17 | 0.596× | −9.83% |
| Base | 1,441.458 | $104.34 | 0.951× | −0.99% |
| Upside | 1,706.587 | $123.94 | 1.143× | 2.71% |

The peer cross-check produces **15.88×–19.00× EV/constructed operating EBIT**,
implying approximately **$119.65–$143.54 per WDFC share**, with a two-peer median
of $131.60. It is deliberately identified as a limited historical comparison.
Different fiscal and share-count dates remain visible; these are selected
FY2025 earnings, not latest LTM or fully normalized recurring earnings.

For RPM, source evidence is its
[FY2025 annual report](https://www.sec.gov/Archives/edgar/data/110621/000119312525185357/d944593dars.pdf).
For Clorox, the [financial exhibit](https://www.sec.gov/Archives/edgar/data/21076/000002107625000039/clx-20250630_d2.htm)
and [proxy](https://www.sec.gov/Archives/edgar/data/21076/000155278125000311/e25287_clx-def14a.htm)
support the operating lines, bridge and dated shares. Clorox intangible
amortization is moved into constructed operating EBIT. The bridge includes the
documented Glad terminal obligation and retirement deficits; finance leases and
minority interests are handled explicitly. Reported unusual items are retained
where disclosed rather than silently labeled recurring. DCF and the peer range
are not mechanically averaged into a target price.

## Hypothetical acquisition

The entry price assumes a 20% premium to the dated WDFC reference quote. This
produces approximately $3.184 billion of enterprise value. New term debt is
$335.952 million, or 3× the case's $111.984 million historical EBIT-plus-CF-D&A
proxy. That proxy differs from the issuer's adjusted EBITDA. Entry EV is about
28.43× this proxy, while the assumed exit is 18× forecast EBITDA; the price and
exit assumptions help explain the weak equity returns.

| Sources | USD millions | Uses | USD millions |
| --- | ---: | --- | ---: |
| Sponsor equity | 2,943.181 | Seller equity consideration | 3,153.774 |
| New term debt | 335.952 | Existing debt repayment | 86.995 |
| Acquired cash above reserve | 33.130 | Other-claim settlement | 1.100 |
| | | Transaction fees | 63.675 |
| | | Financing fees | 6.719 |
| **Total** | **3,312.263** | **Total** | **3,312.263** |

The company retains a $25 million minimum cash reserve. The term loan assumes
7.5% interest, 5% annual amortization of initial principal and year-five
maturity. A $100 million revolver carries 9% interest. The annual waterfall
uses a 75% cash sweep after required principal and revolving repayments. Fees
are 2% of entry EV, 2% of new term debt and 2% of exit EV. There are no interim
sponsor distributions.

Interest is based on beginning debt and financing movements occur at year end.
When maturity occurs **before exit**, all remaining term principal is due in
that year's financing waterfall. When maturity **coincides with exit**, scheduled
amortization is paid during the period and the residual balloon is settled once
in the sale bridge. The Downside sale repays a residual $134.579 million balloon.
The model does not require an unnecessary bridge loan immediately before that
same-date sale. If sale proceeds cannot repay debt, or an earlier financing
requirement is unfunded, returns are withheld.

All three supplied cases are feasible under the model's specified annual cash,
debt and covenant assumptions. That result is separate from return quality and
does not establish actual financing availability. The Base and Downside lose
sponsor capital over the modeled period.

## Review and use

Run [the command-line exporter](guides/run_corporate_case.md), or start
`python -m pilot.founder_service` and open `http://127.0.0.1:8765/corporate.html`
with a local founder or reviewer key. The authenticated workspace allows
temporary assumption edits and exports the exact input/output bundle. Source
facts remain server-owned. Editing inputs makes an earlier result stale and
disables its export until recalculation. No transaction is authorized or sent.

The [workbook builder](guides/build_corporate_workbook.md) uses the same bundle
to produce an editable analyst workbook. Its case selector and financial
schedules use formulas. The [source map](code-map.md) links every maintained
source file to its reading guide. Runtime calculations do not need an AI model,
prompt, API key or network connection.

Verification includes independently specified small-number accounting and
financing examples, the zero-growth DCF benchmark, source and forecast
reconciliations, scaling and input-boundary checks, failure gating, and
authenticated API tests. Code review by another agent is not qualified
independent human validation. The [verification record](corporate-validation.md)
summarizes the scoped evidence. The draft pull request records the latest
release checks and remaining browser/CI status.

Before use for an employer's live decision, the specific model needs qualified
economic/accounting challenge, verified closing data, employer-approved data
and deployment, supported-environment browser verification, and native workbook
review. Purchase accounting, merger accretion/dilution, detailed tax/lease/FX
schedules, stub periods, complete diluted claims, a broader comparable universe,
credit recovery, sector-specific models and enterprise controls remain outside
this case. See the updated [coverage assessment](valuation-institutional-readiness.md).
