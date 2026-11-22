"""Run the first local Doc AI path, including an explicit synthetic demo."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pilot.document_application import DocumentApplication, write_json_new  # noqa: E402
from pilot.document_contracts import DOCUMENT_CLASSES  # noqa: E402


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True, help="Private local runtime folder outside the source tree")
    parser.add_argument("--tenant", default="synthetic-demo")
    parser.add_argument("--domain", choices=("commercial", "family", "civic"), default="commercial")
    parser.add_argument("--subject", default="example-invoice")
    parser.add_argument("--case")
    parser.add_argument("--actor", default="local-operator", help="Local actor attestation, not authentication")
    commands = parser.add_subparsers(dest="command", required=True)
    ingest = commands.add_parser("ingest")
    ingest.add_argument("file", type=Path)
    ingest.add_argument("--class", dest="document_class", choices=sorted(DOCUMENT_CLASSES), required=True)
    ingest.add_argument("--synthetic", action="store_true")
    inspect = commands.add_parser("inspect")
    inspect.add_argument("document_id")
    review = commands.add_parser("review")
    review.add_argument("claim_id")
    review.add_argument("--review-id", required=True)
    review.add_argument("--decision", choices=("accept", "reject"), required=True)
    review.add_argument("--reason", required=True)
    review.add_argument("--revision", type=int, required=True)
    review.add_argument("--supersedes-review")
    correct = commands.add_parser("correct")
    correct.add_argument("candidate_json", type=Path)
    correct.add_argument("--revision", type=int, required=True)
    export = commands.add_parser("export")
    export.add_argument("document_id")
    export.add_argument("--output", type=Path, required=True)
    demo = commands.add_parser("demo")
    demo.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    context = {"tenant_id": args.tenant, "domain": args.domain, "subject_id": args.subject, "case_id": args.case}
    try:
        if args.command in {"export", "demo"} and args.output.exists():
            raise ValueError("Output already exists; choose a new artifact path")
        actor = "synthetic-demo-runner" if args.command == "demo" else args.actor
        with DocumentApplication(args.root, context=context, actor=actor) as app:
            if args.command == "ingest":
                result = app.ingest(args.file, document_class=args.document_class,
                                    source_status="synthetic" if args.synthetic else "supplied")
            elif args.command == "inspect":
                result = app.inspect(args.document_id)
            elif args.command == "review":
                result = app.review(args.claim_id, review_id=args.review_id, decision=args.decision, reason=args.reason,
                                    expected_revision=args.revision, supersedes_review_id=args.supersedes_review)
            elif args.command == "correct":
                if args.candidate_json.stat().st_size > 65536:
                    raise ValueError("Correction JSON exceeds 64 KiB")
                result = app.correct(json.loads(args.candidate_json.read_text(encoding="utf-8")), expected_revision=args.revision)
            elif args.command == "export":
                result = app.export(args.document_id)
                write_json_new(args.output, result)
            else:
                # Demo can review only this bundled synthetic original. It never
                # accepts a user-supplied document or represents human review.
                result = app.ingest(ROOT / "tests/fixtures/docai/invoice_native.txt",
                                    document_class="MEP_INVOICE", source_status="synthetic")
                document_id = result["document"]["document_id"]
                for candidate in result["candidates"]:
                    review_id = "demo-" + candidate["claim_id"]
                    if any(r["review_id"] == review_id for r in result["reviews"]):
                        continue
                    current = app.inspect(document_id)
                    app.review(candidate["claim_id"], review_id=review_id, decision="accept",
                               reason="Automated synthetic demonstration only; no human approval is represented.",
                               expected_revision=current["revision"])
                result = app.export(document_id)
                write_json_new(args.output, result)
        print(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False))
        return 0
    except (ValueError, OSError, json.JSONDecodeError) as error:
        print(json.dumps({"status": "held", "reason": str(error)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
