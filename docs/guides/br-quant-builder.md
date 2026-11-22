# Quantitative engine builder agent

The [agent profile](../../.codex/agents/br-quant-builder.toml) defines a development worker for financial rules, conditional event models and CUDA computation.

Start with the assigned calculation contract and [probability engine guide](offer_probability.md). Inspect cents, rounding, event conditioning and cost treatment before looking at optimization. Unknown probabilities stay unknown. An assumed scenario distribution is not an empirically calibrated model.

The worker preserves an inspectable CPU reference and an explicit CUDA backend. GPU parity and performance require an actual device; a skipped test cannot satisfy those gates. The R interface is also distinct from a runtime that has been executed.

Read the profile's assigned-scope and handoff rules. Check the TOML with `tomllib` and validate its source-to-guide link with `python tools/check_guides.py`.
