# Valuation & Risk

The valuation engine turns operating assumptions into cash flows and equity value. The decision layer reruns the model under dated event scenarios, checks the evidence, and separates value from the proposed entry price. Every saved run carries a Deal ID, permanent asset ID, source references and a digest of its inputs and engine version.

## Run it

From the repository root, with Python 3.12 or later:

```sh
python -m pilot.founder_service
```

Open `http://127.0.0.1:8765/valuation.html` and use the reviewer or founder access key printed in the terminal. The connected parcel review and valuation workspace share the same authenticated local service. A restart invalidates session keys; saved valuation runs remain in the database.

For a terminal-only calculation:

```sh
python tools/run_valuation.py data/valuation/nvidia_workbook_reproduction.json --output .runs/nvidia-valuation.json
python tools/run_valuation.py data/valuation/synthetic_business.json --output .runs/business-valuation.json
python tools/run_valuation.py data/valuation/synthetic_property.json --output .runs/property-valuation.json
```

These examples are research demonstrations. They do not contain a verified current market quote. Calculations can be inspected while the decision remains on hold.

## Layers

| Component | Responsibility |
| --- | --- |
| [Financial engine](../pilot/valuation.py) | Corporate FCFF, property income DCF, explicit annual paths, event effects, terminal value, enterprise-to-equity bridge, sensitivity and reverse growth. |
| [Decision layer](../pilot/valuation_layer.py) | Source checks, scenario weights, price comparison, entry ceiling, independent qualification gates and optional capital limits. |
| [Snapshot store](../pilot/valuation_store.py) | Immutable research runs, idempotent writes, restart recovery and links to existing parcel evidence. |
| [Local service](../pilot/founder_service.py) | Sessions, authorization, same-origin requests and JSON transport. |
| [Workspace](../web/valuation.html) | Edit assumptions, inspect results, save a version and export the evidence packet. |

This extends the existing pilot rather than creating a second application or replacing the acquisition underwriter. New stock and business studies are identified as research deals. A run attached to an existing parcel deal must use that deal's permanent parcel identity. Its result is appended as evidence; it never silently replaces the approved underwriting packet.

## Value, events and price

Corporate operating value is the discounted value of forecast free cash flow to the firm plus terminal value. Cash and nonoperating assets are added; debt and other declared equity-bridge claims are deducted. Dividing equity value by actual units gives value per share or per ownership unit. Property valuation discounts NOI less recurring capital expenditure and adds the sale proceeds from next year's NOI and the exit capitalization rate, less selling costs.

For each event, change identified assumptions and rerun the cash flows. Near-term shocks expire after the specified duration. A temporary growth-rate reduction can leave a permanently lower revenue base even after the growth rate recovers. Persistent margin effects also change terminal earnings. Discount-rate and reinvestment effects remain separately visible.

The layer applies a user-selected margin of safety once, to probability-weighted event-adjusted value:

```text
adjusted value = sum(scenario probability × scenario equity value per unit)
entry ceiling = adjusted value × (1 − margin of safety)
discount to value = (adjusted value − price) / adjusted value
upside to value = (adjusted value − price) / price
```

A 30% discount to unchanged value corresponds to approximately 42.86% upside to that value. The source author's historical entry reference is displayed separately from the application's event-adjusted ceiling.

Scenario probabilities are assumptions. The reported loss probability sums the weights of supplied scenarios with value below the comparison price. It is not an empirically calibrated forecast, and the scenarios do not bound every possible loss.

## Source reproduction

The [Nvidia example](../data/valuation/nvidia_workbook_reproduction.json) numerically reproduces the linked author workbook at approximately **$199.490586 per share** before event changes, and **$190.571480** in its saved replacement scenario. It preserves the source's explicit growth, margin, tax and discount paths and its next-year reinvestment timing. The figures are dated model outputs, not current fair-value assertions.

The [source audit](valuation-source-audit.md) records the conflicting date fields, missing price timestamp, discount-rate provenance and capitalized commitments. The original workbook is not redistributed. The model's calculation can reconcile while the underlying financial facts remain unverified.

