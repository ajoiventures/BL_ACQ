# Test the valuation formulas

From the repository root run:

```bash
python -m unittest discover -s tests -p test_valuation.py -v
```

The tests use standard-library `unittest`. They do not make network requests or
fetch quotes. Read [the financial contract](valuation.md) before changing a timing
convention: a plausible-looking answer can still use the wrong cash-flow year,
denominator, claim treatment or discount curve.

## Independent financial checks

- A level corporate perpetuity produces $150 of operating value at every tested
  horizon: $100 sales times 20% margin times 75% after-tax retention, divided by
  10% WACC. Net claims of $12 produce $138 equity and $69 for each of two units.
- A three-year example checks individual revenue and margin fade steps, positive
  reinvestment, next-year terminal NOPAT and the stable-growth/ROIC identity.
- A two-year property case checks every operating cash flow, selling costs,
  next-year NOI capitalization and end-of-horizon sale discounting.
- Different annual WACCs use their cumulative product. Lead reinvestment funds
  next-year revenue, including the terminal revenue transition in the last year.
- A source workbook regression reproduces operating value about $5.229292 trillion,
  equity about $4.850614 trillion, and $199.490586 per share from explicit historical
  paths and claims. This proves numerical reproduction only. It is not a current
  quote, a $200 price input, a $140 recommendation, or verification of the source's
  date and commitment treatment.

## Failure modes the suite protects

Losses have no automatic tax benefits and declining revenue has no automatic
capital release. Negative FCFF and equity remain visible. Temporary margin shocks
recover, temporary growth-rate recovery does not erase the lost sales base, and a
one-time cost is discounted once. Permanent margin, growth, rate and reinvestment
changes are checked in both the explicit period and terminal assumptions. Explicit
paths receive the same shocks.

The inverse tests recover known rates in increasing and decreasing value curves,
reject a value-destroying growth curve with a peak, and return no invented rate
for an unreachable target. An explicit growth path cannot silently be solved by
changing an unused scalar. Sensitivity tests prove the center equals the baseline,
invalid spreads/capitalization rates become null cells with reasons, and path
discounts shift in parallel.

Malformed fields, unknown keys, booleans, strings, nonfinite and excessive values,
bad path lengths, unsupported property margin shocks and infeasible terminal
reinvestment fail explicitly. Zero shocks reproduce the base exactly, inputs
remain unchanged, and normal model/grid outputs serialize with `allow_nan=False`.
