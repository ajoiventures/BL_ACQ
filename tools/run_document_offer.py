"""Run the synthetic document-to-offer workflow with no AI, credentials or network."""

import argparse
from copy import deepcopy
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pilot.document_evidence import EvidenceStore
from pilot.document_offer_layer import evaluate_with_evidence, export_r_review


def renovation_bindings(packet):
    baseline = next(s["renovation_cents"] for s in packet["scenarios"] if s["id"] == "baseline")
    bindings = []
    for scenario in packet["scenarios"]:
        offset = scenario["renovation_cents"]-baseline
        if offset < 0:
            raise ValueError("This demo expects nonnegative renovation scenario buffers")
        bindings.append({"field": "renovation_quote_cents", "group": "scenario",
                         "record_id": scenario["id"], "key": "renovation_cents", "offset_cents": offset})
    return bindings


def _single_document_bundle(bundle, document):
    identity = document["metadata"]["document_id"]
    return {"schema_version": bundle["schema_version"], "documents": [deepcopy(document)],
            "claims": [deepcopy(c) for c in bundle["claims"] if c["document_id"] == identity]}


def run_demo(*, backend="cpu"):
    packet = json.loads((ROOT/"data/offer_probability/duplex.json").read_text())
    bundle = json.loads((ROOT/"data/document_evidence/duplex_quote.json").read_text())
    documents = sorted(bundle["documents"], key=lambda d: d["metadata"]["version"])
    if len(documents) != 2 or any(d["metadata"]["illustrative"] is not True for d in documents):
        raise ValueError("Demo requires exactly two explicitly synthetic document versions")
    bindings = renovation_bindings(packet)
    with TemporaryDirectory(prefix="br-document-demo-") as directory:
        db = Path(directory)/"evidence.sqlite"
        with EvidenceStore(db, actor="synthetic_preparer") as store:
            store.ingest_bundle(_single_document_bundle(bundle, documents[0]))
            unreviewed = evaluate_with_evidence(store, packet, bindings, backend=backend)
        with EvidenceStore(db, actor="synthetic_finance_reviewer") as store:
            old_claim = next(c for c in bundle["claims"] if c["document_id"] == documents[0]["metadata"]["document_id"])
            store.review_claim("demo-review-v1", old_claim["claim_id"], deal_id=packet["deal_id"],
                               decision="accept", reviewed_on=packet["as_of"], expires_on="2026-12-22",
                               reason="Synthetic fixture review: amount reconciles to the first quote.")
            original = evaluate_with_evidence(store, packet, bindings, backend=backend)
        with EvidenceStore(db, actor="synthetic_preparer") as store:
            store.ingest_bundle(_single_document_bundle(bundle, documents[1]))
            pending_revision = evaluate_with_evidence(store, packet, bindings, backend=backend)
        with EvidenceStore(db, actor="synthetic_finance_reviewer") as store:
            revised_claim = next(c for c in bundle["claims"] if c["document_id"] == documents[1]["metadata"]["document_id"])
            store.review_claim("demo-review-v2", revised_claim["claim_id"], deal_id=packet["deal_id"],
                               decision="accept", reviewed_on=packet["as_of"], expires_on="2026-12-22",
                               reason="Synthetic fixture review: revised scope has a $55000 baseline quote.")
            revised = evaluate_with_evidence(store, packet, bindings, backend=backend)
    return {"schema_version": "br-document-offer-demo/1", "illustrative": True,
            "development_swarm_is_product_runtime": False, "ai_enabled": False,
            "note": "Four simulated review states. No actual seller documents, approvals, offers or closing actions.",
            "stages": {"unreviewed": unreviewed, "original_reviewed": original,
                       "revision_pending": pending_revision, "revision_reviewed": revised}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", choices=("cpu", "cuda"), default="cpu")
    parser.add_argument("--output", type=Path, help="New JSON output file; existing files are protected")
    parser.add_argument("--r-export", type=Path, help="New directory for versioned R review exchange; does not execute R")
    args = parser.parse_args()
    if args.output and args.output.exists():
        parser.error("Output already exists; choose a new path")
    if args.r_export and args.r_export.exists():
        parser.error("R export directory already exists; choose a new path")
    report = run_demo(backend=args.backend)
    if args.r_export:
        export_r_review(report["stages"]["revision_reviewed"], args.r_export)
    payload = json.dumps(report, sort_keys=True, indent=2, allow_nan=False)+"\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8") as handle:
            handle.write(payload)
        print(str(args.output.resolve()))
    else:
        print(payload, end="")


if __name__ == "__main__":
    main()
