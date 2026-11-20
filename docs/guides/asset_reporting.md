# Read the asset reporting workflow

[asset_reporting.py](../../Python_Asset_Demo/asset_reporting.py) turns warranty dates and replacement costs into four report files. The five-row [practice CSV](../../Python_Asset_Demo/SYNTHETIC_assets.csv) uses invented assets and generic vendors. Run the **Run Example** task to follow this guide.

1. Start at `run`. It reads the CSV once into `original`. The reader parses that snapshot and the manifest hashes those same bytes. A later edit to the source belongs to a later run.
2. Step into `analyze`. It rejects duplicate IDs, invalid costs and malformed rows. Follow DEMO-003 with the example date of September 13, 2026. Its October 13 deadline lands exactly 30 days away. Look for `due_soon` in the record and the two missing values in the exceptions.
3. Inspect `summary`. The example has five assets, four dated assets, two due soon and one expired. The due-soon share is 2/4. The four recorded costs total 1,750. A blank cost stays unknown, and an explicit zero enters the count of known costs.
4. Return to `run`. It stages the summary, checked rows, exceptions and manifest together. The rename makes the batch visible. An existing destination protects a previous report from being overwritten.

The manifest records the input hash, script hash, parameters and hashes of the three result files. Matching hashes establish byte identity. The quality of a warranty date still depends on the source evidence.

**Try a change.** Make a copy of the sample, change DEMO-003’s date to October 14, and run the CLI below with a fresh output path. Check how the record, count and manifest change.

```powershell
python -B Python_Asset_Demo/asset_reporting.py Python_Asset_Demo/SYNTHETIC_assets.csv .runs/warranty-lesson --as-of 2026-09-13
```

Continue with [the test walkthrough](test_asset_reporting.md).
