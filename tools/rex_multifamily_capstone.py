"""Build the REX-02.06 investment decision and actual-status record."""
from hashlib import sha256
import json
from pathlib import Path


def build(root):
    inputs = {}

    def read(relative):
        raw = (root / relative).read_bytes()
        inputs[relative] = sha256(raw).hexdigest()
        return json.loads(raw)

    coverage = "college-park-coverage"
    design = read("rex-multifamily-design-receipt.json")
    market = read("rex-multifamily-taxonomy-receipt.json")
    gis = read(f"{coverage}/rex-multifamily-gis-receipt.json")
    geography = read(f"{coverage}/rex-multifamily-gis-review.geojson")
    underwriting = read("rex-multifamily-underwriting-receipt.json")
    terms = read("rex-multifamily-negotiation-receipt.json")
    permit_review = read(f"{coverage}/candidate-permit-review.json")

    if inputs[f"{coverage}/rex-multifamily-gis-review.geojson"] != gis["output_sha256"]:
        raise ValueError("GIS output differs from its receipt")
    if design["source_sha256"] != gis["source_sha256"]:
        raise ValueError("Design and GIS source revisions differ")

    identity = design["parcel_id"]
    features = [row["properties"] for row in geography["features"]
                if row["properties"]["parcel_id"] == identity]
    permits = [row for row in permit_review["results"]
               if f'12095:{row["county_parcel_id"]}' == identity]
    if len(features) != 1 or len(permits) != 1:
        raise ValueError("Expected exactly one GIS row and permit review for the candidate")

    parcel, permit = features[0], permits[0]
    permit_path = f'{coverage}/{permit["response"]}'
    records = read(permit_path)
    if inputs[permit_path] != permit["sha256"] or len(records) != permit["rows"]:
        raise ValueError("Permit response differs from its receipt")
    if parcel["reported_units"] != design["reported_units"] or any(
        item["lawful_units"] is not None or item["decision"] != "HOLD"
        for item in (parcel, design, permit)
    ):
        raise ValueError("Candidate evidence changed. Reconcile before using this memo.")

    return {
        "project": "REX-02.06",
        "parcel_id": identity,
        "decision": "HOLD",
        "reported_units": parcel["reported_units"],
        "lawful_units": None,
        "market_parcels": market["parcels"],
        "permit_rows_reviewed": len(records),
        "permit_review_as_of": permit_review["as_of"],
        "physical_alternative": "NO_ACTION",
        "training_only": {
            "hold_scenarios": underwriting["three_year_hold"]["scenarios"],
            "price_ceiling_cents": terms["price_ceiling_cents"],
        },
        "observed_status": {
            "action": "RETAIN_RESEARCH_HOLD",
            "transaction_outcome": None,
            "realized_cash_cents": None,
        },
        "release_requirements": [
            "Parcel-linked evidence of lawful use and unit count",
            "Documented title, seller authority and occupancy terms",
            "Verified parcel-specific cash flow, condition and financing",
        ],
        "inputs_sha256": inputs,
    }


if __name__ == "__main__":
    print(json.dumps(build(Path("docs/acquisition")), indent=2))
