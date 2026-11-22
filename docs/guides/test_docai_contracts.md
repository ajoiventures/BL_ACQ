# Check the document-neutral contract boundary

[test_docai_contracts.py](../../tests/test_docai_contracts.py) validates the
[contract example bundle](../../schemas/docai/examples.json) and makes targeted
adverse changes to it. The tests run with the Python standard library and make
no model or service calls. The round-trip case patches socket construction to
fail so a future accidental transport call cannot silently enter that path.

Run from the repository root:

```bash
python -m unittest tests.test_docai_contracts -v
```

## What the checks establish

| Check family | Concrete failure it prevents |
| --- | --- |
| Neutral identity | A missing tenant/subject, unknown domain or inserted financial `deal_id` passing as a generic document |
| Schema and exact types | Unknown properties/versions, tuples/bytes/nonstring JSON keys, NaN/Infinity and Boolean-as-integer coercion |
| Source/version binding | A changed source hash, tenant, source version or extraction identity attaching to another document |
| Version history shape | Missing or self-referential predecessors and duplicate asset associations |
| URI and time | Credential-bearing or whitespace-containing references, implicit timezone strings and impossible dates |
| Coverage | Unknown or truncated coverage being labeled complete, count/hash mismatches, or retained text exceeding declared limits |
| Disabled state | A disabled adapter claiming bytes/pages were processed or supplying usable candidate evidence |
| Provider provenance | Missing model/API/raw-response metadata, provider output relabeled as native, confidence used on native claims, and provider self-acceptance fields |
| Evidence spans | Changed quotes/hashes, source-page mismatches and UTF-8 byte offsets passed as Unicode code-point offsets |
| Numeric precision | Float/string/Boolean money, missing units/currency, out-of-range integers and lossy values above `2**53` |
| Exact decimal measurements | Exponent/float/nonfinite notation, missing unit and noncanonical negative zero |
| Review binding | A review targeting another claim/run/context/version, changing the claim value or predating its creation |
| Class scope | Unknown documents producing candidates, unregistered class fields and registry claims of twelve functioning parsers |

The example has no acquisition deal. Its family context, source identity and
review identity are preserved through each validator, and mutating a returned
nested dictionary does not mutate the supplied record. This is important when a
caller reuses a validated source while evaluating multiple proposals.

The Unicode case begins a page with an emoji and verifies a later amount. The
correct offset is computed from the Python string; substituting the encoded
UTF-8 byte length fails. The precision case round-trips `2**53 + 1` through the
runtime JSON encoding without changing its integer value. An external consumer
must supply its own equally exact decoding.

## Structural schema verification

[records.schema.json](../../schemas/docai/records.schema.json) is a structural
interchange aid. The executable validators remain authoritative for cross-record
identities, hashes, code-point slices, UTC calendar normalization, exact runtime
types, aggregate UTF-8 text budgets and class-specific field/type relationships.
JSON Schema validators may treat numerically integral JSON numbers as integers;
the Python boundary deliberately rejects a Python float such as `12500.0`.

If `jsonschema` is already installed in the inspection environment, a separate
optional check is:

```bash
python - <<'PY'
import json
from pathlib import Path
from jsonschema import Draft202012Validator

schema = json.loads(Path("schemas/docai/records.schema.json").read_text())
bundle = json.loads(Path("schemas/docai/examples.json").read_text())
Draft202012Validator.check_schema(schema)
validator = Draft202012Validator(schema)
for name in ("document", "extraction", "candidate", "review"):
    validator.validate(bundle[name])
print("Structural schema and all four examples passed")
PY
```

This inspection is not a runtime package requirement. It uses the installed
Draft 2020-12 implementation and does not fetch the sources named by document
URIs.

## What remains outside this test boundary

These checks do not read original source files, authenticate reviewers, exercise
transaction races or enforce append-only database history. Those obligations
belong to native reader, vault and application tests. They also do not measure
parser semantic accuracy, OCR quality, CUDA performance, provider latency,
NVIDIA availability or R behavior. Native processing tests and corpus metrics
must demonstrate their own outcomes before any of those capabilities are
reported as available.

The tests preserve a separate schema boundary from the existing acquisition
evidence engine. They do not claim an automatic migration or a production access
control system. See the [contract mechanics guide](document_contracts.md) for
the explicit adapter and reviewer-authority responsibilities.
