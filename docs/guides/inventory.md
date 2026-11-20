# Inventory a source handoff

Use the inventory before combining branches or unpacking old handoffs. It gives each source occurrence a relative path, byte count, line count and SHA-256 digest. Equal hashes identify byte-for-byte copies across differently named packages. Keep reports containing private source names in the private review directory.

## Walk through a small example

Run from the repository root with Python 3.10 or newer. Choose a fresh filename in an existing directory outside the source tree. The command refuses to overwrite files and rejects destinations inside scanned paths. Use a different filename for each run.

```powershell
python tools/inventory.py --source "demo=Python_Asset_Demo" --output ../demo-inventory.json
$report = Get-Content -Raw ../demo-inventory.json | ConvertFrom-Json
$report.roots[0].sources | Select-Object path, lines, python_syntax
$report.roots[0].limitations
```

1. The label before `=` describes the source in the output. Repeat `--source` to compare another tree, a ZIP file, or an individual script. A directory input includes ZIPs beneath it.
2. Review `archives` to identify each handoff by its own hash. Source members use `package.zip!path/to/file`. The tool reads these in memory. Directory links, dependency trees, Git internals and bytecode caches are skipped.
3. Compare `source_occurrences` with `unique_source_hashes`. Inspect the recorded branch revision separately when comparing snapshots. A digest establishes file identity. The Python syntax check parses the source without importing it. Functional correctness requires review and tests.
4. Check `limitations` before accepting coverage. Exit code 1 means the inventory includes explicit limitations, such as an unreadable source, a nested archive or a size bound. A recorded Python syntax failure is a review finding. Use exit code 2 for CLI usage errors.

Pass `--exclude-dir NAME` for generated or private subdirectories outside the review scope. The supported source extensions and size limits are at the top of `tools/inventory.py`. The report covers those formats. Generic configuration, generated binary scenes, prose and database records are outside the source-file count. For a repeatability check, run twice against the same immutable inputs and compare the JSON files.
