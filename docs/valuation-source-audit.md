# Valuation source audit

## Scope and status

The Nvidia example reproduces the saved arithmetic in Aswath Damodaran's historical model. Its status is **audited workbook reproduction / input verification hold**. This means the calculation was reproduced; company filings, obligation composition, current market price, and acquisition qualifications have not been independently verified. The original workbook is linked below and is not redistributed in this repository.

The service-business and property examples contain invented inputs. Their scenario weights are demonstrations, not forecasts or evidence of investment opportunities. Every example preserves unknown buyable, fundable, and sellable qualifications.

## Sources and dates

- [Primary author discussion, November 19, 2026](https://aswathdamodaran.substack.com/p/the-value-of-human-frailty-nvidias).
- [NYU source workbook](https://pages.stern.nyu.edu/~adamodar/pc/blog/NvidiaJensenEffect.xlsx).
- [Yahoo/Stocktwits article, November 20, 2026](https://finance.yahoo.com/markets/stocks/articles/dean-valuation-says-nvidia-30-085810133.html).

The author describes a valuation as of **October 29, 2026**. However, `Input sheet!B3` contains Excel date serial 44865, **October 31, 2022**. File metadata records modification at `2026-11-19T19:08:45Z`. The stored **$163** price has no quote timestamp. These dates are preserved as separate facts; none establishes a current market observation. The example request is evaluated as of November 21, 2026.

Source records remain unverified for investment decisions. Their explicit issues include the date conflict, unreconciled financial periods and commitments, and WACC provenance. The source quote has a null timestamp and cannot establish a current price gap. A copied historical price is never silently refreshed by the example's request date.

## Units and independently reproduced outputs

The workbook uses **USD millions and shares millions**. The JSON converts amounts to **absolute USD** and share count to **actual shares**; rates remain fractions.

| Saved result | Absolute USD, except per-share values |
| --- | ---: |
| Operating asset value | 5,229,292,259,308.031 |
| Book debt | 38,351,000,000 |
| Present value of additional commitments | 446,512,655,203.99054 |
| Minority interests | 1,558,000,000 |
| Cash | 56,586,000,000 |
| Nonoperating assets | 51,157,000,000 |
| Equity value | 4,850,613,604,104.04 |
| Actual shares | 24,315,000,000 |
| Baseline value per share | 199.49058622677524 |
| Saved replacement-case value per share | 190.57148039915842 |

The source baseline and replacement case were independently calculated from the forecast paths and equity bridge. The saved replacement assumptions reduce equity value by about **4.47094%**. The article's approximately **$140** threshold is a separate judgment, about 30% below a rounded pre-event $200 valuation. It is not the saved replacement-case output. The application's margin-of-safety policy is a separate calculation against its selected scenario-adjusted value.

## Calculation conventions

The JSON retains full-precision growth, margin, tax, and discount-rate paths for ten forecast years. Base revenue is $302.970 billion. The terminal inputs are a 50% operating margin, 25% tax rate, 4.95% growth, 12% return on invested capital, and 9% discount rate. The final explicit discount-rate entry supplies the terminal discount rate.

Reinvestment in year `t` funds the revenue increase in `t+1`, divided by a sales-to-capital ratio of `1.206668138058751`. Year ten uses the revenue increase into year eleven. Terminal reinvestment is terminal NOPAT multiplied by terminal growth divided by terminal ROIC. Discount factors are cumulative products of annual discount factors.

The saved margin path is 65%, 59%, 56%, 53%, and 50%, followed by 50%. A standard evenly spaced interpolation from year one to year five would produce different results. The explicit source path avoids silently changing this convention. Scalar tax of 25% governs the terminal year; the explicit tax path starts at 17.5% and reaches 25% in year ten.

The saved replacement scenario changes year-one growth to 40%, its margin path to 60%, 56%, 54%, 52%, and 50%, and sales-to-capital to 1.21. Its other paths are unchanged. Example weights of 50%, 30%, and 20% and the third adverse scenario are **illustrative design inputs, not author-supplied probabilities**.

## Commitments and double counting

The source commitment schedule is $120.0, $130.8, $128.8, $46.8, $40.8, and $52.8 billion, totaling $520 billion nominally. Discounting at 5.6503% produces the $446.513 billion present value above. The source also recasts operating income; it does not simply subtract this nominal stream again from annual forecast cash flows. The underlying obligation types and source filings still need review.

The JSON puts book debt in `debt` and the additional commitments plus minority interests in `debt_like_claims`. Each of these balances has a unique claim ID and is marked for the equity bridge, with no duplicate deduction from cash flows. The complete claim register reconciles the model's declared bridge balances; it does not independently validate their economic classification. Existing balance-sheet lease debt must not be capitalized a second time. Contingent guarantees require explicit expected-payout assumptions rather than an automatic full-notional deduction.

## Remaining model review points

- **WACC provenance:** the source's active 9.794239381% initial WACC comes from a multibusiness industry-average mix of Computers/Peripherals, Electronics (General), and Entertainment. This differs from the front-sheet Semiconductor label and may be template residue. The reproduction preserves the number and flags it for review.
- **Terminal dependence:** about 66.942% of baseline operating asset value comes from discounted terminal value.
- **Terminal transition:** terminal reinvestment is 41.25% of NOPAT, a substantial change from the explicit year-ten assumption. The resulting cash-flow discontinuity is preserved and disclosed.
- **Inactive inputs:** dormant distress probabilities, options inputs, negative-growth overrides, and alternative discount-rate methods are not activated by the import.
- **Interpretation:** discount to value and upside from price use different denominators. A 30% discount to unchanged value implies 42.857% upside to that value, not 30%.
- **Property scope:** the synthetic property separates NOI from annual capital expenditure and uses debt as an equity-bridge balance. It does not establish levered IRR, debt-service coverage, income taxes, or monthly distributable cash flow.

Reproduction accuracy does not resolve these input-quality issues. No example authorizes an order, offer, financing commitment, or transfer of capital.
