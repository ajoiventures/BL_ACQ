# Test the evidence and price boundary

Open [test_valuation_layer.py](../../tests/test_valuation_layer.py). `request_fixture` describes a hand-checkable $100 corporate perpetuity and explicitly synthetic test evidence. The tests separately change the event assumptions, margin of safety, quote timestamp, qualification evidence, liabilities and capital policy.

Run `python -m unittest discover -s tests -p test_valuation_layer.py -v`. Regression cases cover quote-source kind and date mismatches, floating-point policy boundaries, whole-property sizing and incomplete obligation reconciliation. A passing test establishes calculation and policy behavior, not the reliability of live investment inputs. Unknown fields and non-finite numbers are rejected rather than ignored.
