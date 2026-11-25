"""Apply bounded economic-development screens to labeled offline fixture packets.

Run: python -m tools.apply_economic_development
Or: python -m tools.apply_economic_development --kind baseline --input packet.json
No network, GPU, source acceptance, operational transition or external action.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from backend.core.economic_development import VERSION, EconomicDevelopmentError, baseline, data_center

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "docs/economic-development/fixtures"
FIXTURE_NAMES = ("baseline.json", "data-center-unknown.json", "data-center-fail.json", "data-center-hypothetical.json")


def fixtures() -> list[dict]:
    return [json.loads((FIXTURES / name).read_text(encoding="utf-8")) for name in FIXTURE_NAMES]


def apply(output: Path, input_packet: dict | None = None, kind: str | None = None) -> dict:
    if input_packet is not None and kind not in ("baseline", "data-center"):
        raise EconomicDevelopmentError("A supplied packet requires --kind baseline or --kind data-center")
    if input_packet is None and kind is not None:
        raise EconomicDevelopmentError("--kind requires --input")
    if input_packet is None:
        packets = fixtures()
        reports = [baseline(packets[0])] + [data_center(item) for item in packets[1:]]
    else:
        reports = [(baseline if kind == "baseline" else data_center)(input_packet)]
    code_paths = ("backend/core/economic_development.py", "backend/economic_routes.py", "tools/apply_economic_development.py")
    result = {
        "application_version": VERSION, "mode": "OFFLINE_CPU_ANALYST_SCREENING",
        "input_kind": "SUPPLIED_UNVERIFIED_PACKET" if input_packet is not None else "HYPOTHETICAL_FIXTURES",
        "executed_backends": ["CPU_REFERENCE"], "accepted_evidence": False, "external_actions": 0,
        "financial_authority_cents": 0, "ticket_closure_authority": 0,
        "independent_review": "NOT_PERFORMED_BY_THIS_APPLICATION",
        "source_sha256": {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in code_paths},
        "reports": reports,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, help="Optional supplied JSON packet; no source is fetched")
    parser.add_argument("--kind", choices=("baseline", "data-center"))
    parser.add_argument("--output", type=Path, default=FIXTURES / "application-report.json")
    args = parser.parse_args()
    try:
        packet = json.loads(args.input.read_text(encoding="utf-8")) if args.input else None
        result = apply(args.output, packet, args.kind)
        print(json.dumps({"mode": result["mode"], "statuses": [item["status"] for item in result["reports"]],
                          "report_sha256": [item["report_sha256"] for item in result["reports"]],
                          "accepted_evidence": False, "external_actions": 0}, indent=2))
    except (EconomicDevelopmentError, OSError, json.JSONDecodeError) as exc:
        parser.exit(2, str(exc) + "\n")


if __name__ == "__main__":
    main()
