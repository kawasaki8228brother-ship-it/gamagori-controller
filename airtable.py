from __future__ import annotations

import hashlib
import json
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict

from models import EventRecord
from repositories import SQLiteStateRepository

logger = logging.getLogger("gamagori-controller")


class AirtableAdapter(ABC):
    @abstractmethod
    async def append_event(self, record: EventRecord) -> tuple[bool, str, str]:
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

    async def append_event(self, record: EventRecord) -> tuple[bool, str, str]:
        calc_hash = self.generate_canonical_hash(record.payload)
        if calc_hash != record.payload_hash:
            logger.error("[HASH_MISMATCH] %s expected=%s got=%s", record.race_id, record.payload_hash, calc_hash)
            return False, "HASH_MISMATCH", record.event_uuid

        ok, status, persisted_uuid = await self.repo.append_shadow_event_atomic(record)
        logger.info(
            "[DRY_RUN:%s] race=%s type=%s dl_ver=%s key=%s hash=%s readback=NOT_APPLICABLE_DRY_RUN",
            status,
            record.race_id,
            record.event_type,
            record.deadline_version,
            record.idempotency_key,
            record.payload_hash[:8],
        )
        return ok, status, persisted_uuid
