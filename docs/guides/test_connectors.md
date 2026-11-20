# Exercise the connector boundary

[The test](../../tests/test_connectors.py) seeds an approval for one exact action, then changes a field before each attempt. Follow the remaining approvals in the temporary in-memory journal. A failed action should leave the approval untouched. The approved action consumes it. A repeat then fails. The actual integration must provide the atomic and durable journal described in the [connector guide](pilot_connectors.md).
