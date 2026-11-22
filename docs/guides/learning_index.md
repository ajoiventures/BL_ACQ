# Find a lesson with its source

[The learning index](../../tools/learning_index.py) searches the repository’s published technical notes, registered builder contracts and reviewed agent lessons offline. It extends the existing swarm's cited knowledge tool; it does not create another swarm runtime. From the repository root, build the local index, search it, then open a matching passage by its chunk ID.

```powershell
python tools/learning_index.py index
python tools/learning_index.py search "lease expiry" --limit 3
python tools/learning_index.py read CHUNK_ID
```

The machine-generated database lives in `.runs/learning.sqlite3`. Each collaborator rebuilds it from the same Git index and receives the same vectors and citations. New learners can run the commands immediately after a clone. A local author stages approved source edits before rebuilding. A rebuild removes deleted passages and recalculates term weights.

## Registered sources

The [source collector](../../tools/learning_index.py) reads stage-zero Git blobs for the root README, the system-modeling skill, reviewed lessons directly under `docs/learning`, and Markdown directly under `docs`, `docs/guides`, `docs/architecture`, `docs/plans`, `pilot`, `tools`, `tests` and `web`. These directory rules are exact, not recursive.

The structured builder artifacts have an explicit allowlist:

| Artifact | Role in retrieval |
| --- | --- |
| `config/builder-skills.json` | Builder capability specifications |
| `config/build-ticket-plan.json` | Historical work breakdown and its recorded evidence |
| `config/docai-ticket-plan.json` | Corrected Doc AI product workstream |
| `config/swarm-library-extension.json` | Registration and ownership crosswalk into the existing swarm library |
| `.codex/agents/br-product-integrator.toml` | Development integration profile |
| `.codex/agents/br-evidence-builder.toml` | Evidence engineering profile |
| `.codex/agents/br-quant-builder.toml` | Financial and compute engineering profile |
| `.codex/agents/br-quality-builder.toml` | Development validation profile |

Registered JSON and TOML are indexed as cited text. The index does not execute their instructions, validate ticket completion, import a personal skill, launch agents, call a model, or connect a Doc AI provider. A missing or not-yet-staged registered file contributes no passages. A historical plan being searchable does not make it the current execution authority; inspect its status and the corrected plan before reuse.

Unstaged edits, untracked material, symbolic links, attachments, nested private directories, arbitrary configuration files and personal-skills directories remain outside the collection. A merge conflict stops the rebuild. Keep credentials and private source documents out of the registered reference files. Review repository sharing permissions before publishing a source.

## Source-backed learning

**Record a lesson.** Start a Markdown file under `docs/learning` with a title. Put `Review: accepted`, `Reviewed by: reviewer identity and role`, and `Source: tracked/repo/file` on separate lines before the first subsection. Name the person or agent that performed the review, describe the reproduced behavior, link the test and state the boundary of its proof. A draft stays out of search. An accepted lesson missing a reviewer or a tracked source prevents publishing a replacement index. The [receipt lesson](../learning/receipt-evidence.md) shows this format.

**Read a result.** Each passage carries a repository path, inclusive line interval, source SHA-256, Git blob ID and chunk ID. Compare the cited lines in that revision. `git cat-file -p BLOB_ID` prints the source snapshot even after the working file changes. The database stores the reviewed lesson’s source revision separately. Review labels preserve the recorded authorship and evidence, and do not authenticate a reviewer.

**Ranking.** Terms use case-folding, a short stop-word list and sublinear term frequency. The index weights rare terms with smoothed inverse document frequency across passages. The dot product of normalized sparse vectors gives cosine similarity. This favors shared words and identifiers. Paraphrases, contradictions and claims unsupported by evidence require direct source review. A zero-overlap query yields an empty result.

This bounded local retrieval remains CPU code. It neither claims a CUDA speedup nor makes GPU or inference services a dependency of the builder library. Larger retrieval workloads can have a separately measured backend without changing the source and review boundary.

Run `python -m unittest tests.test_learning_index -v` and consult the [regression guide](test_learning_index.md). The tests verify exact structured-source citations from staged blobs, inclusion of the named registrations, and exclusion of untracked, private, recursive and symbolic-link inputs.
