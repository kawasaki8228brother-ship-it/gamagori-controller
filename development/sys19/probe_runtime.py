"""Local-only runtime/reference probe. No installs, environment dump or URLs."""
from pathlib import Path
import argparse
import importlib.metadata as metadata
import json
import platform
import ssl
import sqlite3
import sys
from runtime_check import inspect_runtime

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--requirements',type=Path,default=Path(__file__).with_name('requirements.reference.txt'))
    parser.add_argument('--expected-sha256',default='dba91fc609884c39b70c1660151e959779d86613fe0ce13c61626506123a2dc7')
    parser.add_argument('--target-python',default='3.14.3')
    args=parser.parse_args()
    try:
        raw=args.requirements.read_bytes()
        installed=[(d.metadata['Name'],d.version) for d in metadata.distributions()]
        report=inspect_runtime(raw,args.expected_sha256,installed,sys.version.split()[0],args.target_python)
    except (OSError,ValueError,TypeError):
        print(json.dumps({'status':'INPUT_REJECTED','raw_input_not_echoed':True,'production_GO':False}))
        return 2
    report['environment']={'python':sys.version.split()[0],'os':platform.platform(),'openssl':ssl.OPENSSL_VERSION,'sqlite':sqlite3.sqlite_version}
    print(json.dumps(report,sort_keys=True))
    return 0 if report['status']=='REFERENCE_ENV_MATCH' else 2

if __name__=='__main__':raise SystemExit(main())
