# Document-engine validation plan

This plan maps current claims to checks and preserves wider acceptance gaps.
It supports BR-BUILD-061. The integrator reviews executed evidence; a builder
self-report or a scheduler's completed flag does not authenticate completion.

| Claim | Independent or adverse evidence | Acceptance boundary |
| --- | --- | --- |
| Document identity is immutable | Real SQLite tests attempt changed-content reuse, mutation and partial bundle failures | Immutable records and rollback are proved for the tested local API; production archival and identity remain separate |
| Only current reviewed facts enter projection | Pending, rejected, future, expired, superseded, conflicting and wrong-deal cases | No fallback to an older accepted quote when a newer effective revision is pending |
| Money retains its meaning | Boolean/noninteger/bounds/unit/currency rejection; known exact cents | No implicit dollars/cents conversion or silent float rounding |
| Event calculations reconcile | Independently stated known answers, exact terminal mass, conditional/unconditional distinctions and discrete chance boundaries | Assumed inputs are not empirical calibration; deadlines remain descriptive in the current packet |
| Source changes propagate atomically | Four-stage real-store demonstration plus price/probability-context holds and unchanged input copies | All required bindings succeed together; no transaction authorization follows |
| Synthetic provenance remains visible | A synthetic reviewed source entering a non-illustrative input packet remains illustrative in the adjusted result | Review cannot turn fictional evidence into real evidence |
| The product path is independent of AI | Empty AI credentials and socket construction forbidden during the complete demonstration | This verifies the tested local path; it is not an attestation about every future integration |
| R exchange preserves values | Exact rational strings, empty unknowns, content digest, row IDs and overwrite protection | Python export contract only; independent R execution is still required |
| CUDA is explicit | CPU reference plus unavailable-backend behavior; real-device parity test when present | Skipped hardware checks are unavailable evidence, never a measured speedup |
| Builder scheduling respects constraints | Cycles, unknown dependencies, phase gates, blocked work, zero CUDA/R, capacity, owner and path conflicts | Offline planning heuristic; statuses and resources are supplied assertions |
| Changes preserve the existing workspace | Related domain regression suite, lint, scoped types, source guides, tool tests and applicable recovery checks | Browser/runtime restrictions must be recorded if a required check cannot run |

## Handoff and completion record

Every completion assertion records the ticket ID, source paths and revision,
acceptance criteria, commands executed, observed results, unavailable checks,
remaining limitations and reviewing integrator. A failed check returns work
to its owner and retains the failure. Effective prerequisites must also be
completed before a ticket can be completed in the scheduler.

Use `implementation_evidence` to record verified portions of a broader
planned ticket. Do not narrow a broad acceptance criterion merely to turn the
status green. In particular, authenticated review independence, generalized
document reconciliation, full financing/liquidity coverage, empirical
probability calibration, multi-round negotiation policy, cross-language
parity, GPU benchmarking and production readiness have their own gates.

The [build verification record](../plans/document-engine-verification.md)
contains the results observed for this increment. The
[canonical ticket plan](../../config/build-ticket-plan.json) records completed
versus still-planned work and its evidence.
