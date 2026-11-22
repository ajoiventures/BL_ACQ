# Follow the linked corporate statements

Open [corporate_model.py](../../pilot/corporate_model.py). The public function
`project_statements(opening, drivers)` builds a normalized income statement,
balance sheet and cash-flow statement for one to ten annual periods. It returns
the schedules, explicit model conventions, numerical reconciliations and funding
shortfalls. It uses the Python standard library and has no network, AI or trade
execution dependency.

This module is a bounded research implementation. It does not generate statutory
GAAP statements, a jurisdiction-specific tax return, a merger purchase-price
allocation or an institutionally approved model. Its model version is
`br-statements-1`.

## Input contract

Amounts are **absolute USD**, shares are actual shares, rates are decimal
fractions and days use a fixed 365-day denominator. Every listed field is
required, including explicit zeros. Unknown keys, missing keys, booleans,
numeric strings, NaN and infinity are rejected. Monetary/count inputs are at
most `1e15` in magnitude; signed opening equity and retained earnings are
permitted. Revenue and opening shares must be positive. Calculated numeric
outputs must remain finite and within `1e100` in absolute magnitude.

Dates must be ISO `YYYY-MM-DD`. Forecast periods are exact annual anniversaries
of the opening date. A February 29 opening rolls to February 28 in nonleap
years and returns to February 29 in leap years. There are no stub periods,
quarterly periods or 52/53-week fiscal-calendar rules.

### Opening balances

| Field | Meaning |
| --- | --- |
| `period_end`, `revenue` | Historical balance-sheet date and annual revenue immediately before forecast year one. |
| `cash` | Starting cash; forecast deficits are shown explicitly. |
| `accounts_receivable`, `inventory` | Operating balances. |
| `operating_other_current_assets` | Other operating current assets included in operating NWC. |
| `other_current_assets` | Separate frozen current assets, excluded from operating NWC. |
| `net_ppe`, `net_intangibles` | Opening net PPE and finite-lived intangible assets with explicit rollforwards. |
| `other_noncurrent_assets` | Frozen balance, potentially containing goodwill, ROU assets and other separately identified items. |
| `accounts_payable`, `operating_accruals` | Operating liabilities included in operating NWC. |
| `other_current_liabilities`, `other_noncurrent_liabilities` | Separate frozen liabilities excluded from operating NWC. |
| `debt` | Aggregate funded debt, without a current/noncurrent split. |
| `equity`, `retained_earnings` | Total shareholder equity and retained earnings. Other equity is their difference. |
| `shares` | Actual outstanding common shares, not an EPS weighted-average input. |
| `tax_loss_carryforward` | Opening nominal tax losses used only under the specified simplified convention. |

Opening assets must equal liabilities plus equity within numerical tolerance.
Normalization must preserve an independently reconciled source balance sheet.
Moving an item into a frozen balance is an assumption about its future behavior,
not a claim that it lacks economic value or requires no diligence.

### Annual drivers

| Field | Meaning and bounds |
| --- | --- |
| `period_end` | Exact annual anniversary. |
| `revenue_growth` | Growth from the previous year's sales; greater than -1 and no more than 3. |
| `gross_margin` | **Pre-D&A** gross margin, 0–1. It is not automatically identical to a reported GAAP margin. |
| `ebitda_margin` | EBITDA/sales, -1–1 and no greater than pre-D&A gross margin. |
| `depreciation_rate` | Depreciation/opening net PPE, 0–1. |
| `amortization` | Cashless expense on opening finite-lived intangibles; cannot exceed their opening carrying value. |
| `capex_pct_revenue`, `intangible_capex` | PPE additions/sales (0–1) and explicit intangible additions. All additions occur at year end. |
| `receivable_days`, `inventory_days`, `payable_days` | Receivables/sales, inventory/COGS and payables/COGS on a 365-day basis; 0–3650 days. |
| `operating_other_current_assets_pct_revenue`, `operating_accruals_pct_revenue` | Operating balance/sales ratios, 0–1. |
| `tax_rate`, `nol_utilization_limit` | Tax rate and fraction of positive pretax income usable against opening NOLs, each 0–1. |
| `interest_rate` | Annual interest/opening funded debt, 0–1. |
| `debt_issued`, `debt_repaid` | Explicit year-end financing flows. Repayment cannot exceed opening debt plus issuance. |
| `dividend_payout` | Fraction of positive net income distributed at year end, 0–1. Loss years pay zero under this convention. |
| `stock_compensation_pct_revenue` | SBC/sales, 0–1 and no greater than total pre-D&A operating expense/sales. |
| `stock_compensation_share_price` | Positive assumed issue price for immediately settled equity awards. |
| `equity_issued`, `issuance_share_price` | Cash equity proceeds and positive issue price. |
| `shares_repurchased`, `repurchase_share_price` | Actual share count repurchased and positive repurchase price; closing shares must remain positive. |
| `minimum_cash` | Required ending cash. A shortfall does not cause automatic borrowing. |

All three share-price inputs remain required and positive even in a period with
zero related transactions. The specification keeps those assumptions explicit
and avoids interpreting a blank or zero price as a funding source.

## Statement construction

