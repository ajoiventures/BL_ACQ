# A receipt must identify independent settlement evidence
Review: accepted
Reviewed by: Codex independent code-review agent and ledger implementation agent
Source: tests/test_pilot_domain.py

## Reproduced decision

Verified source revision `be51964c2f6c72eac94ee1c1891fc1adc9121adb`. The regression was `test_evidence_cannot_change_role_across_entities_in_either_order` in the pilot domain suite.

A cross-entity accounting check showed that an invoice reference from a different service could be used to settle an invoice. Testing each new receipt against only its own invoice missed that case. The ledger now reserves separate evidence roles across entities. The same constraint applies when documents arrive in the opposite order.

The independent code review reproduced the original case with synthetic records, and the ledger agent added the both-order regression in [the accounting suite](../../tests/test_pilot_domain.py). Follow the operation from evidence role through journal posting in [the ledger](../../pilot/ledger.py). Matching an invoice with an independently reviewed receipt changes its status from open to settled. This evidence covers the four-entity simulation. It does not verify a bank deposit.

## Recheck

Run `python -B -m unittest discover -s tests -p test_pilot_domain.py -v` and inspect the evidence-role collision test. Retain this case when changing the journal or adding a new payment connector.
