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

if __name__=="__main__":entry("G4_ENV",g4_env)
