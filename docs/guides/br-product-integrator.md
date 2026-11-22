# Product integrator agent

The [agent profile](../../.codex/agents/br-product-integrator.toml) defines a development coordinator. It does not start a service or put an agent inside the product.

Start with `AGENTS.md`, the [skill catalog](../../config/builder-skills.json),
[existing-library crosswalk](../../config/swarm-library-extension.json) and
[active Doc AI plan](../plans/docai-ticket-plan.md). This profile serves existing
L1/L2 ownership and SW-00 coordination, with SW-13 independent review. Preserve
PROJECT_INTERNAL ticket closure authority. Workers receive bounded paths and
must return the commands they actually ran.

The [builder scheduler](../../tools/schedule_builder_work.py) produces a proposed schedule. The integrator dispatches work using the agent capacity actually available and reserves room to review and integrate it. Estimated durations are assumptions; the planner does not launch agents.

Inspect `developer_instructions` for the engine-before-layer boundary, CPU/CUDA precision rules, R separation and prohibited transaction effects. Check the profile with Python's `tomllib` and verify its guide through `python tools/check_guides.py`.

Develop the provider contract with the document core. Live inference follows
the smallest reviewable workflow's readiness gate; the prior acquisition plan
does not delay it. Builder profiles remain outside the Doc AI runtime.
