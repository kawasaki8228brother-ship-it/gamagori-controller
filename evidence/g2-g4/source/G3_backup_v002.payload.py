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

# HQ13 permits SQLite's normal read-lock/read-mark updates to existing SHM only.
ALLOW_EXISTING_SHM_READMARKS = True

def watch_directory(root):
    import ctypes
    library=ctypes.CDLL(None,use_errno=True)
    fd=library.inotify_init1(os.O_NONBLOCK|os.O_CLOEXEC)
    if fd<0:raise Stop("WATCH_UNAVAILABLE")
    # CREATE/DELETE/MOVE/MODIFY/ATTRIB and directory identity events; no file.
    mask=0x100|0x200|0x40|0x80|0x2|0x4|0x400|0x800
    if library.inotify_add_watch(fd,os.fsencode(root),mask)<0:
        os.close(fd);raise Stop("WATCH_UNAVAILABLE")
    return fd

def check_events(fd,destination,source):
    import struct
    output_names={destination.name+s for s in ("","-journal","-wal","-shm")}
    source_names={source.name+s for s in ("","-wal","-shm")}
    count=0
    while True:
        try:data=os.read(fd,65536)
        except BlockingIOError:break
        if not data:break
        offset=0
        while offset<len(data):
            if len(data)-offset<16:raise Stop("WATCH_FORMAT")
            _,mask,_,size=struct.unpack_from("iIII",data,offset)
            if offset+16+size>len(data):raise Stop("WATCH_FORMAT")
            name=os.fsdecode(data[offset+16:offset+16+size].split(b"\0")[0]);offset+=16+size;count+=1
            if mask&(0x4000|0x8000|0x400|0x800):raise Stop("WATCH_LOST_OR_ROOT_CHANGED")
            if mask&(0x100|0x200|0x40|0x80) and name not in output_names:raise Stop("UNEXPECTED_FILE_EVENT")
            if mask&(0x2|0x4) and name not in output_names|source_names:raise Stop("UNEXPECTED_FILE_EVENT")
    return count

def g3(root=Path("/var/data"),at=None,deadline_seconds=15,free_override=None,copy_fn=None):
    global _write_target
    if sqlite3.sqlite_version!="3.50.4" or sys.platform!="linux":raise Stop("UNTESTED_SQLITE_PLATFORM")
    root=Path(root).absolute();at=at or now_jst()
    destination=root/("gamagori_shadow.pre-certifi-97640c8c."+at.strftime("%Y%m%d")+".sqlite3")
    # lexists includes dangling symlinks. Existing destination: no source open.
    if os.path.lexists(destination): raise Stop("DEST_EXISTS")
    for suffix in ("-journal","-wal","-shm"):
        if os.path.lexists(str(destination)+suffix):raise Stop("DEST_AUX_EXISTS")
    source,sizes,wal=checked_source(root)
    if wal and not ALLOW_EXISTING_SHM_READMARKS: raise Stop("WAL_READMARK_POLICY_UNRESOLVED")
    free=(free_override if free_override is not None else __import__("shutil").disk_usage(root).free)
    required=2*(sizes["db"]+sizes["wal"])+64*1024*1024
    if free<required:raise Stop("SPACE")
    baseline_names=set(os.listdir(root))
    source_ids={p:(p.stat().st_dev,p.stat().st_ino) for p in (source,Path(str(source)+"-wal"),Path(str(source)+"-shm")) if p.exists()}
    deadline=time.monotonic()+deadline_seconds
    source_connection=None;target=None;fd=None;watch=None;created=False;phase="source"
    try:
        watch=watch_directory(root)
        source_connection=ro_connect(source)
        deadline_progress(source_connection,deadline)
        source_connection.execute("BEGIN")
        integrity(source_connection)
        tables=("race_states","idempotency_keys","shadow_events")
        source_rows={t:source_connection.execute("SELECT COUNT(*) FROM "+t).fetchone()[0] for t in tables}
        check_events(watch,destination,source)
        phase="reserve"
        _write_target=destination
        fd=os.open(destination,os.O_RDWR|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        created=True;identity=os.fstat(fd)
        if not stat.S_ISREG(identity.st_mode):raise Stop("DEST_FILE")
        uri=destination.as_uri()+"?mode=rw";_write_sqlite.add(uri)
        target=sqlite3.connect(uri,uri=True,timeout=2.5,isolation_level=None)
        target.execute("PRAGMA temp_store=MEMORY")
        target.execute("PRAGMA synchronous=FULL")
        phase="backup"
        def progress(status,remaining,total):
            if time.monotonic()>deadline:raise Stop("BACKUP_DEADLINE")
            if __import__("shutil").disk_usage(root).free<16*1024*1024:raise Stop("SPACE_DURING_COPY")
        if copy_fn is None:source_connection.backup(target,pages=64,progress=progress,sleep=0.05)
        else:copy_fn(source_connection,target,progress)
        phase="copy_integrity"
        deadline_progress(target,deadline);integrity(target)
        if {t:target.execute("SELECT COUNT(*) FROM "+t).fetchone()[0] for t in tables}!=source_rows:raise Stop("COPY_ROWS")
        target.close();target=None
        source_connection.execute("ROLLBACK");source_connection.close();source_connection=None
        os.fsync(fd)
        directory_fd=os.open(root,os.O_RDONLY|os.O_DIRECTORY)
        try:os.fsync(directory_fd)
        finally:os.close(directory_fd)
        extra=set(os.listdir(root))-baseline_names
        if extra!={destination.name}:raise Stop("UNEXPECTED_FILES")
        if any(os.path.lexists(str(destination)+s) for s in ("-journal","-wal","-shm")):raise Stop("DEST_AUX_REMAINS")
        for path,original_id in source_ids.items():
            if not path.exists() or (path.stat().st_dev,path.stat().st_ino)!=original_id:raise Stop("SOURCE_IDENTITY")
        current=destination.lstat()
        if (current.st_dev,current.st_ino)!=(identity.st_dev,identity.st_ino):raise Stop("DEST_IDENTITY")
        if current.st_size<512:raise Stop("DEST_SIZE")
        phase="hash"
        os.lseek(fd,0,os.SEEK_SET);digest=hashlib.sha256()
        while True:
            if time.monotonic()>deadline:raise Stop("VERIFY_DEADLINE")
            block=os.read(fd,65536)
            if not block:break
            digest.update(block)
        final=os.fstat(fd)
        if (final.st_size,final.st_mtime_ns)!=(current.st_size,current.st_mtime_ns):raise Stop("DEST_CHANGED_DURING_HASH")
        events=check_events(watch,destination,source)
        if set(os.listdir(root))-baseline_names!={destination.name}:raise Stop("UNEXPECTED_FILES")
        os.close(fd);fd=None
        return [{"free_before":free,"required":required,"source_sizes":sizes},{"backup":destination.name,"bytes":current.st_size,"sha256":digest.hexdigest()},{"r":"BACKUP_VERIFIED","source_mode":"ro","src_integrity":"ok","copy_integrity":"ok","rows":source_rows,"aux_left":0,"events":events,"no_execution_GO":True}]
    except Exception as exc:
        why=exc.why if isinstance(exc,Stop) else type(exc).__name__
        return [{"r":"STOP","phase":phase,"why":why,"created":created,"partial_retained":created}]
    finally:
        if target is not None:target.close()
        if source_connection is not None:source_connection.close()
        if fd is not None:os.close(fd)
        if watch is not None:os.close(watch)
        _write_target=None


if __name__=="__main__": entry('G3_BACKUP_DESIGN',g3)
