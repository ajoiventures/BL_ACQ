# Test inventory coverage and output safety

Run this regression suite from the repository root.

```powershell
python -m unittest discover -s tests -p test_inventory.py -v
```

The test creates a temporary source directory containing one Python file and a ZIP with the same bytes. It checks that the CLI finds two occurrences with one digest. It then exercises the output contract. An existing JSON file keeps its original bytes, an output inside the scanned tree is rejected, and a completed inventory survives a repeated command targeting the same name.

When extending format recognition, add a tiny source member to the fixture and update the expected occurrence and unique-hash counts. To exercise a new limitation, inspect the returned JSON and exit status. The [inventory guide](inventory.md) explains the command and report fields.
