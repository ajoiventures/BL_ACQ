# Follow the operating value to equity

`pilot/valuation.py` is a deterministic, standard-library financial calculation.
It does not fetch prices, qualify source evidence, approve a trade, promise a return,
or write a transaction. Call it from the repository root:

```python
from pilot.valuation import value_model, reverse_growth, sensitivity_grid

assumptions = {
    "revenue": 100_000, "operating_margin": .20, "growth_rate": .08,
    "target_margin": .20, "tax_rate": .25, "wacc": .10,
    "terminal_growth": .02, "sales_to_capital": 2, "terminal_roic": .12,
    "years": 5, "cash": 10_000, "non_operating_assets": 0,
    "debt": 20_000, "debt_like_claims": 0, "units": 1,
}
base = value_model("corporate_dcf", assumptions)
inverse = reverse_growth("corporate_dcf", assumptions, None, base["value_per_unit"])
grid = sensitivity_grid("corporate_dcf", assumptions, None)
```

## Monetary and schema contract

All monetary inputs and outputs use **absolute USD**, not cents and not millions.
Convert a source reported in millions before calling this module. This differs
from the existing acquisition underwriting module, which uses integer cents.
`units` is an actual share/unit count, or `1` for a whole business. A property must
use `units=1`. Rates are decimal fractions: `.10` means 10%, not 10 basis points.
Values are floating-point estimates and are not rounded during the computation.

Every scalar key shown below is required. Unknown keys, missing keys, strings,
booleans, NaN and infinity raise `ValueError`. Inputs are not mutated. Currency
amounts are nonnegative and at most `1e15`; starting revenue/NOI and units must be
positive. Forecasts run for an integer 1-30 years. Intermediate/output values must
be finite and no greater than `1e100` in absolute magnitude.

| Corporate key | Meaning / allowed domain |
| --- | --- |
| `revenue` | Current annual sales, before forecast year 1 |
| `operating_margin`, `target_margin` | Current and stable operating margins, -1 to 1 |
| `growth_rate` | Initial forecast revenue growth, greater than -1 and at most 3 |
| `tax_rate` | Operating tax rate, 0-1; also the terminal tax rate |
| `wacc` | Unlevered operating cash-flow discount rate, 0-1 |
| `terminal_growth` | Sustainable perpetual growth, 0-.20; negative stable growth is outside this implementation |
| `sales_to_capital` | Positive revenue increase per dollar of net reinvestment, .01-100 |
| `terminal_roic` | Stable return on invested capital, greater than 0 and at most 1 |
| `years` | Explicit forecast length |
| `cash`, `non_operating_assets` | Assets not already captured by operating cash flows |
| `debt`, `debt_like_claims` | Claims deducted once in the operating-value-to-equity bridge |
| `units` | Actual denominator for equity value per unit |

