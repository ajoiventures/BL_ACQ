# Start Here

Open [black-river.code-workspace](../black-river.code-workspace) in VS Code. In the Explorer, use `Python_Asset_Demo/` for reporting, `web/` for the founder interface, `tools/` for verification and `docs/guides/` for worked examples. The [code map](code-map.md) links each source to its guide.

## Lesson 1 — Follow an unknown cost

Open [the sample CSV](../Python_Asset_Demo/SYNTHETIC_assets.csv). DEMO-003 is missing a replacement cost. DEMO-005 has an explicit zero. Predict how these values affect the total.

Open [the analysis](../Python_Asset_Demo/asset_reporting.py) and set a breakpoint inside the row loop in `analyze`. Start **Walk through one synthetic report** with F5. When `asset_id` becomes `DEMO-003`, inspect the raw input, parsed cost and exception list. Continue until the launcher prints the report directory. Compare its `checked_records.json`, `exceptions.csv`, `summary.json`, and `manifest.json` with the input.

Run the equivalent commands in a terminal from the checkout. The tasks use uv and Python 3.12 or newer. A selected Python interpreter can also run the commands after `uv run --no-project`.

```sh
uv run --no-project python -B tools/run_example.py
uv run --no-project python -B -m unittest discover -s Python_Asset_Demo -v
uv run --no-project python -B tools/check_guides.py
```

## Lesson 2 — Follow a parcel across screens

Start the local interface, then visit `http://127.0.0.1:8765`.

```sh
uv run --no-project python -m http.server 8765 --bind 127.0.0.1 --directory web
```

In the commercial workspace, open **Orchard parcel**, advance the synthetic workflow, and inspect the funding hold. Load the verified funding fixture and record the simulated review. Open the activity view to trace the steps. Try saving a note and use **Device handoff** to transfer the draft to a second local session.

Read [the synthetic workflows](../web/fixtures.js) to see which record owns each transition. Then read [the screen behavior](../web/app.js) to see where the interface enforces the funding requirement.

## What to open next

Use the [code map](code-map.md) to compare the two verification approaches. The asset tests check records, money and publication behavior. The browser replay drives the interface and checks evidence, approvals, and handoff as a user would experience them.
