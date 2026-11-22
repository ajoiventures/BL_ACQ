# Corporate source evidence and normalization record

**Prepared November 22, 2026. Historical analysis cutoff: October 31, 2025.**

The accompanying `data/corporate/wdfc_source_facts.json` contains a complete transcribed set of WD-40 Company FY2023–FY2025 income statements, balance sheets, cash-flow statements and equity rollforwards. It also contains two public peer reference calculations and dated daily closing prices. This is a source and classification record, not independent audit assurance or employer approval.

## Source selection and dates

| Source | Published | Financial period / locator | Use |
|---|---|---|---|
| [WD-40 FY2025 Form 10-K](https://www.sec.gov/Archives/edgar/data/105132/000010513225000067/wdfc-20250831.htm) | October 27, 2025 | August 31, 2025; F-3 balance sheets, F-4 income, F-6 equity, F-7 cash flows | FY2023–FY2025 income, cash flows and equity; FY2024–FY2025 balance sheets |
| [WD-40 FY2024 Form 10-K](https://www.sec.gov/Archives/edgar/data/105132/000010513224000064/wdfc-20240831.htm) | October 21, 2024 | August 31, 2024; F-3 balance sheets | FY2023 balance sheet and selected comparative note facts |
| [RPM FY2025 annual report](https://www.sec.gov/Archives/edgar/data/110621/000119312525185357/d944593dars.pdf) | August 21, 2025 SEC ARS publication | May 31, 2025; embedded Form 10-K pp34–35 and 37 | Audited peer financial statements; notes and July 21 cover share count |
| [Clorox FY2025 Form 10-K financial exhibit](https://www.sec.gov/Archives/edgar/data/21076/000002107625000039/clx-20250630_d2.htm) | August 8, 2025 | June 30, 2025; Exhibit 99.1 pp25, 27 and 29 | Audited peer income, balance sheet and cash-flow data |
| [Clorox 2025 proxy](https://www.sec.gov/Archives/edgar/data/21076/000155278125000311/e25287_clx-def14a.htm) | October 7, 2025 | “Who Is Entitled to Vote”; September 22 record date | Exact dated common share count; June 30 reference closing price cross-check |

The JSON records accession numbers, SEC filing-index URLs, publication dates, source types and detailed table/note locators. RPM's annual report includes an unaudited introductory summary and an embedded audited Form 10-K; the data uses the latter. Clorox's financial statements are in Exhibit 99.1 rather than the main cover document. Original 2025 filing vintages are used, without importing later restatements.

All historical financial statement amounts use **USD thousands** in the JSON. Clorox originally reports USD millions, converted by multiplying by 1,000. Exact shares are actual shares; weighted-average WD-40 EPS denominators remain in thousands of shares. Expense lines in the income statement are positive expenses; cash outflows and equity reductions are negative. Rounded note disclosures retain an explicit precision warning.

## Date discipline

October 31 is the analysis cutoff and historical quote date. WD-40's actual balance sheet is dated August 31. Carrying that balance sheet into a hypothetical October 31 model opening is an **analyst opening-balance proxy**, with intervening transactions still requiring review. Subsequent columns in that model should be “Model Year 1–5,” rather than presenting them as the issuer's fiscal-year forecasts. Financial period, source publication date, share-count date, market event date and retrieval date are distinct fields.

The peer comparisons deliberately use annual reference financials with visible fiscal year ends. They are not described as latest-quarter balances or latest twelve-month metrics. The same-day quotes do not eliminate the gaps between financial, share-count and price dates.

## Historical statement reconciliation

**All 69 source arithmetic controls in the integrated case pass with zero residual at the presented precision.** These checks recalculate gross profit, operating expenses, operating income, pretax and net income; current and total assets; current and total liabilities; equity components and the balance-sheet equation; issued less treasury shares; each cash-flow section; cash movement including FX; beginning and ending cash; equity rollforwards; and ties back to the balance sheet. The source checks operate directly on the transcribed data, independently of the forecast engine. This count includes the additional net-income and reported-total cross-statement controls added after the initial transcription audit.

This establishes internal arithmetic consistency. It does not prove every transcription matches the original source, establish completeness of economic claims, or replace a second person's source-to-cell review. Full copyrighted filings are linked rather than redistributed. Source-content hashes are null because archived document bytes were not retained.

## WD-40 classifications requiring explicit treatment

| Item | Source fact | Treatment and reason |
|---|---|---|
| Tax normalization | FY2025 net income 90,994; tax provision 10,632; cash-flow tax-release adjustment 11,929; reported ETR 10.5% | Preserve actual earnings and separately choose a recurring forecast tax rate. Note 15 explains the release. FY2024/FY2023 ETRs provide context; the release is not recurring operating performance. |
| Other current assets | 26,366 in FY2025, including 7,290 held-for-sale assets and approximately 4,900 tax receivable | Do not automatically scale the entire account as operating working capital. Holding unsupported balances constant is a model convention, not a source fact. |
| Held-for-sale assets | Note 3, F-17: inventory 3,349; goodwill 1,120; intangibles 2,821; no disposal-group liabilities | The amounts are already in other current assets and must not be added to inventory or goodwill again. The operation was not classified as discontinued. |
| Depreciation and amortization | Cash-flow D&A 8,191; intangible amortization 183; PPE depreciation approximately 7,600 | The rounded PPE disclosure is not an exact residual of cash-flow D&A less intangible amortization. Keep these measures separate. |
| Cloud implementation | Cash-flow amortization 1,688; gross capitalized costs approximately 16,600 and accumulated amortization approximately 3,800 | Cloud amortization is separately presented from cash-flow D&A. Associated costs sit in other assets and operating cash flows; they are not automatically PPE capex. |
| R&D | Approximately 8,700 in FY2025, inside SG&A | Do not subtract it again. |
| Leases | Current operating liability 2,282 inside accrued liabilities; noncurrent 8,423; operating ROU 10,385; prepaid finance ROU 3,149 with no remaining finance lease debt | A rent-expensed valuation excludes operating leases from financing debt unless operating cash flows are adjusted consistently. Carving current leases out of operating accruals prevents accidental working-capital forecasting or double counting. |
| Equity and cash | FY2024 equity treasury purchases 8,129 versus cash purchases 8,094 | Preserve the 35 difference. Reported historical cash flows also include FX and reclassifications, so they need not equal naive balance-sheet account changes. |
| Target claims | Borrowings 86,995; uncertain tax benefits with interest and penalties approximately 1,100 within other long-term liabilities of 1,407 | A frozen tax liability must not disappear from the valuation. Either deduct a disclosed tax-claim proxy in the equity bridge or explicitly show its omission and sensitivity. Do not deduct it again if settlement is included in forecast cash flows. |

The tax-claim disclosure is in **Note 15, F-28**. The source record does not establish a complete closing claims register. Accrued liabilities, contingent matters, cash accessibility, dilution and events after August 31 require review before treating the opening balance sheet as a transaction closing balance sheet. No target pension liability has been invented.

## Historical quotes

| Ticker | October 31, 2025 close | Publisher source |
|---|---:|---|
| WDFC | $194.28 | [ChartExchange WDFC historical table](https://chartexchange.com/symbol/nasdaq-wdfc/historical/) |
| RPM | $109.28 | [ChartExchange RPM historical table](https://chartexchange.com/symbol/nyse-rpm/historical/) |
| CLX | $112.46 | [ChartExchange CLX historical table](https://chartexchange.com/symbol/nyse-clx/historical/) |

The dated historical **Close** column was used, with the corresponding OHLC and volume retained in JSON. Current banners, after-hours prices, repurchase averages and the SEC cover's market value of nonaffiliate shares were not used as closing quotes or total market capitalization. Clorox's June 30 historical close of $120.07 matches the price stated in its proxy, which provides a limited cross-check of that publisher's historical-price convention.

These quote rows were retrieved on November 22, 2026. Their market event date is October 31, 2025, but the original publication timestamp and an unchanged archived vendor vintage are unavailable. Consequently the dataset does not establish a fully point-in-time licensed backtest feed. It makes no current November 2026 price claim.

## Peer construction and limitations

RPM and Clorox provide adjacent comparisons through branded maintenance, cleaning and household products. Both are materially larger and have different portfolios. RPM has substantial industrial and construction exposure; Clorox has additional consumer categories. Two peers do not define a statistically representative sector valuation.

The consistent objective is operating line-item earnings after depreciation and intangible amortization, with all adjustments visible. This is not issuer adjusted EBIT or a claim of normalized recurring profit:

- **RPM:** 7,372,644 revenue less 4,322,166 cost of sales, 2,150,537 SG&A, 24,979 restructuring and 11,352 goodwill impairment produces **863,610**. Investment and other income are excluded. Star Brands was acquired April 30, so annual earnings contain only the post-acquisition period while debt includes acquisition financing. No unsupported full-year pro-forma earnings are manufactured.
- **Clorox:** 7,104,000 revenue less 3,891,000 product costs, 1,124,000 S&A, 770,000 advertising, 121,000 R&D and 118,000 divestiture loss gives 1,080,000. Note 18 places 21,000 intangible amortization inside other expense; reclassifying that operating charge gives **1,059,000**. This avoids overstating operating earnings merely because of presentation. The remaining other-income/expense components are excluded. The calculation retains the 5,000 insurance recovery in product costs and the divestiture loss, so it is explicitly a line-item benchmark rather than a recurring-profit normalization. ERP-related advance shipments are another comparability limitation.

The JSON supplies raw facts and an **analyst-convention** enterprise-value bridge. Its arithmetic example includes RPM's 17,252 contingent acquisition consideration and 14,086 recognized pension deficit liabilities, with no automatic deduction for captive-insurance assets or surplus assets in different pension plans. Clorox's bridge includes 36,000 finance leases outside reported borrowings, its 501,000 Glad terminal obligation, and 107,000 net retirement deficits. Operating lease debt is excluded consistently with retaining rent expense. Book debt and book NCI are proxies; no claim of market fair value is made.

Those pension additions are optional classification choices. A model may omit pension adjustments uniformly if it exposes that convention; the components are separate so changes remain reviewable. For the example bridge as recorded, RPM EV/operating EBIT is approximately **19.00x**, and Clorox is **15.88x**. They are calculations from the displayed facts and conventions, not observed vendor multiples or endorsed fair values. Target tax-claim treatment should be reviewed alongside these peer-claim choices.

### Compact integration contract

`market_quote.close` and `.date` supply the target quote. For each object in `comparables`, read `entity.ticker`, `quote`, `shares.value`, `shares.as_of`, `fiscal_period_end`, `financials_published_on`, `constructed_operating_ebit.value`, and `suggested_enterprise_value_bridge`. Monetary bridge inputs are USD thousands. Market capitalization is `price × actual shares / 1,000`. Suggested enterprise value is market capitalization plus debt, NCI, preferred stock and other claims, less cash and specifically selected nonoperating assets. Divide it by the documented operating EBIT. Never substitute diluted weighted-average EPS shares or nonaffiliate float value into that formula.
