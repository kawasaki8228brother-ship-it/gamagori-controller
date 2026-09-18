"""Prepared beforeinfo -> live model adapter; not yet wired to the C fetcher.

The legacy numeric ST view only contains unmarked values. All recognized F/L
readings remain available in the lossless field, including marker-only entries.
No completion policy, source identity/freshness or real-race status is inferred.
"""
from dataclasses import asdict, dataclass
from models import LiveDataCompleteness, SourceEvidence
from start_reading import ExhibitionStartReading
from v11_candidate.observation import parse_beforeinfo_observation, ParseState

PARSER_VERSION = 'C_BEFOREINFO_LOSSLESS_ST_V1_CANDIDATE'


@dataclass(frozen=True)
class BeforeinfoTransfer:
    live_data: LiveDataCompleteness
    section_reports: dict
    runtime_connected: bool = False


def prepare_beforeinfo(html: str, url: str, acquired_at: str) -> BeforeinfoTransfer:
    observed = parse_beforeinfo_observation(html)
    readings = {boat: ExhibitionStartReading(**asdict(reading))
                for boat, reading in observed.data.starts.items()}
    ordinary = {boat: value.seconds_magnitude for boat, value in readings.items()
                if value.marker is None and value.seconds_magnitude is not None}
    sections = {key: asdict(value) for key, value in observed.sections.items()}
    status = 'OK' if all(v.state == ParseState.PARSED for v in observed.sections.values()) else 'PARTIAL'
    data = LiveDataCompleteness(
        is_complete=False,
        exhibition_times=dict(observed.data.exhibition_times),
        entry_courses=dict(observed.data.entry_courses),
        start_exhibition_st=ordinary,
        start_exhibition_readings=readings,
        weather_info=dict(observed.data.weather),
        missing_fields=list(observed.data.missing_fields),
        source_evidence={'beforeinfo': SourceEvidence(url=url, acquired_at=acquired_at,
                        status=status, parser_status=PARSER_VERSION)},
    )
    return BeforeinfoTransfer(data, sections)
