# Document-to-offer application layer

Source: [document_offer_layer.py](../../pilot/document_offer_layer.py).

## Responsibility

Join the document evidence engine to the offer probability engine. Preserve
the original packet; apply only explicit reviewed money bindings; return the
baseline and changed calculations with source provenance. This application
layer contains no document AI, network calls, runtime agents or transaction
execution. The build-time swarm that wrote the code is outside the product.

## Contracts

`evaluate_with_evidence(store, packet, bindings, backend="cpu")` returns a
`br-document-offer-layer/1` report. Each binding names `field`, `group`
(`global`, `scenario`, `offer`), `record_id`, a whitelisted monetary `key`,
and an explicit nonnegative `offset_cents`. Only scenario targets can use an
offset; it remains an analyst assumption, not an extracted document fact.

An unresolved evidence projection withholds `after_evidence` and returns
`evidence_review_required`. Accepted inputs produce `research_requires_review`.
Both statuses keep `execution_allowed`, `ai_enabled` and
`runtime_agents_enabled` false. Neither state authorizes an acquisition.

Outcome probabilities, scenario weights, investment floors and workflow
authority cannot be changed through these document bindings. Changed offer
terms require a newly revalidated probability context, including new offers
and a live seller counter. Changed economics also hold any externally
estimated probabilities until a new packet revalidates their input context.
The synthetic renovation sensitivity holds explicitly assumed probabilities
constant. All bindings apply together or none are released.

An illustrative packet or illustrative evidence makes the adjusted result
illustrative. Synthetic evidence cannot lose that label by entering a packet
that was previously marked non-illustrative.

The report preserves its input packet, bindings, evidence projection, changed
fields, original result, new result, application holds and SHA-256 digest.
The digest identifies content; it is not a signature or proof of who reviewed it.

## R exchange

`export_r_review(report, directory)` creates a new directory containing
`offer_review.csv` and `manifest.json`. It validates the report digest first.
Unknown EV is empty, never zero. Exact rational numerators/denominators are
base-10 integer strings and must stay character or use arbitrary precision.
This typed exchange does not execute R or establish R/Python runtime parity.
See the [R validation guide](r-evidence-validation.md).

## Verification

Run `python -m unittest discover -s tests -p test_document_offer_layer.py -v`.
The [test guide](test_document_offer_layer.md) describes the material cases.
Use the [demonstration command](run_document_offer.md) to inspect the four
review states and source-to-profit changes.
