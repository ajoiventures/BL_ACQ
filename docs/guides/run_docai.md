# Run the native Doc AI increment

[CLI source](../../tools/run_docai.py) · [Application mechanics](document_application.md)

Run from the repository root with Python 3.12. Text/DOCX processing uses the
standard library. Native PDF processing requires the pinned optional dependency:

```bash
python -m pip install -r requirements-docai.txt
python tools/run_docai.py --help
```

## Synthetic demonstration

Choose a new output path. The command archives the bundled synthetic invoice,
extracts six fields, records explicitly automated synthetic review events and
exports the result. It cannot run automated demonstration reviews on an arbitrary
input file. The actor is fixed to `synthetic-demo-runner` for this command.

```bash
python tools/run_docai.py --root /tmp/br-docai-demo demo --output /tmp/br-docai-demo/accepted-invoice.json
```

Output is JSON. The amount is `125000` integer cents with the source quote
`1,250.00`. Source status remains `synthetic`; execution authority is `none`.
The existing output is never overwritten. An intake retry preserves prior
records. A demo export does not represent real human approval or provider
accuracy.

## Normal intake and review

```bash
python tools/run_docai.py --root /tmp/br-docai-local --tenant example --subject invoice-1 --actor reviewer-1 ingest tests/fixtures/docai/invoice_native.txt --class MEP_INVOICE --synthetic
```

The returned document ID, claim IDs, exact source spans, current revision and
holds are the inputs for the following operations. Repeat the same root and
context arguments; use the actual identifiers returned by intake:

```bash
python tools/run_docai.py --root /tmp/br-docai-local --tenant example --subject invoice-1 inspect DOCUMENT_ID
python tools/run_docai.py --root /tmp/br-docai-local --tenant example --subject invoice-1 --actor reviewer-1 review CLAIM_ID --review-id review-001 --decision accept --reason "Checked typed value against the original and exact quote." --revision 1
python tools/run_docai.py --root /tmp/br-docai-local --tenant example --subject invoice-1 export DOCUMENT_ID --output /tmp/br-docai-local/reviewed-export.json
```

Inspect again for the current revision before each new review. Export stays
held until all required fields are accepted without unresolved conflicts. The
CLI records local actor attestations; it does not authenticate those identities.

For correction, prepare a complete `br.docai.v1` candidate using the documented
schema and existing extraction page. Set `method: manual`, a new `claim_id`, the
current actor as `proposed_by`, a valid timestamp and exact source spans. Set
`supersedes_claim_id` to the prior candidate when replacing it. Submit with:

```bash
python tools/run_docai.py --root /tmp/br-docai-local --tenant example --subject invoice-1 --actor preparer-1 correct correction.json --revision CURRENT_REVISION
```

The replacement needs review. A later review decision must explicitly identify
its preceding review via `--supersedes-review`. The old history is retained.
Exit code 2 and a structured `status: held` error identify invalid input, stale
state or failed output. CLI processing is synchronous; there is no work queue.

See [native evaluation](evaluate_docai_native.md) for corpus scoring. The
demonstration and evaluator make no network call and activate no AI service.
