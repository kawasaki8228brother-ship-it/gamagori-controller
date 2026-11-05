"""Explicitly initialized local-only immutable research evidence store.

Construction performs no I/O. This module has no production connector, replay,
STOP-clear, overwrite, or delete operation. SQLite is only a new local ledger.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import threading
import uuid


_HEX = re.compile(r"^[0-9a-f]{64}$")
_ID = re.compile(r"^[A-Za-z0-9_.-]{1,128}$")
_REASON = re.compile(r"^[A-Z][A-Z0-9_]{0,95}$")
_OWNER = "MODEL11_THIRD_RESEARCH_STORE_V005"


class _Unsafe(ValueError):
    pass


def _need(condition, reason):
    if not condition:
        raise _Unsafe(reason)


def _timestamp(value):
    _need(isinstance(value, str) and not value.endswith("-00:00"), "AWARE_TIME_REQUIRED")
    fraction = re.search(r"\.(\d+)", value)
    _need(not fraction or len(fraction.group(1)) <= 6, "TIMESTAMP_PRECISION")
    matched = re.fullmatch(r"\d{4}-\d{2}-\d{2}T(?P<hour>\d{2}):(?P<minute>\d{2}):(?P<second>\d{2})(?:\.\d{1,6})?(?P<offset>Z|[+-]\d{2}:\d{2})", value)
    _need(matched is not None, "TIMESTAMP_RFC3339_REQUIRED")
    _need(int(matched["hour"]) <= 23 and int(matched["minute"]) <= 59
          and int(matched["second"]) <= 59, "TIMESTAMP_CLOCK_RANGE")
    offset = matched["offset"]
    if offset != "Z":
        _need(int(offset[1:3]) <= 23 and int(offset[4:6]) <= 59, "TIMESTAMP_OFFSET_RANGE")
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        raise _Unsafe("AWARE_TIME_REQUIRED") from None
    _need(result.tzinfo is not None and result.utcoffset() is not None, "AWARE_TIME_REQUIRED")
    return result


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
                      allow_nan=False).encode("ascii")


def _digest(raw):
    return hashlib.sha256(raw).hexdigest()


def _reason(reason):
    return reason if isinstance(reason, str) and _REASON.fullmatch(reason) else "UNSPECIFIED_STOP"


def _parse(raw):
    def pairs(values):
        result = {}
        for key, value in values:
            _need(key not in result, "DUPLICATE_JSON_KEY")
            result[key] = value
        return result
    def constant(_):
        raise _Unsafe("NONFINITE_JSON")
    try:
        return json.loads(raw.decode("utf-8"), object_pairs_hook=pairs, parse_constant=constant)
    except (UnicodeError, ValueError, TypeError):
        raise _Unsafe("INVALID_JSON_BYTES") from None


def _process_identity(pid):
    """Local Linux PID-reuse guard; not an application/worker identity proof."""
    try:
        text = Path("/proc" + "/" + str(pid) + "/stat").read_text(encoding="ascii")
        start_ticks = text[text.rfind(")") + 2:].split()[19]
        boot = Path("/proc/sys/kernel/random/boot_id").read_text(encoding="ascii").strip()
        return boot + ":" + start_ticks
    except (OSError, IndexError, UnicodeError):
        return None


class ShadowStore:
    """New owned local root only. Caller must pass the independent launch gate."""

    def __init__(self, root, namespace="MODEL11_THIRD_RESEARCH", clock=None, fault=None):
        # Deliberately no stat, mkdir, resolve, sqlite connection, time or RNG.
        self.root = Path(root)
        self.namespace = namespace
        self.clock = clock
        self.fault = fault
        self._initialized = False
        self._storage_id = None
        self._session = None
        self._process = None
        self._initialize_lock = threading.RLock()
        self._closed = False

    def _now(self):
        value = self.clock() if self.clock is not None else datetime.now(timezone.utc)
        if isinstance(value, str):
            value = _timestamp(value)
        _need(isinstance(value, datetime) and value.tzinfo is not None
              and value.utcoffset() is not None, "CLOCK_NOT_AWARE")
        return value

    def _fault(self, stage):
        if self.fault is not None:
            self.fault(stage)

    def _fsync_dir(self, directory):
        descriptor = os.open(directory, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)

    def _exclusive(self, path, raw):
        _need(isinstance(raw, bytes), "RAW_BYTES_REQUIRED")
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(path, flags, 0o600)
        try:
            with os.fdopen(descriptor, "wb", closefd=False) as stream:
                stream.write(raw)
                stream.flush()
                os.fsync(descriptor)
        finally:
            os.close(descriptor)
        self._fsync_dir(path.parent)
        _need(path.read_bytes() == raw, "EXCLUSIVE_FILE_READBACK_MISMATCH")

    def _safe_root(self):
        absolute = Path(os.path.abspath(self.root))
        for path in (absolute, *absolute.parents):
            _need(not path.is_symlink(), "SYMLINK_PATH_FORBIDDEN")
        _need(absolute.is_dir(), "STORE_ROOT_NOT_DIRECTORY")
        for directory, dirs, files in os.walk(absolute, followlinks=False):
            for name in dirs + files:
                _need(not (Path(directory) / name).is_symlink(), "SYMLINK_IN_STORE")
        return absolute

    @contextmanager
    def _db(self):
        self._safe_root()
        db = sqlite3.connect(self.root / "ledger.sqlite3", timeout=5, isolation_level=None)
        db.row_factory = sqlite3.Row
        try:
            db.execute("PRAGMA synchronous=FULL")
            db.execute("PRAGMA foreign_keys=ON")
            db.execute("BEGIN IMMEDIATE")
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def initialize(self):
        with self._initialize_lock:
            return self._initialize_impl()

    def _initialize_impl(self):
        """Explicit creation/verification. Never adopt a nonempty unowned root."""
        try:
            if self._initialized:
                self._safe_root()
                marker = _parse((self.root / "OWNER.json").read_bytes())
                _need(marker.get("storage_id") == self._storage_id and marker.get("namespace") == self.namespace,
                      "OWNERSHIP_MISMATCH")
                _need(self._process == _process_identity(os.getpid()), "FORKED_INSTANCE_REUSE_FORBIDDEN")
                return {"status": "HOLD" if self.is_stopped() or self._closed else "READY", "storage_id": self._storage_id,
                        "namespace": self.namespace, "reason": "STORE_SESSION_CLOSED" if self._closed else
                        "DURABLE_STOP_PRESENT" if self.is_stopped() else None}
            _need(isinstance(self.namespace, str) and _ID.fullmatch(self.namespace), "NAMESPACE_INVALID")
            absolute = Path(os.path.abspath(self.root))
            for path in (absolute, *absolute.parents):
                _need(not path.is_symlink(), "SYMLINK_PATH_FORBIDDEN")
            if not absolute.exists():
                absolute.mkdir(mode=0o700)  # Parent must already be owned/approved.
                self._fsync_dir(absolute.parent)
            _need(absolute.is_dir(), "STORE_ROOT_NOT_DIRECTORY")
            self.root = absolute
            owner = self.root / "OWNER.json"
            if not owner.exists():
                _need(not any(self.root.iterdir()), "NONEMPTY_UNOWNED_ROOT")
                marker = {"format": _OWNER, "namespace": self.namespace, "storage_id": uuid.uuid4().hex}
                try:
                    self._exclusive(owner, _json(marker))
                except FileExistsError:
                    pass  # Another initializer won; inspect that exact owner below.
            self._safe_root()
            marker = _parse(owner.read_bytes())
            _need(isinstance(marker, dict) and marker.get("format") == _OWNER
                  and marker.get("namespace") == self.namespace
                  and isinstance(marker.get("storage_id"), str)
                  and re.fullmatch(r"[0-9a-f]{32}", marker["storage_id"]), "OWNERSHIP_MISMATCH")
            self._storage_id = marker["storage_id"]
            allowed = {"OWNER.json", "ledger.sqlite3", "ledger.sqlite3-journal", "ledger.sqlite3-wal",
                       "ledger.sqlite3-shm", "artifacts", "results", "audits", "STOP.json"}
            _need(not {path.name for path in self.root.iterdir()} - allowed, "UNEXPECTED_STORE_ENTRY")
            for name in ("artifacts", "results", "audits"):
                directory = self.root / name
                directory.mkdir(mode=0o700, exist_ok=True)
                _need(directory.is_dir() and not directory.is_symlink(), "STORE_FOLDER_INVALID")
            with self._db() as db:
                version = db.execute("PRAGMA user_version").fetchone()[0]
                _need(version in (0, 5), "LEDGER_SCHEMA_UNREVIEWED")
                db.execute("CREATE TABLE IF NOT EXISTS meta (name TEXT PRIMARY KEY, value TEXT NOT NULL)")
                db.execute("CREATE TABLE IF NOT EXISTS races (race_key TEXT PRIMARY KEY, namespace TEXT NOT NULL, race_id TEXT NOT NULL, input_sha TEXT NOT NULL, model_sha TEXT NOT NULL, deadline TEXT NOT NULL, token TEXT NOT NULL, session TEXT NOT NULL, owner_pid INTEGER NOT NULL, owner_process TEXT NOT NULL, state TEXT NOT NULL, reason TEXT, receipt_sha TEXT, commit_metadata BLOB, created_at TEXT NOT NULL, committed_at TEXT, finalized_at TEXT, UNIQUE(namespace,race_id))")
                db.execute("CREATE TABLE IF NOT EXISTS results (revision INTEGER PRIMARY KEY AUTOINCREMENT, race_key TEXT NOT NULL, result_sha TEXT NOT NULL, final INTEGER NOT NULL, available_at TEXT NOT NULL, metadata_raw BLOB NOT NULL, created_at TEXT NOT NULL, UNIQUE(race_key,result_sha), FOREIGN KEY(race_key) REFERENCES races(race_key))")
                db.execute("CREATE TABLE IF NOT EXISTS selections (race_key TEXT NOT NULL, sequence INTEGER NOT NULL, result_sha TEXT NOT NULL, observed_revision INTEGER NOT NULL, metadata_raw BLOB NOT NULL, selected_at TEXT NOT NULL, PRIMARY KEY(race_key,sequence), FOREIGN KEY(race_key,result_sha) REFERENCES results(race_key,result_sha))")
                db.execute("CREATE TABLE IF NOT EXISTS audits (kind TEXT NOT NULL, identity_sha TEXT NOT NULL, report_sha TEXT NOT NULL, receipt_sha TEXT NOT NULL, metadata_raw BLOB NOT NULL, created_at TEXT NOT NULL, PRIMARY KEY(kind,identity_sha,report_sha))")
                db.execute("PRAGMA user_version=5")
                db.execute("INSERT OR IGNORE INTO meta(name,value) VALUES('storage_id',?)", (self._storage_id,))
                _need(db.execute("SELECT value FROM meta WHERE name='storage_id'").fetchone()[0] == self._storage_id,
                      "LEDGER_OWNER_ID_MISMATCH")
                uncertain = False
                for pending in db.execute("SELECT * FROM races WHERE state IN ('RESERVED','STAGING','COMPLETION_PENDING','COMMITTED')").fetchall():
                    owner_dead = _process_identity(pending["owner_pid"]) != pending["owner_process"]
                    incomplete = pending["state"] == "COMMITTED" and owner_dead and not (self.root / "artifacts" / pending["race_key"] / "completion.json").is_file()
                    abandoned = pending["state"] != "COMMITTED" and _process_identity(pending["owner_pid"]) != pending["owner_process"]
                    if incomplete or abandoned:
                        db.execute("UPDATE races SET state='HOLD_UNCERTAIN',reason='RESTART_INCOMPLETE_PERSIST' WHERE race_key=?", (pending["race_key"],))
                        uncertain = True
                expected_results = {Path(row["race_key"]) / (row["result_sha"] + ".raw")
                                    for row in db.execute("SELECT race_key,result_sha FROM results").fetchall()}
                actual_results = {path.relative_to(self.root / "results") for path in (self.root / "results").rglob("*") if path.is_file()}
                _need(actual_results == expected_results, "ORPHAN_OR_MISSING_RESULT_FILES")
                expected_audits = set()
                for row in db.execute("SELECT kind,identity_sha,report_sha FROM audits").fetchall():
                    base = Path(row["kind"]) / row["identity_sha"]
                    expected_audits |= {base / (row["report_sha"] + ".raw"), base / (row["report_sha"] + ".receipt.json")}
                actual_audits = {path.relative_to(self.root / "audits") for path in (self.root / "audits").rglob("*") if path.is_file()}
                _need(actual_audits == expected_audits, "ORPHAN_OR_MISSING_AUDIT_FILES")
            self._fsync_dir(self.root)
            self._session = uuid.uuid4().hex
            self._process = _process_identity(os.getpid())
            _need(self._process is not None, "PROCESS_IDENTITY_UNVERIFIED")
            self._initialized = True
            if uncertain:
                self._durable_stop("RESTART_INCOMPLETE_PERSIST")
            return {"status": "HOLD" if self.is_stopped() else "READY", "storage_id": self._storage_id,
                    "namespace": self.namespace, "reason": "DURABLE_STOP_PRESENT" if self.is_stopped() else None}
        except Exception as exc:
            reason = exc.args[0] if isinstance(exc, _Unsafe) else "INITIALIZE_IO_UNCERTAIN"
            # No write is permitted merely to mark an unowned or symlinked root.
            if self._storage_id is not None:
                self._durable_stop(reason)
            return {"status": "STOP", "reason": _reason(reason), "production_go": False}

    def _ready(self, writes=True):
        _need(self._initialized, "STORE_NOT_INITIALIZED")
        self._safe_root()
        if writes:
            _need(not self._closed, "STORE_SESSION_CLOSED")
            _need(not self.is_stopped(), "DURABLE_STOP_PRESENT")

    def _durable_stop(self, reason):
        try:
            self._safe_root()
            raw = _json({"kind": "DURABLE_STOP", "reason": _reason(reason),
                         "storage_id": self._storage_id, "namespace": self.namespace})
            try:
                self._exclusive(self.root / "STOP.json", raw)
            except FileExistsError:
                pass  # First STOP remains immutable; there is no clear operation.
            return True
        except Exception:
            return False

    def stop(self, reason="OPERATOR_STOP"):
        try:
            self._ready(writes=False)
            durable = self._durable_stop(reason)
            return {"status": "STOPPED" if durable else "STOP_UNCERTAIN", "reason": _reason(reason),
                    "durable": durable, "production_go": False}
        except Exception:
            return {"status": "STOP_UNCERTAIN", "reason": "STORE_NOT_READY", "durable": False}

    def is_stopped(self):
        if not self._initialized:
            return True
        try:
            self._safe_root()
            return (self.root / "STOP.json").exists()
        except Exception:
            return True

    def bind_context(self, context_sha256):
        """Pin approved code/config/storage binding once; no reset/migration API."""
        try:
            self._ready()
            _need(isinstance(context_sha256, str) and _HEX.fullmatch(context_sha256), "CONTEXT_HASH_INVALID")
            with self._db() as db:
                row = db.execute("SELECT value FROM meta WHERE name='context_sha256'").fetchone()
                if row is not None:
                    _need(row[0] == context_sha256, "CONTEXT_IDENTITY_CHANGED")
                else:
                    db.execute("INSERT INTO meta(name,value) VALUES('context_sha256',?)", (context_sha256,))
            return {"status": "CONTEXT_PINNED", "context_sha256": context_sha256,
                    "storage_id": self._storage_id}
        except Exception as exc:
            reason = exc.args[0] if isinstance(exc, _Unsafe) else "CONTEXT_WRITE_UNCERTAIN"
            if self._initialized:
                self._durable_stop(reason)
            return {"status": "HOLD", "reason": _reason(reason)}

    def _key(self, race_id):
        _need(isinstance(race_id, str) and _ID.fullmatch(race_id), "RACE_ID_INVALID")
        return _digest((self.namespace + "\0" + race_id).encode("ascii"))

    def reserve(self, race_id, input_sha256, model_sha256, deadline):
        try:
            self._ready()
            key = self._key(race_id)
            _need(isinstance(input_sha256, str) and _HEX.fullmatch(input_sha256)
                  and isinstance(model_sha256, str) and _HEX.fullmatch(model_sha256), "RESERVATION_HASH_INVALID")
            end = _timestamp(deadline)
            now = self._now()
            conflict = False
            with self._db() as db:
                row = db.execute("SELECT * FROM races WHERE race_key=?", (key,)).fetchone()
                if row is not None:
                    if row["input_sha"] != input_sha256 or _timestamp(row["deadline"]) != end:
                        conflict = True
                        answer = {"status": "CONFLICT", "key": key, "reason": "RACE_INPUT_OR_DEADLINE_CHANGED"}
                    elif row["state"] == "COMMITTED":
                        if not (self.root / "artifacts" / key / "completion.json").is_file():
                            answer = {"status": "HOLD", "key": key, "reason": "COMMIT_COMPLETION_PENDING_NO_REPLAY"}
                        else:
                            answer = {"status": "DUPLICATE", "key": key, "reason": "RACE_ALREADY_COMMITTED_NO_REPLAY"}
                    else:
                        answer = {"status": "HOLD", "key": key, "reason": "EXISTING_RESERVATION_NO_REPLAY"}
                else:
                    now = self._now()
                    _need(now < end, "DEADLINE_ALREADY_PASSED")
                    token = uuid.uuid4().hex
                    db.execute("INSERT INTO races(race_key,namespace,race_id,input_sha,model_sha,deadline,token,session,owner_pid,owner_process,state,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                               (key, self.namespace, race_id, input_sha256, model_sha256, deadline,
                                token, self._session, os.getpid(), self._process, "RESERVED", now.isoformat()))
                    answer = {"status": "RESERVED", "key": key, "race_id": race_id, "token": token,
                              "session": self._session, "storage_id": self._storage_id}
            if conflict:
                self._durable_stop("RACE_INPUT_OR_DEADLINE_CHANGED")
            if answer["status"] == "DUPLICATE":
                check = self.readback(race_id)
                if check["status"] != "COMMITTED":
                    return {"status": "HOLD", "key": key, "reason": "DUPLICATE_READBACK_FAILED"}
                answer["receipt"] = check["receipt"]
            return answer
        except Exception as exc:
            if self._initialized and not isinstance(exc, _Unsafe):
                self._durable_stop("RESERVATION_IO_UNCERTAIN")
            return {"status": "HOLD", "reason": _reason(exc.args[0] if isinstance(exc, _Unsafe) else "RESERVATION_IO_UNCERTAIN")}

    def _reservation_row(self, db, reservation, allow_committed_duplicate=False):
        _need(isinstance(reservation, dict), "RESERVATION_INVALID")
        key = reservation.get("key")
        _need(isinstance(key, str) and _HEX.fullmatch(key), "RESERVATION_INVALID")
        row = db.execute("SELECT * FROM races WHERE race_key=?", (key,)).fetchone()
        _need(row is not None and row["namespace"] == self.namespace, "RESERVATION_NOT_FOUND")
        session_ok = (reservation.get("session") == row["session"] if allow_committed_duplicate and row["state"] == "COMMITTED"
                      else reservation.get("session") == self._session and row["session"] == self._session)
        _need(reservation.get("token") == row["token"] and session_ok
              and reservation.get("storage_id") == self._storage_id,
              "RESERVATION_SESSION_OR_TOKEN_MISMATCH")
        return row

    def _hold(self, reservation, reason):
        try:
            with self._db() as db:
                if isinstance(reservation, dict) and isinstance(reservation.get("key"), str):
                    db.execute("UPDATE races SET state='HOLD_UNCERTAIN',reason=? WHERE race_key=?",
                               (_reason(reason), reservation["key"]))
        except Exception:
            pass
        durable = self._durable_stop(reason) if self._initialized else False
        return {"status": "HOLD_UNCERTAIN", "reason": _reason(reason), "durable_stop": durable,
                "artifacts_preserved": True, "production_go": False}

    def mark_hold(self, reservation, reason="OPERATOR_HOLD"):
        return self._hold(reservation, reason)

    def commit(self, reservation, input_raw, forecast_raw, metadata):
        claimed = False
        committed_existing = False
        try:
            self._ready()
            _need(isinstance(input_raw, bytes) and isinstance(forecast_raw, bytes), "RAW_BYTES_REQUIRED")
            _need(isinstance(metadata, dict), "COMMIT_METADATA_REQUIRED")
            generated = _timestamp(metadata.get("generated_at"))
            with self._db() as db:
                row = self._reservation_row(db, reservation, allow_committed_duplicate=True)
                committed_existing = row["state"] == "COMMITTED"
                if not committed_existing:
                    _need(row["state"] == "RESERVED", "RESERVATION_NOT_WRITABLE")
                    _need(_digest(input_raw) == row["input_sha"], "RAW_INPUT_HASH_MISMATCH")
                    deadline = _timestamp(row["deadline"])
                    now = self._now()
                    _need(generated <= now < deadline and generated < deadline, "GENERATION_OR_COMMIT_LATE")
                    db.execute("UPDATE races SET state='STAGING' WHERE race_key=?", (row["race_key"],))
                    claimed = True
                snapshot = dict(row)
            if committed_existing:
                prior = self.readback(snapshot["race_id"])
                _need(prior["status"] == "COMMITTED" and prior["input_raw"] == input_raw
                      and prior["forecast_raw"] == forecast_raw
                      and prior["receipt"]["metadata_sha256"] == _digest(_json(metadata)),
                      "COMMITTED_PAYLOAD_CONFLICT")
                return {"status": "DUPLICATE", "key": snapshot["race_key"], "receipt": prior["receipt"],
                        "receipt_sha256": prior["receipt_sha256"], "local_integrity": "MATCHED"}
            self._fault("commit_after_claim")
            self._ready()
            directory = self.root / "artifacts" / snapshot["race_key"]
            directory.mkdir(mode=0o700)  # Exclusive: preexisting means ambiguity.
            self._fsync_dir(directory.parent)
            self._exclusive(directory / "input.raw", input_raw)
            self._fault("commit_after_input")
            self._ready()
            self._exclusive(directory / "forecast.raw", forecast_raw)
            self._fault("commit_after_forecast")
            self._ready()
            persisted = self._now()
            _need(generated <= persisted < deadline, "DEADLINE_DURING_PERSIST")
            receipt = {"kind": "IMMUTABLE_FORECAST_RECEIPT_V005", "namespace": self.namespace,
                       "storage_id": self._storage_id, "race_id": snapshot["race_id"],
                       "key": snapshot["race_key"], "input_sha256": _digest(input_raw),
                       "input_bytes": len(input_raw), "forecast_sha256": _digest(forecast_raw),
                       "forecast_bytes": len(forecast_raw), "model_sha256": snapshot["model_sha"],
                       "generated_at": generated.isoformat(), "persist_observed_at": persisted.isoformat(),
                       "deadline": snapshot["deadline"], "metadata_sha256": _digest(_json(metadata)),
                       "validity": "REQUIRES_COMMITTED_LEDGER_AND_READBACK", "external_authenticity": "UNVERIFIED"}
            receipt_raw = _json(receipt)
            self._exclusive(directory / "receipt.json", receipt_raw)
            self._fault("commit_after_receipt")
            _need(self._now() < deadline, "DEADLINE_AFTER_RECEIPT")
            self._fault("commit_before_ledger")
            with self._db() as db:
                current = self._reservation_row(db, reservation)
                _need(current["state"] == "STAGING", "COMMIT_STATE_CHANGED")
                _need(not self.is_stopped(), "DURABLE_STOP_PRESENT")
                completed = self._now()
                _need(persisted <= completed < deadline, "CLOCK_OR_DEADLINE_BEFORE_LEDGER")
                db.execute("UPDATE races SET state='COMPLETION_PENDING',receipt_sha=?,committed_at=?,commit_metadata=? WHERE race_key=?",
                           (_digest(receipt_raw), completed.isoformat(), _json(metadata), snapshot["race_key"]))
            self._fault("commit_after_ledger")
            _need(self._now() < deadline, "DEADLINE_AFTER_LEDGER")
            completion = {"receipt_sha256": _digest(receipt_raw),
                          "finished_observed_at": self._now().isoformat()}
            _need(completed <= _timestamp(completion["finished_observed_at"]) < deadline, "CLOCK_OR_DEADLINE_BEFORE_COMPLETION")
            self._ready()
            self._exclusive(directory / "completion.json", _json(completion))
            _need(_timestamp(completion["finished_observed_at"]) <= self._now() < deadline, "CLOCK_OR_DEADLINE_AFTER_COMPLETION")
            # The public COMMITTED state is exposed only after completion bytes
            # are fully fsynced/read back, preventing a duplicate reader from
            # seeing a just-created but still empty completion marker.
            with self._db() as db:
                current = self._reservation_row(db, reservation)
                _need(current["state"] == "COMPLETION_PENDING", "COMPLETION_STATE_CHANGED")
                self._ready()
                finalized = self._now()
                _need(_timestamp(completion["finished_observed_at"]) <= finalized < deadline,
                      "CLOCK_OR_DEADLINE_AT_FINALIZATION")
                db.execute("UPDATE races SET state='COMMITTED',finalized_at=? WHERE race_key=?",
                           (finalized.isoformat(), snapshot["race_key"]))
            _need(finalized <= self._now() < deadline, "CLOCK_OR_DEADLINE_AFTER_FINALIZATION")
            verified = self.readback(snapshot["race_id"])
            _need(verified["status"] == "COMMITTED", "FINAL_READBACK_FAILED")
            _need(_timestamp(completion["finished_observed_at"]) <= self._now() < deadline, "CLOCK_OR_DEADLINE_AFTER_READBACK")
            return {"status": "COMMITTED", "key": snapshot["race_key"], "receipt": receipt,
                    "receipt_sha256": _digest(receipt_raw), "local_integrity": "MATCHED",
                    "production_go": False}
        except Exception as exc:
            reason = exc.args[0] if isinstance(exc, _Unsafe) else "COMMIT_IO_UNCERTAIN"
            if committed_existing:
                self._durable_stop(reason)
                return {"status": "CONFLICT", "reason": _reason(reason), "artifacts_preserved": True}
            # Once reserved, even rejected commit attempts cannot become replay.
            if claimed or self._initialized:
                return self._hold(reservation, reason)
            return {"status": "HOLD", "reason": _reason(reason)}

    def readback(self, race_id):
        try:
            self._ready(writes=False)
            key = self._key(race_id)
            with self._db() as db:
                row = db.execute("SELECT * FROM races WHERE race_key=?", (key,)).fetchone()
                _need(row is not None, "RACE_NOT_FOUND")
                snapshot = dict(row)
            if snapshot["state"] != "COMMITTED":
                return {"status": "HOLD", "reason": snapshot["reason"] or "RACE_NOT_COMMITTED",
                        "state": snapshot["state"], "artifacts_preserved": True}
            directory = self.root / "artifacts" / key
            receipt_raw = (directory / "receipt.json").read_bytes()
            receipt = _parse(receipt_raw)
            completion = _parse((directory / "completion.json").read_bytes())
            input_raw, forecast_raw = (directory / "input.raw").read_bytes(), (directory / "forecast.raw").read_bytes()
            _need(_digest(receipt_raw) == snapshot["receipt_sha"], "RECEIPT_HASH_MISMATCH")
            _need(receipt.get("key") == key and receipt.get("storage_id") == self._storage_id
                  and receipt.get("race_id") == race_id and receipt.get("namespace") == self.namespace,
                  "RECEIPT_IDENTITY_MISMATCH")
            _need(_digest(input_raw) == snapshot["input_sha"] == receipt.get("input_sha256")
                  and len(input_raw) == receipt.get("input_bytes"), "INPUT_READBACK_MISMATCH")
            _need(_digest(forecast_raw) == receipt.get("forecast_sha256")
                  and len(forecast_raw) == receipt.get("forecast_bytes"), "FORECAST_READBACK_MISMATCH")
            _need(_timestamp(snapshot["committed_at"]) < _timestamp(snapshot["deadline"]), "COMMITTED_TIME_LATE")
            _need(_timestamp(receipt.get("generated_at")) <= _timestamp(receipt.get("persist_observed_at"))
                  <= _timestamp(snapshot["committed_at"]), "RECEIPT_CLOCK_CHAIN_INVALID")
            _need(snapshot["commit_metadata"] is not None
                  and _digest(bytes(snapshot["commit_metadata"])) == receipt.get("metadata_sha256"), "COMMIT_METADATA_READBACK_MISMATCH")
            _need(completion.get("receipt_sha256") == snapshot["receipt_sha"]
                  and _timestamp(snapshot["committed_at"]) <= _timestamp(completion.get("finished_observed_at"))
                  <= _timestamp(snapshot["finalized_at"]) < _timestamp(snapshot["deadline"]), "COMPLETION_READBACK_MISMATCH")
            return {"status": "COMMITTED", "receipt": receipt, "input_raw": input_raw,
                    "forecast_raw": forecast_raw, "receipt_sha256": snapshot["receipt_sha"],
                    "metadata": _parse(bytes(snapshot["commit_metadata"])),
                    "local_integrity": "MATCHED", "stopped": self.is_stopped()}
        except Exception as exc:
            reason = exc.args[0] if isinstance(exc, _Unsafe) else "READBACK_IO_UNCERTAIN"
            if self._initialized and reason != "RACE_NOT_FOUND":
                self._durable_stop(reason)
            return {"status": "HOLD", "reason": _reason(reason), "local_integrity": "UNVERIFIED"}

    def list_forecasts(self):
        """Local ledger scope only; never proof of complete official schedule."""
        try:
            self._ready(writes=False)
            with self._db() as db:
                rows = db.execute("SELECT race_id,state,deadline FROM races WHERE namespace=? ORDER BY race_id", (self.namespace,)).fetchall()
            return {"status": "FORECASTS_LISTED", "forecasts": [dict(row) for row in rows],
                    "official_schedule_completeness": "UNVERIFIED"}
        except Exception:
            return {"status": "HOLD", "reason": "FORECAST_LIST_UNCERTAIN"}

    def save_result(self, race_id, raw_result, metadata):
        writing = False
        try:
            self._ready()
            key = self._key(race_id)
            _need(isinstance(raw_result, bytes) and isinstance(metadata, dict), "RESULT_BYTES_AND_METADATA_REQUIRED")
            result = _parse(raw_result)
            _need(isinstance(result, dict) and result.get("race_id") == race_id, "RESULT_RACE_ID_MISMATCH")
            _need(type(result.get("final")) is bool, "RESULT_FINAL_FLAG_REQUIRED")
            available = _timestamp(result.get("available_at"))
            for field in ("race_id", "final", "available_at"):
                if field in metadata:
                    _need(metadata[field] == result[field], "RESULT_METADATA_BINDING")
            digest = _digest(raw_result)
            metadata_raw = _json(metadata)
            with self._db() as db:
                race = db.execute("SELECT * FROM races WHERE race_key=?", (key,)).fetchone()
                _need(race is not None and race["state"] == "COMMITTED", "RESULT_FORECAST_NOT_COMMITTED")
                _need(available <= self._now(), "RESULT_AVAILABLE_IN_FUTURE")
                if result["final"]:
                    _need(available >= _timestamp(race["deadline"]), "RESULT_AVAILABLE_BEFORE_DEADLINE")
                prior = db.execute("SELECT * FROM results WHERE race_key=? AND result_sha=?", (key, digest)).fetchone()
                if prior is not None:
                    _need(bytes(prior["metadata_raw"]) == metadata_raw, "RESULT_DUPLICATE_METADATA_CHANGED")
                    duplicate = True
                else:
                    duplicate = False
                    directory = self.root / "results" / key
                    directory.mkdir(mode=0o700, exist_ok=True)
                    self._fsync_dir(directory.parent)
                    writing = True
                    self._exclusive(directory / (digest + ".raw"), raw_result)
                    self._fault("result_after_file")
                    self._ready()
                    db.execute("INSERT INTO results(race_key,result_sha,final,available_at,metadata_raw,created_at) VALUES(?,?,?,?,?,?)",
                               (key, digest, int(result["final"]), result["available_at"], metadata_raw, self._now().isoformat()))
            self._fault("result_after_ledger")
            check = self.read_result(race_id, digest)
            _need(check["status"] == "RESULT_READ", "RESULT_FINAL_READBACK_FAILED")
            return {"status": "RESULT_DUPLICATE" if duplicate else "RESULT_SAVED", "result_sha256": digest,
                    "bytes": len(raw_result), "final": result["final"], "selection_required": True,
                    "production_go": False}
        except Exception as exc:
            reason = exc.args[0] if isinstance(exc, _Unsafe) else "RESULT_IO_UNCERTAIN"
            if self._initialized:
                self._durable_stop(reason)
            return {"status": "HOLD_UNCERTAIN" if writing else "HOLD", "reason": _reason(reason),
                    "artifacts_preserved": True}

    def list_results(self, race_id):
        try:
            self._ready(writes=False)
            key = self._key(race_id)
            with self._db() as db:
                rows = db.execute("SELECT rowid AS revision,result_sha,final,available_at,created_at FROM results WHERE race_key=? ORDER BY rowid", (key,)).fetchall()
                selected = db.execute("SELECT result_sha,sequence,observed_revision FROM selections WHERE race_key=? ORDER BY sequence DESC LIMIT 1", (key,)).fetchone()
            results = [{"result_sha256": row["result_sha"], "final": bool(row["final"]),
                        "available_at": row["available_at"], "recorded_at": row["created_at"],
                        "revision": row["revision"]} for row in rows]
            return {"status": "RESULTS_LISTED", "results": results,
                    "final_count": sum(row["final"] for row in results),
                    "selected_sha256": selected["result_sha"] if selected else None,
                    "selection_sequence": selected["sequence"] if selected else None,
                    "selection_observed_revision": selected["observed_revision"] if selected else None,
                    "ambiguity": "MULTIPLE_FINAL_VERSIONS_REQUIRE_EXPLICIT_SELECTION" if sum(row["final"] for row in results) > 1 else None}
        except Exception:
            return {"status": "HOLD", "reason": "RESULT_LIST_UNCERTAIN"}

    def read_result(self, race_id, result_sha256):
        try:
            self._ready(writes=False)
            key = self._key(race_id)
            _need(isinstance(result_sha256, str) and _HEX.fullmatch(result_sha256), "RESULT_HASH_INVALID")
            with self._db() as db:
                row = db.execute("SELECT * FROM results WHERE race_key=? AND result_sha=?", (key, result_sha256)).fetchone()
                _need(row is not None, "RESULT_VERSION_NOT_FOUND")
                snapshot = dict(row)
            raw = (self.root / "results" / key / (result_sha256 + ".raw")).read_bytes()
            _need(_digest(raw) == result_sha256, "RESULT_READBACK_HASH_MISMATCH")
            return {"status": "RESULT_READ", "raw_result": raw, "metadata": _parse(bytes(snapshot["metadata_raw"])),
                    "result_sha256": result_sha256, "final": bool(snapshot["final"]), "local_integrity": "MATCHED"}
        except Exception as exc:
            reason = exc.args[0] if isinstance(exc, _Unsafe) else "RESULT_READ_UNCERTAIN"
            if self._initialized and reason not in ("RESULT_VERSION_NOT_FOUND", "RESULT_HASH_INVALID"):
                self._durable_stop(reason)
            return {"status": "HOLD", "reason": _reason(reason)}

    def select_result(self, race_id, result_sha256, selection_metadata):
        try:
            self._ready()
            key = self._key(race_id)
            _need(isinstance(selection_metadata, dict) and selection_metadata.get("explicit") is True,
                  "EXPLICIT_RESULT_SELECTION_REQUIRED")
            _need(isinstance(selection_metadata.get("selection_id"), str)
                  and _ID.fullmatch(selection_metadata["selection_id"]), "SELECTION_ID_REQUIRED")
            checked = self.read_result(race_id, result_sha256)
            _need(checked["status"] == "RESULT_READ" and checked["final"] is True, "SELECTED_RESULT_NOT_FINAL_OR_VERIFIED")
            metadata_raw = _json(selection_metadata)
            with self._db() as db:
                previous = db.execute("SELECT * FROM selections WHERE race_key=? ORDER BY sequence DESC LIMIT 1", (key,)).fetchone()
                if previous is not None and previous["result_sha"] == result_sha256 and bytes(previous["metadata_raw"]) == metadata_raw:
                    sequence = previous["sequence"]
                else:
                    sequence = previous["sequence"] + 1 if previous else 1
                    frontier = db.execute("SELECT MAX(rowid) FROM results WHERE race_key=?", (key,)).fetchone()[0]
                    db.execute("INSERT INTO selections(race_key,sequence,result_sha,observed_revision,metadata_raw,selected_at) VALUES(?,?,?,?,?,?)",
                               (key, sequence, result_sha256, frontier, metadata_raw, self._now().isoformat()))
            self._fault("select_after_ledger")
            return {"status": "RESULT_SELECTED", "result_sha256": result_sha256,
                    "selection_sequence": sequence, "external_authority": "UNVERIFIED_OPERATOR_ASSERTION"}
        except Exception as exc:
            reason = exc.args[0] if isinstance(exc, _Unsafe) else "RESULT_SELECTION_UNCERTAIN"
            if self._initialized:
                self._durable_stop(reason)
            return {"status": "HOLD", "reason": _reason(reason)}

    def read_selected_result(self, race_id):
        listing = self.list_results(race_id)
        if listing["status"] != "RESULTS_LISTED" or listing["selected_sha256"] is None:
            return {"status": "HOLD", "reason": "EXPLICIT_FINAL_RESULT_NOT_SELECTED"}
        # A newer final version must never silently keep an earlier settlement.
        selected = listing["selected_sha256"]
        finals = [row for row in listing["results"] if row["final"]]
        if any(row["revision"] > listing["selection_observed_revision"] for row in finals):
            return {"status": "HOLD", "reason": "NEWER_FINAL_REQUIRES_EXPLICIT_SELECTION"}
        answer = self.read_result(race_id, selected)
        answer["selection_sequence"] = listing["selection_sequence"]
        return answer

    def close(self):
        """Normal shutdown never silently abandons a usable reservation."""
        try:
            self._ready(writes=False)
            with self._db() as db:
                rows = db.execute("SELECT race_key FROM races WHERE session=? AND state IN ('RESERVED','STAGING','COMPLETION_PENDING')", (self._session,)).fetchall()
                for row in rows:
                    db.execute("UPDATE races SET state='HOLD_UNCERTAIN',reason='SHUTDOWN_WITH_RESERVATION' WHERE race_key=?", (row["race_key"],))
            if rows:
                self._durable_stop("SHUTDOWN_WITH_RESERVATION")
            self._closed = True
            return {"status": "HOLD" if rows else "CLOSED", "pending_n": len(rows)}
        except Exception:
            self._durable_stop("SHUTDOWN_UNCERTAIN")
            return {"status": "HOLD", "reason": "SHUTDOWN_UNCERTAIN"}

    def save_audit_report(self, kind, identity, raw_bytes, metadata=None):
        """Append-only daily/operations reports, never a forecast replacement."""
        writing = False
        try:
            self._ready()
            _need(kind in ("DAILY_SETTLEMENT", "OPERATIONS_AUDIT"), "AUDIT_KIND_INVALID")
            _need(isinstance(identity, str) and _ID.fullmatch(identity), "AUDIT_IDENTITY_INVALID")
            _need(isinstance(raw_bytes, bytes), "AUDIT_RAW_BYTES_REQUIRED")
            metadata = {} if metadata is None else metadata
            _need(isinstance(metadata, dict), "AUDIT_METADATA_REQUIRED")
            if kind == "DAILY_SETTLEMENT":
                selected_results = metadata.get("selected_results")
                _need(isinstance(selected_results, dict) and selected_results, "AUDIT_RESULT_SELECTION_MAPPING_REQUIRED")
                for race_id, result_sha in selected_results.items():
                    selected = self.read_selected_result(race_id)
                    _need(selected["status"] == "RESULT_READ" and selected["result_sha256"] == result_sha,
                          "AUDIT_RESULT_SELECTION_MISMATCH")
            identity_sha, report_sha = _digest(identity.encode("ascii")), _digest(raw_bytes)
            metadata_raw = _json(metadata)
            with self._db() as db:
                if kind == "DAILY_SETTLEMENT":
                    for race_id, result_sha in metadata["selected_results"].items():
                        race_key = self._key(race_id)
                        pin = db.execute("SELECT * FROM selections WHERE race_key=? ORDER BY sequence DESC LIMIT 1", (race_key,)).fetchone()
                        newer_final = db.execute("SELECT MAX(rowid) FROM results WHERE race_key=? AND final=1", (race_key,)).fetchone()[0]
                        _need(pin is not None and pin["result_sha"] == result_sha
                              and newer_final <= pin["observed_revision"], "AUDIT_SELECTION_CHANGED_DURING_SAVE")
                previous = db.execute("SELECT * FROM audits WHERE kind=? AND identity_sha=? AND report_sha=?",
                                      (kind, identity_sha, report_sha)).fetchone()
                if previous is not None:
                    _need(bytes(previous["metadata_raw"]) == metadata_raw, "AUDIT_DUPLICATE_METADATA_CHANGED")
                    duplicate = True
                else:
                    duplicate = False
                    directory = self.root / "audits" / kind / identity_sha
                    directory.parent.mkdir(mode=0o700, exist_ok=True)
                    self._fsync_dir(self.root / "audits")
                    directory.mkdir(mode=0o700, exist_ok=True)
                    self._fsync_dir(directory.parent)
                    receipt = {"kind": kind, "identity_sha256": identity_sha, "report_sha256": report_sha,
                               "report_bytes": len(raw_bytes), "metadata_sha256": _digest(metadata_raw),
                               "selected_results": metadata.get("selected_results"),
                               "storage_id": self._storage_id, "namespace": self.namespace,
                               "recorded_at": self._now().isoformat(), "external_authenticity": "UNVERIFIED"}
                    receipt_raw = _json(receipt)
                    writing = True
                    self._exclusive(directory / (report_sha + ".raw"), raw_bytes)
                    self._fault("audit_after_file")
                    self._ready()
                    self._exclusive(directory / (report_sha + ".receipt.json"), receipt_raw)
                    db.execute("INSERT INTO audits(kind,identity_sha,report_sha,receipt_sha,metadata_raw,created_at) VALUES(?,?,?,?,?,?)",
                               (kind, identity_sha, report_sha, _digest(receipt_raw), metadata_raw, receipt["recorded_at"]))
            self._fault("audit_after_ledger")
            checked = self.read_audit_report(kind, identity, report_sha)
            _need(checked["status"] == "AUDIT_READ", "AUDIT_FINAL_READBACK_FAILED")
            return {"status": "AUDIT_DUPLICATE" if duplicate else "AUDIT_SAVED", "report_sha256": report_sha,
                    "receipt_sha256": checked["receipt_sha256"], "bytes": len(raw_bytes),
                    "kind": kind, "production_go": False}
        except Exception as exc:
            reason = exc.args[0] if isinstance(exc, _Unsafe) else "AUDIT_IO_UNCERTAIN"
            if self._initialized:
                self._durable_stop(reason)
            return {"status": "HOLD_UNCERTAIN" if writing else "HOLD", "reason": _reason(reason),
                    "artifacts_preserved": True}

    def read_audit_report(self, kind, identity, report_sha256):
        try:
            self._ready(writes=False)
            _need(kind in ("DAILY_SETTLEMENT", "OPERATIONS_AUDIT"), "AUDIT_KIND_INVALID")
            _need(isinstance(identity, str) and _ID.fullmatch(identity), "AUDIT_IDENTITY_INVALID")
            _need(isinstance(report_sha256, str) and _HEX.fullmatch(report_sha256), "AUDIT_HASH_INVALID")
            identity_sha = _digest(identity.encode("ascii"))
            with self._db() as db:
                row = db.execute("SELECT * FROM audits WHERE kind=? AND identity_sha=? AND report_sha=?",
                                 (kind, identity_sha, report_sha256)).fetchone()
                _need(row is not None, "AUDIT_VERSION_NOT_FOUND")
                snapshot = dict(row)
            directory = self.root / "audits" / kind / identity_sha
            raw = (directory / (report_sha256 + ".raw")).read_bytes()
            receipt_raw = (directory / (report_sha256 + ".receipt.json")).read_bytes()
            receipt = _parse(receipt_raw)
            _need(_digest(raw) == report_sha256 and _digest(receipt_raw) == snapshot["receipt_sha"], "AUDIT_READBACK_HASH_MISMATCH")
            _need(receipt.get("report_sha256") == report_sha256 and receipt.get("report_bytes") == len(raw)
                  and receipt.get("identity_sha256") == identity_sha and receipt.get("kind") == kind
                  and receipt.get("metadata_sha256") == _digest(bytes(snapshot["metadata_raw"]))
                  and receipt.get("storage_id") == self._storage_id, "AUDIT_RECEIPT_BINDING_MISMATCH")
            return {"status": "AUDIT_READ", "raw_report": raw, "receipt": receipt,
                    "metadata": _parse(bytes(snapshot["metadata_raw"])), "report_sha256": report_sha256,
                    "receipt_sha256": snapshot["receipt_sha"], "local_integrity": "MATCHED"}
        except Exception as exc:
            reason = exc.args[0] if isinstance(exc, _Unsafe) else "AUDIT_READ_UNCERTAIN"
            if self._initialized and reason not in ("AUDIT_VERSION_NOT_FOUND", "AUDIT_HASH_INVALID", "AUDIT_KIND_INVALID", "AUDIT_IDENTITY_INVALID"):
                self._durable_stop(reason)
            return {"status": "HOLD", "reason": _reason(reason)}
