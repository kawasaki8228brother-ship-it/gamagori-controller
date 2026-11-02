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

TARGETS=[("WWW","https://www.boatrace.jp/",False),("BARE","https://boatrace.jp/",False),("FALLBACK","https://boatraceopenapi.github.io/",False),("NEGATIVE_1","https://dv-g3b-emudhra.we-have-a-problem.com/",True),("NEGATIVE_2","https://dv-g3b-aaa-emudhra.we-have-a-problem.com/",True)]
ISSUER_CODES=frozenset((2,19,20))

class ScopeBlocked(Exception): pass

def exception_nodes(exc,limit=16,max_depth=8):
    queue=[(exc,0)];seen=set();nodes=[];limited=False
    while queue:
        current,depth=queue.pop(0)
        if current is None or id(current) in seen:continue
        if depth>max_depth or len(nodes)>=limit:
            limited=True;continue
        seen.add(id(current));nodes.append(current)
        queue.extend(((current.__cause__,depth+1),(current.__context__,depth+1)))
    return nodes,limited

def safe_verify_message(value):
    if not isinstance(value,str):return None
    value="".join(c if 32<=ord(c)<=126 else "?" for c in value)
    # Only the real verify_message attribute is accepted. Suppress URL/path-like
    # tokens even if an unusual TLS provider puts them in that attribute.
    value=re.sub(r"\S*(?:://|@)\S*","[REDACTED]",value)
    value=re.sub(r"(?<!\w)/\S+","[REDACTED]",value)
    return value[:100]

def classify_exception(exc):
    import httpx,socket
    nodes,limited=exception_nodes(exc)
    certificates=[e for e in nodes if isinstance(e,ssl.SSLCertVerificationError)]
    code=None;message=None;codes=[]
    for certificate in certificates:
        candidate=getattr(certificate,"verify_code",None)
        codes.append(candidate if type(candidate) is int else None)
    if certificates:
        code=codes[0]
        message=safe_verify_message(getattr(certificates[0],"verify_message",None))
    if any(isinstance(e,httpx.ProxyError) for e in nodes):why="PROXY"
    elif any(isinstance(e,httpx.TimeoutException) for e in nodes):why="TIMEOUT"
    elif any(isinstance(e,socket.gaierror) for e in nodes):why="DNS"
    elif any(isinstance(e,ScopeBlocked) for e in nodes):why="SCOPE"
    elif limited:why="CHAIN_LIMIT"
    elif certificates and len(set(codes))!=1:why="VERIFY_AMBIGUOUS"
    elif certificates and code in ISSUER_CODES:
        return "CERT_REJECTED",code,message,"ISSUER_VERIFY"
    elif certificates:why="VERIFY_OTHER"
    else:why="TRANSPORT_OTHER"
    return "OTHER_FAILURE",code,message,why

def tls_summary(rows,baseline=False):
    expected={name:negative for name,_,negative in TARGETS}
    complete=len(rows)==5 and {r["id"] for r in rows}==set(expected)
    if baseline:
        failed=any(expected.get(r["id"]) is False and r["tls"]=="CERT_REJECTED" for r in rows)
        result="FAIL" if failed else "BASELINE_OBS_EXPECTED" if complete and all(r["tls"]=="CONNECTED" for r in rows) else "UNVERIFIED"
    else:
        failed=any((expected.get(r["id"]) is True and r["tls"]=="CONNECTED") or (expected.get(r["id"]) is False and r["tls"]=="CERT_REJECTED") for r in rows)
        passed=complete and all((r["tls"]=="CERT_REJECTED" and r["verify_code"] in ISSUER_CODES) if expected[r["id"]] else r["tls"]=="CONNECTED" for r in rows)
        result="FAIL" if failed else "TLS_OBS_PASS" if passed else "UNVERIFIED"
    return {"r":result,"mode":"BASELINE" if baseline else "POST","go":False}

async def probe_targets(targets,allowed_origins,client_factory=None,baseline=False):
    import httpx
    current={"http":None}
    def in_scope(url):
        return url.scheme=="https" and not url.username and not url.password and (url.host,url.port or 443) in allowed_origins
    async def gate(request):
        if not in_scope(request.url):raise ScopeBlocked()
    async def observe(response):
        if not in_scope(response.request.url):raise ScopeBlocked()
        if current["http"] is None:current["http"]=response.status_code
    # Preserve HQ12's URLs, order, four communication options and single attempt.
    # The response hook remembers the FIRST target response before any redirect.
    kwargs={"timeout":8.0,"verify":True,"trust_env":True,"follow_redirects":True,
            "event_hooks":{"request":[gate],"response":[observe]}}
    rows=[]
    async with (client_factory or httpx.AsyncClient)(**kwargs) as client:
        for name,url,negative in targets:
            current["http"]=None
            row={"id":name,"tls":"OTHER_FAILURE","http":None,"verify_code":None,"verify_message":None}
            try:
                await client.get(url)
                if current["http"] is None:row["why"]="NO_RESPONSE_OBSERVED"
            except Exception as exc:
                if current["http"] is None:
                    row["tls"],row["verify_code"],row["verify_message"],row["why"]=classify_exception(exc)
            if current["http"] is not None:
                row["tls"]="CONNECTED";row["http"]=current["http"]
            rows.append(row)
    return rows+[tls_summary(rows,baseline)]

def checked_app_timeout():
    try:value=float(os.environ.get("HTTP_TIMEOUT_SECONDS","8"))
    except ValueError:raise Stop("APP_TIMEOUT_UNKNOWN")
    if value!=8.0:raise Stop("APP_TIMEOUT_DIFFERS_FROM_HQ12")
    if "SSLKEYLOGFILE" in os.environ:raise Stop("KEYLOG_ENV_PRESENT")

def run_tls_mode(baseline=False):
    import asyncio
    checked_app_timeout()
    env_count=sum(name in os.environ for name in ENV_NAMES)
    if env_count:return [{"r":"STOP","why":"SSL_PROXY_ENV_PRESENT","env_overrides":env_count,"go":False}]
    gate=baseline_gate() if baseline else g4_env()
    expected="BASELINE_ENV_PASS" if baseline else "ENV_OBS_PASS"
    if gate[-1]["r"]!=expected:return gate+[{"r":"STOP","why":"BASELINE_PREFLIGHT" if baseline else "POST_PREFLIGHT","go":False}]
    from urllib.parse import urlsplit
    origins={(urlsplit(url).hostname,443) for _,url,_ in TARGETS}
    global _network
    _network=True
    observed=asyncio.run(probe_targets(TARGETS,origins,baseline=baseline))
    ca=gate[0] if baseline else gate[1]
    return [{"gate":expected,"ca_sha":ca["ca_sha"],"ca_n":ca["ca_n"],
             "eff_n":ca["eff_n"],"eff_eq":ca["eff_eq"],"env_overrides":0}]+observed

def g4_tls_v003():return run_tls_mode(False)
def g4_baseline_v003():return run_tls_mode(True)

if __name__=="__main__": entry('G4_TLS_V003',g4_tls_v003)
