import sys, os, ssl, json, hashlib, re, io, contextlib, shutil, datetime

# The command uses the same "python" launch token as "python main.py".
# Runtime equivalence to the live worker needs a separately approved reference.
sys.dont_write_bytecode = True
_blocked = {}
_path_redactions = 0
_errors = []

def _guard(event, args):
    deny = {"subprocess.Popen", "os.system", "os.exec", "os.posix_spawn", "os.spawn", "os.fork", "os.forkpty", "os.remove", "os.rename", "os.rmdir", "os.mkdir", "os.link", "os.symlink", "os.chmod", "os.chown", "os.truncate", "os.utime", "os.setxattr", "os.removexattr"}
    write = False
    env_file = False
    if event == "open":
        mode, flags = args[1:3]
        write = (isinstance(mode, str) and any(c in mode for c in "wax+")) or (isinstance(flags, int) and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND))
        env_file = isinstance(args[0], (str, bytes)) and os.fsdecode(args[0]).rsplit("/", 1)[-1].startswith(".env")
    app_import = event == "import" and args[0].split(".")[0] in {"main", "official", "repositories", "airtable", "models", "state_machine", "parsers", "closing", "sqlite_readonly_audit", "v11_candidate"}
    if write or env_file or app_import or event == "sqlite3.connect" or event.startswith("socket.") or event in deny:
        _blocked[event] = _blocked.get(event, 0) + 1
        raise PermissionError("V002_SIDE_EFFECT_BLOCKED")

sys.addaudithook(_guard)

def _path(value):
    global _path_redactions
    if value is None:
        return None
    value = os.fspath(value)
    suspicious = not value.startswith("/") or any(ord(c) < 32 or ord(c) == 127 for c in value) or any(x in value for x in ("@", "://", "?", "#")) or re.search(r"(?i)(?:password|passwd|secret|credential|token|bearer|authorization)", value)
    if suspicious:
        _path_redactions += 1
        return "[REDACTED_UNSAFE_PATH]"
    return value

def _version(value):
    value = str(value)
    return value if re.fullmatch(r"[0-9][A-Za-z0-9.!+_-]{0,79}", value) else "[REDACTED_INVALID_VERSION]"

def _collect(section, fn):
    try:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            value = fn()
        return {"section": section, "data": value}
    except Exception as exc:
        _errors.append(section)
        return {"section": section, "error_type": type(exc).__name__}

def _python():
    u = os.uname()
    return {"version": sys.version.split()[0], "sys.executable": _path(sys.executable), "sys.prefix": _path(sys.prefix), "launch_token": "python", "same_as_live_worker": "UNVERIFIED_REFERENCE_REQUIRED", "os": {"system": u.sysname, "release": u.release, "machine": u.machine}}

def _environment():
    upper = "SSL_CERT_FILE SSL_CERT_DIR REQUESTS_CA_BUNDLE HTTP_PROXY HTTPS_PROXY ALL_PROXY NO_PROXY".split()
    return {key: "present" if key in os.environ else "absent" for key in upper + [x.lower() for x in upper]}

def _certifi():
    import certifi
    path = certifi.where()
    with open(path, "rb") as stream:
        data = stream.read()
    count = len(re.findall(br"-----BEGIN CERTIFICATE-----.*?-----END CERTIFICATE-----", data, re.S))
    return {"version": _version(certifi.__version__), "certifi.where()": _path(path), "bundle_sha256": hashlib.sha256(data).hexdigest(), "bundle_cert_count": count}

def _ssl_paths():
    value = ssl.get_default_verify_paths()._asdict()
    for key in ("cafile", "capath", "openssl_cafile", "openssl_capath"):
        value[key] = _path(value[key])
    for field, env_field in (("cafile", "openssl_cafile_env"), ("capath", "openssl_capath_env")):
        if value[env_field] in os.environ:
            value[field] = "[REDACTED_ENV_VALUE]"
    return value

def _httpx():
    import httpx
    from httpx._config import create_ssl_context
    context = create_ssl_context()
    return {"version": _version(httpx.__version__), "method": "httpx._config.create_ssl_context() defaults; no connection", "loaded_cert_count": len(context.get_ca_certs(binary_form=True)), "store_stats": context.cert_store_stats(), "check_hostname": context.check_hostname, "verify_mode": int(context.verify_mode), "capath_lazy_certificates": "NOT_ENUMERATED_BEFORE_CONNECTION"}

def _freeze_rows(distributions):
    rows, redacted, invalid_names = [], 0, 0
    for distribution in distributions:
        name = str(distribution.metadata.get("Name") or "")
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,199}", name):
            name, invalid_names = "INVALID_PACKAGE_NAME", invalid_names + 1
            rows.append(name + " [REDACTED]")
            redacted += 1
            continue
        version = str(distribution.version)
        files = distribution.files
        direct_reference = files is None or any(str(item).replace("\\", "/").endswith("/direct_url.json") or str(item) == "direct_url.json" for item in files)
        line = name + "==" + version
        unsafe = direct_reference or any(x in line for x in ("@", "://", "/", "\\")) or not re.fullmatch(r"[0-9][A-Za-z0-9.!+_-]{0,79}", version)
        if unsafe:
            rows.append(name + " [REDACTED]")
            redacted += 1
        else:
            rows.append(line)
    return {"method": "importlib.metadata.distributions(); same interpreter; no origin URL content read", "rows": sorted(rows), "row_count": len(rows), "redacted_line_count": redacted, "invalid_package_name_count": invalid_names, "safe_inventory_complete": redacted == 0, "A2_review": "NOT_PERFORMED"}

def _freeze():
    from importlib.metadata import distributions
    return _freeze_rows(distributions())

def _db_sizes():
    value = {"method": "os.stat only; no database open", "path_reference": "HISTORICAL_FIXED_PATH_NOT_RUNTIME_VERIFIED"}
    for role, suffix in (("db", ""), ("wal", "-wal"), ("shm", "-shm")):
        try:
            value[role] = {"exists": True, "size_bytes": os.stat("/var/data/gamagori_shadow.db" + suffix).st_size}
        except FileNotFoundError:
            value[role] = {"exists": False}
    return value

def _frame(records):
    body = b"".join((json.dumps(row, sort_keys=True, ensure_ascii=True, separators=(",", ":")) + "\n").encode("ascii") for row in records)
    footer = "END CERTIFI_AUDIT_V002 lines=" + str(len(records)) + " bytes=" + str(len(body)) + " sha256=" + hashlib.sha256(body).hexdigest() + "\n"
    return b"BEGIN CERTIFI_AUDIT_V002\n" + body + footer.encode("ascii")

def _run():
    rows = [_collect("python", _python), _collect("openssl", lambda: {"version": ssl.OPENSSL_VERSION}), _collect("env_presence", _environment), _collect("certifi", _certifi), _collect("default_verify_paths", _ssl_paths), _collect("httpx_default_context", _httpx), _collect("var_data", lambda: {"free_bytes": shutil.disk_usage("/var/data").free}), _collect("sqlite_sizes", _db_sizes), _collect("freeze", _freeze)]
    rows.append({"section": "gate", "data": {"result": "COLLECTION_ONLY_NO_GO", "runtime_identity": "UNVERIFIED_REFERENCE_REQUIRED", "collection_errors": list(_errors), "path_redaction_count": _path_redactions, "blocked_side_effects": dict(_blocked), "A2_review": "NOT_PERFORMED", "production_authorization": "NOT_GRANTED"}})
    sys.stdout.buffer.write(_frame(rows))
    sys.stdout.buffer.flush()

if __name__ == "__main__":
    _run()
