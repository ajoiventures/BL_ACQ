# Verify the offer probability engine

The [tests](../../tests/test_offer_probability.py) check the inspectable
[probability engine](../../pilot/offer_probability.py). Run from the repository
root:

```powershell
python -m unittest discover -s tests -p "test_offer_probability.py"
```

The acceptance cases verify the independently calculated duplex profits,
expected pursuit values, acquisition probabilities and policy-constrained
ranking. Terminal outcomes must reconcile exactly to probability one and to
the expected cash value, including the total cost convention for unsuccessful
branches. Boundary cases check no agreement, no closing, and certain closing.

Additional cases distinguish baseline, conditional expectation and conditional
chance policies; verify the discrete 95%-to-70% price boundary; check fractional
cents and whole-cent ceilings; preserve unknown probabilities; reject incomplete
live-counter premises; and bind an unchanged input to a repeatable digest.
Selling-fee rounding is compared with the existing underwriting engine.

Malformed schemas, money/probability types, IDs, duplicate records, dates,
time zones, empty collections, missing evidence references and nonfinite values
are rejected. A simulated unavailable CUDA backend must propagate its error,
including when a packet has no known agreement probabilities.

NumPy batch tests run when NumPy is installed. Real GPU parity is opt-in with
`BLACK_RIVER_TEST_CUDA=1` and a compatible installed CuPy/CUDA environment.
The opt-in test validates execution and accuracy; it is not a representative
performance benchmark. A skipped GPU test is not evidence of CUDA execution.

No R runtime is exercised by these tests. No AI, network service, seller
communication, signing or payment is required by the core engine.
