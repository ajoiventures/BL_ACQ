# Reproduce the storage checks

[The storage suite](../../tests/test_pilot_storage.py) uses temporary SQLite databases and a controllable clock. From the repository root run `python -B -m unittest discover -s tests -p test_pilot_storage.py -v`.

Start with the populated migration case. It creates a version 1 deal plus an unrelated table, opens the current store twice, and checks both preserved data and the newly durable queue. The migration failure case checks that DDL can roll back atomically.

Then follow the four-worker test. Each worker uses its own SQLite connection and shares a barrier. All four enqueue the same key and attempt to claim it. Only one obtains the lease. The expiry test moves time exactly to the deadline, rejects the former worker's receipt, reassigns the job and verifies the history after reopening the database.

Finally inspect the mixed-domain and outer transaction cases. Evidence must belong to the same deal and scope as its decision, and a checkpoint rolls back together with the core records when the transaction fails.
