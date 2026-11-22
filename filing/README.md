# Trace local filing and original-byte receipts

[inbox.py](inbox.py) extends the existing `file_document(path, root,
destination=None)` interface. It takes one local regular file, preserves its
original bytes, chooses a configured folder and appends or replays a SQLite
receipt. [routes.json](routes.json) supplies only generic `Review` and `Invoices`
routes in this increment; no private organizational route configuration was copied.

```bash
python filing/inbox.py tests/fixtures/docai/invoice_native.txt --root .runs/native-archive
python filing/inbox.py tests/fixtures/docai/invoice_native.txt --root .runs/native-archive --to Review
```

The return object retains exactly `destination`, `file`, `sha256` and `reason`.
`file` is an absolute archived path with the original suffix. Ordinary legacy
archive names retain `sha256--filename`; long names retain a bounded Unicode
prefix and their suffix. Source files remain untouched. Explicit destinations
must exactly match a safe configured relative route. One content match selects
that folder; no match, several matches or unreadable native text selects Review.
This content routing is a convenience, not a verified classification or review.

## Snapshot, replay and history

Intake reads at most 16 MiB plus one guard byte from a regular file and checks
its size and file metadata before and after the read. It hashes that actual
snapshot, writes a private temporary copy and creates the archive without
overwriting an existing target. A conflicting existing target fails integrity
checking. An identical target is reused.

The `receipts(path TEXT PRIMARY KEY, hash TEXT, reason TEXT, filed_at TEXT
DEFAULT CURRENT_TIMESTAMP)` table and existing rows are preserved. New records
use `INSERT OR IGNORE`; a hash conflict fails visibly. Replaying after an
interruption between archive creation and receipt insertion repairs the missing
receipt. Existing reasons and dates are not rewritten. For compatibility, the
returned `reason` describes the current routing request, which can differ from
an older persisted reason after an explicit reroute or configuration change.
Different route/name combinations can have distinct receipts for identical
content; this is content-addressed naming, not a global deduplication database.

## Native parsing

`extract(path)` remains a text-only compatibility helper. New consumers call
`extract_details(path, limits=...)`, or use the strict document adapter described
in [the native extraction guide](../docs/guides/document_native.md). Structured
results preserve page text hashes, coverage, limits and failure reasons. A PDF
scan does not become an empty successful extraction. Native reader success does
not approve extracted facts or infer invoice fields.

TXT, MD and CSV use strict UTF-8. DOCX reads bounded UTF-8 main-document XML.
PDF uses the optional dependency pinned in
[requirements-docai.txt](../requirements-docai.txt):

```bash
python -m pip install -r requirements-docai.txt
```

PDF/DOCX run in a subprocess with a ten-second deadline, a 512 MiB address-space
ceiling and an OS CPU-time limit. If enforceable resource limits are unavailable,
these readers return `RESOURCE_LIMIT_UNAVAILABLE`; this increment is tested on
Linux, not a cross-platform sandbox certification. No source is sent to a model
or network service. The selected future NVIDIA connection remains a separate
adapter/readiness task.

## Local trust and compatibility boundary

New archive roots use mode 0700; original copies and a newly created receipt
database use mode 0600. Existing directory permissions and receipt history are
not silently migrated. On POSIX the archive root must belong to the current
user and cannot be writable by group or others. Operators must keep existing
ancestors and archive descendants private: local checks do not implement user
authentication, tenant authorization, virus scanning or protection against a
hostile process with the same OS identity. Paths containing symlinks, unsafe
routes, nonregular sources and symlinked database sidecars fail explicitly.

The port derives from the audited generic `filing/inbox.py` with SHA-256
`7dac3fae6722ed660f4d4c9be66df16cfc59932eb15688226c724c9322aa7b0a`.
The recovered implementation is a reuse reference, not deployment authority.
This versioned BL_ACQ increment does not replace the organizational workspace
or migrate its private archive or database.

Run `python -m unittest tests.test_docai_native` for the
[compatibility and adverse-case checks](../docs/guides/test_docai_native.md).
