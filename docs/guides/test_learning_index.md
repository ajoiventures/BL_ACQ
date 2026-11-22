# Check retrieval and source boundaries

[The test suite](../../tests/test_learning_index.py) builds a temporary Git repository and SQLite index. Run `python -B -m unittest discover -s tests -p test_learning_index.py -v`.

Trace the uncommon word in the sample accepted lesson. The test resolves the chunk back to its exact lines, compares vectors across two builds and checks the recorded reviewer. Then change or delete a staged source. Rebuilding removes the old chunk and its search hits.

The remaining cases cover working-copy edits, skipped lesson drafts, excluded private paths, bad provenance and a preexisting unrelated database. The fixtures use synthetic text and require the Git executable plus Python’s standard library.

Builder-library cases verify the explicit plan/catalog/profile registrations,
resolve a structured JSON result to its staged blob, SHA-256 and exact lines,
and exclude untracked drafts, nested/private sources, unregistered configuration
and symbolic links. JSON/TOML retrieval remains cited text; it does not execute
agent or provider configuration.
