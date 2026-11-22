"""Run the sourced corporate case and export a complete reproducible JSON bundle."""

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from pilot.corporate_case import evaluate_case, load_case  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", choices=("Base", "Downside", "Upside"), default="Base")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        case, facts = load_case()
        case["selected_case"] = args.case
        report = evaluate_case(case, facts)
        bundle = {"case": case, "facts": facts, "report": report}
        if args.output:
            if args.output.resolve() in {ROOT / "data/corporate/wdfc_2025_case.json", ROOT / "data/corporate/wdfc_source_facts.json"}:
                raise ValueError("Output cannot replace source data or assumptions")
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(bundle, indent=2, allow_nan=False) + "\n")
        print(json.dumps({"case": args.case, "dcf_per_share": report["valuation"]["value_per_share"],
                          "acquisition_moic": report["acquisition"]["returns"]["moic"],
                          "acquisition_annual_irr": report["acquisition"]["returns"]["annual_irr"],
                          "financing": report["acquisition"]["feasibility"]["status"],
                          "status": report["status"]}, allow_nan=False))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
