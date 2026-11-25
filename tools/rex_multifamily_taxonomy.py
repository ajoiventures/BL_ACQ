"""Build the REX-02.01 sourced multifamily taxonomy as aggregate counts."""
from collections import Counter
import json
from pathlib import Path

from tools.screen_orange_final_roll import load_final_roll

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "docs/acquisition/orange-final-roll/official_final_roll_inventory.csv"
DIGEST = "46930f23b1dd129cc95c36d89c301ecdc6f1ed1a3f3b06cd0034ec1b3c86926a"


def summarize(source=SOURCE, digest=DIGEST):
    _, records = load_final_roll(source, digest, 6078)
    counts = Counter((r["source_reported_units"], r["source_use_code"]) for r in records)
    return {
        "project": "REX-02.01",
        "source_sha256": digest,
        "parcels": len(records),
        "reported_units": sum(r["source_reported_units"] for r in records),
        "parcel_count_by_reported_units": dict(sorted(Counter(r["source_reported_units"] for r in records).items())),
        "use_code_counts": [
            {"reported_units": units, "source_use_code": code, "parcels": total}
            for (units, code), total in sorted(counts.items())
        ],
        "lawful_units_verified": sum(r["legal_units"] is not None for r in records),
        "decision_counts": dict(Counter(r["decision"] for r in records)),
        "scope": "Retained source-reported cohort. This exercise grants no release or buy authority.",
    }


if __name__ == "__main__":
    print(json.dumps(summarize(), indent=2))
