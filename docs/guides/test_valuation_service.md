# Test authenticated valuation delivery

Open [test_valuation_service.py](../../tests/test_valuation_service.py). Each test starts the real loopback service against a temporary database. It exercises unauthenticated and cross-scope rejection, same-origin enforcement, saved-run replay, conflict handling and recovery after a restart.

Research identity cases attempt a second asset under an existing deal ID, then
retry the rejected operation ID with the correct asset. They also verify that
different deals can share an asset, that two competing saves serialize to one
success and one conflict, and that an idempotent replay cannot bypass a conflicting
canonical parcel deal created after the original research snapshot.

Integrity cases deliberately alter the stored request, model version, embedded
report request, row asset, JSON format and operation receipt. Reads or replays
must return a conflict rather than corrupted or unrelated history. The historical
read test changes the active model version and patches valuation evaluation to
fail, proving that retrieval verifies the original versioned request digest
without recalculating the historical financial result. History listings use the
same integrity checks as individual retrieval.

Run `python -m unittest discover -s tests -p test_valuation_service.py -v`. Inspect the database assertions: a calculation creates neither a saved run nor an approval; saving a parcel valuation appends evidence without altering the founder decision history.
