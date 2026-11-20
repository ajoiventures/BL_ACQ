# A second approved packet exposes the settlement correction limit
Review: accepted
Reviewed by: Codex redesign agent and independent code-review agent
Source: pilot/acceptance.py

## Observed limitation

Verified source revision `be51964c2f6c72eac94ee1c1891fc1adc9121adb`. Run the synthetic [acceptance workflow](../../pilot/acceptance.py) to settle the Orchard deal. In the restored database, republish the fixture with the nonbinding financing cap increased by $100 (10,000 cents) and keep all other inputs fixed. Record fresh independent review and founder approval for the revised packet digest.

The revised packet reached `bid_ready_simulation`. A second call to `settle` raised `ValueError: Conflicting replay for evidence_id`. Event identifiers depend on deal and entity, while the new payload names a different approval. A byte-for-byte comparison of the ten saved service, invoice and receipt records confirmed that the failed transaction preserved the original events. The redesign agent reported the limitation and an independent agent reproduced the two-revision check in a temporary SQLite database.

## Next acceptance case

Define an explicit supersession or correction action that identifies the historical settlement and both approval revisions. Verify that an economics-only amendment leaves collected cash and receipt counts unchanged. A genuine correction must carry its own evidence, independent review and an auditable reference to the original posting. The current fixture proves same-revision replay and rollback on this conflicting revision.
