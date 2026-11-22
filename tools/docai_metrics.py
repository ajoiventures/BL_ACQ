"""Score a frozen document corpus without calling a parser, model, or provider."""
from __future__ import annotations

import argparse
from collections import Counter
from decimal import Decimal, InvalidOperation
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import re
import statistics
import sys
from typing import Any


CORPUS_SCHEMA = "br.docai-corpus.v1"
PREDICTION_SCHEMA = "br.docai-predictions.v1"
REPORT_SCHEMA = "br.docai-metrics.v1"
STATUSES = {"complete", "partial", "needs_ocr", "unsupported", "error"}
SPLITS = {"development", "holdout"}
SPAN_KEYS = {"page", "text_sha256", "start", "end", "quote"}
HEX64 = re.compile(r"[0-9a-f]{64}")
USD_DECIMAL = re.compile(r"(?:0|[1-9][0-9]{0,12})(?:\.[0-9]{1,12})?")
MAX_JSON_BYTES = 32_000_000


class EvaluationError(ValueError):
    """An input is incompatible, ambiguous, or not bound to this corpus."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise EvaluationError(message)


def _hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def corpus_fingerprint(corpus: dict[str, Any]) -> str:
    """Hash canonical JSON, not a file's indentation or final newline."""
    return _hash(json.dumps(corpus, sort_keys=True, separators=(",", ":"),
                            ensure_ascii=False, allow_nan=False).encode("utf-8"))


def _text(value: Any, label: str) -> str:
    _require(isinstance(value, str) and bool(value.strip()), f"{label} must be nonempty text")
    return value


def _choice(value: Any, choices: set[str], label: str) -> str:
    _require(isinstance(value, str) and value in choices, f"Invalid {label}")
    return value


def _sha(value: Any, label: str) -> str:
    _require(isinstance(value, str) and HEX64.fullmatch(value) is not None,
             f"{label} must be a lowercase SHA-256")
    return value


def _span(value: Any, label: str) -> dict[str, Any]:
    _require(isinstance(value, dict) and set(value) == SPAN_KEYS, f"Invalid {label} fields")
    _require(type(value["page"]) is int and value["page"] >= 1, f"Invalid {label} page")
    _require(type(value["start"]) is int and type(value["end"]) is int
             and 0 <= value["start"] < value["end"], f"Invalid {label} offsets")
    _sha(value["text_sha256"], label + " text hash")
    _text(value["quote"], label + " quote")
    _require(len(value["quote"]) == value["end"] - value["start"],
             f"{label} quote length must match Unicode-codepoint offsets")
    return value


def validate_corpus(corpus: Any) -> dict[str, dict[str, Any]]:
    """Validate labels without treating a label or reviewer name as authentication."""
    _require(isinstance(corpus, dict), "Corpus must be an object")
    _require(corpus.get("schema_version") == CORPUS_SCHEMA, "Unsupported corpus schema")
    _text(corpus.get("corpus_id"), "corpus_id")
    _text(corpus.get("scope"), "scope")
    _require(type(corpus.get("version")) is int and corpus["version"] > 0,
             "Corpus version must be a positive integer")
    _require(corpus.get("offset_unit") == "unicode_codepoints", "Unsupported span offset unit")
    docs = corpus.get("documents")
    _require(isinstance(docs, list) and 0 < len(docs) <= 10_000,
             "Corpus documents must contain 1 through 10,000 records")
    indexed = {}
    for doc in docs:
        _require(isinstance(doc, dict), "Corpus document must be an object")
        doc_id = _text(doc.get("document_id"), "document_id")
        _require(doc_id not in indexed, f"Duplicate corpus document: {doc_id}")
        _choice(doc.get("split"), SPLITS, f"split: {doc_id}")
        _require(doc.get("origin") == "synthetic", "This corpus contract permits synthetic originals only")
        _choice(doc.get("expected_processing_status"), STATUSES, f"status: {doc_id}")
        _text(doc.get("source_file"), "source_file")
        _sha(doc.get("source_sha256"), "source_sha256")
        refs = doc.get("reference_texts")
        _require(isinstance(refs, list), f"Missing reference texts: {doc_id}")
        pages = {}
        for ref in refs:
            _require(isinstance(ref, dict) and type(ref.get("page")) is int and ref["page"] >= 1,
                     f"Invalid reference page: {doc_id}")
            _require(ref["page"] not in pages, f"Duplicate reference page: {doc_id}")
            _text(ref.get("path"), "reference path")
            pages[ref["page"]] = _sha(ref.get("sha256"), "reference sha256")
        fields = doc.get("fields")
        _require(isinstance(fields, list) and 0 < len(fields) <= 256,
                 f"Require 1 through 256 field labels: {doc_id}")
        seen = set()
        for field in fields:
            _require(isinstance(field, dict), f"Invalid field label: {doc_id}")
            name = _text(field.get("field"), "field")
            _require(name not in seen, f"Duplicate label: {doc_id}/{name}")
            seen.add(name)
            _require(type(field.get("critical")) is bool, f"Invalid critical flag: {name}")
            expectation = field.get("expectation")
            _choice(expectation, {"value", "abstain"}, f"expectation: {name}")
            spans = field.get("allowed_spans")
            _require(isinstance(spans, list), f"Invalid allowed spans: {name}")
            if expectation == "value":
                _text(field.get("canonical_value"), "canonical_value")
                _require(bool(spans), f"Answerable label needs a source span: {name}")
            else:
                _require(field.get("canonical_value") is None and not spans,
                         f"Abstention label cannot contain an accepted answer/span: {name}")
                _text(field.get("reason"), "abstention reason")
            for span in spans:
                _span(span, "gold span")
                _require(pages.get(span["page"]) == span["text_sha256"],
                         f"Gold span is not bound to a reference page: {doc_id}/{name}")
        indexed[doc_id] = doc
    return indexed