The corporate model follows an FCFF framework: operating profit after tax less
net reinvestment, discounted at the cost of capital. Methodological context is
[Aswath Damodaran's DCF valuation questions](https://pages.stern.nyu.edu/~adamodar/New_Home_Page/valquestions/valquestions.htm).
The growth fade, numeric envelope, shock rules and conservative no-disinvestment
rule below are explicit implementation choices, not universal valuation rules.

## Corporate forecast and terminal timing

For two or more years, growth fades linearly from `growth_rate` in year 1 to
`terminal_growth` in the final explicit year. A one-year forecast uses initial
growth in year 1 because there is no fade interval. Margin moves toward its target
at `year / years`, so year 1 begins the margin transition and the final explicit
year reaches the target. Starting sales are multiplied by that year's growth.

```text
operating_profit[t] = revenue[t] * margin[t]
tax[t] = max(operating_profit[t], 0) * tax_rate[t]
NOPAT[t] = operating_profit[t] - tax[t]
reinvestment[t] = max(revenue[t] - revenue[t-1], 0) / sales_to_capital
FCFF[t] = NOPAT[t] - reinvestment[t] - first_year_cash_cost[t]
discount_factor[t] = product(1 / (1 + WACC[k]), k=1..t)
```

Operating losses produce neither a tax credit nor a modeled tax-loss carryforward.
Shrinking sales produce no automatic release of invested capital. Reinvestment
represents net capital expenditure plus incremental working capital; do not also
subtract those same growth investments elsewhere.

Optional `growth_path`, `margin_path`, `tax_path` and `discount_path` lists override
the relevant explicit-year scalar/fade. Each list has exactly `years` finite
numeric entries in the corresponding scalar domain. Discounts use the cumulative
product of annual rates, not the final rate raised to the year count. The last
`discount_path` entry supplies terminal WACC. Scalar `target_margin`, `tax_rate`
and `terminal_growth` still specify the terminal economics. This means a path
ending at a different margin/tax rate makes an explicit terminal transition.

Optional `reinvestment_timing` is `same_year` by default. Set it to `next_year` to
fund the following year's positive sales increase in the current year. Its final
explicit-year investment funds terminal-year sales. This convention exists for
audited source reproduction; it changes timing and must be disclosed.

```text
terminal_revenue = final_explicit_revenue * (1 + terminal_growth)
terminal_NOPAT = terminal_revenue * terminal_margin * (1 - terminal_tax_rate)
terminal_reinvestment = terminal_NOPAT * terminal_growth / terminal_roic
terminal_FCFF = terminal_NOPAT - terminal_reinvestment
terminal_value_at_year_N = terminal_FCFF / (terminal_WACC - terminal_growth)
```

The final two formulas incorporate the reinvestment shock multiplier when used.
Terminal NOPAT must be positive. Terminal WACC must exceed stable growth, and
effective terminal reinvestment cannot exceed terminal NOPAT. Base terminal ROIC
must be at least stable growth. The model does not assume that growth is free.

## Property model

Required keys are `noi`, `growth_rate`, `discount_rate`, `terminal_cap_rate`,
`annual_capex`, `selling_cost_rate`, `years`, `debt`, `cash` and `units`.
Growth has the same scalar domain as corporate growth. Discount and selling-cost
rates are 0-1; exit capitalization rate must be greater than 0 and at most 1.

NOI is current annual property operating income after property operating expenses
and property taxes, but before debt service, investor income taxes, and separately
modeled capital expenditure. Capex stays at the specified annual nominal amount
unless its shock multiplier changes it. NOI grows at the input rate throughout
the explicit forecast. The exit is valued at the end of year N from year N+1 NOI:

```text
FCF[t] = NOI[t] - annual_capex - first_year_cash_cost[t]
net_sale_at_year_N = NOI[N+1] / terminal_cap_rate * (1 - selling_cost_rate)
operating_asset_value = sum(PV(FCF[t])) + PV(net_sale_at_year_N)
equity_value = operating_asset_value - debt + cash
```

Capitalizing NOI is a market exit assumption; capex is not separately capitalized
again into that exit. Input cap rate and exit cost require independent evidence.
Property `tax=0` and `nopat=NOI` are common-schema fields and **do not assert that
the investor owes no income tax**. Margin shocks are not meaningful for an NOI-only
model and nonzero values are rejected. Change NOI or its growth instead.

## Shared shock contract

Omitting shocks, passing `None`, passing `{}`, or supplying zero deltas with a
reinvestment multiplier of one gives the same valuation.

| Shock | Application |
| --- | --- |
| `near_term_growth_delta` | Additive growth-rate change for the first `duration_years` |
| `near_term_margin_delta` | Additive corporate margin change for that same temporary period |
| `long_term_growth_delta` | Added to every explicit corporate growth rate; corporate perpetual growth stays fixed. For property, it also applies to exit-year NOI growth. |
| `long_term_margin_delta` | Added to every explicit corporate margin and the terminal margin |
| `discount_rate_delta` | Added to all annual discount rates and terminal WACC; does not change a property exit cap rate |
| `reinvestment_multiplier` | Multiply corporate explicit and terminal reinvestment, or property annual capex |
| `one_time_cost` | After-tax cash outflow deducted once in forecast year 1; no extra tax deduction is modeled |
| `duration_years` | Integer 0-30; defaults to 1. A nonzero temporary shock requires a positive duration. |

Rate/margin deltas are bounded to -1 through 1, the multiplier to 0-10, and cost
to 0-`1e15`. Effective forecast growth must remain greater than -1 and at most 5;
effective margins stay within -1 to 1 and effective discount rates within 0-1.
Shocks also apply to supplied explicit paths. A temporary growth shock changes
the revenue/NOI base permanently: later growth rates recover, but there is no
invented catch-up. A temporary margin shock recovers when its duration ends.

Doubling corporate reinvestment at fixed stable growth halves effective terminal
ROIC. A multiplier producing a terminal reinvestment ratio above 100% is rejected.
Zero reinvestment is permitted as an explicitly warned optimistic assumption;
`effective_terminal_roic` is then null rather than infinite.

## Result and claim reconciliation

`enterprise_value` means operating-asset value. `net_claims` is debt plus
debt-like claims minus cash and non-operating assets, so `equity_value` always
equals `enterprise_value - net_claims`. Property net claims are debt minus cash.
Neither negative equity nor negative cash flow is clamped to zero. This is an
asset DCF, not a limited-liability option valuation.

The result includes `value_per_unit`, `terminal_value`, `pv_terminal`,
`terminal_share`, `forecast`, `warnings` and model-specific terminal details.
`terminal_share` is null for nonpositive operating-asset value; it can exceed 1
when the explicit cash-flow present value is negative. Each forecast row records
year, revenue or NOI, growth, operating profit, tax, NOPAT, reinvestment, one-time
cost, FCF, discount rate, cumulative discount factor and present value. The unused
revenue/NOI field is null. More than 75% terminal dependence emits a review warning.

Claims must be classified by the caller. If lease payments, supply commitments,
or another obligation already reduce the modeled cash flows, deducting their
present value again can double count the burden. A numerical reproduction of a
published workbook does not resolve that accounting/economic judgment. This
module always discloses the need for separate claim review.

## Reverse valuation and sensitivity

`reverse_growth(model_type, assumptions, shock, target_price, low=-.20, high=.80)`
solves only scalar initial growth. The target uses the same per-unit denominator
as `value_model`; it is never interpreted as enterprise value. The routine first
samples 129 evenly spaced growth rates. It supports monotonic increasing or
decreasing observed curves. It returns `non_monotonic` for a sampled reversal or
flat curve, `out_of_range` when the target is outside observed bounds, and `solved`
only when a forward valuation at the implied rate matches the target within
`max(1e-8 USD, abs(target) * 1e-10)`. Invalid inputs still raise `ValueError`.

`attainable_bounds` explicitly states its sampled basis, endpoint prices and
sampled minimum/maximum. Sampling does not prove global monotonicity or economic
feasibility. A verified price match is not a growth forecast. `implied_growth_rate`
and the `implied_rate` alias stay null when no solution is returned. A supplied
`growth_path` yields `unsupported_explicit_path`: changing a scalar overridden by
the path would not define a meaningful inverse.

`sensitivity_grid` returns five rows of discount-rate shifts (-2, -1, 0, +1, +2
percentage points) and five columns of terminal-growth or exit-cap-rate shifts
(-1, -.5, 0, +.5, +1 percentage points). The center is the baseline. If a discount
path exists, each row shifts the whole curve in parallel; row values display the
effective terminal rate after shocks. Cells contain `value_per_unit` plus `reason`.
An invalid combination has null value and its validation reason, not a fabricated
number. The requested baseline itself must be valid.

Run the [valuation test guide](test_valuation.md) for formulas and audited source
reproduction. Caller-owned source evidence, decisions, persistence and approvals
must remain separate from these calculations.
