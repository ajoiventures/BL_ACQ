"""Thin local Doc AI application: filing, native proposals, review and export.

The initial field extractor recognizes an explicitly declared invoice label
grammar. It does not interpret arbitrary invoices, scan images, or call a model.
"""
import hashlib
import json
from pathlib import Path

from filing.inbox import file_document
from pilot.document_contracts import SCHEMA_VERSION, canonical_json, validate_context
from pilot.document_invoice import invoice_candidates
from pilot.document_native import extract_document
from pilot.document_vault import DocumentVault, utc_now


MEDIA_TYPES = {".txt": "text/plain", ".md": "text/markdown", ".csv": "text/csv", ".pdf": "application/pdf",
               ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"}
MAX_ORIGINAL_BYTES = 16 * 1024 * 1024


def _identifier(prefix, value):
    return prefix + hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()[:40]


def original_fingerprint(path):
    """Hash bounded original bytes; a symlink is not an accepted original."""
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError("Expected a regular original file without a symlink")
    digest, count = hashlib.sha256(), 0
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(65536), b""):
            count += len(block)
            if count > MAX_ORIGINAL_BYTES:
                raise ValueError("Original exceeds the 16 MiB intake bound")
            digest.update(block)
    return digest.hexdigest(), count


class DocumentApplication:
    """Synchronous single-user application; no daemon or leased work queue."""

    def __init__(self, root, *, context, actor):
        self.context = validate_context(context)
        self.root = Path(root).expanduser().absolute()
        # Private local root; OS ownership remains the actual trust boundary.
        if any(part.is_symlink() for part in (self.root, *self.root.parents)):
            raise ValueError("The local application root must not traverse symlinks")
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        if not self.root.is_dir():
            raise ValueError("Application root must be a directory")
        self.context_root = self.root / _identifier("context-", self.context)
        if self.context_root.is_symlink():
            raise ValueError("Context root must not be a symlink")
        self.context_root.mkdir(exist_ok=True, mode=0o700)
        database = self.context_root / "documents.sqlite3"
        if database.is_symlink():
            raise ValueError("Document database must not be a symlink")
        self.vault = DocumentVault(database, context=self.context, actor=actor)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.vault.__exit__(*exc)

    def ingest(self, path, *, document_class, source_status="supplied", limits=None):
        """Retain the original, then atomically persist a bounded native result."""
        path = Path(path)
        receipt = file_document(path, self.context_root / "filing")
        archived = Path(receipt["file"])
        digest, byte_count = original_fingerprint(archived)
        if digest != receipt["sha256"]:
            raise ValueError("Archived original no longer matches its filing receipt")
        document_id = _identifier("doc-", [self.context, digest, document_class, source_status])
        old = self.vault.document(document_id)
        if old is not None:
            # Idempotent intake preserves the first run, review history and time.
            return self.inspect(document_id)
        document = {"schema_version": SCHEMA_VERSION, "document_id": document_id, "context": self.context,
                    "version": 1, "source_uri": "local://original/" + digest, "title": path.name,
                    "media_type": MEDIA_TYPES.get(path.suffix.lower(), "application/octet-stream"),
                    "document_class": document_class, "content_sha256": digest, "byte_count": byte_count,
                    "received_at": utc_now(), "source_status": source_status,
                    "predecessor_document_id": None, "asset_links": []}
        run_id = _identifier("run-", [document_id, "native.v1", limits])
        extraction = extract_document(archived, document, run_id, limits=limits)
        candidates = invoice_candidates(document, extraction)
        return self.vault.add_bundle(document, extraction, candidates, archive=receipt)

    def _verify_original(self, snapshot):
        archived = Path(snapshot["archive"]["file"])
        if not archived.is_absolute():
            raise ValueError("Archive receipt must identify its absolute original")
        if not archived.resolve().is_relative_to(self.context_root.resolve()):
            raise ValueError("Archive is outside its document context")
        if any(part.is_symlink() for part in (archived, *archived.parents)):
            raise ValueError("Archived original traverses a symlink")
        digest, count = original_fingerprint(archived)
        document = snapshot["document"]
        if digest != document["content_sha256"] or count != document["byte_count"]:
            raise ValueError("Archived original has changed; review and export are held")

    def inspect(self, document_id):
        snapshot = self.vault.inspect(document_id)
        self._verify_original(snapshot)
        return snapshot

    def review(self, claim_id, **request):
        candidate = self.vault._record("candidate", claim_id)
        if candidate is None:
            raise ValueError("Candidate is absent from this context")
        self.inspect(candidate["document_id"])
        return self.vault.review(claim_id, **request)

    def correct(self, candidate, *, expected_revision):
        self.inspect(candidate.get("document_id"))
        return self.vault.correct(candidate, expected_revision=expected_revision)

    def export(self, document_id):
        # The transaction holds the database revision while original integrity is
        # checked. Local filesystem owners can still mutate files; no WORM claim.
        with self.vault.store.transaction():
            self.inspect(document_id)
            return self.vault.accepted_export(document_id)


def write_json_new(path, record):
    """Never overwrite an earlier evidence/export artifact."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(record, stream, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write("\n")
