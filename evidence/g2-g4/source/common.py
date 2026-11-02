import sys, os, ssl, json, hashlib, datetime as dt, time, sqlite3, stat, io, contextlib, re
from pathlib import Path

AUDITOR_SHA = "354940e9a77d2eaf86feaa1c50089db4a0e410cc5f2fdafd6598d66367566b94"
OFFICIAL_SHA = "8598ef5937c5b944d87b6cfa8c29dea10dc6f09781cb73a0c55521c5f6a29373"
REQUIREMENTS_SHA = "dba91fc609884c39b70c1660151e959779d86613fe0ce13c61626506123a2dc7"
CA_SHA = "2ef52ad56b4803e264045c915e55c236cbfa045b84b81efefc218a19eb44bd2b"
HEAD = "97640c8c307fed8eaa19f2557f5057ccade18da1"
STATES = "PENDING DATA_WAIT CLOSING_WINDOW FREEZE_ZONE SAFE_STOP C_EVENT_DONE REOPENED TERMINAL".split()
ENV_NAMES = "SSL_CERT_FILE SSL_CERT_DIR REQUESTS_CA_BUNDLE HTTP_PROXY HTTPS_PROXY ALL_PROXY NO_PROXY".split()
ENV_NAMES += [x.lower() for x in ENV_NAMES]
_read_sqlite, _write_sqlite = set(), set()
_write_target = None
_network = False

class Stop(Exception):
    def __init__(self, why): self.why = why

def audit_guard(event, args):
    blocked = event.startswith("socket.") and not _network
    blocked = blocked or event in {"subprocess.Popen", "os.system", "os.exec", "os.posix_spawn", "os.fork", "os.spawn", "os.mkdir", "os.remove", "os.rename", "os.rmdir", "os.link", "os.symlink", "os.chmod", "os.chown", "os.truncate", "os.utime"}
    if event == "sqlite3.connect":
        blocked = str(args[0]) not in _read_sqlite | _write_sqlite
    if event == "open":
        path, mode, flags = args
        write = (isinstance(mode, str) and any(c in mode for c in "wax+")) or (isinstance(flags, int) and flags & (os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND))
        if write:
            blocked = _write_target is None or not isinstance(path, (str, bytes, os.PathLike)) or Path(os.fsdecode(path)).absolute() != _write_target
        if isinstance(path, (str, bytes, os.PathLike)) and Path(os.fsdecode(path)).name.startswith(".env"):
            blocked = True
    if blocked: raise PermissionError("G_SIDE_EFFECT_BLOCKED")

def frame(rows):
    body = b"".join((json.dumps(row,sort_keys=True,separators=(",",":"),ensure_ascii=True)+"\n").encode("ascii") for row in rows)
    end = "END CERTIFI_AUDIT_V002 lines="+str(len(rows))+" bytes="+str(len(body))+" sha256="+hashlib.sha256(body).hexdigest()+"\n"
    return b"BEGIN CERTIFI_AUDIT_V002\n"+body+end.encode("ascii")

def metadata(kind):
    return {"g":kind,"py":sys.version.split()[0],"ssl":ssl.OPENSSL_VERSION,"sq":sqlite3.sqlite_version}

def entry(kind, fn):
    sys.dont_write_bytecode = True
    sys.addaudithook(audit_guard)
    rows = [metadata(kind)]
    try:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            result = fn()
        rows.extend(result)
    except Stop as exc:
        rows.append({"r":"STOP","why":exc.why})
    except Exception as exc:
        rows.append({"r":"STOP","e":type(exc).__name__})
    sys.stdout.buffer.write(frame(rows));sys.stdout.buffer.flush()

def now_jst(): return dt.datetime.now(dt.timezone(dt.timedelta(hours=9)))

def checked_source(root):
    root = Path(root).absolute()
    if root.is_symlink() or not root.is_dir(): raise Stop("DATA_ROOT")
    source = root / "gamagori_shadow.db"
    try: info = source.lstat()
    except FileNotFoundError: raise Stop("DB_MISSING")
    if not stat.S_ISREG(info.st_mode) or info.st_size < 32: raise Stop("DB_FILE")
    with source.open("rb") as stream: header = stream.read(32)
    if header[:16] != b"SQLite format 3\0": raise Stop("DB_HEADER")
    wal_mode = header[18:20] == b"\x02\x02"
    if not wal_mode and header[18:20] != b"\x01\x01": raise Stop("JOURNAL_UNKNOWN")
    sizes = {"db":info.st_size,"wal":0,"shm":0}
    for name in ("wal","shm"):
        sidecar=Path(str(source)+"-"+name)
        if sidecar.exists():
            s=sidecar.lstat()
            if not stat.S_ISREG(s.st_mode): raise Stop("SIDECAR_FILE")
            sizes[name]=s.st_size
        elif wal_mode: raise Stop("WAL_SIDECAR_MISSING")
    return source, sizes, wal_mode

def ro_connect(path):
    uri=Path(path).resolve().as_uri()+"?mode=ro"
    _read_sqlite.add(uri)
    connection=sqlite3.connect(uri,uri=True,timeout=2.5,isolation_level=None)
    connection.execute("PRAGMA query_only=ON")
    connection.execute("PRAGMA temp_store=MEMORY")
    connection.execute("PRAGMA busy_timeout=2500")
    return connection

def deadline_progress(connection, deadline):
    connection.set_progress_handler(lambda: int(time.monotonic()>deadline),1000)

def integrity(connection):
    if connection.execute("PRAGMA integrity_check").fetchall()!=[("ok",)]: raise Stop("INTEGRITY")
