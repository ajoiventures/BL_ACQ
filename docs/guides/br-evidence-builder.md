# Evidence builder agent

The [agent profile](../../.codex/agents/br-evidence-builder.toml) defines a development worker for documents, reviewed claims, mappings and workflow evidence.

Follow the assigned ticket into the [document evidence engine](../../pilot/document_evidence.py) and [application layer](../../pilot/document_offer_layer.py). A candidate fact carries deal identity, source location, type, units and review history. The builder must preserve holds for missing, conflicting, stale and superseded evidence.

Read the profile's ownership and handoff instructions before dispatch. It may change only assigned paths and returns source changes, verification commands and remaining risks. It cannot approve its own delivery or perform a real acquisition action.

The optional AI provider boundary is deliberately later. This worker's existence during development does not create a runtime AI dependency. Validate the TOML with `tomllib` and run `python tools/check_guides.py` after profile edits.
