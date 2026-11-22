# Follow acquisition financing and sponsor returns

Open [acquisition_finance.py](../../pilot/acquisition_finance.py). Begin at `evaluate_acquisition`: follow the entry funding bridge, annual cash and debt waterfall, exit debt repayment and sponsor receipts. The public functions are `evaluate_acquisition(opening, operating_forecast, terms)` and `annual_irr(cash_flows)`.

The module is an annual hypothetical financing model for an operating-business acquisition. It is not a lender commitment, purchase-accounting model, merger model, credit-loss model, tax opinion or execution system. Outputs always set `execution_allowed` to false. General valuation and buyout context is described in CFA Institute's [free-cash-flow valuation](https://www.cfainstitute.org/insights/professional-learning/refresher-readings/2026/free-cash-flow-valuation) and [private-equity](https://www.cfainstitute.org/insights/professional-learning/refresher-readings/2026/private-equity) materials; the exact timing and conventions below are this implementation's specified choices.

## Input contract

Amounts are **absolute USD**, rates are decimal fractions and periods are ISO dates. Inputs are not mutated. Opening and terms objects reject unknown keys and missing required keys. Booleans, strings, nonfinite values and amounts outside the documented numeric envelope are rejected. Rates range from zero to one; ordinary monetary inputs range from zero to `1e15`. Signed forecast EBIT, EBITDA and working-capital changes may range from `-1e15` to `1e15`.

`opening` requires the first four fields below and permits the optional `other_claims` field:

| Key | Meaning |
| --- | --- |
| `period_end` | Time-zero financial date, in `YYYY-MM-DD` form. |
| `cash` | Acquired cash used in the equity purchase price and closing funding bridge. |
| `debt` | Interest-bearing debt repaid at closing. It is not left in the new debt schedule. |
| `tax_loss_carryforward` | Assumed available opening loss allowance. The module does not verify legal availability after a change of control. |
| `other_claims` | Optional nonnegative debt-like claims, default zero. They reduce seller equity consideration and are separately settled at face amount at close. This is an explicit settlement assumption; it does not estimate a tax authority's or other claimant's actual settlement. |

`operating_forecast` contains one to ten annual rows. Required fields are `year`, `period_end`, `revenue`, `cogs`, `ebitda`, `ebit`, `depreciation`, `amortization`, `stock_compensation`, `capex`, `delta_nwc` and `tax_rate`. Full output rows from the linked-statement engine can be supplied: additional statement fields are deliberately ignored by this financing function. Required fields are validated. In particular, EBITDA must reconcile to EBIT plus depreciation and amortization within local floating-point resolution. Capex means the **total** physical and intangible cash investment.

Years are consecutive integers starting at one. Each date must be an anniversary of the original opening date. A February 29 opening maps to February 28 in nonleap years and returns to February 29 in leap years. This is an equal-annual-period model, not actual-day XIRR or a stub-period model. A case prepared with later-published financial statements must not be labeled as a trading decision made before those statements became public.

`terms` requires the following keys:

| Key | Convention |
| --- | --- |
| `entry_enterprise_value` | Positive operating-business value, excluding all cash and interest-bearing debt. |
| `transaction_fee_rate` | Closing cash fee as a fraction of entry enterprise value. |
| `financing_fee_rate` | Closing cash fee as a fraction of initial term debt. |
| `initial_term_debt` | New term principal funded at closing. Initial revolver debt is zero. |
| `term_interest_rate` | Annual cash interest on opening term principal. |
| `term_amortization_rate` | Scheduled annual principal as a fraction of original term debt, capped by remaining principal. |
| `term_maturity_year` | Integer from one to 30. Earlier-than-exit maturity requires full principal repayment in the annual waterfall. A maturity coincident with exit settles the residual balloon in the same modeled sale transaction. |
| `revolver_limit` | Maximum outstanding revolving principal. No extra financing is invented above this limit. |
| `revolver_interest_rate` | Annual cash interest on opening revolving principal. |
| `minimum_cash` | Cash retained or funded at close and preserved by the annual repayment waterfall. |
| `cash_sweep_rate` | Fraction of cash above minimum cash, after mandatory term and revolving repayment, applied to optional term repayment. |
| `exit_ebitda_multiple` | Positive exit multiple, at most 100, applied to final modeled EBITDA. |
| `exit_fee_rate` | Cash fee as a fraction of exit enterprise value. |
| `nol_utilization_limit` | Fraction of positive annual pretax income eligible for the assumed loss allowance. This is a model parameter, not an automatically applicable tax rule. |

