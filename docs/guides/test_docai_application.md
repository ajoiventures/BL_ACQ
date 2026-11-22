# Document application adverse-case tests

[Tests](../../tests/test_docai_application.py) · [Application guide](document_application.md)

Run `python -m unittest tests.test_docai_application -v`. Tests use temporary
local folders and the bundled synthetic invoice corpus. They never submit a
document to a provider. A network-construction tripwire covers the complete
native intake/review/export demonstration.

The suite verifies pending intake, exact integer cents and quotations, synthetic
status preservation, changed payload/actor replay, stale revisions, explicit
review reversal, manual corrections, same-label self-review rejection, conflict
holds, wrong citations, contextual isolation, append-only records, reopened
state, corrupted originals and injected failure between filing and bundle
commit. Source successors hold old accepted output and cannot fork a version.

Parser controls cover partial extraction, ambiguous amounts, unknown classes,
unsupported numeric forms and overflow. One explicit test demonstrates that an
exact citation contract does not prove semantic value correctness: this remains
a review and evaluation responsibility.

These tests establish behavior for the local trusted-OS path. They do not prove
authenticated identities, service ACLs, all parser classes, production recovery,
model quality, external connection, R execution or GPU performance. The PDF
worker and hostile-file checks live in the separate native parser suite.
