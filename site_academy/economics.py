"""Research-only urban economics models. Run with --list, --demo, or a JSON packet."""
import argparse
import inspect
import json
import math
from pathlib import Path


def number(value, label, minimum=None, maximum=None):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError(f"{label} must be a finite number")
    if minimum is not None and value < minimum or maximum is not None and value > maximum:
        raise ValueError(f"{label} is outside the permitted range")
    return value


def positive(value, label):
    if number(value, label) <= 0:
        raise ValueError(f"{label} must be positive")
    return value


def median_location(locations_km, deliveries):
    """Ch. 2, pp. 42–44. Minimize sum_i w_i |x_i - x| on one unconstrained line."""
    if not isinstance(locations_km, list) or not isinstance(deliveries, list) or not locations_km or len(locations_km) != len(deliveries):
        raise ValueError("Supply equal nonempty lists of locations and delivery counts")
    pairs = sorted((number(x, "location"), positive(w, "deliveries")) for x, w in zip(locations_km, deliveries))
    total = sum(w for _, w in pairs)
    running = 0
    for i, (x, w) in enumerate(pairs):
        running += w
        if running >= total / 2:
            upper = pairs[i + 1][0] if running == total / 2 else x
            return {"optimal_interval_km": [x, upper], "one_way_delivery_km": sum(w * abs(km - x) for km, w in pairs)}


def labor_shift(base_jobs, export_job_change, demand_multiplier, supply_elasticity, absolute_demand_elasticity):
    """Ch. 5, pp. 103–104. Local elasticities predict equilibrium after a horizontal shift."""
    base = positive(base_jobs, "base jobs")
    shift = number(export_job_change, "export job change") * positive(demand_multiplier, "demand multiplier") / base
    es = number(supply_elasticity, "supply elasticity", 0)
    ed = number(absolute_demand_elasticity, "absolute demand elasticity", 0)
    wage = shift / positive(es + ed, "elasticity sum")
    return {"demand_shift_fraction": shift, "wage_change_fraction": wage, "equilibrium_job_change": base * wage * es}


def residual_bid(annual_revenue, annual_nonland_cost, annual_transport_cost, area_m2):
    """Ch. 6, pp. 128–134. Maximum annual land rent with fixed inputs and normal return in costs."""
    net = number(annual_revenue, "revenue", 0) - number(annual_nonland_cost, "nonland costs", 0) - number(annual_transport_cost, "transport costs", 0)
    return {"annual_residual_usd": net, "annual_bid_usd_m2": net / positive(area_m2, "area")}


def far_capacity(parcel_m2, permitted_far, net_share, unit_net_m2):
    """Ch. 9. Floor-area arithmetic under supplied hypothetical intensity and efficiency."""
    gross = positive(parcel_m2, "parcel area") * number(permitted_far, "FAR", 0)
    net = gross * number(net_share, "residential net share", 0, 1)
    return {"gross_floor_m2": gross, "net_residential_m2": net, "whole_units_upper_bound": math.floor(net / positive(unit_net_m2, "unit area"))}


def congestion(flow_vehicles_hour, marginal_minutes_per_flow_unit, value_usd_hour):
    """Ch. 10, pp. 262–265. External delay q t'(q) valued at common hourly time cost."""
    delay = number(flow_vehicles_hour, "flow", 0) * number(marginal_minutes_per_flow_unit, "derivative", 0)
    return {"external_vehicle_minutes_per_added_vehicle": delay,
            "marginal_external_usd_per_vehicle": delay * number(value_usd_hour, "time value", 0) / 60}


def transit_cost(fare_usd, walk_minutes, headway_minutes, ride_minutes, access_usd_hour, wait_usd_hour, ride_usd_hour):
    """Ch. 11. Expected waiting time for random arrivals at a reliable uniform headway."""
    wait = positive(headway_minutes, "headway") / 2
    time = (number(walk_minutes, "walk minutes", 0) * number(access_usd_hour, "access time value", 0)
            + wait * number(wait_usd_hour, "wait time value", 0)
            + number(ride_minutes, "ride minutes", 0) * number(ride_usd_hour, "ride time value", 0)) / 60
    return {"expected_wait_minutes": wait, "generalized_usd_trip": time + number(fare_usd, "fare", 0)}


def foundation_gap(target_usd_pupil, tax_base_usd_pupil, required_tax_rate):
    """Ch. 12, pp. 329–331. Foundation-plan gap under a nonnegative grant floor."""
    local = number(tax_base_usd_pupil, "tax base", 0) * number(required_tax_rate, "tax rate", 0, 1)
    return {"local_usd_pupil": local, "grant_usd_pupil": max(0, number(target_usd_pupil, "foundation", 0) - local)}


def prevention_benefit(baseline_incidents, causal_reduction_fraction, harm_usd_incident, annual_program_usd):
    """Ch. 13, pp. 354–356. Public-program cost-benefit screen with assumed causal effect."""
    avoided = number(baseline_incidents, "annual incidents", 0) * number(causal_reduction_fraction, "causal reduction", 0, 1)
    return {"expected_incidents_averted": avoided, "annual_net_benefit_usd": avoided * number(harm_usd_incident, "social harm", 0) - number(annual_program_usd, "program cost", 0)}


