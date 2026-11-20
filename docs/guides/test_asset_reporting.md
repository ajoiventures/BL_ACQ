# Read the reporting tests

[test_asset_reporting.py](../../Python_Asset_Demo/test_asset_reporting.py) exercises two levels. `analyze` tests use in-memory records to check business rules. `run` tests use temporary files to check the complete report, which lets the suite verify the CLI's underlying data flow without touching your lesson output.

```powershell
python -B -m unittest discover -s Python_Asset_Demo -v
```

| Test to trace | What to inspect |
| --- | --- |
| `test_boundaries` | The five dates cover yesterday, today, the last included day, the next day and a blank. Inspect the denominator for the due-soon percentage. |
| `test_missing_is_not_zero` | Compare a blank cost with the string `"0"`. Their counts and totals show why the distinction matters. |
| `test_rejects_malformed_columns_and_widths` | Each bad CSV must fail before creating the destination directory. |
| `test_manifest_matches_snapshot_and_report` | A controlled replacement of `Path.read_bytes` changes the input after the first read. The record and manifest must still match the first snapshot. |
| `test_failed_publish_cleans_stage_and_allows_retry` | The simulated rename failure leaves the destination available for the next run. |

**Debug exercise.** Place a breakpoint at `analyze(data, DAY)` in the boundary test. Step into the function, inspect `end` and `days`, and follow the result back to the assertion. Then run the whole suite so the other input and file guarantees remain covered.
