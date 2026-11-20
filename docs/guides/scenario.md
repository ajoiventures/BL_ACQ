# Replay Orchard from thesis through reconciliation

Run `python -m pilot.scenario` from the repository root. The command prints a JSON report to stdout. It reads local synthetic inputs and keeps the simulation in memory.

Start with `deal_fixture`. Its ten evidence references belong to one district, parcel and acquisition. The dates deliberately anchor the replay to November 20, 2026. `run_scenario` first computes the proposed decision, then supplies a named fixture reviewer for that exact packet. The result contains qualification, underwriting and ledger sections. The reviewer identity here is simulated.

Trace the service simulation next. Four independent entities record invoices. Two receive evidenced payment. Both receipts are replayed to exercise duplicate handling. The report has $2,050 cash, $800 in receivables and $2,850 in service income. Each total is in integer cents in the JSON.

Read the [qualification and underwriting guide](underwriting.md) and the [accounting guide](ledger.md) for the rules behind those amounts.
