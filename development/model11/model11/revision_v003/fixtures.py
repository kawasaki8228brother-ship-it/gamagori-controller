"""Explicitly invented pre-deadline course fixtures; no real course inference."""
from copy import deepcopy

from ..synthetic import make_dataset
from ..engine import canonical_hash
from .course import apply_course_fixture


def make_dataset_v003(days=36, races_per_day=2, seed=20261105,
                      course_policy_id="EXHIBITION_ONLY_V001"):
    original = make_dataset(days, races_per_day, seed)
    result = deepcopy(original)
    result["races"] = []
    for source in original["races"]:
        race = apply_course_fixture(source, course_policy_id)
        # Keep the original simulator's pre-outcome course feature for the
        # exhibition lane. The helper's deliberately shifted-map fixture remains
        # available for F3 mismatch tests; it is not substituted into this demo's
        # outcomes/odds data-generating process.
        courses = {str(boat["boat"]): boat["course"] for boat in source["boats"]}
        observation = race["course_inputs"]["exhibition"]
        observation["courses"] = courses
        observation["evidence_sha256"] = canonical_hash({
            "synthetic_course_fixture": "EXHIBITION_ENTRY", "race_id": race["race_id"], "courses": courses})
        if course_policy_id != "FRAME_ONLY_V001":
            for boat in race["boats"]:
                boat["course"] = courses[str(boat["boat"])]
        result["races"].append(race)
    result["course_fixture_policy"] = course_policy_id
    result["classification"] = "SYNTHETIC_ONLY"
    result["course_evidence_authenticity"] = "SYNTHETIC_INVENTED_NOT_REAL_OBSERVATIONS"
    result["exhibition_fixture_convention"] = "ORIGINAL_PRE_OUTCOME_SIMULATOR_COURSES_NOT_REAL_OR_RESULT_ENTRY"
    return result
