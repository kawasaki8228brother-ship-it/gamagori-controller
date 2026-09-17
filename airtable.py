from __future__ import annotations

import hashlib
import json
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict

from models import (
    AppendOutcome,
    AppendOutcomeStatus,
    EventRecord,
    FailureClass,
)
from repositories import SQLiteStateRepository

logger = logging.getLogger("gamagori-controller")


class AirtableAdapter(ABC):
    @abstractmethod
    async def append_event(self, record: EventRecord) -> AppendOutcome:
        raise NotImplementedError


class DryRunAirtableAdapter(AirtableAdapter):
    """No network writes. Persists only to local Shadow DB for audit/testing."""

    def __init__(self, repo: SQLiteStateRepository):
        self.repo = repo

    @staticmethod
    def generate_canonical_hash(payload: Dict[str, Any]) -> str:
        canonical_json = json.dumps(
            payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
        return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()

    async def append_event(self, record: EventRecord) -> AppendOutcome:
        # EventRecord requires identity_hash, but fail closed here as a second line of defense
        # against malformed/model_construct inputs instead of allowing logging or persistence
        # to raise outside the explicit AppendOutcome failure contract.
        if not record.identity_hash:
            logger.error("[IDENTITY_HASH_MISSING] %s", record.race_id)
            return AppendOutcome(
                status=AppendOutcomeStatus.FAILED,
                failure_class=FailureClass.NON_RETRYABLE,
                message="IDENTITY_HASH_MISSING",
            )

        calc_hash = self.generate_canonical_hash(record.payload)
        if calc_hash != record.payload_hash:
            logger.error(
                "[HASH_MISMATCH] %s expected=%s got=%s",
                record.race_id,
                record.payload_hash,
                calc_hash,
            )
            return AppendOutcome(
                status=AppendOutcomeStatus.FAILED,
                failure_class=FailureClass.NON_RETRYABLE,
                message="HASH_MISMATCH",
            )

        outcome = await self.repo.append_shadow_event_atomic(record)
        level = logging.ERROR if outcome.status == AppendOutcomeStatus.DUPLICATE_CONFLICT else logging.INFO
        logger.log(
            level,
            "[DRY_RUN:%s] race=%s type=%s dl_ver=%s key=%s identity=%s hash=%s "
            "existing_uuid=%s readback=NOT_APPLICABLE_DRY_RUN",
            outcome.status.value,
            record.race_id,
            record.event_type,
            record.deadline_version,
            record.idempotency_key,
            record.identity_hash[:8],
            record.payload_hash[:8],
            outcome.event_uuid or "NONE",
        )
        return outcome