# Institutional readiness and coverage

Assessment date: **November 21, 2026**. Status: **research prototype; institutional use has not been validated or approved**.

This document defines a higher development target for the valuation feature. It separates implemented behavior, missing coverage, proposed acceptance evidence and employer authorization. It is a project specification and assessment, not a certification, legal opinion, independent model-validation report or claim that the future modules already exist.

## 1. What the current build can support

The current code supports learning, inspectable research calculations and a demonstration of software engineering around valuation. A professional user can examine its formulas and restricted cases. Using a result in an employer's research, client work, reporting or capital decision requires the applicable software, data, security and model-review processes, as well as validation for that particular use.

The implemented financial models are unlevered corporate FCFF and aggregate property NOI DCF. There are scenario reruns, sensitivity tables, a scalar reverse-growth solver, source-consistency checks, entry-price rules, optional research sizing and saved snapshots. See the [feature guide](valuation.md), [mathematical specification](guides/valuation.md), [decision layer](../pilot/valuation_layer.py) and [snapshot store](../pilot/valuation_store.py).

The current examples do not establish an independently verified company valuation. The Nvidia workbook is a numerical reproduction with unresolved input-quality questions; the business and property examples are synthetic. Reproducing a workbook and passing code tests demonstrate specific behaviors, not the economic truth of the source assumptions.

Deterministic code is appropriate for reproducible calculations. It still requires correct accounting, an appropriate method, reliable data, numerical verification and qualified judgment. AI assistance with development or review does not supply institutional approval.

## 2. Define the professional use before expanding the library

The recommended first target is **fundamental corporate valuation and acquisition finance for nonfinancial operating businesses**, with detailed property underwriting as the adjacent Black River workflow. This choice follows the project's acquisition purpose. It is a proposed scope; it does not establish readiness for a particular employer or desk.

A current first-party J.P. Morgan analyst description lists three-statement, DCF, comparable-company, precedent-transaction, LBO and merger-related modeling, together with Excel and presentation skills. It is evidence of one role's breadth, not a universal checklist for every finance job. [Employer example](https://jpmc.fa.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CX_1001/job/210800574/?keyword=Data+Analyst).

The following coverage map is a proposed product boundary. Each extension needs its own specification and validation cases.

| Workstream | Coverage to build and demonstrate | Current position |
| --- | --- | --- |
| Fundamental equity research | Historical financials; linked statements and business drivers; diluted earnings/share schedules; FCFF/FCFE; appropriate peer and sector valuation; valuation reconciliation and investment explanation. | Restricted FCFF, scenarios and sensitivities exist. Linked accounting, market comparables and sector models are missing. |
| Investment banking and M&A | Corporate valuation; trading comparables; precedent transactions; sum-of-the-parts; sources and uses; financing; purchase accounting; combined pro forma statements; synergies; accretion/dilution. | A generic enterprise-to-equity bridge exists. Transaction models are missing. |
| Private equity and LBO | Entry financing/fees; operating forecast; debt tranches and interest; amortization; minimum cash/revolver; cash sweep; exit bridge; investor cash flows; MOIC/IRR and attribution. | Unlevered value does not establish sponsor returns or financing feasibility. |
| Corporate and private credit | Cash generation; liquidity runway; leverage/coverage; maturities/refinancing; covenants; collateral/seniority; recovery. Calibrated default-loss estimation is a separate extension. | The current engine has no loan schedule, covenant or recovery model. |
| CRE acquisitions | Rent roll; lease expiration; vacancy/concessions; operating costs; taxes/insurance; TI/LC/capex; debt/refinance; DSCR/LTV/debt yield; dated investor returns. Add development draws and waterfalls when required. | Aggregate NOI DCF is available for a narrow screen. Lease-level and financing models are missing. |
| Rates and fixed income | Instrument schedules; calendars/day counts; accrued interest; clean/dirty price; curve construction/repricing; duration, convexity, DV01 and key-rate risk. | Outside current scope. |
| Options and structured products | Contract/exercise conventions; appropriate no-arbitrage models; volatility inputs/calibration; Greeks; convergence and hedging checks. Structured products require additional instrument-specific treatment. | Outside current scope. |
| Systematic investment research | Point-in-time data; research/backtest separation; leakage/survivorship controls; portfolio construction; exposures; turnover/cost/borrow assumptions; robustness and out-of-sample analysis. | Scenario analysis is not a backtesting or portfolio-risk system. |

