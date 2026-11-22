# Verify the sourced corporate case

Open [test_corporate_case.py](../../tests/test_corporate_case.py). From the repository
root, run:

```bash
python -m unittest discover -s tests -p test_corporate_case.py -v
```

The suite covers the adapter that joins reported historical statements, explicit
forecast assumptions, valuation, public peer comparisons and acquisition finance.
It complements the separate linked-statement and financing-engine suites. It uses
local case data and small arithmetic fixtures, without calling market-data services.

## Independent valuation benchmarks

The simplest fixture earns $133 1/3 of EBIT and pays 25% operating tax, producing
$100 of annual FCFF with no incremental investment at zero growth. At 10% WACC,
the infinite stream has $1,000 operating value. Opening cash of $20, debt of $120,
no other claims and ten shares produce $900 equity value, or $90 per share. The
expected answer stays the same with one, five or thirty explicit annual periods:
the terminal value accounts for the remaining identical stream.

A separate WACC fixture uses a 4% risk-free rate, beta 1.2 and 5% equity risk
premium: cost of equity is 10%. A 75% equity weight contributes 7.5 percentage
points; 25% debt at an 8% pretax rate and 25% tax contributes 1.5 points. WACC is
therefore 9%, and the $100 constant stream is worth $1,111.11.

The growth fixture makes the reinvestment requirement explicit. Year-one NOPAT
of $100 plus $20 D&A, less $35 capex and $5 working-capital investment, gives
$80 FCFF. With 2% terminal growth and 20% terminal ROIC, next-period NOPAT is
$102 and required reinvestment is $10.20. Terminal FCFF is $91.80, making its
year-one terminal value $1,147.50 at 10% WACC. The expected enterprise value is
`(80 + 1147.50) / 1.10`. These expectations are specified independently of the
adapter implementation.

The tests also establish that cash, debt and other claims affect equity once
without altering operating FCFF when the operating forecast and WACC are held
constant. Zero WACC, growth at or above WACC, invalid terminal ROIC, nonpositive
terminal earnings and nonfinite derived values must be rejected explicitly.

## Peer bridge benchmark

Synthetic peer A has $1,000 market capitalization, $300 debt, $20 NCI, $10
preferred stock, $30 other claims, $100 cash and $10 selected nonoperating assets.
Its enterprise value is $1,250. With $100 operating EBIT the multiple is 12.5x.
Peer B has enterprise value $2,200 and EBIT $100, or 22x. The median is 17.25x.
Applying that multiple to $100 target EBIT produces $1,725 enterprise value and
$162.50 per share after the fixture's $20 cash and $120 debt bridge.

The input deliberately mixes actual share counts and USD-per-share quotes with
statement values in USD thousands. That makes omitted NCI or claims, reversed
asset deductions, double counting and unit-conversion errors observable. The
comparison requires peer prices on the exact analysis date and rejects future
financial-publication dates, financial period ends or share-count dates.

## Historical controls and evidence eligibility

The source controls include the reported WD-40 FY2025 balance sheet and the
cash reconciliation `46,699 + 87,925 - 2,388 - 74,116 + 10 = 58,130`, in USD
thousands. Equity is separately rolled forward with income, dividends, stock
compensation, tax withholding, treasury purchases and OCI. The historical
$35,000 difference between FY2024 equity treasury purchases and cash purchases
is preserved. Tampering with a reported subtotal or total must fail even when
the model could recompute a different total from components.

Normalization must preserve the raw source dictionaries and retain the distinction
between the August 31 reported balance sheet and the October 31 hypothetical
opening. Current operating lease liabilities are reclassified once, and held-for-sale
assets and tax receivables do not become operating prepaids.

The historical vendor quote records intentionally have a null original publication
date, a dated market event and later retrieval evidence. That narrow retrospective
quote case is accepted; a null or missing filing publication date is not a general
way to bypass the analysis cutoff. The target and peer quote dates remain visible.

For the sourced peers, constructed EBIT must also reconcile to its documented
raw income lines. Changing only the saved constructed EBIT cannot silently
change the comparison multiple. In particular, Clorox's intangible amortization
inside other expense must remain in the operating-earnings bridge.

## Integrated scenarios and remaining limits

Base, Downside and Upside must preserve reported facts, reconcile their projected
statements, produce different business and valuation outcomes, and return
`execution_allowed: false`. Repeating the same inputs must reproduce the same
report and digest. A change in target other claims must reduce DCF and peer-implied
equity consistently. The acquisition treatment settles the claim at closing:
seller consideration falls while settlement rises, leaving total uses and sponsor
funding unchanged when the bid enterprise value is held constant.

Malformed public inputs must produce `ValueError` rather than a calculation that
contains NaN/infinity, a missing-field crash or a division-by-zero error. The tests
do not certify issuer disclosures, economic forecasts, fair value, tax treatment,
the completeness of closing claims, market-data vintage, employer approval or
production readiness. Source-to-cell review and the qualifications in the
[source evidence record](../corporate-source-audit.md) remain necessary.
