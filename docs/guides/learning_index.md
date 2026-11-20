# Find a lesson with its source

[The learning index](../../tools/learning_index.py) searches the repository’s published technical notes and reviewed agent lessons offline. From the repository root, build the local index, search it, then open a matching passage by its chunk ID.

```powershell
python tools/learning_index.py index
python tools/learning_index.py search "lease expiry" --limit 3
python tools/learning_index.py read CHUNK_ID
```

The machine-generated database lives in `.runs/learning.sqlite3`. Each collaborator rebuilds it from the same Git index and receives the same vectors and citations. New learners can run the commands immediately after a clone. A local author stages approved source edits before rebuilding. A rebuild removes deleted passages and recalculates term weights.

**Source boundary.** The [source collector](../../tools/learning_index.py) reads stage-zero Git blobs for the root README, the system-modeling skill, reviewed lessons directly under `docs/learning`, and Markdown directly under `docs`, `docs/guides`, `docs/architecture`, `pilot`, `tools`, `tests` and `web`. Unstaged edits, untracked material, symbolic links and attachments fall outside that collection. A merge conflict stops the rebuild. Review repository sharing permissions before adding a new source.

**Record a lesson.** Start a Markdown file under `docs/learning` with a title. Put `Review: accepted`, `Reviewed by: reviewer identity and role`, and `Source: tracked/repo/file` on separate lines before the first subsection. Name the person or agent that performed the review, describe the reproduced behavior, link the test and state the boundary of its proof. A draft stays out of search. An accepted lesson missing a reviewer or a tracked source prevents publishing a replacement index. The [receipt lesson](../learning/receipt-evidence.md) shows this format.

**Read a result.** Each passage carries a repository path, inclusive line interval, source SHA-256, Git blob ID and chunk ID. Compare the cited lines in that revision. `git cat-file -p BLOB_ID` prints the source snapshot even after the working file changes. The database stores the reviewed lesson’s source revision separately. Review labels preserve the recorded authorship and evidence, and do not authenticate a reviewer.

**Ranking.** Terms use case-folding, a short stop-word list and sublinear term frequency. The index weights rare terms with smoothed inverse document frequency across passages. The dot product of normalized sparse vectors gives cosine similarity. This favors shared words and identifiers. Paraphrases, contradictions and claims unsupported by evidence require direct source review. A zero-overlap query yields an empty result.

Run the [regression checks](test_learning_index.md) to verify the retrieval path.
