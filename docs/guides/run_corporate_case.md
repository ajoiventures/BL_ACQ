# Reproduce a corporate case bundle

Open [run_corporate_case.py](../../tools/run_corporate_case.py). It loads the
versioned WD-40 facts and assumptions, selects Base, Downside or Upside, invokes
the corporate adapter, and optionally exports `{case, facts, report}` as JSON.
The financial runtime uses the Python standard library without an AI service,
network request or market-data subscription.

From the repository root:

```sh
python tools/run_corporate_case.py --case Base --output .runs/wdfc-base.json
python tools/run_corporate_case.py --case Downside --output .runs/wdfc-downside.json
python tools/run_corporate_case.py --case Upside --output .runs/wdfc-upside.json
```

Each invocation prints a compact result containing DCF value per share, sponsor
MOIC and annual IRR, financing status and the research review state. The optional
JSON file also includes all source facts, annual schedules, checks, assumptions
and implementation fingerprints. Invalid data or output errors return exit 1.
The CLI refuses to overwrite either source data file with its output.

To inspect or edit inputs, start with
[wdfc_2025_case.json](../../data/corporate/wdfc_2025_case.json). Preserve the
distinction between a source fact and an assumption. The authenticated
[corporate workspace](../../web/corporate_html.md) permits temporary assumption
edits without rewriting the source facts. The workbook builder consumes the
same complete JSON bundle; see [its guide](build_corporate_workbook.md).

The [case memo](../corporate-case.md) explains the results, date convention and
remaining professional-review limits. The forecast years are hypothetical model
years ending October 31, not the issuer's fiscal years or current estimates.