def _safe_file(root: Path, relative: str) -> Path:
    path = PurePosixPath(relative)
    _require(not path.is_absolute() and bool(path.parts)
             and all(part not in {".", ".."} for part in path.parts)
             and "\\" not in relative, "Corpus paths must be relative without traversal")
    target = (root / relative).resolve()
    _require(target.is_relative_to(root.resolve()), "Corpus path escapes its root")
    _require(target.is_file(), f"Missing corpus artifact: {relative}")
    _require(target.stat().st_size <= 8_000_000, f"Corpus artifact too large: {relative}")
    return target


def verify_corpus(corpus: dict[str, Any], root: Path) -> dict[str, Any]:
    """Check original/reference hashes and every golden quote against stored text."""
    docs = validate_corpus(corpus)
    files = set()
    labels = 0
    for doc in docs.values():
        source = _safe_file(root, doc["source_file"])
        _require(_hash(source.read_bytes()) == doc["source_sha256"],
                 f"Original hash mismatch: {doc['document_id']}")
        files.add(doc["source_file"])
        texts = {}
        for ref in doc["reference_texts"]:
            data = _safe_file(root, ref["path"]).read_bytes()
            _require(_hash(data) == ref["sha256"], f"Reference hash mismatch: {ref['path']}")
            try:
                texts[ref["page"]] = data.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise EvaluationError("Reference text must be valid UTF-8") from exc
            files.add(ref["path"])
        for field in doc["fields"]:
            labels += 1
            for span in field["allowed_spans"]:
                text = texts[span["page"]]
                _require(span["end"] <= len(text) and text[span["start"]:span["end"]] == span["quote"],
                         f"Gold quote mismatch: {doc['document_id']}/{field['field']}")
    return {"status": "verified", "documents": len(docs), "files": len(files), "field_labels": labels}


def _duration(value: Any, label: str) -> float | None:
    if value is None:
        return None
    _require(type(value) in {int, float} and 0 <= value <= 1_000_000_000_000
             and math.isfinite(value),
             f"{label} must be finite, nonnegative and at most 1e12 milliseconds, or null")
    return float(value)


def _cost(value: Any) -> Decimal | None:
    if value is None:
        return None
    _require(isinstance(value, str) and len(value) <= 26
             and USD_DECIMAL.fullmatch(value) is not None,
             "reported_cost_usd must be an unsigned fixed-point decimal string or null")
    try:
        amount = Decimal(value)
    except InvalidOperation as exc:
        raise EvaluationError("Invalid reported_cost_usd") from exc
    _require(amount.is_finite() and amount >= 0, "reported_cost_usd must be finite and nonnegative")
    _require(amount <= Decimal('1000000000000') and amount.as_tuple().exponent >= -12,
             "reported_cost_usd exceeds the 1e12 USD/12-decimal-place reporting bounds")
    return amount


def _ratio(numerator: int, denominator: int) -> dict[str, Any]:
    return {"numerator": numerator, "denominator": denominator,
            "value": numerator / denominator if denominator else None}


def _times(values: list[float]) -> dict[str, Any]:
    return {"reported_documents": len(values), "total_ms": math.fsum(values) if values else None,
            "mean_ms": math.fsum(values) / len(values) if values else None,
            "median_ms": statistics.median(values) if values else None}


