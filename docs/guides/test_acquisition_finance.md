# Verify acquisition financing

Open [test_acquisition_finance.py](../../tests/test_acquisition_finance.py), then run:

```sh
python -m unittest discover -s tests -p test_acquisition_finance.py -v
```

The tests exercise [the acquisition financing engine](../../pilot/acquisition_finance.py) independently of a particular issuer. They deliberately use small, hand-calculable values rather than assuming that one sourced-company run establishes correctness.

## Funding and financing benchmarks

The entry benchmark has EV $100, acquired cash $20, existing debt $10, new debt $60, minimum cash $5 and total fees $2.60. It verifies seller proceeds of $110, debt payoff of $10, cash funding of $15 and sponsor equity of $47.60. Variants change acquired cash and old debt to establish that neither is double-counted. A separate $7.25 debt-like claim reduces seller proceeds and adds a distinct settlement use without changing aggregate funding; absent claims remain equivalent to an explicit zero.

The annual benchmark has EBITDA $30, depreciation $5, capex $5 and working-capital investment $2. With $60 of opening debt at 10%, 25% taxes, $6 of mandatory principal and a full sweep, first-year cash generation after interest is $12.25 and ending term debt is $47.75. The second year ends with $34.58125 of term debt. A six-times EBITDA exit, 1% fee and $5 cash reserve yield $148.61875 of sponsor proceeds.

Other cases verify revolving draws for mandatory payments, revolving repayment before the optional term sweep, principal maturity before exit, no payment beyond outstanding debt, no invented financing above the revolving limit, NOL generation/use, and the explicit cash replacement of recurring stock compensation. A maturity coincident with exit is tested separately: ordinary amortization and the sweep occur in the annual waterfall, and the remaining $34.58125 balloon is paid once from sale proceeds. Reducing those proceeds below remaining debt still withholds sponsor returns. An earlier maturity still requires operating cash or permitted revolving funding before exit.

## Failure and numerical checks

Insufficient liquidity, unpaid required principal, configured covenant breaches and exit debt shortfalls remain visible and withhold sponsor MOIC/IRR. A later recovery cannot erase an earlier breach. Monetary rescaling from `1e-12` through `1e12` preserves financing decisions, proportional balances and return ratios.

Known annual-IRR examples include a $100 contribution with $121 received after two years, which yields 10%, and a $100 contribution with $20 and $99 receipts, which also yields 10%. Separate tests evaluate the resulting NPV. Total losses and nonconventional sign patterns receive explicit statuses rather than a guessed root. Date checks enforce annual anniversaries, including a February 29 start. Additional cases reject malformed inputs, missing/unknown terms, nonfinite values, booleans and inconsistent EBIT/EBITDA. Inputs must remain unchanged after evaluation.

These tests demonstrate the specified financial arithmetic and boundaries. They do not establish real loan terms, source accuracy, forecast accuracy or institutional acceptance. The supported assumptions and omissions are described in [the engine guide](acquisition_finance.md).
