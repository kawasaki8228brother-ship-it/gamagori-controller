BASELINE_CA_SHA="9cc2a774b5198dcff14d9be1e66091f538975d867ce029a96bce15a55dfd730f"

def old_certifi_version(value):
    # PEP 440 month zero-padding: 2026.07.22 and 2026.7.22 are the same release.
    return isinstance(value,str) and re.fullmatch(r"2026\.0?7\.22",value) is not None

def baseline_observations_pass(observations):
    return (old_certifi_version(observations["certifi_module"])
            and old_certifi_version(observations["certifi_metadata"])
            and observations["ca_sha"]==BASELINE_CA_SHA
            and observations["ca_n"]==121 and observations["eff_n"]==121
            and observations["eff_eq"] and observations["verify_required"]
            and observations["hostname"] and observations["env_overrides"]==0
            and observations["runtime"] and observations["app_source"])

def baseline_gate(project=None,environ=None,context_factory=None):
    import certifi,httpx
    from importlib.metadata import version
    from httpx._config import create_ssl_context
    project=Path.cwd() if project is None else Path(project)
    environ=os.environ if environ is None else environ
    env_count=sum(name in environ for name in ENV_NAMES)
    if env_count:return [{"env_overrides":env_count},{"r":"STOP_BASELINE_ENV","go":False}]
    data=Path(certifi.where()).read_bytes()
    pems=re.findall(br"-----BEGIN CERTIFICATE-----.*?-----END CERTIFICATE-----",data,re.S)
    bundle={hashlib.sha256(ssl.PEM_cert_to_DER_cert(p.decode())).hexdigest() for p in pems}
    context=(context_factory or create_ssl_context)()
    effective={hashlib.sha256(c).hexdigest() for c in context.get_ca_certs(binary_form=True)}
    observed={"certifi_module":certifi.__version__,"certifi_metadata":version("certifi"),
              "ca_sha":hashlib.sha256(data).hexdigest(),"ca_n":len(pems),"eff_n":len(effective),
              "eff_eq":len(bundle)==121 and bundle==effective,
              "verify_required":context.verify_mode==ssl.CERT_REQUIRED,
              "hostname":context.check_hostname,"env_overrides":env_count,
              "runtime":sys.version_info[:3]==(3,14,3) and httpx.__version__=="0.28.1",
              "app_source":hashlib.sha256((project/"official.py").read_bytes()).hexdigest()==OFFICIAL_SHA}
    passed=baseline_observations_pass(observed)
    return [{"old_release":old_certifi_version(observed["certifi_module"]) and old_certifi_version(observed["certifi_metadata"]),
             "ca_sha":observed["ca_sha"],"ca_n":observed["ca_n"],"eff_n":observed["eff_n"],
             "eff_eq":observed["eff_eq"],"env_overrides":env_count,"runtime":observed["runtime"],"app_source":observed["app_source"]},
            {"r":"BASELINE_ENV_PASS" if passed else "STOP_BASELINE_ENV","go":False}]
