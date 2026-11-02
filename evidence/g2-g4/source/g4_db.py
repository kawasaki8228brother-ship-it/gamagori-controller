def g4_db(root=Path("/var/data")):
    source,sizes,wal=checked_source(root)
    connection=ro_connect(source)
    try:
        deadline_progress(connection,time.monotonic()+5)
        connection.execute("BEGIN");integrity(connection)
        tables=("race_states","idempotency_keys","shadow_events")
        counts={table:connection.execute("SELECT COUNT(*) FROM "+table).fetchone()[0] for table in tables}
        duplicate=connection.execute("SELECT COUNT(*) FROM (SELECT idempotency_key FROM shadow_events GROUP BY idempotency_key HAVING COUNT(*)>1)").fetchone()[0]
        orphan_event=connection.execute("SELECT COUNT(*) FROM shadow_events e LEFT JOIN idempotency_keys k ON k.idempotency_key=e.idempotency_key AND k.event_uuid=e.event_uuid WHERE k.idempotency_key IS NULL").fetchone()[0]
        orphan_key=connection.execute("SELECT COUNT(*) FROM idempotency_keys k LEFT JOIN shadow_events e ON k.idempotency_key=e.idempotency_key AND k.event_uuid=e.event_uuid WHERE e.idempotency_key IS NULL").fetchone()[0]
        latest=connection.execute("SELECT MAX(updated_at) FROM race_states").fetchone()[0]
        # Do not print untrusted timestamp strings or payload/event identifiers.
        if latest is not None:
            if not isinstance(latest,str) or not re.fullmatch(r"\d{4}-\d\d-\d\d[ T]\d\d:\d\d:\d\d(?:\.\d{1,6})?(?:Z|[+-]\d\d:\d\d)?",latest):raise Stop("STATE_TIME_FORMAT")
            try:dt.datetime.fromisoformat(latest)
            except (ValueError,TypeError):raise Stop("STATE_TIME_FORMAT")
        connection.execute("ROLLBACK")
        return [{"integrity":"ok","rows":counts},{"dup":duplicate,"orphan_event":orphan_event,"orphan_key":orphan_key,"state_updated_max":latest},{"r":"STOP_DB" if duplicate or orphan_event or orphan_key else "DB_OBS_PASS","poll":"NEEDS_RUNTIME_LOGS","dedup_scope":"LOCAL_DB_ONLY","go":False}]
    finally:connection.close()

if __name__=="__main__":entry("G4_DB",g4_db)
