# Corporate case verification record

Date: November 22, 2026. This record describes scoped development evidence.
It is not an independent institutional model-validation opinion or a release
approval. The draft pull request records the latest hosted workflow result.

## Automated project checks

| Check | Observed result |
| --- | --- |
| Pilot/domain/API suite | 154 tests passed |
| Asset reporting suite | 9 tests passed |
| Tooling suite | 1 test passed |
| Total | **164 tests passed** |
| Ruff configured fatal-error rules | Passed |
| Existing mypy gate | Passed for its three configured source files; not comprehensive typing of the financial modules |
| Corporate browser-client syntax | `node --check web/corporate.js` passed |
| Source guides and local links | 59 source/config files and 82 Markdown documents checked; zero errors |
| Synthetic backup/recovery | Reconciliation and restoration passed |

The 71 new corporate tests comprise 13 statement tests, 24 acquisition-finance
tests, 26 case integration tests and eight real-service tests. Existing valuation
and pilot tests remain in the total. Test quantity alone does not establish model
completeness or economic validity.

## Financial benchmarks and failure cases

The statement benchmark starts with assets 600, liabilities 250 and equity 350.
Its separately specified first-year expectations include revenue 1,100, EBITDA
220, EBIT 195, net income 142.5, CFO 144.5, cash 121.5, debt 90 and equity 448.5.
The identities are checked alongside NOL behavior, share compensation and share
movements, asset schedules, explicit funding gaps, dates, invalid inputs and
scale changes. See [the statement tests](guides/test_corporate_model.md).

The zero-growth DCF reference values perpetual FCFF of 100 at 10% as operating
value 1,000. With 20 cash, 120 debt and ten shares, equity value per share is 90.
The case tests also verify units, source availability, quote dates, peer EBIT
construction and equity bridges. See [the integration tests](guides/test_corporate_case.md).

The acquisition benchmarks independently specify seller consideration, closing
cash use, fees, sponsor equity, debt repayments and exit receipts. They exercise
pre-exit maturity failure, a balloon paid at a coincident sale, insufficient sale
proceeds, capped revolver funding, minimum cash, covenant failure, zero debt,
tax-loss use and conventional IRR boundaries. A two-year coincident-maturity
fixture settles a 34.58125 balloon once and yields sponsor proceeds of 148.61875;
its returns agree with the same case whose loan matures after exit. See
[the financing tests](guides/test_acquisition_finance.md).

API checks use the real local HTTP service. They exercise authentication,
commercial scope, Origin, server-owned source facts, exact export inputs,
malformed/nonfinite/deeply nested requests, the body-size boundary, unavailable
source files, all three cases, an explicit financing failure and absence of
persistent changes. Static-asset and DOM-ID checks do not constitute browser
interaction or visual-layout verification.

## Workbook evidence

The workbook contains **1,149 live formulas in eight sheets**, with no external
workbook links. Its builder recalculates the three scenarios and makes **569
numeric comparisons** with Python; the maximum normalized discrepancy is
approximately **1.52 × 10⁻¹³**. The observed headline values are:

| Case | DCF/share | Sponsor MOIC | Annual sponsor IRR |
| --- | ---: | ---: | ---: |
| Base | 104.3416411922 | 0.951362096570 | −0.009922550488 |
| Downside | 68.1743999604 | 0.596149558994 | −0.098281364032 |
| Upside | 123.9406771587 | 1.143002610364 | 0.027092231588 |

IRR values in this table are decimal rates. The workbook also compares annual
statement and financing schedules, tests active-case switching, perturbs
later-year growth/tax and the financing interest rate, checks active versus
inactive missing inputs, restores the Base inputs and scans formulas for
errors. Missing required WACC, financing, source-cash and peer-expense inputs
also make affected outputs unavailable. Invalid margin ordering, unfunded
early maturity and insufficient exit repayment are rejected or withhold returns.
Eighteen rendered views cover all eight sheets. The final export contains zero
cached formula errors. The generated validation JSON contains exact comparisons
and perturbation observations. The
[builder guide](guides/build_corporate_workbook.md) explains reproduction.

Recalculation uses the spreadsheet artifact engine. **Native desktop Excel was
not separately exercised.** The workbook's cash-boundary allowance uses a local
relative tolerance; Python exposes a local floating-point allowance. These are
numerical-resolution conventions, not accounting materiality thresholds.

## Remaining gates

The founder browser replay cannot launch Chromium in this environment: the
process reports `socket() failed: Operation not permitted`. No workaround that
bypasses the environment restriction was used. This leaves full project-browser
acceptance incomplete. The new corporate page has service and syntax coverage,
but no completed browser interaction/visual pass or dedicated corporate replay.

The old valuation replay also remains an outstanding supported-environment
gate. A previous hosted workflow failed without exposed job steps/logs; the
current commit's hosted result must be read separately rather than inferred
from local tests.

Qualified human accounting/economic validation, verified closing data, archived
point-in-time market provenance, native workbook review, employer acceptance and
desk-specific coverage remain open. See [the case memo](corporate-case.md) and
[the coverage assessment](valuation-institutional-readiness.md).
