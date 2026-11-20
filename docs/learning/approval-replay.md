# Restore the approval receipt with the evidence revision
Review: accepted
Reviewed by: Codex independent code-review agent and Founder service implementation agent
Source: tests/test_founder_service.py

## Reproduced decision

Verified source revision `be51964c2f6c72eac94ee1c1891fc1adc9121adb`. The check was `test_evidence_revision_is_frozen_and_requires_new_review` in the Founder service suite, followed by the backup acceptance replay.

A saved founder decision must identify the evidence packet that the reviewer saw. The independent review found that regenerating a packet from the current fixture could change the interpretation of an older approval. The service now retains the packet digest and binds approvals to that stored revision. A changed packet requires a new review.

Trace the database checkpoint and receipt through [the Founder service](../../pilot/founder_service.py). The [revision regression](../../tests/test_founder_service.py) covers superseded evidence. The [recovery tests](../../tests/test_acceptance.py) separately restore the decision history and replay the final request. Both suites passed on Windows using synthetic inputs.

## Recheck

When changing the review workflow, reproduce a revision change and a retried operation after database restore. The checked boundary is the authenticated loopback simulation. A production identity or live transaction requires its own verification.
