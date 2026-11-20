# Reproduce and restore a synthetic pilot

[The acceptance command](../../pilot/acceptance.py) runs one deal from intake through settlement. It loads the acquisition packet, processes intake, saves a draft, and records independent review and a founder approval. That durable approval and its evidence digest authorize the settlement task.

Each service, invoice and receipt is stored as a separate evidence event under that deal. Follow `reconcile` as it rebuilds the four entity statements from the saved events. Two invoices settle, two stay open, and the journal records six entries. All amounts and actors are synthetic.

After SQLite backup, the command compares the restored decision history, ledger, task history, drafts and receipts with the original. It submits the final approval request again and verifies that the same receipt returns without changing history. The [regression tests](../../tests/test_acceptance.py) also try to settle before approval.

Run `python -m pilot.acceptance` from the repository root. The command reports the number of decisions and settled invoices, plus reconciliation and recovery status. Its fixture actors represent operating roles in a simulation.