The other examples are a [synthetic operating business](../data/valuation/synthetic_business.json) and a [synthetic income property](../data/valuation/synthetic_property.json).

## Evidence and qualification

Sources carry IDs, URLs, observation dates, review assertions and unresolved issues. The application performs consistency and age checks. It does not retrieve the URL or independently establish that a user's verification assertion is true. A source with an unresolved issue stays on hold even if its verification box is checked.

Financial inputs, scenarios, price and all three qualification gates need supporting evidence. A price must reference a quote or transaction-price source. Both the price and its source observation must satisfy the quote-age limit, and the price cannot postdate the observation that supports it. Buyable, fundable and sellable are independent; a lower price does not manufacture funding or an exit market. Statuses are:

- **Hold:** missing or stale evidence, an unresolved qualification, illustrative data, or nonpositive modeled equity value.
- **Watch:** evidence checks are satisfied but price or scenario-loss policy is not.
- **Review candidate:** the declared evidence and numeric policy pass. Independent investment approval remains a separate workflow.

None of these states permits order placement, fund movement or settlement. No capital is committed by this module.

An optional `capital` object limits research position size by available cash after reserves, concentration capacity and modeled scenario loss budget. Sizing cannot exceed the asset's total equity units. Whole properties and businesses modeled as one unit allow only zero or one whole purchase, with `quantity_step=1`. A hold or watch returns zero proposed units. This is a research bound, not a promise that losses cannot exceed the scenarios.

## Obligation accounting

Each claim record has a unique ID and exactly one cash-flow or equity-bridge treatment. Bridge claim totals cannot exceed debt plus debt-like claims declared in the model. Any unreconciled balance remains on hold; the report shows the declared, reconciled and outstanding totals. Claim records reconcile existing amounts; they are never automatically deducted a second time. An input author must still reconcile reported debt, leases and contingent commitments against the original financial statements. The application cannot detect the same economic obligation entered under unrelated IDs or concealed inside aggregate inputs.

## API

| Method and route | Result |
| --- | --- |
| `GET /api/valuation/examples` | Public synthetic/historical demonstration requests. |
| `POST /api/session` | Existing local reviewer/founder sign-in. |
| `POST /api/valuation/evaluate` | Validate and calculate a request without saving. |
| `POST /api/valuation/runs` | Recalculate and save `{request_id, packet}` atomically. |
| `GET /api/valuation/runs` | Latest 100 immutable commercial-workspace runs. |
| `GET /api/valuation/runs/VR-…` | A saved request and its frozen result. |

Inputs use absolute USD, actual shares and decimal rates. There is no live price connector, FX conversion or automatic input refresh. A digest changes when inputs, evidence, policy or engine version change. Repeating a save with the same operation ID and packet returns the original receipt; reusing that ID for different inputs returns a conflict.

## Validation

Run `python -m unittest discover -s tests -p 'test_valuation*.py' -v` for financial and HTTP checks. The full pilot gate is `python tools/check_pilot.py` after installing `requirements-checks.txt` and the required Playwright browsers.

Tests cover hand-calculated cash flows, cumulative changing discount rates, the source-workbook reproduction, temporary and lasting shocks, invalid terminal economics, inverse solutions and unavailable roots, source holds, scenario weights, obligation accounting, authorization, replay, restart recovery and asset identity.

The [valuation browser replay](guides/replay_valuation.md) runs against the real service and checks historical price labeling, stale-result locks, immutable history, interrupted-save retry, export, keyboard use and mobile layouts. Run `python tools/replay_valuation.py --engine both` to execute it separately. A browser launch restriction leaves this gate outstanding; it is not evidence that the interface passed.

## Limits

The corporate model is unlevered and applies no immediate tax credit to operating losses; it does not model tax-loss carryforwards. Declining revenue does not automatically release invested capital. The terminal corporate model requires nonnegative perpetual growth and sustainable positive operating earnings. Property NOI and recurring capital expenditure must be separately defined. Neither model forecasts capital structure changes, refinancing terms, dilution or liquidity by itself. The reverse solver changes one initial growth assumption while holding other assumptions fixed; it explicitly declines to solve a scalar initial growth when an annual growth path is supplied.