def evaluate(corpus: dict[str, Any], predictions: Any, *, split: str = "holdout") -> dict[str, Any]:
    """Score exact canonical strings and golden spans; do not normalize wrong output."""
    all_docs = validate_corpus(corpus)
    _choice(split, SPLITS | {"all"}, "split; use development, holdout, or all")
    docs = {key: doc for key, doc in all_docs.items() if split == "all" or doc["split"] == split}
    _require(isinstance(predictions, dict), "Predictions must be an object")
    _require(predictions.get("schema_version") == PREDICTION_SCHEMA, "Unsupported prediction schema")
    _require(predictions.get("corpus_id") == corpus["corpus_id"]
             and predictions.get("corpus_sha256") == corpus_fingerprint(corpus),
             "Predictions must bind the exact canonical corpus hash and ID")
    _require(predictions.get("scope") == corpus["scope"], "Prediction scope differs from corpus")
    rows = predictions.get("documents")
    _require(isinstance(rows, list) and len(rows) <= 10_000,
             "Prediction documents must be a list of at most 10,000 records")
    output = {}
    for row in rows:
        _require(isinstance(row, dict), "Prediction document must be an object")
        doc_id = _text(row.get("document_id"), "prediction document_id")
        _require(doc_id in all_docs, f"Prediction for unknown document: {doc_id}")
        _require(doc_id not in output, f"Duplicate prediction document: {doc_id}")
        _choice(row.get("processing_status"), STATUSES, f"processing status: {doc_id}")
        fields = row.get("fields")
        _require(isinstance(fields, list) and len(fields) <= 256,
                 f"Prediction fields must be a list of at most 256 records: {doc_id}")
        indexed = {}
        for field in fields:
            _require(isinstance(field, dict), "Prediction field must be an object")
            _require(set(field) <= {"field", "decision", "canonical_value", "span", "review_decision"},
                     "Unknown prediction-field property")
            name = _text(field.get("field"), "prediction field")
            _require(name not in indexed, f"Duplicate prediction field: {doc_id}/{name}")
            decision = field.get("decision")
            _choice(decision, {"propose", "abstain", "error"}, "prediction decision")
            review = field.get("review_decision", "pending")
            _choice(review, {"pending", "accepted", "rejected"}, "claimed review decision")
            if decision == "propose":
                _text(field.get("canonical_value"), "prediction canonical_value")
                if field.get("span") is not None:
                    _span(field["span"], "prediction span")
            else:
                _require(field.get("canonical_value") is None and field.get("span") is None,
                         "Abstention/error must not carry a proposed answer or span")
                _require(review != "accepted", "Abstention/error cannot be accepted as a fact")
            indexed[name] = field
        output[doc_id] = (row, indexed)
        _duration(row.get("latency_ms"), "latency_ms")
        _duration(row.get("review_ms"), "review_ms")
        _cost(row.get("reported_cost_usd"))

    counts = Counter({name: 0 for name in (
        "documents", "reported_documents", "missing_documents", "processing_status_correct",
        "labeled_fields", "answerable_fields", "abstention_required_fields", "proposals", "labeled_proposals",
        "answerable_proposals", "correct_values", "correct_spans", "grounded_correct_values",
        "abstentions", "correct_abstentions", "errors", "missing_fields", "unexpected_fields",
        "false_proposals", "claimed_accepted_fields", "false_accepts", "critical_false_accepts")})
    latency, review_times, costs, cases = [], [], [], []
    status_counts = Counter({status: 0 for status in sorted(STATUSES)})
    for doc_id, doc in docs.items():
        counts["documents"] += 1
        result = output.get(doc_id)
        row, predicted = result if result else ({}, {})
        if result:
            counts["reported_documents"] += 1
            status_counts[row["processing_status"]] += 1
            counts["processing_status_correct"] += row["processing_status"] == doc["expected_processing_status"]
            for key, destination in (("latency_ms", latency), ("review_ms", review_times)):
                value = _duration(row.get(key), key)
                if value is not None:
                    destination.append(value)
            cost = _cost(row.get("reported_cost_usd"))
            if cost is not None:
                costs.append(cost)
        else:
            counts["missing_documents"] += 1
        labels = {field["field"]: field for field in doc["fields"]}
        for name in sorted(labels.keys() | predicted.keys()):
            gold, got = labels.get(name), predicted.get(name)
            answerable = bool(gold and gold["expectation"] == "value")
            counts["labeled_fields"] += gold is not None
            counts["answerable_fields"] += answerable
            counts["abstention_required_fields"] += bool(gold and not answerable)
            counts["unexpected_fields"] += gold is None
            decision = got["decision"] if got else "missing"
            value_ok = span_ok = False
            if decision == "propose":
                counts["proposals"] += 1
                counts["labeled_proposals"] += gold is not None
                counts["answerable_proposals"] += answerable
                value_ok = answerable and got["canonical_value"] == gold["canonical_value"]
                span_ok = answerable and got.get("span") in gold["allowed_spans"]
                counts["correct_values"] += value_ok
                counts["correct_spans"] += span_ok
                counts["grounded_correct_values"] += value_ok and span_ok
                counts["false_proposals"] += not value_ok
                if got.get("review_decision", "pending") == "accepted":
                    counts["claimed_accepted_fields"] += 1
                    false_accept = not (value_ok and span_ok)
                    counts["false_accepts"] += false_accept
                    counts["critical_false_accepts"] += false_accept and bool(gold and gold["critical"])
            elif decision == "abstain":
                counts["abstentions"] += 1
                counts["correct_abstentions"] += bool(gold and not answerable)
            elif decision == "error":
                counts["errors"] += 1
            else:
                counts["missing_fields"] += 1
            cases.append({"document_id": doc_id, "field": name, "decision": decision,
                          "expected": gold["expectation"] if gold else "unregistered_field",
                          "value_correct": bool(value_ok), "span_correct": bool(span_ok)})
    c = counts
    ratios = {
        "field_precision": _ratio(c["answerable_proposals"], c["proposals"]),
        "field_recall": _ratio(c["answerable_proposals"], c["answerable_fields"]),
        "exact_value_accuracy": _ratio(c["correct_values"], c["answerable_proposals"]),
        "value_precision": _ratio(c["correct_values"], c["proposals"]),
        "value_recall": _ratio(c["correct_values"], c["answerable_fields"]),
        "span_fidelity": _ratio(c["correct_spans"], c["proposals"]),
        "grounded_value_recall": _ratio(c["grounded_correct_values"], c["answerable_fields"]),
        "required_abstention_accuracy": _ratio(c["correct_abstentions"], c["abstention_required_fields"]),
        "proposal_coverage": _ratio(c["labeled_proposals"], c["labeled_fields"]),
        "document_reporting_coverage": _ratio(c["reported_documents"], c["documents"]),
        "processing_status_accuracy": _ratio(c["processing_status_correct"], c["documents"]),
    }
    return {"schema_version": REPORT_SCHEMA, "corpus_id": corpus["corpus_id"],
            "corpus_sha256": corpus_fingerprint(corpus), "scope": corpus["scope"], "split": split,
            "counts": dict(counts), "processing_status_counts": dict(status_counts),
            "metrics": ratios, "latency": _times(latency),
            "review_time": _times(review_times),
            "reported_cost": {"currency": "USD", "reported_documents": len(costs),
                              "total": str(sum(costs, Decimal(0))) if costs else None},
            "cases": cases, "artifact_integrity": {"status": "not_checked_by_pure_scorer"},
            "calibration": {"status": "not_evaluated", "reason": "No validated probability-like scores or sufficient held-out sample supplied."},
            "runtime": {"backend": "cpu_reference", "network_used": False, "inference_performed": False},
            "limitations": ["Review decisions and usage are reported input, not authenticated or independently observed here.",
                            "Synthetic corpus scores do not establish provider quality, production readiness, or population accuracy.",
                            "Null rates mean zero denominator; missing output is not a successful abstention."]}


def load_json(path: Path) -> Any:
    _require(path.stat().st_size <= MAX_JSON_BYTES, "Evaluation JSON exceeds the 32 MB input bound")

    def object_pairs(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise EvaluationError(f"Duplicate JSON key: {key}")
            result[key] = value
        return result

    def invalid_constant(value):
        raise EvaluationError(f"Nonfinite JSON constant: {value}")

    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=object_pairs,
                      parse_constant=invalid_constant)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", required=True, type=Path)
    parser.add_argument("--predictions", required=True, type=Path)
    parser.add_argument("--split", choices=["development", "holdout", "all"], default="holdout")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        corpus = load_json(args.corpus)
        integrity = verify_corpus(corpus, args.corpus.parent)
        report = evaluate(corpus, load_json(args.predictions), split=args.split)
        report["artifact_integrity"] = integrity
        text = json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n"
        if args.output:
            with args.output.open("x", encoding="utf-8") as stream:
                stream.write(text)
        else:
            sys.stdout.write(text)
    except (EvaluationError, ValueError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
