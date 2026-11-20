# Trace a durable pilot operation

[Store](../../pilot/storage.py) is the standard-library SQLite boundary for the synthetic pilot. Each connection binds to one actor and one of the commercial, family or civic scopes. The calling service supplies that identity. Use one Store per worker or request.

1. At open, the migration transaction locks writers, checks the namespaced version ledger and applies missing DDL. Version 1 creates the parcel, deal, evidence and decision contracts. Version 2 adds tasks and an append-only event journal. Version 3 adds durable claim request receipts. A failed migration rolls back.
2. Save a parcel, deal, evidence and decision in that order. A repeated identical save reuses the record. Foreign keys bind children to the same scope and the decision to evidence for its own deal. Wrap related calls in `store.transaction()` to include a checkpoint written through `store.connection` in the same commit.
3. Call `enqueue(task_id, deal_id, kind)` with the same task ID on retries. For each new poll, generate a request ID and call `claim(lease_seconds=60, request_id=poll_id)`. A transport retry reusing that ID returns the original live assignment or `None` once it is unavailable. A new poll uses a fresh ID. SQLite serializes the selection, receipt, update and event insert.
4. Pass that result to `complete` or `retry`. Repeating the same receipt is safe. An expired worker loses authority over the task. The next claim records the expiry and advances the attempt number. Call `history(task_id)` for the ordered evidence.

A lease can expire after work has started. Use a stable downstream idempotency key for any retried side effect. This local store implements the synthetic SQLite pilot. The [tests](../../tests/test_pilot_storage.py) exercise a real on-disk database with independent workers.
