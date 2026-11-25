"""Classify documented lawful-unit counts for research routing."""


def route_unit_band(lawful_units, *, evidence_state):
    if evidence_state not in {"VERIFIED", "UNKNOWN", "CONFLICT"}:
        raise ValueError("Unknown unit evidence state")
    if lawful_units is not None and (type(lawful_units) is not int or lawful_units < 0):
        raise ValueError("Unit count must be a nonnegative integer or null")
    if evidence_state != "VERIFIED" or lawful_units is None:
        return {"band": "HOLD", "financing_research_path": None}
    if not 2 <= lawful_units <= 20:
        return {"band": "OUT_OF_SCOPE", "financing_research_path": None}
    if lawful_units <= 5:
        band = "PRIMARY"
    elif lawful_units <= 10:
        band = "SECONDARY"
    else:
        band = "SELECTIVE"
    path = "RESIDENTIAL_PROGRAM_RESEARCH" if lawful_units <= 4 else "COMMERCIAL_PROGRAM_RESEARCH"
    return {"band": band, "financing_research_path": path}
