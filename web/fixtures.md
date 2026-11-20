# Synthetic workflows and coverage

`fixtures.js` is the source of the module labels, fictional records, evidence versions, ordered transition names and coverage table. Each record belongs to one of the three workspaces. A record's event count indexes its next transition.

1. Follow the settlement record from Review invoice through Attach settlement receipt to Reconcile simulated receipt.
2. Compare these transitions to the Capital module and scoped activity trace.
3. Follow the entry for contact lookup into the System coverage list. Network identifies the future service directly.

Changing a fixture's meaning requires updating its version and replay cases. An imported draft with an obsolete version stays outside the receiving workspace.