def maintenance(annual_rent_uplift, years, discount_rate, upfront_usd):
    """Ch. 14, pp. 368–372. Incremental maintenance with constant year-end rent change."""
    n = number(years, "years", 1, 1000)
    if int(n) != n:
        raise ValueError("years must be whole")
    rate = number(discount_rate, "discount rate", 0)
    annuity = n if rate == 0 else -math.expm1(-n * math.log1p(rate)) / rate
    return {"incremental_npv_usd": number(annual_rent_uplift, "annual rent uplift") * annuity - number(upfront_usd, "upfront cost", 0)}


def price_ceiling(ceiling_usd, demand_intercept_units, demand_units_per_usd, supply_intercept_units, supply_units_per_usd):
    """Ch. 15. Linear housing supply and demand with a binding or slack rent ceiling."""
    cap = number(ceiling_usd, "ceiling", 0)
    demand = number(demand_intercept_units, "demand intercept", 0)
    supply = number(supply_intercept_units, "supply intercept")
    d = positive(demand_units_per_usd, "demand slope")
    s = positive(supply_units_per_usd, "supply slope")
    eq = (demand - supply) / (s + d)
    if eq < 0 or demand - d * eq <= 0:
        raise ValueError("Curves must have a positive-quantity nonnegative-price intersection")
    rent = min(eq, cap)
    supplied, wanted = max(0, supply + rent * s), demand - rent * d
    return {"equilibrium_rent_usd": eq, "modeled_rent_usd": rent, "supplied_units": supplied, "shortage_units": max(0, wanted - supplied)}


def public_good(individual_marginal_benefits_usd, incremental_cost_usd):
    """Ch. 16. Vertically aggregate marginal benefits from one shared project increment."""
    if not isinstance(individual_marginal_benefits_usd, list) or not individual_marginal_benefits_usd:
        raise ValueError("Supply a list of marginal benefit estimates")
    total = sum(number(v, "marginal benefit") for v in individual_marginal_benefits_usd)
    return {"aggregate_marginal_benefit_usd": total, "incremental_surplus_usd": total - number(incremental_cost_usd, "incremental cost", 0)}


def matching_grant(project_usd, grant_share, grant_cap_usd):
    """Ch. 17, pp. 447–449. Grant share of eligible total cost subject to a dollar cap."""
    total = number(project_usd, "eligible cost", 0)
    grant = min(total * number(grant_share, "share", 0, 1), number(grant_cap_usd, "cap", 0))
    return {"grant_usd": grant, "local_usd": total - grant}


MODELS = {model.__name__: model for model in (
    median_location, labor_shift, residual_bid, far_capacity, congestion, transit_cost,
    foundation_gap, prevention_benefit, maintenance, price_ceiling, public_good, matching_grant
)}


def run(packet):
    if not isinstance(packet, dict) or set(packet) != {"model", "inputs"} or not isinstance(packet["inputs"], dict):
        raise ValueError("Supply an object with model and inputs")
    model = MODELS.get(packet["model"]) if isinstance(packet["model"], str) else None
    if model is None:
        raise ValueError("Unknown economic model")
    try:
        inspect.signature(model).bind(**packet["inputs"])
    except TypeError as exc:
        raise ValueError(str(exc)) from exc
    result = model(**packet["inputs"])
    return {"model": model.__name__, "method": model.__doc__, "inputs": packet["inputs"],
            "results": result, "status": "scenario", "financial_authority_usd": 0}


def demo():
    common = dict(fare_usd=2, walk_minutes=8, ride_minutes=20, access_usd_hour=18, wait_usd_hour=18, ride_usd_hour=12)
    base, option = [run(dict(model="transit_cost", inputs={**common,"headway_minutes":h})) for h in (30, 15)]
    benefit = base["results"]["generalized_usd_trip"] - option["results"]["generalized_usd_trip"]
    return {"label":"SIMULATION · illustrative Florida Main Street transit study",
            "routing":["SW-01 validates routes and headways","SW-04 compares generalized costs","SW-05 checks operator cost","SW-13 reviews evidence"],
            "base":base,"option":option,"time_benefit_usd_per_existing_trip":benefit,
            "next_decision":"Collect actual boarding counts, time variability and incremental service cost before estimating aggregate surplus."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    cmd = parser.add_mutually_exclusive_group(required=True)
    cmd.add_argument("--list", action="store_true")
    cmd.add_argument("--demo", action="store_true")
    cmd.add_argument("--input", type=Path, help="JSON file with model and inputs")
    args = parser.parse_args()
    try:
        if args.list:
            result = {name: {"inputs":list(inspect.signature(f).parameters), "method":f.__doc__} for name,f in MODELS.items()}
        elif args.demo:
            result = demo()
        else:
            result = run(json.loads(args.input.read_text()))
        print(json.dumps(result, indent=2, allow_nan=False))
    except (ValueError, OverflowError, OSError) as exc:
        parser.exit(2, f"Model error: {exc}\n")


if __name__ == "__main__":
    main()
