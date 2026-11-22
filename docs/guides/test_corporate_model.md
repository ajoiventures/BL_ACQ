# Verify linked financial statements

Open [test_corporate_model.py](../../tests/test_corporate_model.py). Run
`python -m unittest discover -s tests -p test_corporate_model.py -v` from the
repository root.

The first fixture starts with $600 of assets, $250 of liabilities and $350 of
equity. Its one-year forecast is independently specified: $1,100 revenue,
$220 EBITDA, $195 EBIT, $142.50 net income, $144.50 operating cash flow,
$58 of investment and $65 of net financing outflow. Closing cash is $121.50,
debt $90, equity $448.50 and total assets $696.50. Those explicit expected
values exercise the linked statements, including dividends, stock compensation,
new equity, share repurchases and a working-capital investment.

Additional cases verify:

- Balance-sheet, cash and retained-earnings identities over several years,
  using separately assembled sums rather than only trusting the model's checks.
- SBC expense, cash-flow addback, equity credit and explicit dilution, while
  conservative economic FCFF retains SBC as a compensation cost.
- Loss-year NOL creation, limited utilization, no immediate tax credit, and the
  distinction between statement taxes and unlevered FCFF taxes.
- Opening-debt interest and year-end debt/share movements.
- Minimum-cash and negative-cash failures without an automatic balancing loan.
- Economically equivalent monetary scales from `1e-12` to `1e12`, including
  rejection of an opening imbalance at each scale, the exact zero-cash boundary,
  and a small genuine funding gap.
- Input immutability, complete schemas, finite numeric values, calendar
  anniversaries, leap years, unsupported schedules and finite derived outputs.

These are arithmetic and contract tests for the bounded model. They do not
independently verify an issuer's source data, forecasts, tax eligibility or
employer approval. See the [model specification](corporate_model.md) for the
conventions that a qualified reviewer must challenge.
