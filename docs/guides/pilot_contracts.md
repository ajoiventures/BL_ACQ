# Read the pilot records

[The contracts](../../pilot/contracts.py) declare immutable Python dataclasses used by the [store](../../pilot/storage.py). A parcel combines an internal ID with its local jurisdiction and parcel number. A deal references a parcel. Each evidence item records its source and an observation date in YYYY-MM-DD form. Each decision points to evidence for the same deal.

The store binds records to the current domain and records the creating actor. A stable record ID lets a client safely repeat the same submission. Changed evidence gets a new evidence ID. The Task returned by a worker claim carries the scoped task ID, worker, lease deadline and attempt number. A worker passes that record back to finish the attempt.

Open [the storage tests](../../tests/test_pilot_storage.py) and trace the case that attempts to attach another deal's evidence.
