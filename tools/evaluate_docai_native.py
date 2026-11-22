"""Evaluate the actual local native reader and invoice grammar on synthetic files."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import sys
import time
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pilot.document_application import invoice_candidates, MEDIA_TYPES
from pilot.document_contracts import SCHEMA_VERSION, validate_document
from pilot.document_native import extract_document
from tools.docai_metrics import (EvaluationError, PREDICTION_SCHEMA, corpus_fingerprint,
                                evaluate, load_json, validate_corpus, verify_corpus)


FIELDS = ("vendor", "invoice_number", "invoice_date", "due_date", "total_cents", "currency")
SOURCE_PATHS = ("tools/evaluate_docai_native.py", "tools/docai_metrics.py",
                "pilot/document_application.py", "pilot/document_contracts.py",
                "pilot/document_invoice.py", "pilot/document_native.py", "filing/inbox.py")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _source_hashes() -> dict[str, str]:
    return {relative: hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()
            for relative in SOURCE_PATHS}


def _canonical_value(candidate: dict) -> str:
    value = candidate["value"]
    if candidate["value_type"] == "money_cents" and type(value) is int:
        return str(value)
    if candidate["value_type"] in {"text", "date"} and type(value) is str:
        return value
    raise EvaluationError("Native v1 evaluation accepts exact text/date/integer-cent candidates only")


def evaluate_native(corpus: dict, root: Path, *, split: str = "all") -> dict:
    """Return measured predictions, report and extraction evidence without writing.

    Gold values, spans and expected status are used only by the scorer. The
    production reader receives original bytes, document identity and read limits;
    its candidate function receives only that document and the actual extraction.
    """
    if split not in {"development", "holdout", "all"}:
        raise EvaluationError("Use development, holdout, or all")
    indexed = validate_corpus(corpus)
    integrity = verify_corpus(corpus, root)
    if corpus["scope"] != "native_invoice_contract_v1":
        raise EvaluationError("Native runner requires the native_invoice_contract_v1 scope")
    documents = [doc for doc in indexed.values() if split == "all" or doc["split"] == split]
    if not documents:
        raise EvaluationError("No documents in the selected split")
    source_hashes = _source_hashes()
    started_at = _utc_now()
    records, rows = [], []
    for label in documents:
        # verify_corpus has already confined paths to the corpus root and checked
        # hashes. The native reader independently verifies these bytes again.
        path = (root / label["source_file"]).resolve()
        document = validate_document({
            "schema_version": SCHEMA_VERSION, "document_id": label["document_id"],
            "context": {"tenant_id": "docai-evaluation", "domain": "commercial",
                        "subject_id": "synthetic-fixtures", "case_id": corpus["corpus_id"]},
            "version": 1, "source_uri": "fixture://" + corpus["corpus_id"] + "/" + label["source_file"],
            "title": path.name, "media_type": MEDIA_TYPES.get(path.suffix.lower(), "application/octet-stream"),
            "document_class": label["document_class"], "content_sha256": label["source_sha256"],
            "byte_count": path.stat().st_size, "received_at": _utc_now(), "source_status": "synthetic",
            "predecessor_document_id": None, "asset_links": []})
        run_id = "native-eval-" + uuid4().hex
        start = time.perf_counter()
        extraction = extract_document(path, document, run_id, limits=label.get("read_limits") or None)
        candidates = invoice_candidates(document, extraction)
        elapsed_ms = (time.perf_counter() - start) * 1000
        if extraction["method"] != "native" or extraction["provider"] is not None:
            raise EvaluationError("Native evaluation must not contain provider extraction")
        fields = {}
        for candidate in candidates:
            name = candidate["field"]
            if name in fields or candidate["method"] != "native" or len(candidate["spans"]) != 1:
                raise EvaluationError("Native evaluation requires one native candidate and span per field")
            fields[name] = {"field": name, "decision": "propose",
                            "canonical_value": _canonical_value(candidate), "span": candidate["spans"][0],
                            "review_decision": "pending"}
        for name in FIELDS:
            # No candidate is an explicit abstention by this adapter. Runtime
            # exceptions fail the evaluation; they never become safe abstentions.
            fields.setdefault(name, {"field": name, "decision": "abstain", "canonical_value": None,
                                     "span": None, "review_decision": "pending"})
        rows.append({"document_id": document["document_id"], "processing_status": extraction["status"],
                     "fields": list(fields.values()), "latency_ms": elapsed_ms,
                     "review_ms": None, "reported_cost_usd": None})
        records.append({"document": document, "extraction": extraction, "candidates": candidates,
                        "observed_native_and_candidate_ms": elapsed_ms})
    if _source_hashes() != source_hashes:
        raise EvaluationError("Implementation files changed during evaluation; rerun on a stable revision")
    verify_corpus(corpus, root)
    predictions = {"schema_version": PREDICTION_SCHEMA, "corpus_id": corpus["corpus_id"],
                   "corpus_sha256": corpus_fingerprint(corpus), "scope": corpus["scope"], "documents": rows}
    report = evaluate(corpus, predictions, split=split)
    report["artifact_integrity"] = integrity
    execution = {"schema_version": "br.docai-native-evaluation.v1", "started_at": started_at,
                 "finished_at": _utc_now(), "python_version": platform.python_version(),
                 "platform": platform.platform(), "source_sha256": source_hashes,
                 "corpus_sha256": corpus_fingerprint(corpus), "split": split,
                 "timing_basis": "perf_counter wall time per native extraction plus candidate generation; excludes corpus validation and report I/O",
                 "cache_basis": "Uncontrolled OS cache and parser startup; no steady-state or service-latency claim",
                 "review_performed": False, "cost_basis": "Not measured; no operating-cost or free-service claim",
                 "provider_calls": 0, "model_downloads": 0, "backend": "cpu",
                 "scope": "Native reader and candidate function; archive, authenticated review and accepted export are separate tests",
                 "runs": records}
    return {"predictions": predictions, "report": report, "execution": execution}


def write_evaluation(output_dir: Path, results: dict) -> None:
    """Write a new artifact directory; never overwrite another evaluation."""
    output_dir.mkdir(parents=True, exist_ok=False)
    for name in ("predictions", "report", "execution"):
        with (output_dir / (name + ".json")).open("x", encoding="utf-8") as stream:
            json.dump(results[name], stream, indent=2, ensure_ascii=False, allow_nan=False)
            stream.write("\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, default=ROOT / "tests/fixtures/docai/manifest.json")
    parser.add_argument("--split", choices=["all", "development", "holdout"], default="all")
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.output_dir.exists():
            raise EvaluationError("Output directory must be new; earlier results are preserved")
        results = evaluate_native(load_json(args.corpus), args.corpus.parent, split=args.split)
        write_evaluation(args.output_dir, results)
        print(json.dumps({"output_dir": str(args.output_dir.resolve()),
                          "documents": results["report"]["counts"]["documents"],
                          "quality_verdict": "requires independent review; see predeclared policy"}))
    except (EvaluationError, ValueError, OSError, KeyError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