Optional `max_net_leverage` and `min_interest_coverage` are either null/omitted or positive ratios up to 100. They apply to each annual forecast period. Setting them does not establish the actual wording of a credit agreement.

## Entry funding bridge

The seller equity price is:

`entry enterprise value + acquired cash - existing debt - other debt-like claims`

Uses are seller equity consideration, repayment of existing debt, separate settlement of other declared debt-like claims, transaction fees, financing fees and any cash top-up required to reach minimum operating cash. Sources are new term debt, the acquired cash **above** minimum operating cash, and the sponsor contribution. Acquired cash below the reserve cannot fund the purchase. Claims are not deducted a second time in the annual or exit schedules.

This yields the independent funding identity:

`sponsor equity = entry enterprise value + minimum cash + transaction fees + financing fees - new term debt`

For example, EV of $100, acquired cash of $20, existing debt of $10, $60 of new debt, a $5 reserve, $2 of transaction fees and $0.60 of financing fees require $47.60 of sponsor equity. Seller proceeds are $110; the old lender receives $10. The $15 of acquired cash used as funding is counted once. Reducing acquired cash to $2 changes seller proceeds to $92 and adds a $3 reserve top-up, without changing sponsor funding. With EV unchanged, adding a $7.25 debt-like claim reduces seller proceeds to $102.75 and adds a separate $7.25 settlement use; sponsor funding remains $47.60.

This convention treats **all** cash as outside enterprise value, including the required operating reserve. An EV definition that already embeds required cash would need a different, explicitly specified bridge. Negative seller equity and a transaction without a positive sponsor contribution are outside this module's supported scope.

## Annual financing waterfall

Each year's interest uses beginning-of-year debt. Operating cash generation is based on forecast EBIT/EBITDA and the financing model's own taxes. Debt drawings, principal payments and cash sweeps occur at year end:

1. Calculate term and revolving cash interest, pretax income and cash taxes.
2. Calculate cash flow available for debt service: EBITDA less cash taxes, total capex and the change in operating working capital.
3. Subtract cash interest and add opening cash.
4. Calculate scheduled term amortization and any maturity principal due **before** the modeled exit transaction.
5. Draw only the available revolving capacity needed to fund the reserve and mandatory principal.
6. Pay mandatory term principal only from actual modeled cash above the reserve.
7. Repay revolving principal from remaining excess cash.
8. Apply the selected cash-sweep fraction to remaining term principal, preserving the reserve.
9. Retain the remaining cash. Do not create interim sponsor distributions.

The schedule exposes every opening balance, draw, repayment, sweep and closing balance, with separate cash, term-debt and revolver reconciliation differences. `scheduled_principal_due` is the ordinary amortization obligation. `maturity_principal_due_before_exit` is the additional balloon that must be funded before the exit transaction. Their sum is `mandatory_principal_due`. Principal cannot be repaid beyond its outstanding balance. Revolver availability is assumed through the modeled exit. The annual convention does not establish sufficient intrayear or seasonal liquidity, nor does it model commitment fees or interest on a midyear draw.

If maturity occurs **before** the final model year, the full remaining principal is due in that year's operating waterfall. If maturity occurs **on the same year-end date as the modeled exit**, the waterfall first pays scheduled amortization and any available sweep; remaining principal is shown as `maturity_balloon_due_at_exit` and settled once in the exit bridge. This avoids inventing a refinancing need immediately before a simultaneous sale. It explicitly assumes that the sale closes on that maturity date. Scheduled amortization remains an operating-period obligation, and insufficient sale proceeds still produce an exit debt-repayment failure.

