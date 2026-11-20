# Verify the acquisition and accounting rules

Run `python -m unittest discover -s tests -p test_pilot_domain.py -v` from the repository root.

The deal tests reuse the same synthetic parcel and change one input per case. They cover each binding limit and a tie, wrong-entity evidence, incomplete and stale records, unsupported property families, geographic bounds, wetlands, road access, missing title evidence, and replaying an approval against changed economics. Examine each subtest after a failure to identify the first incorrect rule.

The accounting tests take a snapshot before rejected entries and compare the entire report afterwards. Replayed settlements add no cash. The four-entity case reconciles source evidence to entity balances and the consolidated result. Extend the same fixtures when adding a new accepted transaction type.
