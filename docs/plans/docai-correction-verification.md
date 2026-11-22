# Doc AI scope and library integration verification

Reviewed on November 22, 2026. This record covers the correction after the
earlier document/evidence/acquisition increment. It does not certify a complete
Doc AI implementation or a provider connection.

## Changes delivered by this correction

- Audited document filing, model-client, evidence, application, ticket and
  Academy code across the available snapshots. Recorded implemented,
  disabled, unverified and planned capabilities in the
  [current-state audit](../architecture/docai-current-state.md).
- Added the [active Doc AI plan](docai-ticket-plan.md): 24 child work items
  beneath 38 verified existing master requirements. The original 84-item
  plan and its statuses remain intact as related work.
- Added the [library crosswalk](../../config/swarm-library-extension.json):
  14 procedures, four task profiles, all 84 original capability/ticket/status
  pairs, and six separately planned organizational integration items.
- Corrected project instructions, architecture, profile ownership and guides
  to preserve the existing organization and distinguish the Doc AI product,
  optional providers, builder tooling and downstream financial consumers.
- Extended the existing cited learning index with explicit builder artifact
  registrations. It retains the Git-index boundary and excludes untracked,
  arbitrary/private, nested and symbolic-link sources.

The active plan contains no inherited completed implementation tickets.
Its provider flags remain false. The actual selected-client implementation is
explicit work in BR-DOC-012, separate from the generic seam/mock in BR-DOC-007
and the later live evaluation in BR-DOC-013.

## Executed checks

| Check | Observed result | Meaning |
| --- | --- | --- |
| `python -m unittest tests.test_learning_index tests.test_builder_schedule -v` | 28 passed | Nine retrieval checks and 19 scheduler checks; no model or product deployment |
| Ruff `E9,F63,F7,F82` on the two changed Python files | Passed | Configured fatal-error subset; no comprehensive style/type claim |
| `python tools/check_guides.py` | Passed | Maintained source/guide coverage and local Markdown links |
| Four `br-*` TOML profiles | Parsed successfully | Configuration syntax, not running agents |
| Exact catalog/crosswalk reconciliation | 14 skill names, four profiles, 84 original ticket/capability/status pairs matched | No dropped or reset historical items |
| Six SWLIB items | Valid acyclic dependencies, one execution lane each, zero CUDA/R needs, ordered effort ranges and write scopes | Reviewable work package, not an organizational database import |
| Active Doc AI plan | 24 unique children, all 38 referenced parents present, valid scheduler graph | Requirements traceability and planning consistency |
| Provider policy | All live/model-download/production enablement flags false | No provider activation from this correction |
| Learning-index build and search | Successful staged-source build; Doc AI queries returned corrected architecture and audit sources with blob/hash citations | Existing library retrieval now includes the correction |
| `git diff --check` | Passed | No whitespace errors in the correction |

The integration also received an independent, fresh-context assignment review
using the corrected AI-adapter procedure and raw current plan/audit/crosswalk.
It recovered the selected-client/offline/live/production sequence, existing
ownership and required connection evidence without editing source or making
service calls. This is procedural review, not model-quality evaluation.

## Reproducible schedule result

The actual CLI accepted `config/docai-ticket-plan.json`:

```sh
python tools/schedule_builder_work.py --plan config/docai-ticket-plan.json
```

Declared statuses: 18 planned, four blocked and two deferred. Dependency
propagation yields 16 scheduled, six blocked and two excluded, with zero
completed. Ready next are BR-DOC-001 and BR-DOC-003. The profile is three
workers plus one reserved integrator; no CUDA or R is allocated.

Exact JSON file-byte SHA-256:
`2269f4ce1dfc2edcb89dfbbd38d813cba62f71d2a330f3e7f4b385c8ad98fc26`.

Scheduler canonical-JSON `plan_sha256`:
`81843cd61e8d5ff14dba5733c55363fb3e8d82e0641d1f5a141a444f43ad4e75`.

These hashes cover different representations of the same plan. The reported
930 relative-minute point schedule and 590–1,900 low/high scenarios use
assumed effort for the schedulable scope. They exclude blocked work, external
waiting and provisioning. They are neither confidence intervals nor delivery
promises. A changed plan needs a fresh schedule.

## Existing master publication boundary

The correction was appended to the existing BR-SWARM-001 orchestration,
BR-SWARM-SKILLS-001 library, BR-SWARM-ARCH-002 architecture and
BR-ENG-MASTER-001 backlog. Read-back verified every added paragraph once and
preservation of the original normalized text. Private source bodies and
storage locators are not reproduced in this repository.

Personal procedure updates and canonical documentation registration are
separate from organizational application import. No live Academy database,
canonical BR-T status, private executor channel or provider was changed by
this repository crosswalk.

## Limits and open gates

- No NVIDIA or Ollama provider call, credential probe, model download or
  live document upload ran. The existing local client remains unverified.
- No R execution, actual CUDA benchmark, production rollout, operating
  acquisition action or live worker dispatch ran.
- Native parser completeness, document-neutral identity, real provider
  compatibility and the general Doc AI application remain implementation work.
- The financial engines and their recorded earlier validation were preserved;
  their full suite was not repeated for this bounded index/plan correction.
- Hosted release acceptance remains separate. The earlier published commit
  had a failed hosted run with unavailable job diagnostics. This record makes
  no claim that the new revision passed hosted CI or browser acceptance.
- The recovered organizational workspaces lacked verified Git/deployment
  identity. BR-DOC-001 remains open for canonical execution source and reviewed
  adapter ownership; copying a snapshot does not resolve that decision.

See the [full plan](docai-ticket-plan.md) and
[engine/application boundaries](../architecture/document-engine-layers.md)
before dispatching implementation work.
