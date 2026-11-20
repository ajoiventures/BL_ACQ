# Reconcile a synthetic service invoice

Read the methods of `Ledger` in posting order. `approve_service` collects the owner and completion reference. `post_invoice` accepts an independently reviewed amount for that completed service. Its journal entry debits accounts receivable and credits service income. At this point the customer owes money and recorded cash is zero.

`post_receipt` matches a full payment to an open invoice in the same entity using separate settlement evidence and an independent reviewer. Its entry debits cash and credits receivables. Replaying an identical invoice or receipt preserves the original entries. Reusing an ID with different data, reusing settlement evidence, changing entity or presenting a partial receipt raises an error before balances change.

`report` rebuilds balances from the journal. It checks them against an independent aggregation of source invoices and receipts, then sums the entities. Run `python -m pilot.scenario` and inspect `ledger.entries`, `ledger.invoices` and `ledger.entity_balances_cents`. The fixture models one external-customer invoice per service. Intercompany transfers, partial payments, multi-currency accounting and live banking are outside this pilot.
