# Test a restored deal

[The acceptance tests](../../tests/test_acceptance.py) exercise the same [pilot command](../../pilot/acceptance.py) used in the workspace. Use `python -B -m unittest discover -s tests -p test_acceptance.py -v` from the repository root.

The first test loads the candidate and tries to settle before the founder decision. Compare the saved evidence and task list on both sides of that failure. Neither collection changes.

The second test reopens the backup, checks its saved draft and three decision-operation receipts, and runs settlement a second time. Compare the six journal entries and task history. The completed settlement key recovers the result without creating another invoice, receipt or approval.
