"""Lossless start-display value for the C model; no scoring or race-status inference."""
from __future__ import annotations
import math
import re
import unicodedata
from typing import Literal
from pydantic import BaseModel, ConfigDict, field_validator, model_validator


class ExhibitionStartReading(BaseModel):
    model_config = ConfigDict(frozen=True, extra='forbid')
    raw: str
    marker: Literal['F', 'L'] | None = None
    seconds_magnitude: float | None = None

    @field_validator('raw', mode='before')
    @classmethod
    def exact_text(cls, value):
        if type(value) is not str:
            raise ValueError('START_RAW_MUST_BE_TEXT')
        return value

    @field_validator('marker', mode='before')
    @classmethod
    def exact_marker(cls, value):
        if value is not None and (type(value) is not str or value not in ('F', 'L')):
            raise ValueError('INVALID_START_MARKER')
        return value

    @field_validator('seconds_magnitude', mode='before')
    @classmethod
    def exact_magnitude(cls, value):
        if value is not None and (type(value) not in (int, float) or not math.isfinite(value)):
            raise ValueError('INVALID_START_MAGNITUDE')
        return value

    @model_validator(mode='after')
    def consistent_reading(self):
        text = unicodedata.normalize('NFKC', self.raw).strip()
        if text in ('F', 'L'):
            expected = (text, None)
        else:
            match = re.fullmatch(r'([FL])?((?:[0-9])?\.\d{2})', text)
            if match is None:
                raise ValueError('INVALID_START_RAW')
            expected = (match[1], float(match[2]))
        if (self.marker, self.seconds_magnitude) != expected:
            raise ValueError('START_RAW_MARKER_MAGNITUDE_CONFLICT')
        return self
