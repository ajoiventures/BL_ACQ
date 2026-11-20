"""Build a reproducible warranty report from an asset CSV."""
import argparse
import csv
import hashlib
import io
import json
import os
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from tempfile import TemporaryDirectory

REQUIRED = {"asset_id", "asset_name", "vendor", "warranty_end", "replacement_cost"}
def analyze(rows, as_of, horizon=30):
    """Validate identifiers/costs; retain missing values; classify dated records."""
    if horizon < 0:
        raise ValueError("horizon must be nonnegative")
    seen, checked, exceptions = set(), [], []
    for line, row in enumerate(rows, start=2):
        # DictReader represents surplus fields with a None key and missing fields
        # with None values. Empty strings are valid observations in this dataset.
        if None in row or None in row.values():
            raise ValueError(f"CSV record {line}: field count differs from the header")
        asset_id = row.get("asset_id", "").strip()
        if not asset_id or asset_id in seen:
            raise ValueError(f"CSV line {line}: missing or duplicate asset_id")
        seen.add(asset_id)
        name = row.get("asset_name", "").strip()
        vendor = row.get("vendor", "").strip()
        raw_date = row.get("warranty_end", "").strip()
        raw_cost = row.get("replacement_cost", "").strip()
        end = date.fromisoformat(raw_date) if raw_date else None
        cost = None
        if raw_cost:
            try:
                cost = Decimal(raw_cost)
            except InvalidOperation as exc:
                raise ValueError(f"{asset_id}: invalid replacement_cost") from exc
            if not cost.is_finite() or cost < 0:
                raise ValueError(f"{asset_id}: cost must be finite and nonnegative")
        days = (end - as_of).days if end else None
        status = ("unknown" if days is None else "expired" if days < 0
                  else "due_soon" if days <= horizon else "later")
        reasons = []
        if not name: reasons.append("missing asset name")
        if not vendor: reasons.append("missing vendor")
        if end is None: reasons.append("missing warranty date")
        if cost is None: reasons.append("missing replacement cost")
        if status in {"expired", "due_soon"}: reasons.append(status)
        record = dict(asset_id=asset_id, asset_name=name, vendor=vendor,
                      warranty_end=end.isoformat() if end else "",
                      days_to_end=days, status=status,
                      replacement_cost=str(cost) if cost is not None else None)
        checked.append(record)
        if reasons:
            exceptions.append(dict(asset_id=asset_id, reasons="; ".join(reasons)))
    counts = {s: sum(r["status"] == s for r in checked)
              for s in ["expired", "due_soon", "later", "unknown"]}
    total = len(checked)
    known = total - counts["unknown"]
    known_costs = [Decimal(r["replacement_cost"]) for r in checked
                   if r["replacement_cost"] is not None]
    summary = dict(
        as_of=as_of.isoformat(), horizon_days=horizon, total_assets=total,
        warranty_status_counts=counts, dated_assets=known,
        date_coverage=known / total if total else None,
        due_soon_share_of_dated=counts["due_soon"] / known if known else None,
        assets_with_known_cost=len(known_costs),
        known_replacement_cost_total=str(sum(known_costs, Decimal("0"))) if known_costs else None,
        exception_assets=len(exceptions),
        boundary="Administrative date classification; not equipment condition, claim eligibility, or savings.")
    assert sum(counts.values()) == total
    assert len(checked) == len(seen)
    return summary, checked, exceptions

def run(input_path, output_dir, as_of, horizon=30):
    """Hash and analyze one snapshot, then publish a complete, fresh directory."""
    input_path, output_dir = Path(input_path), Path(output_dir)
    original = input_path.read_bytes()
    with io.StringIO(original.decode("utf-8-sig"), newline="") as stream:
        reader = csv.DictReader(stream, strict=True)
        header = reader.fieldnames or []
        if not REQUIRED.issubset(header):
            raise ValueError("CSV is missing required columns")
        if any(not name.strip() for name in header) or len(set(header)) != len(header):
            raise ValueError("CSV needs a distinct, nonempty name for every column")
        try:
            summary, records, exceptions = analyze(reader, as_of, horizon)
        except csv.Error as exc:
            raise ValueError(f"Invalid CSV near line {reader.line_num}: {exc}") from exc
    if os.path.lexists(output_dir):
        raise FileExistsError(output_dir)
    manifest = dict(
        input_name=input_path.name,
        input_sha256=hashlib.sha256(original).hexdigest(),
        script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        as_of=as_of.isoformat(), horizon_days=horizon,
        input_records=len(records), status="demo-analysis-not-independent-review")
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=output_dir.parent) as temp:
        # Keep staging on the destination filesystem so rename publishes the batch.
        stage = Path(temp) / "report"
        stage.mkdir()
        for name, value in [("summary.json", summary), ("checked_records.json", records)]:
            (stage / name).write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
        with (stage / "exceptions.csv").open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=["asset_id", "reasons"])
            writer.writeheader()
            writer.writerows(exceptions)
        manifest["output_sha256"] = {
            path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted(stage.iterdir())
        }
        (stage / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        if os.path.lexists(output_dir):
            raise FileExistsError(output_dir)
        try:
            stage.rename(output_dir)
        except OSError as exc:
            if os.path.lexists(output_dir):
                raise FileExistsError(output_dir) from exc
            raise
    return summary

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("input_csv", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--as-of", required=True, type=date.fromisoformat)
    parser.add_argument("--horizon", type=int, default=30)
    args = parser.parse_args()
    print(json.dumps(run(args.input_csv, args.output_dir, args.as_of, args.horizon), indent=2))
