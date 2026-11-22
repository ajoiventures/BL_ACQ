# Product integrator agent

The [agent profile](../../.codex/agents/br-product-integrator.toml) defines a development coordinator. It does not start a service or put an agent inside the product.

Start with `AGENTS.md`, the [skill catalog](../../config/builder-skills.json) and the [ticket plan](../plans/document-engine-tickets.md). The integrator owns shared contracts, work allocation, acceptance evidence and release reporting. Workers receive bounded paths and must return the commands they actually ran.

The [builder scheduler](../../tools/schedule_builder_work.py) produces a proposed schedule. The integrator dispatches work using the agent capacity actually available and reserves room to review and integrate it. Estimated durations are assumptions; the planner does not launch agents.

Inspect `developer_instructions` for the engine-before-layer boundary, CPU/CUDA precision rules, R separation and prohibited transaction effects. Check the profile with Python's `tomllib` and verify its guide through `python tools/check_guides.py`.
