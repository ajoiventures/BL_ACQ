# Run a valuation from the terminal

Open [run_valuation.py](../../tools/run_valuation.py). It accepts either a request JSON object or an example containing `request`, delegates all calculation to the engine and decision layer, and writes a complete JSON result.

```sh
python tools/run_valuation.py data/valuation/nvidia_workbook_reproduction.json --output .runs/nvidia-valuation.json
```

The output includes cash flows, scenarios, policy results, source references and input digest. Invalid input returns a nonzero exit code. The tool rejects an output path that would overwrite the request and never submits an order or modifies a saved approval.