The [CFA statement-modeling reading](https://www.cfainstitute.org/insights/professional-learning/refresher-readings/2026/introduction-to-financial-statement-modeling) treats forecasts of all three financial statements as a foundation for company valuation. Separate primary readings describe [free-cash-flow valuation](https://www.cfainstitute.org/insights/professional-learning/refresher-readings/2026/free-cash-flow-valuation), [private equity](https://www.cfainstitute.org/insights/professional-learning/refresher-readings/2026/private-equity), [corporate credit](https://www.cfainstitute.org/insights/professional-learning/refresher-readings/2026/credit-analysis-for-corporate-issuers), [private real estate](https://www.cfainstitute.org/insights/professional-learning/refresher-readings/2026/private-real-estate-investments), [rates](https://www.cfainstitute.org/insights/professional-learning/refresher-readings/2026/term-structure-and-interest-rate-dynamics), [options](https://www.cfainstitute.org/insights/professional-learning/refresher-readings/2026/valuation-contingent-claims) and [active equity research](https://www.cfainstitute.org/insights/professional-learning/refresher-readings/2026/active-equity-investing-strategies). These support choosing modules by assignment; adding an options model would not repair missing corporate accounting schedules.

## 3. Material limits in the current code

### Accounting and financing

Corporate reinvestment currently uses a sales-to-capital relationship. It does not produce separate capex, depreciation, working-capital and balance-sheet schedules. Taxes on operating losses are floored at zero; there is no tax-loss carryforward model. Debt and shares are opening valuation inputs, without a dynamic financing, repayment, dilution or repurchase schedule.

Property cash flows are before investor income tax and debt service. Subtracting outstanding debt in the equity bridge does not compute annual cash available for distribution, DSCR, a refinancing gap, levered IRR or a lender's covenant position. Those need actual financing cash flows and dates.

Claims have unique IDs and their aggregate bridge amounts reconcile. That does not establish whether an obligation belongs in the cash flows, the bridge, both through different economic components, or a contingent scenario. Economic classification remains a review task. The register cannot identify a hidden duplicate obligation entered under unrelated names.

### Method and timing

The forecast uses annual end-of-year discounting, with optional annual paths. It has no calendar-aware stub periods, quarterly cash flows, midyear convention, or currency conversion. WACC is supplied; there is no independent construction of risk-free rates, beta, risk premiums, debt cost or market capital weights.

Corporate terminal growth must be nonnegative and terminal NOPAT positive. Negative equity values are retained rather than valued as a limited-liability option. The model does not automatically switch to a liquidation, restructuring or financial-institution method. A supported mathematical input range is not an economic endorsement of every value inside that range.

The reinvestment multiplier can be zero, including with positive terminal growth, with a warning. A professional use profile must challenge the implied capital productivity and determine whether the case is admissible. The present warning is not evidence that positive growth without investment is sustainable. Temporary growth changes also alter the subsequent revenue base; the model does not invent catch-up growth.

The reverse solver tests sampled monotonicity within chosen bounds. It cannot prove a globally unique economic solution. A solved implied growth rate is an assumption consistent with the model and price, not a prediction of realized growth.

### Risk and decision semantics

The API field `downside_probability` is the sum of supplied scenario weights whose modeled present equity value is below the comparison price. There is no estimated probability distribution of future total returns, common realization horizon, or calibration to market outcomes. It must be described as **scenario weight below the comparison price** in professional use. It is not VaR, expected shortfall, a probability of default or a guaranteed chance of losing money.

The optional sizing bound uses the most adverse included positive-weight scenario. Omitted events, liquidity, correlations, gap risk, financing terms and market-price behavior can cause different losses. A positive DCF value does not demonstrate realizable liquidity or sufficient cash to service a loan. Buyable/fundable/sellable are supported declarations awaiting review; the layer does not prove the underlying assertions.

### Data and operational evidence

Source review is a user assertion. A source URL and observation date do not bind each financial number to a document location, publication timestamp, security identifier or transformation. The current asset ID is a stable local identifier; it does not reconcile an issuer, share class, filing and market quote against a security master.

Only date-level observation fields and USD inputs are supported. There is no filing ingestion, restatement management, authorized quote feed, market-session handling, corporate-action adjustment or point-in-time data store.

Snapshot digests bind the request and a model-version label. They do not independently authenticate every financial output, prove a source's truth, bind the executable code/dependency environment, or prevent a privileged database operator from changing data and checksums together. The local session service and SQLite store are not evidence of enterprise access, disaster recovery or records-governance acceptance.

Browser verification and hosted CI remain outstanding for the first draft. A launch restriction must remain visible as an incomplete gate, not be counted as a passed UI test.

## 4. Acceptance evidence for the first professional module

These are proposed project gates, not regulator-issued requirements. The employer may set different controls and tolerances. A module advances only with recorded evidence for its defined use.

| Gate | Required deliverable | Acceptance evidence |
| --- | --- | --- |
| Intended use | Model specification and supported-use profile. | Named instrument/company types, currency, timing, valuation basis, users, output decisions and exclusions. An unsupported case is rejected or routed to another method. |
| Data lineage | Reviewed financial dataset and source map. | Material inputs trace to entity/security, source document, location, period, publication/retrieval time, scale, currency and transformation. Actuals, estimates and judgments are distinguishable. |
| Accounting integrity | Historical normalization and linked forecast. | Balance sheets balance; beginning-to-ending cash, debt, retained earnings and shares roll forward; financing and operating flows reconcile; no unexplained plug masks an error. |
| Mathematical verification | Separate reference calculations and benchmark report. | Intermediate forecasts, taxes, investments, discount factors, terminal value and equity bridge agree within specified tolerances. Benchmark construction is not a copy of the implementation under test. |
| Economic challenge | Qualified reviewer assessment. | Method choice, reinvestment, discount rate, terminal economics, dilution, claims and adverse cases are challenged. Material disagreements and overrides are resolved or explicitly limited. |
| Output usability | Analyst workbook and review memo. | A reviewer can inspect sources, assumptions, formulas, scenarios, checks and conclusions. Exported outputs reconcile to the engine, and any workbook formulas are recalculated and verified. |
| Reproducibility/change | Versioned release and evidence package. | Source snapshots, request, result, code commit, model configuration, runtime/dependencies and reviewer decisions can be reconstructed. Changes invalidate affected approvals and trigger relevant checks. |
| Operational readiness | Approved deployment and support procedure. | Integration/browser tests pass in the supported environment; identities/permissions, backup/restore, incidents, rollback, data access and employer review are addressed. |

A test count alone does not close these gates. A test that copies the same equation with the same assumptions may simply repeat the same error. Broader testing is justified by a material use or failure mode, not by an arbitrary target number of tests.

### Concrete accounting and calculation checks

The first reference pack should include a hand-solvable zero-growth business. With perpetual FCFF of $100 and a 10% discount rate, operating value is $1,000. Adding $20 of excess cash and subtracting $120 of debt gives $900 of equity; ten shares give $90 per share. Intermediate forecast-plus-terminal calculations should reconcile to that result without relying on the application's own formula as the expected answer.

Additional cases should isolate working-capital investment, capex/depreciation, tax losses and their use, debt maturities, fees, cash sweeps, new equity, dilution, negative interim cash flows and alternative terminal methods. Each supported convention needs an independently specified expected result. Cases outside scope should identify the missing method, rather than silently substituting a generic result.

Scaling tests should preserve economic decisions when monetary inputs and comparison prices are rescaled consistently. They must not treat a fixed absolute tolerance as negligible for every allowed unit price. Boundary tests should cover exact entry thresholds, zero and negative values, high claim balances, terminal-rate limits and inverse roots. Directional expectations must be conditional: higher growth does not always create value when its reinvestment economics are poor.

## 5. Data and financial-model architecture to add

The next complete workflow should begin with historical statements rather than a manually entered revenue number. A proposed input record contains an issuer/security ID, financial concept, amount, currency, scale, period start/end, fiscal period, source filing/accession, source location, publication time, retrieval time, any restatement status, transformation and reviewer attribution.

The SEC supplies submissions and XBRL APIs, including company-level facts. Its aggregate XBRL endpoints have taxonomy/context limits, and fiscal periods need careful interpretation. They are useful source inputs, not a substitute for analyst reconciliation. The project would preserve filing availability dates and avoid using later restatements in an earlier analysis. [SEC EDGAR API documentation](https://www.sec.gov/search-filings/edgar-application-programming-interfaces).

The forecast would connect operating drivers to revenue, expenses, working capital, capex/depreciation, taxes, financing and equity accounts. Separate schedules would produce the income statement, balance sheet and cash-flow statement, and then derive valuation cash flows. Model outputs must explain which amounts belong to operations and which are available to equity after financing.

For the first corporate release, a comparison module should align peer fiscal periods, currencies, numerator/denominator definitions and one-off adjustments. An equity bridge should separately identify cash, debt, leases, minority interests, preferred claims and other material adjustments. A share schedule should explain basic versus diluted counts, options, convertibles, issuance and repurchases where applicable. Different methods should produce an explained range, not an unexamined average.

Financial institutions, REITs, resource companies and other specialized businesses need explicit sector methods. Examples include residual-income/distribution models or REIT NAV and FFO/AFFO comparisons. The generic sales-to-capital model should not acquire an all-sector label merely because it accepts the inputs.

An Excel output layer is a priority for the initial corporate/transaction scope. It should provide source inputs, historical and forecast statements, schedules, assumptions, valuation, scenarios and checks in a reviewer-readable form. A PDF or presentation brief can explain the recommendation and its weaknesses. JSON remains the machine-readable record; neither a formatted workbook nor a polished memo establishes validity by appearance alone.

## 6. Transaction and asset extensions

After the accounting and valuation foundation passes its gates, M&A modeling can add consideration mix, financing/fees, purchase accounting, incremental depreciation/amortization, synergies and combined statements. Accretion/dilution should be calculated from explicit combined earnings and shares, with the economic value conclusion assessed separately.

LBO modeling can reuse the operating forecast but requires actual entry funding, tranche terms, interest, mandatory repayment, revolver behavior, cash sweeps, minimum liquidity, exit debt and dated sponsor cash flows. Report MOIC and IRR with their cash-flow basis and timing. Multiple or absent IRR roots must be handled explicitly. Investor waterfalls and fund economics belong in separate, documented modules.

CRE underwriting should introduce lease-level revenues and costs, contractual dates, vacancy/renewal assumptions, TI/LC, maintenance and growth capex, debt service and refinance. Property value, distributable cash, lender coverage and investor return are different outputs. Development adds draw schedules, interest capitalization, absorption, delivery milestones and completion risk.

Credit should reuse the cash and debt schedules, then add covenant definitions, maturities, collateral and recovery assumptions. Probability-of-default or expected-loss outputs require separately specified estimation and validation. Rates/options and systematic research should have distinct instrument/data contracts and benchmarks; they cannot be validated by the corporate DCF tests.

## 7. Governance benchmark and limits

As of this assessment, the Federal Reserve's April 17, 2026 [SR 26-2](https://www.federalreserve.gov/supervisionreg/srletters/SR2602.htm) supersedes SR 11-7 and SR 21-8. Its stated relevance is principally banking organizations above $30 billion in assets. It is not a universal certification standard for finance software.

The [guidance](https://www.federalreserve.gov/frrs/guidance/supervisory-guidance-on-model-risk-management.htm) is risk-based and nonbinding. It emphasizes purpose, conceptual soundness, effective challenge, validation and monitoring. Deterministic code applying financial theory is not automatically equivalent to an excluded simple arithmetic tool. Classification and controls depend on the institution and use.

[CFA Standard V(A)](https://www.cfainstitute.org/standards/professionals/code-ethics-standards/standards-of-practice-v-a) provides a diligence benchmark for CFA members/candidates, including understanding models and their limitations. [ICAEW's Financial Modelling Code](https://www.icaew.com/-/media/corporate/files/technical/technology/excel/financial-modelling-code.ashx) is a useful principles-based modeling reference. Neither document certifies this implementation. The acceptance gates above are this project's proposed engineering and review standard.

AI review can help find defects and prepare evidence. Professional model acceptance also needs qualified, sufficiently objective human challenge and the employer's applicable approval. A user marking a source reviewed is not the same as an independently validated institutional dataset.

Monitoring a fundamental model should track forecast revenue, margins, investment, financing and cash flows against later observations and investigate deviations. A subsequent stock price alone is not observable ground truth for intrinsic value. A profitable investment does not prove that the model was sound; a loss does not by itself identify which assumption failed.

## 8. Build order and promotion rule

1. **Harden the present research module.** Correct identified defects, clarify output semantics, retain scope limits, complete the supported-environment test gate and assemble independent reference cases.
2. **Deliver one complete corporate case.** Source and normalize a nonfinancial company's historical statements; construct a linked forecast; reconcile DCF and comparables; export the workbook and memo; obtain independent challenge.
3. **Add acquisition finance.** Demonstrate a balanced sources-and-uses schedule, debt/cash roll-forwards, sponsor cash flows and return sensitivities on a fully reviewable transaction case.
4. **Extend by desk.** Add M&A, detailed CRE, credit or another selected module with separate acceptance evidence. Expand the supported-use register only after that module passes.
5. **Obtain employer acceptance for intended use.** Validate the actual deployment, data, permissions, outputs and operating process. A project's internal completion label cannot authorize use inside a firm.

No completion date, employment outcome or investment return is promised by this sequence. The definition of done is a defensible, reproducible result for a named assignment, with the assumptions and limits a reviewer needs to challenge it.

## 9. Numerical review change in this iteration

The stricter review identified an absolute dollar tolerance that could overwhelm a valid very small per-unit value in entry-price and scenario comparisons. The corrected comparison uses a relative tolerance without an absolute-dollar floor. Regression cases include a price ten times modeled value and economically equivalent cases at different scales.

Claim reconciliation now uses accurate summation and a relative numerical tolerance without a fixed dollar floor. A positive balance cannot reconcile to zero, and claims above the declared balance beyond numerical tolerance are rejected at each tested scale. This numerical tolerance is separate from an analyst's accounting-materiality judgment.

The reverse-growth solver now combines a target-relative tolerance with a local floating-point roundoff allowance and reports the achieved price tolerance. Tests cover scaled roots, out-of-range targets, a flat curve and a zero target with distant extreme sample values. The method and its limits are documented in [the mathematical specification](guides/valuation.md).

The model version advances to `br-valuation-2` so revised behavior is distinguished from saved version-one results. This is a bounded numerical correction with targeted verification. It does not implement the missing statement, transaction, sector or enterprise-control modules described above, and it does not change the prototype's institutional-readiness status.
