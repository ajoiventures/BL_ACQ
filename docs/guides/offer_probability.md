# Read and run the offer probability engine

The [offer probability engine](../../pilot/offer_probability.py) enumerates a
one-round acquisition decision with ordinary Python. It does not call AI,
contact a seller, change a contract, authorize an offer, or move money. Builder
agents may develop the module; there are no runtime product agents in it.

## Quick start

Run from the repository root:

```python
import json
from pathlib import Path
from pilot.offer_probability import evaluate_packet

packet = json.loads(Path("data/offer_probability/duplex.json").read_text())
report = evaluate_packet(packet, backend="cpu")
print(report["ranked_research_candidates"])
```

The [synthetic packet](../../data/offer_probability/duplex.json) ranks D, B, E
under the baseline-profit rule and its illustrative probabilities. Under an
expected-profit-given-closing requirement of $45,000, no listed package passes.
The input is a teaching fixture, not a trained seller forecast.

## Follow the calculation

Read `validate_packet`, `_available`, `_evaluate_offer`, `_price_ceilings`, then
`evaluate_packet`. The CPU financial amounts are integer cents. Scenario and
event probabilities are exact `Fraction` values. Selling proceeds are floored
to cents at the same step as [existing underwriting](../../pilot/underwriting.py).
The old standalone probability lab used half-up selling-fee rounding; all
provided duplex values divide exactly and therefore retain identical results.

Scenario weights describe the joint resale/cost distribution **conditional on
acquisition closing**. The $15,000 allowance is spent once in every closed
scenario. Lower resale and higher repair/carry costs can occur together.

For agreement probability a, conditional closing probability q, and mean
completed-project profit mu:

`EV = (1-a)*(-rejection_loss) + a*(1-q)*(-failed_close_loss) + a*q*mu`

These are mutually exclusive TOTAL net branch outcomes. The failed-close
expense already includes pursuit costs; completed-deal profit includes its
pursuit expenses in the closing-cost budget. Refundable deposits are not
automatic losses. Earlier sunk costs are excluded from this prospective EV.

The four-branch economic distribution is enumerated directly. There is no
Monte Carlo sampling noise. This is expected undiscounted cash per attempt,
not NPV or IRR. Rejection has no continuation value. Do not interpret the
one-round calculation as an optimal sequence of repeated counteroffers.

## Versioned input and output

`evaluate_packet(packet, backend="cpu")` returns a JSON-serializable report.
Required identity fields are schema version `br-offer-probability/1`, model ID,
deal ID, ISO as-of date, IANA time zone and USD currency. Input money uses integer
cents and probabilities use integer basis points from 0 through 10,000. Booleans
are not accepted as numbers. Unknown fields and malformed collections fail.

Version 1 accepts up to 1,000 offers and 1,000 scenarios, bounded to 100,000
offer/scenario cells per packet. Split larger workloads into bounded packets.

`probability_basis` is `assumed` or `external_estimate`. An external estimate
requires a descriptive `probability_reference`. Neither label causes the
engine to certify calibration: `probabilities_validated_by_engine` stays false.
Specify the modeled event windows in `event_horizon_note`. The engine does not
fit event deadlines or a predictive model from supplied prose.

Every offer returns `baseline_profit_cents`, `expected_profit_given_close_cents`,
conditional target/loss probabilities, all scenario profits and policy checks.
Expected values and probabilities additionally return `*_exact` records with
numerator and denominator encoded as base-10 strings. Large rational integers
can exceed JavaScript/R's safe numeric range even though individual cents inputs
are bounded. Preserve these strings across interfaces and parse them with an
appropriate exact integer/rational type. These fractions are authoritative when the
convenient numeric field is a floating-point value. Do not round expected cash
to settlement cents while comparing policies.

If both agreement and conditional closing probabilities are known, `event_tree`
contains each terminal probability and cash amount, acquisition probability,
joint acquisition/target probability, and `expected_net_cents_per_attempt`.
If either probability is unknown, the tree is null. Unknown is not zero.
An offer-specific `closing_given_agreement_bp` overrides the packet default;
an explicit null override means unknown.

The original input is not modified. `input_sha256` binds the report to the
canonical input packet so a changed source or assumption creates a new digest.

## Policies and live counters

Policy modes are `baseline`, `expected_conditional`, and `chance_conditional`.
`required_floor_probability_bp` configures the chance rule. The optional
`required_closing_days` is an **exact package requirement**, not a maximum
deadline; null allows any listed package timing. Individual policy results
remain visible even when a different mode controls eligibility.

`accept_live_counter` requires 10,000 agreement basis points and an explicit
premise asserting exact terms, authorization, continuing availability and
effective acceptance, plus a reference. This is conditioning on supplied
premises; the module does not verify actual contract formation. New offers
and new counters remain separate response-probability actions.

`policy_rejected`, `probability_unknown`, and `research_candidate` describe
calculation status. None grants acquisition approval. Candidate ranking retains
the selected financial and timing policy, excludes unknown pursuit values, and
sorts exact expected values. Compare negative EV candidates with the zero-value
pass alternative; the rank itself is not a recommendation to act.

Price ceilings are grouped by each distinct closing-day/timing-cost package.
Editing a timing cost therefore changes its corresponding ceilings. Expected
price ceilings are floored to whole cents. The chance ceiling is evaluated at
discrete outcome boundaries; no interpolated quantile is used. All ceilings
assume fixed scenario and cost structures and do not predict seller acceptance.

## CPU, CUDA and R boundary

The exact CPU engine requires only the standard library. It remains on CPU
because its small, auditable event trees and policy boundaries need exact
rational arithmetic. `batch_expected_values` is the optional NumPy/CuPy
vectorized interface for up to 2,000,000 independent rows. Its inputs are
equally sized one-dimensional arrays of agreement basis points, conditional
closing basis points and mean profit cents, plus total unsuccessful-branch
costs. Output order matches input order.

The CUDA adapter reuses a cached fused kernel, transfers bounded arrays and
returns synchronized float64 expected values. It avoids per-row GPU calls.
Explicit CUDA fails if CuPy or a usable device is unavailable. It never silently
falls back. A packet requested with CUDA still reports exact CPU policy results
and separately identifies accelerated event-value rows and the actual device.
Parity must be within 0.01 cent, one hundredth of a cent, over the bounded
payoff range. This tolerance never changes financial-policy comparisons.

The current workspace has not executed this CUDA adapter. No GPU speed or
production capacity is claimed. Benchmark on the intended GPU, including
transfers, memory, cold/warm timing and reference comparison, before claiming
performance. Refer to [the optional CUDA environment](../../requirements-cuda.txt)
and [CUDA engineering requirements](../../AGENTS.md).

R can consume this versioned JSON/report contract or a typed application-layer
export. Keep the exact fraction fields and cents ranges explicit across the
boundary. This module does not add an R runtime or imply that R executed.

## Tests and source references

Run `python -m unittest discover -s tests -p 'test_offer_probability.py'`.
The [test guide](test_offer_probability.md) describes financial and malformed-input
coverage. AI services are intentionally absent; document AI belongs in a later
adapter that proposes evidence-backed inputs for validation.

- [NVIDIA reference comparison and numerical accuracy](https://docs.nvidia.com/cuda/cuda-c-best-practices-guide/)
- [CuPy fused kernels and reuse](https://docs.cupy.dev/en/stable/reference/generated/cupy.fuse.html)
- [Probability calibration and proper scores](https://scikit-learn.org/stable/modules/calibration.html)