Forecast COGS and gross profit are before D&A. EBITDA equals revenue times its
assumed margin. Pre-D&A operating expense is gross profit less EBITDA and
includes SBC. All modeled depreciation and amortization are then deducted to
obtain EBIT. This presentation does not invent an allocation of historical D&A
between reported COGS and SG&A.

Interest is opening funded debt times the annual rate. All financing flows occur
at year end, so there is no interest/debt/cash-sweep circularity. Interest income,
capitalized interest, financing fees, interest-deduction restrictions and
intra-year funding are outside this module.

```text
pretax income = EBIT − opening debt × interest rate
NOL generated = max(−pretax income, 0)
NOL used = min(opening NOL, max(pretax income, 0) × utilization limit)
tax = (max(pretax income, 0) − NOL used) × tax rate
closing NOL = opening NOL + NOL generated − NOL used
net income = pretax income − tax
```

This assumes book pretax income equals taxable income except for NOL use. Losses
receive no immediate tax credit. There is no loss expiry, ownership-change
limitation, group relief, jurisdictional allocation, deferred-tax recognition or
other tax-basis difference. The utilization percentage is an assumption, not an
automatically applied legal rule. Tax expense equals cash tax in this scope.

Operating NWC equals receivables, inventory and operating other current assets,
less accounts payable and operating accruals. The four explicitly frozen
asset/liability balances stay constant. PPE and finite intangible balances roll
forward from additions and their respective expenses.

```text
CFO = net income + depreciation + amortization + SBC − change in operating NWC
CFI = −PPE additions − intangible additions
CFF = debt issued − debt repaid − dividends + cash equity issued − repurchase cost
closing cash = opening cash + CFO + CFI + CFF
closing retained earnings = opening retained earnings + net income − dividends
closing other equity = opening other equity + SBC + cash equity issued − repurchase cost
closing shares = opening shares + SBC/award price + cash equity/issue price − shares repurchased
```

SBC is an expense already included in EBITDA, a noncash addback in statement CFO,
an equity credit and an issuance of new shares. The simplifying settlement
assumption is immediate year-end delivery of common shares at the specified
price. Vesting, options, repurchase-to-offset policies, net settlement and their
tax effects require a richer equity schedule. Since every modeled share change
occurs at year end, EPS uses opening shares as the weighted-average count.

The model also returns conservative economic `fcff`: EBIT less tax on positive
EBIT, plus D&A, less total capex and change in operating NWC. **SBC is not added
back to this FCFF**, and levered NOL benefits are not inserted into it. The
statement CFO/FCFE and this compensation-expense FCFF therefore deliberately
have different treatment of equity awards. Do not subtract the same future
award dilution again from a valuation that has already retained compensation as
an expense without separately reconciling that treatment.

Method context: CFA Institute describes linked financial statements as a
foundation for company valuation and distinguishes free cash flows from earnings
proxies. The detailed timing, tax and SBC policies here are explicit project
conventions, not prescriptions from those readings:
[financial statement modeling](https://www.cfainstitute.org/insights/professional-learning/refresher-readings/2026/introduction-to-financial-statement-modeling)
and [free cash flow valuation](https://www.cfainstitute.org/insights/professional-learning/refresher-readings/2026/free-cash-flow-valuation).

## Read the result

`forecast` contains flat annual records. Every record includes the common
operating keys `year`, `period_end`, `revenue`, `cogs`, `ebitda`, `ebit`,
`depreciation`, `amortization`, `stock_compensation`, total `capex`, `delta_nwc`,
`tax_rate` and `nol_utilization_limit`. Separate `ppe_capex` and
`intangible_capex` explain total investment. Balance-sheet keys use the opening
names, with derived totals and schedules. The cash-flow fields are
`cash_from_operations`, `cash_from_investing`, `cash_from_financing`,
`change_in_cash` and ending `cash`.

Each year's `checks` exposes an independent residual and a numerical tolerance
for the income statement, balance sheet, operating cash flow and cash, PPE,
intangibles, debt, equity, retained earnings, shares and NOL rollforwards. The
tolerance is `1e-12` times the largest absolute component in that identity; it
has no fixed dollar floor and is not an accounting materiality threshold.

Cash-versus-minimum comparisons separately expose `cash_roundoff_tolerance`:
eight units in the last place of the local opening cash, cash-flow sections,
minimum cash and ending cash. A gap below that numerical resolution is not
reported as a financing shortfall. This avoids a false shortfall when arithmetic
at a zero-cash boundary is rescaled. The raw calculated cash remains visible;
there is no absolute-dollar allowance or accounting-materiality claim.

The report's `checks.all_reconciled` summarizes arithmetic identities. A
`calculated` status means those identities reconcile and specified minimum cash
is met; it does not mean the assumptions, source facts, loan availability or
institutional use are approved. If minimum cash is unmet, status becomes
`funding_shortfall`. Negative cash remains visible as an unfunded gap and later
periods are explicitly mechanical projections. No cash, debt or equity plug
balances the model. Unexpected identity failures produce `reconciliation_error`.

Run the focused verification with
`python -m unittest discover -s tests -p test_corporate_model.py -v`.
