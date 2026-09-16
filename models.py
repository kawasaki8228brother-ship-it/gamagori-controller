from __future__ import annotations

import datetime as dt
import re
from enum import Enum
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field, field_validator

JST = ZoneInfo("Asia/Tokyo")


class RaceStatus(str, Enum):
    PENDING = "PENDING"
    DATA_WAIT = "DATA_WAIT"
    CLOSING_WINDOW = "CLOSING_WINDOW"
    FREEZE_ZONE = "FREEZE_ZONE"
    SAFE_STOP = "SAFE_STOP"
    C_EVENT_DONE = "C_EVENT_DONE"
    REOPENED = "REOPENED"
    TERMINAL = "TERMINAL"


class TerminalReason(str, Enum):
    OFFICIALLY_CLOSED = "OFFICIALLY_CLOSED"
    CANCELLED = "CANCELLED"
    SOURCE_ERROR_TIMEOUT = "SOURCE_ERROR_TIMEOUT"


class MissedObservationReason(str, Enum):
    MISSED_DATA_INCOMPLETE = "MISSED_DATA_INCOMPLETE"
    MISSED_WINDOW_SKIPPED_BY_DEADLINE_CHANGE = "MISSED_WINDOW_SKIPPED_BY_DEADLINE_CHANGE"
    MISSED_SOURCE_ERROR = "MISSED_SOURCE_ERROR"


class SourceEvidence(BaseModel):
    url: str
    acquired_at: str
    status: str
    parser_status: str = "OK"


class OfficialRaceInfo(BaseModel):
    race_id: str
    official_deadline: dt.datetime
    is_closed: bool = False
    is_cancelled: bool = False
    sales_status: str = "UNKNOWN"
    source_url: str
    acquired_at: str


class RaceIndexSnapshot(BaseModel):
    date: str
    races: List[OfficialRaceInfo] = Field(default_factory=list)
    source_url: str
    acquired_at: str


class LiveDataCompleteness(BaseModel):
    is_complete: bool = False
    exhibition_times: Dict[int, float] = Field(default_factory=dict)
    entry_courses: Dict[int, int] = Field(default_factory=dict)
    start_exhibition_st: Dict[int, float] = Field(default_factory=dict)
    weather_info: Dict[str, Any] = Field(default_factory=dict)
    odds_3t: Dict[str, float] = Field(default_factory=dict)
    missing_fields: List[str] = Field(default_factory=list)
    source_evidence: Dict[str, SourceEvidence] = Field(default_factory=dict)


class WindowVersionState(BaseModel):
    closing_window_entered: bool = False
    data_wait_seen: bool = False
    window_skipped_by_shortening: bool = False
    c_event_emitted: bool = False
    source_error_streak_max: int = 0


def validate_trifecta_list(predictions: List[str]) -> List[str]:
    if len(predictions) != 5:
        raise ValueError("Must contain exactly 5 predictions.")
    if len(set(predictions)) != 5:
        raise ValueError("All 5 predictions must be unique.")

    pattern = re.compile(r"^[1-6]-[1-6]-[1-6]$")
    for item in predictions:
        if not pattern.match(item):
            raise ValueError(f"Invalid trifecta format: {item}")
        boats = item.split("-")
        if len(set(boats)) != 3:
            raise ValueError(f"Duplicate boat numbers within prediction: {item}")
    return predictions


class EventRecord(BaseModel):
    event_uuid: str
    idempotency_key: str
    race_id: str
    event_type: str
    source: str = "Observer_C"
    deadline_version: int = 1
    baseline_a_event_id: Optional[str] = None
    baseline_b_event_id: Optional[str] = None
    c_a_predictions: List[str] = Field(default_factory=list)
    c_b_predictions: List[str] = Field(default_factory=list)
    payload: Dict[str, Any]
    observed_at: str
    official_deadline: str
    payload_hash: str
    audit_status: str = "VALID"

    @field_validator("c_a_predictions", "c_b_predictions")
    @classmethod
    def check_predictions(cls, value: List[str]) -> List[str]:
        if not value:
            return value
        return validate_trifecta_list(value)


class RaceState(BaseModel):
    race_id: str
    status: RaceStatus = RaceStatus.PENDING
    terminal_reason: Optional[TerminalReason] = None
    terminal_missed_reason: Optional[MissedObservationReason] = None
    official_deadline: Optional[dt.datetime] = None
    deadline_version: int = 1
    last_checked_at: Optional[dt.datetime] = None
    last_successful_official_fetch_at: Optional[dt.datetime] = None
    consecutive_source_error_count: int = 0
    total_source_error_count: int = 0
    last_error_streak_before_success: int = 0
    c_events: List[str] = Field(default_factory=list)
    terminal_event_id: Optional[str] = None
    window_history: Dict[str, WindowVersionState] = Field(default_factory=dict)

    def window_state(self, version: Optional[int] = None) -> WindowVersionState:
        version = version or self.deadline_version
        key = str(version)
        if key not in self.window_history:
            self.window_history[key] = WindowVersionState()
        return self.window_history[key]
