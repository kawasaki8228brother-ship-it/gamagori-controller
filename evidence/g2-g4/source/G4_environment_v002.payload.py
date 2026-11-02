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

PINS = "Pygments==2.21.0 annotated-types==0.8.0 anyio==4.15.1 beautifulsoup4==4.14.3 certifi==2026.10.23 h11==0.16.0 httpcore==1.0.9 httpx==0.28.1 idna==3.20 iniconfig==2.3.0 packaging==26.3 pluggy==1.6.0 pydantic==2.13.4 pydantic_core==2.46.4 pytest-asyncio==1.3.0 pytest==9.0.2 soupsieve==2.9.2 typing-inspection==0.4.4 typing_extensions==4.16.0".split()
BAD_ROOTS={"125609aa301da0a249b97a8239cb6a34216f44dcac9f3954b14292f2e8c8608f","86a1ecba089c4a8d3bbe2734c612ba341d813e043cf9e8a862cd5c57a36bbe6b","bc4d809b15189d78db3e1d8cf4f9726a795da1643ca5f1358e1ddb0edc0d7eb3"}

def g4_env(project=None,environ=None,context_factory=None,distributions=None):
    import re,certifi,httpx
    from importlib.metadata import distributions as all_distributions
    from httpx._config import create_ssl_context
    project=Path.cwd() if project is None else Path(project)
    environ=os.environ if environ is None else environ
    normalize=lambda s:re.sub(r"[-_.]+","-",s).lower()
    expected={normalize(p.split("==")[0]):p.split("==")[1] for p in PINS}
    found={};duplicates=0
    for dist in (all_distributions() if distributions is None else distributions):
        name=normalize(dist.metadata["Name"])
        if name in found:duplicates+=1
        found[name]=dist.version
    pip=found.pop("pip",None)
    dep_bad=sum(found.get(k)!=v for k,v in expected.items())+len(set(found)-set(expected))+duplicates
    env_present=[name for name in ENV_NAMES if name in environ]
    req_ok=hashlib.sha256((project/"requirements.txt").read_bytes()).hexdigest()==REQUIREMENTS_SHA
    official_ok=hashlib.sha256((project/"official.py").read_bytes()).hexdigest()==OFFICIAL_SHA
    data=Path(certifi.where()).read_bytes()
    pems=re.findall(br"-----BEGIN CERTIFICATE-----.*?-----END CERTIFICATE-----",data,re.S)
    bundle_fps={hashlib.sha256(ssl.PEM_cert_to_DER_cert(p.decode())).hexdigest() for p in pems}
    context=(context_factory or create_ssl_context)()
    effective={hashlib.sha256(c).hexdigest() for c in context.get_ca_certs(binary_form=True)}
    ca_ok=certifi.__version__=="2026.10.23" and hashlib.sha256(data).hexdigest()==CA_SHA and len(pems)==118 and len(bundle_fps)==118
    effective_ok=context.verify_mode==ssl.CERT_REQUIRED and context.check_hostname and effective==bundle_fps and not(BAD_ROOTS&effective)
    runtime_ok=sys.version_info[:3]==(3,14,3) and httpx.__version__=="0.28.1"
    passed=not dep_bad and len(found)==19 and pip is not None and not env_present and req_ok and official_ok and ca_ok and effective_ok and runtime_ok
    return [{"deps":len(found),"bad":dep_bad,"pip":pip is not None,"env_overrides":len(env_present),"req":req_ok,"app_source":official_ok},{"ca_n":len(pems),"ca_sha":hashlib.sha256(data).hexdigest(),"eff_n":len(effective),"eff_eq":effective_ok},{"r":"ENV_OBS_PASS" if passed else "STOP_ENV","runtime":runtime_ok,"go":False}]


if __name__=="__main__": entry('G4_ENV',g4_env)
