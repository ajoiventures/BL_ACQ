"""Score the saved Orlando HPI forecast against a compatible FHFA release PDF."""
import argparse
from datetime import datetime
from decimal import Decimal
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
import re

from pypdf import PdfReader


def score(issue, pdf_bytes, page_number):
    payload = issue["payload"]
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    if sha256(encoded).hexdigest() != issue["sha256"]:
        raise ValueError("Forecast issue checksum mismatch")
    target = payload["target"]
    if (payload["schema"] != "hpi-forecast-issue/1" or target["place_id"] != "36740"
            or target["metric"] != "seasonally adjusted purchase-only annual HPI growth percent"):
        raise ValueError("Unsupported forecast target or series")
    pdf = PdfReader(BytesIO(pdf_bytes))
    cover = pdf.pages[0].extract_text()
    quarter = target["quarter"].replace("-", "")
    if not re.search(rf"\b{re.escape(quarter)}\b", cover):
        raise ValueError("PDF cover does not match the target quarter")
    release = re.search(r"\b[A-Z][a-z]+ \d{1,2}, \d{4}\b", cover)
    if not release:
        raise ValueError("PDF cover has no release date")
    published = datetime.strptime(release[0], "%B %d, %Y").date()
    issued = datetime.fromisoformat(payload["issued_at_utc"]).date()
    if published <= issued:
        raise ValueError("Outcome release must follow forecast issue")
    if not 1 <= page_number <= len(pdf.pages):
        raise ValueError("Outcome page out of bounds")
    page = pdf.pages[page_number - 1].extract_text()
    if "Purchase-Only" not in page or "Seasonally Adjusted" not in page or "1-Yr" not in page:
        raise ValueError("Outcome page has incompatible series metadata")
    observations = re.findall(r"(?m)^\s*Orlando-Kissimmee-Sanford, FL\s+(-?\d+\.\d+)%", page)
    if len(observations) != 1:
        raise ValueError("Expected one Orlando outcome row")
    observed = Decimal(observations[0])
    return {
        "issue_sha256": issue["sha256"], "outcome_pdf_sha256": sha256(pdf_bytes).hexdigest(),
        "outcome_pdf_page": page_number, "outcome_release_date": published.isoformat(),
        "target": target, "observed_pct": str(observed),
        "absolute_error_percentage_points": {
            name: str(abs(observed - Decimal(item["prediction_pct"])))
            for name, item in payload["predictions"].items()
        },
        "scope": "PDF content verified. Source authenticity, first publication and geography continuity require provenance review.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("issue", type=Path)
    parser.add_argument("outcome_pdf", type=Path)
    parser.add_argument("page", type=int)
    parser.add_argument("receipt", type=Path)
    args = parser.parse_args()
    result = score(json.loads(args.issue.read_bytes()), args.outcome_pdf.read_bytes(), args.page)
    with args.receipt.open("x", encoding="utf-8") as output:
        json.dump(result, output, indent=2)
        output.write("\n")


if __name__ == "__main__":
    main()
