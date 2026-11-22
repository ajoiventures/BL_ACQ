# Evidence builder agent

The [agent profile](../../.codex/agents/br-evidence-builder.toml) defines a development worker for documents, reviewed claims, mappings and workflow evidence.

Follow the active [Doc AI plan](../plans/docai-ticket-plan.md) and [source audit](../architecture/docai-current-state.md). Reuse the existing filing interface and [document evidence primitives](../../pilot/document_evidence.py). The [offer consumer](../../pilot/document_offer_layer.py) is acquisition-specific. General candidate facts need subject/case/domain identity, source location, type, units and review history. Preserve holds for missing, conflicting, stale and superseded evidence.

Read the profile's ownership and handoff instructions before dispatch. It may change only assigned paths and returns source changes, verification commands and remaining risks. It cannot approve its own delivery or perform a real acquisition action.

This task profile serves L2 engineering and L4/SW-09 workflow ownership, with SW-00 coordination and SW-13 review. Build the provider contract and fake/disabled tests now; live inference follows a bounded readiness milestone. This worker does not create a runtime AI dependency. Validate the TOML with `tomllib` and run `python tools/check_guides.py` after profile edits.
