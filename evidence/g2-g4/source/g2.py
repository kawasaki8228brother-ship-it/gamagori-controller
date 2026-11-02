def g2(root=Path("/var/data"), auditor=Path("sqlite_readonly_audit.py"), at=None):
    import importlib.util
    if hashlib.sha256(Path(auditor).read_bytes()).hexdigest()!=AUDITOR_SHA: raise Stop("AUDITOR_HASH")
    source,sizes,wal=checked_source(root)
    _read_sqlite.add(source.resolve().as_uri()+"?mode=ro")
    spec=importlib.util.spec_from_file_location("verified_readonly_auditor",auditor)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    at=at or now_jst()
    class BoundedAuditor(module.SQLiteReadOnlyAuditor):
        def _connect_ro(self):
            connection=super()._connect_ro();connection.execute("PRAGMA temp_store=MEMORY");deadline_progress(connection,time.monotonic()+5);return connection
    snap=BoundedAuditor(str(source),busy_timeout_ms=2500).snapshot(at.strftime("%Y%m%d"),process_now_jst=at.isoformat())
    counts={s:0 for s in STATES};unknown=0
    for row in snap["current_date_race_states"]:
        s=row.get("status")
        if "parse_error" in row or s not in counts:unknown+=1
        else:counts[s]+=1
    nonterminal=sum(n for s,n in counts.items() if s!="TERMINAL")
    return [{"day":at.strftime("%Y%m%d"),"mode":"ro","journal":snap["journal_mode"],"pending":counts["PENDING"],"nonterminal":nonterminal,"unknown":unknown},{"states":counts},{"r":"STOP_UNKNOWN" if unknown else "SNAPSHOT_ONLY","review":bool(nonterminal),"semantics":"NOT_TRACE"}]

if __name__=="__main__": entry("G2_A5_V002",g2)
