# Follow an immutable valuation run

Open [valuation_store.py](../../pilot/valuation_store.py). `save_run` recalculates the submitted request before writing it, reserves the operation ID inside the transaction, and returns a frozen result. An existing parcel deal must retain its permanent asset identity. An unrelated stock study is saved as a research deal without manufacturing a parcel.

The first saved research run also binds its deal ID to its asset ID. Later runs
and operation replays must preserve that relationship. If a canonical parcel deal
is created later, it must agree as well. Checks run inside the same serialized
write transaction as the snapshot and receipt; two competing first saves cannot
establish different assets for one deal. Distinct deals may concern the same asset.
A rejected write does not consume its operation ID or append evidence.

`valuation_runs` stores requests, results and engine versions. `valuation_receipts` prevents an operation ID from representing two different packets. Existing parcel studies also append an evidence record; they do not change approvals or settlement state.

Persistence uses the evaluator's frozen request copy. Reusing an existing run
preserves its original result, creation metadata and link type. A receipt is
checked against both the requested digest and the referenced snapshot. A conflict
cannot silently return an unrelated valid run.

Retrieval and history listing recompute SHA-256 over canonical JSON containing
the **stored** model version and stored request. They compare that digest with
the row/report digest and derived run ID, and cross-check deal, asset, request,
model, date and currency identities. Malformed JSON, nonfinite snapshot values,
or identity disagreement produces a conflict. Retrieval never reruns financial
calculations, reapplies today's source policy, or substitutes the current model
version for the stored version.

This request checksum detects input/version corruption and inconsistent snapshot
identities. It is not a signature, and it is not a checksum over every financial
output: an altered result value with unchanged request and consistent metadata
cannot be detected through this digest alone. Deliberate rewriting of both data
and checksum also requires stronger external integrity controls. Source truth
and financial correctness remain separate from storage integrity.

Run `python -m unittest discover -s tests -p test_valuation_service.py -v`. Follow the restart test and inspect the distinction between an expired browser session and a retained valuation record. See the [API table](../valuation.md).
