"""Research-only parcel screens with scope-specific criteria."""
import math


def screen_estate_acreage(program, parcel_area_sqft, *, minimum_acres=35):
    """A parcel's total acreage is only an upper bound on its contiguous uplands."""
    if program not in {"MAIN_STREET_INFILL", "ESTATE"}:
        raise ValueError("Unknown screening program")
    for name, value in (("parcel area", parcel_area_sqft), ("acreage minimum", minimum_acres)):
        if value is None and name == "parcel area":
            continue
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
            raise ValueError(f"Invalid {name}")
    total_acres = None if parcel_area_sqft is None else parcel_area_sqft / 43_560
    if program == "MAIN_STREET_INFILL":
        status = "NOT_APPLICABLE"
    elif total_acres is not None and total_acres < minimum_acres:
        status = "BELOW_MINIMUM_EVEN_BEFORE_CONSTRAINTS"
    else:
        status = "UNKNOWN_CONTIGUOUS_UPLANDS"
    return {
        "program": program,
        "total_area_upper_bound_acres": total_acres,
        "estate_minimum_acres": minimum_acres if program == "ESTATE" else None,
        "contiguous_upland_acres": None,
        "status": status,
    }

def screen_network_access(*, nodes, edges, origin, destinations, mode, network_revision,
                          authority_source, observed_date, cutoff, phases, network_complete=False):
    """Bind a dated network and phase evidence to the parcel's research access screen."""
    from datetime import date

    from .transportation import accessibility, assess_phase

    if not all(isinstance(value, str) and value.strip()
               for value in (network_revision, authority_source)):
        raise ValueError("Network revision and authority source are required")
    if not isinstance(network_complete, bool):
        raise ValueError("Network coverage must be a boolean")
    if date.fromisoformat(observed_date) > date.fromisoformat(cutoff):
        raise ValueError("Network evidence unavailable at cutoff")
    phase_by_id = {}
    for phase in phases:
        evaluated = assess_phase(**phase, cutoff=cutoff)
        phase_id = evaluated["phase_id"]
        if phase_id in phase_by_id:
            raise ValueError("Duplicate phase evidence")
        phase_by_id[phase_id] = evaluated
    observed_edges = []
    withheld = 0
    for edge in edges:
        phase_id = edge.get("phase_id")
        phase = phase_by_id.get(phase_id)
        if phase_id is not None and (phase is None or phase["scenario_only"]):
            observed_edges.append({**edge, "state": "UNKNOWN"})
            withheld += 1
        else:
            observed_edges.append(edge)
    result = accessibility(nodes, observed_edges, origin, destinations, mode,
                           network_complete=network_complete and not withheld)
    return {
        **result,
        "network_revision": network_revision,
        "authority_source": authority_source,
        "observed_date": observed_date,
        "cutoff": cutoff,
        "travel_time_unit": "minutes",
        "phase_evidence": list(phase_by_id.values()),
        "withheld_phase_edges": withheld,
    }



def screen_walkable_main_street(*, parcel_id, district_membership, lawful_units,
                               nodes=(), edges=(), destinations=None, entrance=None,
                               graph_revision=None, network_complete=False, network_draft=False):
    """Screen a parcel with independently supplied district, count and entrance evidence."""
    from .corridor_linkage import corridor_routes

    if district_membership is not None and type(district_membership) is not bool:
        raise ValueError("District membership must be true, false or unknown")
    if lawful_units is not None and (type(lawful_units) is not int or lawful_units < 0):
        raise ValueError("Lawful units must be a nonnegative integer or unknown")
    if type(network_draft) is not bool:
        raise ValueError("Network draft flag must be boolean")
    if graph_revision is None:
        if nodes or edges or destinations or network_complete or network_draft:
            raise ValueError("Supplied pedestrian network requires a revision")
        access = None
    else:
        access = corridor_routes(
            nodes=nodes, edges=edges, corridors=destinations, entrance=entrance,
            graph_revision=graph_revision, mode="walk", network_complete=network_complete and not network_draft,
        )
    reasons = []
    if district_membership is None:
        reasons.append("DISTRICT_MEMBERSHIP_UNVERIFIED")
    elif not district_membership:
        reasons.append("OUTSIDE_VERIFIED_DISTRICT")
    if lawful_units is None:
        reasons.append("LAWFUL_UNITS_UNVERIFIED")
    elif not 2 <= lawful_units <= 4:
        reasons.append("OUTSIDE_UNIT_SCOPE")
    if entrance is None:
        reasons.append("ENTRANCE_UNVERIFIED")
    if access is None:
        reasons.append("PEDESTRIAN_NETWORK_UNAVAILABLE")
    elif network_draft:
        reasons.append("PEDESTRIAN_NETWORK_DRAFT")
    elif not network_complete:
        reasons.append("PEDESTRIAN_NETWORK_INCOMPLETE")
    if access is not None and not any(route.get("within_10_minutes") for route in access["routes"]):
        reasons.append("NO_DOCUMENTED_DESTINATION_WITHIN_TEN_MINUTES")
    return {
        "parcel_id": parcel_id,
        "district_membership": district_membership,
        "lawful_units": lawful_units,
        "decision": "HOLD" if reasons else "WALKABILITY_REVIEW_CANDIDATE",
        "reasons": reasons,
        "access": access,
        "authorization": False,
    }
