# Architecture agent and swarm learning

**Corrected boundary (November 22, 2026):** Doc AI is the product workstream.
The builder swarm is part of the existing Black River swarm and skills
library that builds it. Reuse that organization and its review/learning
procedures; the new builder profiles do not replace its leaders or create
permanent agents inside Doc AI. The earlier evidence-to-offer example is a
downstream consumer demonstration, not a connected Doc AI service.

Use the [Doc AI ticket plan](../../config/docai-ticket-plan.json) for the
product workstream and the [swarm-library extension](../../config/swarm-library-extension.json)
for capability registration and ownership. Preserve the
[earlier builder breakdown](../../config/build-ticket-plan.json) as historical
evidence. The [builder procedure](builder-swarm.md) and
[engine/layer description](document-engine-layers.md) supply reusable
engineering context; neither establishes provider connectivity or deployment.

The [product portfolio](../PRODUCT_PORTFOLIO.md) describes System Architect and Swarm Review as separate offers and shows the tools each can use.

Black River's **System Architect** traces a business requirement through the system boundary, responsible component, behavior, and test. The same [project skill](../../.agents/skills/black-river-system-modeling/SKILL.md) gives the swarm a shared modeling procedure. Ask Codex to use `black_river_system_architect` from this checkout, or invoke `$black-river-system-modeling` for the procedure alone. Codex discovers a project agent from its [TOML definition](../../.codex/agents/black-river-system-architect.toml). [OpenAI custom-agent configuration](https://learn.chatgpt.com/docs/agent-configuration/subagents)

## Existing ownership and extension boundary

The existing BR-SWARM-001 master orchestration, BR-SWARM-SKILLS-001 library
and BR-1291-SKILLS-002 Academy source are organizational references. Resolve
them in the authorized source collection and reconcile their current versions
before changing role or competency definitions. Retrieved snapshots or a
copied workspace are not proof of a deployed execution service.

| Existing owner | Responsibility in this increment |
| --- | --- |
| L1 Strategy and Knowledge, with SW-00 coordination | Register capabilities, reuse the active workstream, resolve ownership and maintain the next handoff |
| L2 AI Systems Engineering | Own Doc AI software, provider interfaces and implementation quality |
| L3 Investment CIO/CFO | Review financial consumers and monetary semantics when they are affected |
| L4 Commercial Operations | Define filing, intake and operator workflow requirements |
| SW-13 Independent Audit | Challenge the evidence and preserve independent review boundaries |

The `br-*` builder roles are execution profiles beneath that ownership, not
new institutional leader IDs. The Doc AI product engine handles documents,
candidate facts and provenance. Its application layer handles intake/review
and downstream delivery. A future provider adapter can supply model-backed
candidate extraction after its connection and evaluation gates; loading a
skill or indexing its instructions never activates that adapter.

## Run one architecture review

| Role | Input and responsibility | Output |
| --- | --- | --- |
| System Architect | Start with an operating question and source revision. Select a context, structure or behavior view. Identify the actor, input contract, evidence, and verification. | A model with source links, boundary assumptions, and acceptance conditions. |
| Specialist agent | Check an assigned lane such as growth, finance, software, or assurance. Tie the claimed behavior and limitation to the source. | Evidence and a proposed lesson if the finding is reusable. |
| Independent reviewer | Reproduce the critical path and at least one material failure. Compare the model to the implementation. | Findings with severity, evidence, and missing checks. |
| Parent agent | Resolve findings with the evidence and maintain the canonical source. | A reviewed lesson, updated documentation or tests, and an issue cross-reference when work remains. |

For the Orchard example, start with the evidence-change model, then inspect the server's transaction and exercise the stale-packet test. A durable lesson should teach why an evidence digest matters, when the guard applies, and which test to rerun after changing it. [Worked approval model](modeling-black-river.md)

## Retrieve and promote lessons

The [learning index](../guides/learning_index.md) now includes exact registered
builder catalogs, plans, four role profiles, and Markdown directly under
`docs/plans`, alongside the existing guides and reviewed lessons. Its Git-index
boundary is unchanged: it reads staged blobs, not arbitrary working files,
private libraries, personal-skill folders or recursively discovered sources.
JSON and TOML remain cited text, not executable agent or provider configuration.

Rebuild after the integrator stages approved source material. Search by
question and read the cited source before reuse. Agents can propose lessons
through their task output. The parent checks the source and promotes reusable
work to a versioned lesson. Git supplies shared history; each workstation
rebuilds its own SQLite index. This registration extends the existing cited
learning tool without introducing another swarm runtime or importing a
separate organizational library implicitly.

Use the public repository for lessons whose source and conclusion are suitable for release. Keep internal documents, credentials and private data in the controlled library. Use the review date and source revision to determine when a lesson needs revalidation. The learning index improves retrieval. An agent learns from it when it reads the retrieved evidence on a later task.