If capacity is insufficient, the output separately identifies cash below the minimum reserve and unpaid mandatory principal. Negative cash is a visible unfunded requirement; it is not an automatic loan. Arithmetic may continue to show the consequences, but later periods do not represent a validated post-default restructuring. Penalty rates, acceleration, lender waivers and recovery are outside scope.

## Stock compensation and tax conventions

The operating forecast's recurring stock-compensation expense is replaced with **equal cash compensation** for this hypothetical acquisition. It remains in EBIT/EBITDA and is not added back to cash flow. The sponsor is therefore not given both the cash benefit of a noncash expense and an assumption of no dilution. This differs explicitly from a standalone model that adds back stock compensation while issuing new shares.

Taxes are recalculated after the new financing interest. The simplified loss-allowance roll-forward is:

- Generated allowance: `max(-pretax income, 0)`.
- Used allowance: the lesser of opening allowance and `max(pretax income, 0) * nol_utilization_limit`.
- Taxable income: positive pretax income less used allowance.
- Cash taxes: taxable income times the annual forecast tax rate.
- Closing allowance: opening allowance plus generated allowance less used allowance.

Losses generate no cash refund. Interest is assumed fully deductible. The model omits jurisdictional tax differences, interest limits, expiration/vintage restrictions, change-of-control limits, deferred-tax accounting, tax deductions for transaction fees and financing-fee amortization. An actual transaction requires those assumptions to be replaced or independently supported.

## Coverage ratios and constraints

Ratios use defined denominators rather than substituting another metric:

| Output | Definition |
| --- | --- |
| `net_leverage` | Ending term plus revolving debt, less **all** ending cash, divided by annual EBITDA. Unavailable when EBITDA is nonpositive. |
| `interest_coverage` | Annual EBITDA divided by annual cash interest. Unavailable when interest is zero. |
| `debt_service_coverage` | Cash flow available for debt service divided by cash interest plus required term principal **before the exit transaction**. Voluntary revolver repayments, sweeps and a balloon settled in the coincident exit transaction are excluded. An earlier maturity balloon is included. Unavailable when this period debt service is zero. |

The optional net-leverage limit fails when EBITDA is nonpositive and that ratio cannot be established. The optional interest-coverage minimum is evaluated when cash interest is positive. A relative `1e-12` tolerance absorbs equality-boundary roundoff; it is not a covenant waiver or accounting materiality threshold.

Any annual funding or configured covenant failure remains visible even if later projected conditions improve. Unsupported nonpositive terminal EBITDA and insufficient exit proceeds to repay the remaining debt also prevent a feasible-return presentation.

## Exit and investor returns

Exit enterprise value equals final EBITDA times the assumed exit multiple. Exit fees are deducted once, ending cash is added once, and outstanding term and revolving principal are deducted once. When maturity coincides with exit, `term_maturity_settlement` identifies the residual balloon within `term_debt_payoff`; it is a memo component, not a second deduction. The report preserves equity before a limited-liability floor, the resulting sponsor proceeds, and any debt-repayment shortfall. It does not model recovery allocation among lenders.

When all modeled financing and exit conditions pass, sponsor cash flows contain the negative closing contribution, zero interim distributions and the final equity receipt. MOIC is total sponsor proceeds divided by the contribution. `annual_irr` solves the equal-period conventional cash-flow equation in log space; monetary scaling leaves the result unchanged. A unique root is supported only for one initial negative contribution followed by nonnegative receipts. Other sign patterns return `unsupported_cash_flow_pattern`. No receipts produce an explicit `total_loss` result with a -100% annualized boundary convention, not a claimed finite NPV root.

When funding, a configured covenant, or exit debt repayment fails, sponsor cash flows, MOIC and IRR are withheld. Exit arithmetic remains available with `indicative_only` set to true. Even `modeled_feasible` means only that the specified numerical conditions pass; it does not verify that a seller accepts the price, a lender provides the financing, or an exit buyer exists.

## Verification

Run `python -m unittest discover -s tests -p test_acquisition_finance.py -v`. The tests use hand-calculated funding, cash, principal and return examples, separate return-root checks, scale invariance and explicit failure cases. See [the test guide](test_acquisition_finance.md). These are software-verification cases, not independent institutional model approval.
