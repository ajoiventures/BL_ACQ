"""Run the Orchard acquisition and four-entity service simulation with fictional records."""

import json
from datetime import date

from .ledger import Invoice, Ledger, Receipt, Service
from .underwriting import Approval, Candidate, Economics, Evidence, underwrite


def deal_fixture():
    as_of = date(2026, 11, 20)
    deal_id, parcel_id, district = "orchard-01", "orchard-parcel", "orchard-district"
    checks = [("district_demand", district, "district-survey"),
              ("coordinates", parcel_id, "parcel-map"), ("legal_use", parcel_id, "use-record"),
              ("closed_comp", deal_id, "sale-A"), ("closed_comp", deal_id, "sale-B"),
              ("closed_comp", deal_id, "sale-C"), ("costs", deal_id, "cost-sheet"),
              ("financing", deal_id, "committed-capacity"), ("title", parcel_id, "title-review"),
              ("spatial", parcel_id, "wetland-access-review")]
    evidence = tuple(Evidence(kind, subject, "synthetic/" + ref, date(2026, 11, 1),
                              date(2026, 12, 1), True, ref) for kind, subject, ref in checks)
    candidate = Candidate(deal_id, parcel_id, district, "Local households seek conventional resale homes",
                          "single_family", 28.57, -81.38, evidence, False, 1200, 0)
    economics = Economics(40_000_000, 4_200_000, 2_400_000, 600, 1000, 1_000_000,
                          7_500_000, 2_000_000, 25_400_000)
    return candidate, economics, as_of


def run_scenario():
    candidate, economics, as_of = deal_fixture()
    prepared = underwrite(candidate, economics, 23_500_000, as_of, "analyst")
    # A named *fixture* reviewer confirms this exact packet after its initial calculation.
    approved = underwrite(candidate, economics, 23_500_000, as_of, "analyst",
                          Approval("fixture-reviewer", prepared["packet_digest"], as_of))
    ledger = Ledger()
    for entity, amount, paid in (("commercial", 125_000, True), ("property", 30_000, False),
                                 ("family", 50_000, False), ("client", 80_000, True)):
        ledger.approve_service(Service(entity, "job-1", "fixture-owner", entity + "-delivery"))
        ledger.post_invoice(Invoice(entity, "bill-1", "job-1", amount, entity + "-invoice",
                                    "fixture-bookkeeper", "fixture-controller"))
        if paid:
            receipt = Receipt(entity, "bill-1", "payment-1", amount, entity + "-receipt",
                              "fixture-bookkeeper", "fixture-controller")
            ledger.post_receipt(receipt)
            ledger.post_receipt(receipt)
    return {"qualification": approved["qualification"], "underwriting": approved,
            "ledger": ledger.report()}


if __name__ == "__main__":
    print(json.dumps(run_scenario(), indent=2, sort_keys=True))
