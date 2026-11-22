# Check document evidence integrity

[test_document_evidence.py](../../tests/test_document_evidence.py) exercises real
temporary SQLite databases and the [synthetic quote fixture](../../data/document_evidence/duplex_quote.json).

Run from the repository root:

```bash
python -m unittest tests.test_document_evidence
```

The cases verify hash/archive reconciliation, pending-to-accepted projection,
typed money and complete source provenance, idempotent replay, immutable history,
future and expired records, version supersession with and without a replacement
claim, later rejection without reviving earlier approval, current accepted
conflicts, explicit conflict resolution, matching-source provenance, deal/scope
isolation, invalid units/types/pages/locations, disabled AI adapters, atomic native
bundle import, rejected review imports, and unsupported storage-version handling.

The tests do not call a model, fetch a source, send a message, move money, or
assert that a signature creates a valid contract. Source and review actors are
trusted application inputs in this pilot. See the [engine guide](document_evidence.md)
for the as-of date and authentication boundaries.
