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
    if sqlite3.sqlite_version!="3.40.1" or sys.platform!="linux":raise Stop("UNTESTED_SQLITE_PLATFORM")
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

if __name__=="__main__": entry("G3_BACKUP_DESIGN",g3)
