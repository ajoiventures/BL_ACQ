"""Bind bounded native extraction to the versioned Doc AI source contract."""
from datetime import datetime, timezone
import hashlib

from filing.inbox import extract_details, WORKER_MEMORY_BYTES, WORKER_TIMEOUT_SECONDS
from pilot.document_contracts import (SCHEMA_VERSION, DEFAULT_LIMITS, canonical_json,
                                      validate_document, validate_extraction, validate_limits)


def _utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def extract_document(path, document, run_id, *, limits=None):
    """Extract archived bytes; caller supplies identity, class and source rights.

    Format failures return structured runs. Invalid identity, changed source,
    symlink paths or a source above the hard intake bound raise ValueError.
    No model, approval, field candidate, network call or persistent write occurs.
    """
    document = validate_document(document)
    effective = dict(DEFAULT_LIMITS)
    if limits is not None:
        if type(limits) is not dict:
            raise ValueError("limits must be an object of explicit overrides")
        effective.update(limits)
    effective = validate_limits(effective)
    started_at = _utc_now()
    result = extract_details(path, limits=effective)
    if (result["source_sha256"], result["input_bytes"]) != (document["content_sha256"], document["byte_count"]):
        raise ValueError("Archived source bytes do not match the supplied document hash and byte count")
    configuration = {"limits": effective, "worker_memory_bytes": WORKER_MEMORY_BYTES,
                     "worker_timeout_seconds": WORKER_TIMEOUT_SECONDS, "text_encoding": "utf-8-strict"}
    run = {"schema_version": SCHEMA_VERSION, "run_id": run_id, "document_id": document["document_id"],
           "document_version": document["version"], "context": document["context"],
           "source_sha256": result["source_sha256"], "method": "native",
           "processor": result["processor"], "processor_version": result["processor_version"],
           "provider": None, "model": None, "model_version": None, "api_version": None,
           "configuration_sha256": hashlib.sha256(canonical_json(configuration).encode("utf-8")).hexdigest(),
           "raw_response": None, "backend": "cpu", "started_at": started_at, "finished_at": _utc_now(),
           "status": result["status"], "coverage": result["coverage"],
           "pages": result["pages"], "errors": result["errors"]}
    return validate_extraction(run, document)
