"""Pure input-readiness candidate for EXHIBITION_ONLY_NO_MARKET.

No caller is wired to this policy. Evidence checks are caller assertions with
references, NOT independent validation of URLs, body identity or freshness.
They default to UNVERIFIED. This does not authorize REVISION, persistence or
BET; deadline, live-state, model and durable-write gates remain separate.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from .observation import BeforeObservation, ObservationContractError, ParseState, SectionReport, coverage


class CheckState(str, Enum):
    PASS = 'PASS'
    FAIL = 'FAIL'
    UNVERIFIED = 'UNVERIFIED'


REQUIRED_CHECKS = ('PAGE_IDENTITY', 'EXHIBITION_FRESHNESS', 'START_FRESHNESS', 'OFFICIAL_PARTICIPANTS')
POLICY_ID = 'C_EXHIBITION_ONLY_NO_MARKET_V1_CANDIDATE'


@dataclass(frozen=True)
class EvidenceCheck:
    state: CheckState = CheckState.UNVERIFIED
    evidence_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.state, CheckState):
            raise ValueError('INVALID_CHECK_STATE')
        if type(self.evidence_ids) is not tuple or any(not isinstance(v, str) or not v.strip() for v in self.evidence_ids):
            raise ValueError('INVALID_EVIDENCE_REFERENCES')
        if self.state == CheckState.PASS and not self.evidence_ids:
            raise ValueError('PASS_REQUIRES_EVIDENCE_REFERENCES')


@dataclass(frozen=True)
class ReadinessContext:
    expected_boats: tuple[int, ...] | None = None
    checks: dict[str, EvidenceCheck] = field(default_factory=dict)


@dataclass(frozen=True)
class ReadinessReport:
    policy_id: str
    state: CheckState
    input_eligible: bool
    reasons: tuple[str, ...]
    warnings: tuple[str, ...]
    capabilities: dict[str, bool]
    marker_only_boats: tuple[int, ...]
    marked_numeric_boats: tuple[int, ...]
    unused_inputs: tuple[str, ...] = ('weather', 'odds')


def assess_exhibition_readiness(observation: BeforeObservation, context: ReadinessContext | None = None) -> ReadinessReport:
    """Fixed-six candidate; incomplete official participant policy fails closed.

    Weather/odds do not gate THIS named policy and must not be read by its
    future evaluator. Numeric coverage is capability, not unmarked-ST identity.
    Markers alone never imply DOWN, a probability change or a race violation.
    """
    context = context if context is not None else ReadinessContext()
    failed, unknown, warnings = [], [], []
    caps = {key: False for key in ('exhibition_six', 'entry_six', 'start_data_six', 'numeric_st_six')}
    marker_only, marked_numeric = (), ()
    if not isinstance(observation, BeforeObservation) or type(observation.sections) is not dict:
        failed.append('INVALID_OBSERVATION')
    else:
        try:
            caps = coverage(observation.data)
            starts = observation.data.starts
            marker_only = tuple(sorted(b for b, s in starts.items() if s.marker in {'F', 'L'} and s.seconds_magnitude is None))
            marked_numeric = tuple(sorted(b for b, s in starts.items() if s.marker in {'F', 'L'} and s.seconds_magnitude is not None))
        except ObservationContractError:
            failed.append('INVALID_OBSERVATION_DATA')
        for name in ('exhibition', 'start'):
            section = observation.sections.get(name)
            if not isinstance(section, SectionReport) or section.state != ParseState.PARSED:
                failed.append('REQUIRED_SECTION_NOT_PARSED:' + name)
        weather = observation.sections.get('weather')
        if not isinstance(weather, SectionReport) or weather.state != ParseState.PARSED:
            warnings.append('UNUSED_WEATHER_UNAVAILABLE')
    for key in ('exhibition_six', 'entry_six', 'start_data_six'):
        if not caps[key]:
            failed.append('REQUIRED_COVERAGE_MISSING:' + key)
    if marker_only:
        warnings.append('MARKER_ONLY_ST_QUALITATIVE_ONLY')
    if marked_numeric:
        warnings.append('NUMERIC_ST_REQUIRES_MARKER_AWARE_INTERPRETATION')

    if not isinstance(context, ReadinessContext) or type(context.checks) is not dict:
        failed.append('INVALID_READINESS_CONTEXT')
    else:
        expected = context.expected_boats
        if expected is None:
            unknown.append('OFFICIAL_PARTICIPANTS_NOT_SUPPLIED')
        elif type(expected) is not tuple or any(type(b) is not int or not 1 <= b <= 6 for b in expected) or len(set(expected)) != len(expected):
            failed.append('INVALID_EXPECTED_BOATS')
        elif set(expected) != set(range(1, 7)):
            unknown.append('REDUCED_FIELD_POLICY_NOT_IMPLEMENTED')
        for key in REQUIRED_CHECKS:
            check = context.checks.get(key)
            if check is None:
                unknown.append(key + ':UNVERIFIED')
            elif not isinstance(check, EvidenceCheck):
                failed.append('INVALID_EVIDENCE_CHECK:' + key)
            elif check.state == CheckState.FAIL:
                failed.append(key + ':FAIL')
            elif check.state == CheckState.UNVERIFIED:
                unknown.append(key + ':UNVERIFIED')
            elif not check.evidence_ids:
                failed.append(key + ':EVIDENCE_MISSING')
    state = CheckState.FAIL if failed else CheckState.UNVERIFIED if unknown else CheckState.PASS
    return ReadinessReport(POLICY_ID, state, state == CheckState.PASS, tuple(failed + unknown), tuple(warnings), caps, marker_only, marked_numeric)
