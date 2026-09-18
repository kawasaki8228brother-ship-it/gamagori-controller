from __future__ import annotations

import datetime as dt
from typing import Any, Dict, List, Optional, Tuple

from models import LiveDataCompleteness


class ClosingEvaluator:
    @staticmethod
    def calculate_time_to_deadline(official_deadline: dt.datetime, now: dt.datetime) -> float:
        return (official_deadline - now).total_seconds() / 60.0

    @staticmethod
    def evaluate_window_status(remaining_minutes: float) -> str:
        if remaining_minutes > 10.0:
            return "TOO_EARLY"
        if 5.0 < remaining_minutes <= 10.0:
            return "IN_CLOSING_WINDOW"
        if 4.0 < remaining_minutes <= 5.0:
            return "FREEZE_ZONE"
        return "SAFE_STOP"

    @staticmethod
    def evaluate_closing_signals(
        race_id: str,
        deadline_version: int,
        official_deadline_iso: str,
        baseline_a_id: Optional[str],
        baseline_b_id: Optional[str],
        live_data: LiveDataCompleteness,
        observed_at_iso: str,
    ) -> Tuple[List[str], List[str], Dict[str, Any]]:
        # Shadow-only placeholder: prediction logic intentionally remains mocked.
        c_a_5pts = ["1-2-3", "1-2-4", "1-3-2", "1-3-4", "1-4-2"]
        c_b_5pts = ["1-2-3", "1-2-5", "1-3-2", "1-5-2", "1-5-3"]

        payload = {
            "schema_version": 1,
            "model_version": "v0.4.1_shadow",
            "controller_version": "v0.4.1",
            "race_id": race_id,
            "source": "Observer_C",
            "deadline_version": deadline_version,
            "official_deadline": official_deadline_iso,
            "baseline_a_event_id": baseline_a_id,
            "baseline_b_event_id": baseline_b_id,
            "c_a_predictions": c_a_5pts,
            "c_b_predictions": c_b_5pts,
            "source_evidence": {
                name: evidence.model_dump() for name, evidence in live_data.source_evidence.items()
            },
            "live_data": {
                "exhibition_times": live_data.exhibition_times,
                "entry_courses": live_data.entry_courses,
                "start_exhibition_st": live_data.start_exhibition_st,
                "start_exhibition_readings": {
                    boat: reading.model_dump()
                    for boat, reading in live_data.start_exhibition_readings.items()
                },
                "weather_info": live_data.weather_info,
                "odds_3t": live_data.odds_3t,
            },
            "observed_at": observed_at_iso,
        }
        return c_a_5pts, c_b_5pts, payload
