import argparse
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import socket
import sqlite3
import ssl
import sys
import unittest


def blocked(*args, **kwargs): raise AssertionError('NETWORK_DISABLED_OFFLINE_COMPLETION')


parser=argparse.ArgumentParser()
parser.add_argument('--repo',type=Path,required=True)
parser.add_argument('--scope',choices=['root','model'],required=True)
parser.add_argument('--xml',type=Path)
args=parser.parse_args()
root=args.repo.resolve()
os.chdir(root)
sys.dont_write_bytecode=True
socket.socket.connect=socket.socket.connect_ex=socket.create_connection=socket.getaddrinfo=blocked
os.environ['PYTEST_DISABLE_PLUGIN_AUTOLOAD']='1'
os.environ.pop('PYTEST_ADDOPTS',None)
sys.path.insert(0,str(root))
print(json.dumps({'python':sys.version,'platform':platform.platform(),'openssl':ssl.OPENSSL_VERSION,'sqlite':sqlite3.sqlite_version,
    'scope':args.scope,'network':'BLOCKED','production_go':False,'existing_environments_changed':False},sort_keys=True),flush=True)
if args.scope=='root':
    import pytest
    class Totals:
        collected=None
        categories=None
        def pytest_sessionfinish(self,session,exitstatus):
            self.collected=session.testscollected
            report=session.config.pluginmanager.getplugin('terminalreporter')
            self.categories={k:len(v) for k,v in report.stats.items() if k in ('passed','failed','skipped','error','subtests passed','subtests failed')}
    totals=Totals()
    opts=['-p','pytest_asyncio.plugin','-p','no:cacheprovider','-q','--tb=short','tests']
    if args.xml:opts.append('--junitxml='+str(args.xml.resolve()))
    code=int(pytest.main(opts,plugins=[totals]))
    print(json.dumps({'status':'PASS_WITH_UNVERIFIED_SKIPS' if not code and totals.categories.get('skipped') else 'PASS' if not code else 'FAIL',
        'tests_collected':totals.collected,'categories':totals.categories,'exit_code':code,'production_go':False},sort_keys=True))
    raise SystemExit(code)
sys.path.insert(0,str(root/'development/model11'))
suite=unittest.defaultTestLoader.discover(str(root/'development/model11/tests'),pattern='test*.py')
result=unittest.TextTestRunner(stream=sys.stdout,verbosity=2).run(suite)
print(json.dumps({'status':'PASS_WITH_UNVERIFIED_SKIPS' if result.wasSuccessful() and result.skipped else 'PASS' if result.wasSuccessful() else 'FAIL',
    'tests_run':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),'skipped':len(result.skipped),'production_go':False},sort_keys=True))
raise SystemExit(0 if result.wasSuccessful() else 1)
