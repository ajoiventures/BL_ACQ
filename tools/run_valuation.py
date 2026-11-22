"""Calculate a valuation research packet from a JSON request or checked-in example."""

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from pilot.valuation_layer import evaluate  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="Request JSON or example containing request")
    parser.add_argument("--output", type=Path, help="Write complete packet; otherwise print it")
    args = parser.parse_args()
    try:
        raw = json.loads(args.input.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("Input must be a request object or an example containing request")
        report = evaluate(raw.get("request", raw))
        encoded = json.dumps(report, indent=2, allow_nan=False) + "\n"
        if args.output:
            if args.input.resolve() == args.output.resolve():
                raise ValueError("Choose an output path different from the source")
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(encoded, encoding="utf-8")
            decision = report["decision"]
            print(f"{report['deal_id']}: {decision['status']}; value {decision['adjusted_value']:,.4f}; "
                  f"entry ceiling {decision['entry_ceiling']:,.4f}. Written {args.output}")
        else:
            print(encoded, end="")
    except (OSError, ValueError, TypeError) as error:
        print(str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
