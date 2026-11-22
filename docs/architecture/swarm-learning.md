# Architecture agent and swarm learning

**Current boundary (November 22, 2026):** the active swarm consists of builders
working on this codebase. The deterministic engines and application layer run
without product AI agents. Follow [the builder swarm plan](builder-swarm.md)
and [engine/layer boundaries](document-engine-layers.md) for the current scope.
Product-facing AI and runtime swarms discussed as future offers below are not
enabled by the development swarm.

The [product portfolio](../PRODUCT_PORTFOLIO.md) describes System Architect and Swarm Review as separate offers and shows the tools each can use.

Black River's **System Architect** traces a business requirement through the system boundary, responsible component, behavior, and test. The same [project skill](../../.agents/skills/black-river-system-modeling/SKILL.md) gives the swarm a shared modeling procedure. Ask Codex to use `black_river_system_architect` from this checkout, or invoke `$black-river-system-modeling` for the procedure alone. Codex discovers a project agent from its [TOML definition](../../.codex/agents/black-river-system-architect.toml). [OpenAI custom-agent configuration](https://learn.chatgpt.com/docs/agent-configuration/subagents)

## Run one architecture review

| Role | Input and responsibility | Output |
| --- | --- | --- |
| System Architect | Start with an operating question and source revision. Select a context, structure or behavior view. Identify the actor, input contract, evidence, and verification. | A model with source links, boundary assumptions, and acceptance conditions. |
| Specialist agent | Check an assigned lane such as growth, finance, software, or assurance. Tie the claimed behavior and limitation to the source. | Evidence and a proposed lesson if the finding is reusable. |
| Independent reviewer | Reproduce the critical path and at least one material failure. Compare the model to the implementation. | Findings with severity, evidence, and missing checks. |
| Parent agent | Resolve findings with the evidence and maintain the canonical source. | A reviewed lesson, updated documentation or tests, and an issue cross-reference when work remains. |

For the Orchard example, start with the evidence-change model, then inspect the server's transaction and exercise the stale-packet test. A durable lesson should teach why an evidence digest matters, when the guard applies, and which test to rerun after changing it. [Worked approval model](modeling-black-river.md)

## Retrieve and promote lessons

The [learning index](../guides/learning_index.md) indexes repository guides and reviewed lessons. Rebuild it after merging updated source material. Search by question and read the cited source before reuse. Agents can propose lessons through their task output. The parent checks the source and promotes reusable work to a versioned lesson. Git supplies the shared history. Each workstation rebuilds its own SQLite index.

Use the public repository for lessons whose source and conclusion are suitable for release. Keep internal documents, credentials and private data in the controlled library. Use the review date and source revision to determine when a lesson needs revalidation. The learning index improves retrieval. An agent learns from it when it reads the retrieved evidence on a later task.
