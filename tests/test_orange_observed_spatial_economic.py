import pytest

from tools.run_orange_observed_spatial_economic import compare_nearby, load_rows
from tools.verify_orange_sales_and_sunbiz import sunbiz


def test_sales_comparison_uses_prior_distinct_parcels_with_same_unit_count():
    def sale(key, transfer, month, lat, units, price):
        return dict(parcel_key=key, sale_id=transfer, sale_month=month,
                    lat=lat, lon=-81.4, reported_units=units, sale_price_dollars=price)

    rows = [
        sale("A", "1", "2026-01", 28.5, 2, 100000),
        sale("B", "2", "2026-02", 28.5001, 3, 120000),
        sale("C", "3", "2026-03", 28.502, 2, 180000),
        sale("C", "4", "2026-04", 28.502, 2, 190000),
        sale("D", "5", "2026-05", 28.8, 2, 200000),
    ]
    output, _ = compare_nearby(rows, "cpu_reference")
    assert [r["nearest_same_unit_sale_id"] for r in output] == [None, None, "1", "1", None]
    assert output[3]["comparable_sale_cents_per_reported_unit"] == 5000000
    assert output[3]["observed_sale_cents_per_reported_unit"] == 9500000
    assert 220 < output[3]["rounded_distance_metres"] < 225


def test_inputs_are_pinned(tmp_path):
    path = tmp_path / "sales.csv"
    path.write_text("x\ny\n")
    with pytest.raises(ValueError, match="digest"):
        load_rows(path, "0" * 64)


def test_daily_sunbiz_evidence_preserves_lengths_and_reports_non_ascii(tmp_path):
    path = tmp_path / "daily.txt"
    row = bytearray(b" " * 1440)
    row[:12] = b"L26000000001"
    row[204:209] = b"AFLAL"
    row[300] = 233
    path.write_bytes(bytes(row) + b"\r\n" + b"malformed\r\n")
    result = sunbiz(path)
    assert result["record_width_histogram"] == {1440: 1, 9: 1}
    assert result["status"] == {"A": 1}
    assert result["non_ascii_records"] == result["invalid_identity_or_width_records"] == 1
    assert result["snapshot_population_verified"] is False
