# Check the code guides

[The checker](../../tools/check_guides.py) reads the maintained sources, the code map and Markdown links. It prints missing mappings or broken paths and returns a failing exit code if it finds a problem. It reads files without changing them.

1. Follow `check` into the directory walk. Build caches and example output are skipped.
2. Inspect the set of source paths. Each source needs one row in the [code map](../code-map.md) pairing it with a linked guide.
3. Follow `local_links` from a document to a target path. The final loop catches references to moved or deleted files. External websites and page anchors are outside this check.

Run `python tools/check_guides.py` from the repository root. To see a failure, try a disposable copy of the workspace and rename one guide there. Restore the filename and rerun. Continue with the [VS Code tasks](vscode.md).
