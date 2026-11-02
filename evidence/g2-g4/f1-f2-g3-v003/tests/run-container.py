"""Portable LOCAL-only reproduction. MODE WORK PROJECT PINNED_SITE arguments."""
from pathlib import Path
import os,subprocess,sys
if len(sys.argv)!=5 or sys.argv[1] not in ('metadata','tls','sqlite'):raise SystemExit('MODE WORK PROJECT PINNED_SITE required')
mode=sys.argv[1];work=Path(sys.argv[2]).resolve();project=Path(sys.argv[3]).resolve();site=Path(sys.argv[4]).resolve()
V=Path(__file__).resolve().parents[1];publish=V.parents[2];work.mkdir(parents=True,exist_ok=True)
image='python@sha256:f21c0d5a44c56805654c15abccc1b2fd576c8d93aca0a3f74b4aba2dc92510e2'
base=['env','-u','DOCKER_HOST','-u','DOCKER_CONTEXT','-u','DOCKER_TLS','-u','DOCKER_TLS_VERIFY','-u','DOCKER_CERT_PATH','docker','--host=unix:///var/run/docker.sock']
command=base+['run','--rm','--network','none','--read-only','--cap-drop','ALL','--security-opt','no-new-privileges','--user',str(os.getuid())+':'+str(os.getgid()),'--tmpfs','/tmp:rw,nosuid,nodev,size=256m',
 '--mount','type=bind,src='+str(publish)+',dst=/evidence,readonly',
 '--mount','type=bind,src='+str(site)+',dst=/pinned-site,readonly',
 '--mount','type=bind,src='+str(project)+',dst=/project,readonly',
 '--mount','type=bind,src='+str(work)+',dst=/work',
 '--env','PYTHONPATH=/pinned-site','--env','PYTHONDONTWRITEBYTECODE=1','--env','PATH=/tmp/audit-venv/bin:/usr/local/bin:/usr/bin:/bin',image,'python','-B','-c']
if mode=='metadata':argv=['python','-B','-c',(V/'tests/container-metadata.py').read_text()]
else:argv=['python','-B','/evidence/evidence/g2-g4/f1-f2-g3-v003/tests/'+mode+'-isolation.py','/work','/project']
code="import venv,os;venv.EnvBuilder(with_pip=False,symlinks=True).create('/tmp/audit-venv');os.execv('/tmp/audit-venv/bin/python',"+repr(argv)+")"
raise SystemExit(subprocess.run(command+[code]).returncode)
