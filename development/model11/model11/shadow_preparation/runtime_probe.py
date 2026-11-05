"""Opt-in local synthetic-environment observation. No writes or network calls."""
from datetime import datetime, timezone
import hashlib
import os
from pathlib import Path
import platform
import shutil
import sqlite3
import ssl
import stat
import sys
import time

from ..shadow_launch.storage import _process_identity


def probe_local_runtime(storage_directory=None, *, enable_offline=False, classification=None):
    """Observe a caller-created synthetic directory, never provision a host/store.

    A submitted classification is an operation guard, not authentication of an
    actual location. This is not a production host preflight or approval gate.
    """
    disabled = {"status": "DISABLED", "application_status": "HOLD", "production_go": False}
    if enable_offline is not True:
        return disabled
    if classification != "SYNTHETIC_ONLY":
        return {**disabled, "status": "HOLD", "reasons": ["EXPLICIT_SYNTHETIC_LOCAL_SCOPE_REQUIRED"]}
    try:
        path = Path(storage_directory)
        if path.is_symlink() or not stat.S_ISDIR(path.stat(follow_symlinks=False).st_mode):
            raise ValueError("LOCAL_DIRECTORY_REQUIRED")
        before, mono_before = datetime.now(timezone.utc), time.monotonic_ns()
        disk = shutil.disk_usage(path)
        process = _process_identity(os.getpid())
        after, mono_after = datetime.now(timezone.utc), time.monotonic_ns()
        return {"schema": "MODEL11_LOCAL_RUNTIME_OBSERVATION_V006", "status": "LOCAL_OBSERVATION_ONLY",
            "classification": "SYNTHETIC_ONLY", "application_status": "HOLD", "production_go": False,
            "python": platform.python_version(), "python_full": sys.version,
            "openssl": ssl.OPENSSL_VERSION, "sqlite": sqlite3.sqlite_version,
            "sqlite_threadsafety": sqlite3.threadsafety, "platform": platform.platform(),
            "process": {"pid": os.getpid(), "identity_available": process is not None,
                "identity_sha256": None if process is None else hashlib.sha256(process.encode("ascii")).hexdigest(),
                "meaning": "LOCAL_LINUX_BOOT_ID_AND_PID_START_TICKS_NOT_EXTERNAL_AUTHENTICATION"},
            "disk": {"total_bytes": disk.total, "used_bytes": disk.used, "free_bytes": disk.free,
                "path_disclosed": False, "capacity_requirement": "UNADOPTED_REAL_PAYLOAD_AND_RETENTION_UNKNOWN"},
            "clock": {"wall_before_utc": before.isoformat(), "wall_after_utc": after.isoformat(),
                "monotonic_before_ns": mono_before, "monotonic_after_ns": mono_after,
                "local_order_observed": before <= after and mono_before <= mono_after,
                "external_utc_accuracy": "UNVERIFIED", "synchronization_evidence": None,
                "clock_offset_threshold": "NOT_ADOPTED"},
            "host_creation": False, "network_used": False, "database_opened": False,
            "task_registered": False, "files_written": False, "launch_allowed": False}
    except Exception:
        return {**disabled, "status": "HOLD", "reasons": ["LOCAL_RUNTIME_OBSERVATION_UNVERIFIED"]}
