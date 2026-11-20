# Check the HTTP and database contract

Run `python -m unittest discover -s tests -p test_founder_service.py -v` from the repository root. Each test starts an HTTP listener and a disposable SQLite database. Requests travel through the actual local handler.

The first test signs the same actor into two sessions and checks that a committed draft survives a restart. It tests a stale version, a changed request with an already used operation ID, an obsolete evidence reference, and a denied role. The second sends competing founder decisions after independent review and verifies the expected conflict, the identical retry response and the durable number of decision rows.

The [browser replay](../tools/replay_founder.md) complements the HTTP checks by discarding an accepted response and using the visible retry button.

The evidence-revision test withdraws simulated committed financing and republishes the changed packet. It checks that the old packet stays visible until publication, that the next digest requires independent review, that prior decisions remain in history and that a funding hold blocks final approval.
