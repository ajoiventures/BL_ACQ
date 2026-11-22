# Follow the valuation decision layer

Open [valuation_layer.py](../../pilot/valuation_layer.py). Start at `evaluate`: observe source and price checks, the baseline model call, scenario reruns, independent qualification checks, and the entry ceiling. Put a breakpoint before `decision` is constructed to compare discount-to-value with upside-to-value.

Run `python -m unittest discover -s tests -p test_valuation_layer.py -v`. The test perpetuity produces a $100 value and a $70 entry ceiling; the corresponding upside is 42.857%, not 30%. Separate tests keep stale inputs and unsupported funding declarations on hold.

The packet digest binds inputs and model version. Source `verified` is a user assertion; this file does not fetch sources. Quote-source kind and observation date must support the price timestamp. Claim records reconcile liabilities without adding another deduction, and incomplete bridge reconciliation stays on hold. Optional capital sizing honors reserves, concentration and whole-asset indivisibility, and leaves `cash_committed` at zero. See the [feature guide](../valuation.md).
