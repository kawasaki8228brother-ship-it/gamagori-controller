from pathlib import Path
import ast, hashlib, importlib.util, json, os, shlex, subprocess, sys

if len(sys.argv) != 2:
    raise SystemExit("one separate isolated work-directory argument is required")
ROOT = Path(sys.argv[1]).resolve()
ROOT.mkdir(parents=True, exist_ok=True)
E = Path(__file__).resolve().parents[1]
PY = Path(sys.executable)
command = E.joinpath("commands/A1-A3_v002.candidate.txt").read_text()
payload = E.joinpath("design/v002.payload.py").read_text()
parts = shlex.split(command[2:-3])
envelope = {"wrapper": parts[3], "sentinel": parts[4]}
environment = dict(os.environ)
environment["PATH"] = str(PY.parent) + os.pathsep + environment.get("PATH", "")
environment["PYTHONDONTWRITEBYTECODE"] = "1"
header = subprocess.run([str(PY), "-B", "-c", "import sys,os,ssl,json;u=os.uname();print(json.dumps(dict(python=sys.version.split()[0],openssl=ssl.OPENSSL_VERSION,os=dict(system=u.sysname,release=u.release,machine=u.machine)),sort_keys=True))"], capture_output=True, text=True, check=True).stdout
log = ["ENV " + header]
spec = importlib.util.spec_from_file_location("frame_verifier", E / "design/verify-v002-output.py")
verifier = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verifier)
assert command.isascii() and "\n" not in command and not command.endswith("\n")
assert command.startswith("{ ") and command.endswith("; }")
shell_args = shlex.split(command[2:-3])
assert shell_args[:3] == ["python", "-B", "-c"] and len(shell_args) == 5
assert shell_args[-1] == envelope["sentinel"]
ast.parse(payload)
full = subprocess.run(["bash", "-c", command], cwd=ROOT, env=environment, capture_output=True, timeout=30)
assert full.returncode == 0 and not full.stderr and verifier.verify(full.stdout)
ROOT.joinpath("v002-isolated-output.private.txt").write_bytes(full.stdout)
body = [json.loads(line) for line in full.stdout.splitlines()[1:-1]]
data = {row["section"]: row for row in body}
assert data["python"]["data"]["sys.executable"] == str(PY)
assert data["python"]["data"]["sys.prefix"] == str(PY.parent.parent)
assert data["python"]["data"]["same_as_live_worker"] == "UNVERIFIED_REFERENCE_REQUIRED"
assert len(data["env_presence"]["data"]) == 14
assert data["certifi"]["data"]["bundle_cert_count"] == 118
assert data["gate"]["data"]["blocked_side_effects"] == {}
log.append("COMPLETE_COMMAND PASS one python -B -c; known isolated interpreter/prefix matched\n")
log.append("LIVE_WORKER_IDENTITY UNVERIFIED (no Render execution or approved live reference)\n")
log.append("ENV_PRESENCE PASS upper/lower names=14 values_not_printed\n")
log.append("FRAME PASS BEGIN/END body_lines=" + str(len(body)) + "\n")

# A single opening shell group is terminated only by the final byte.
quote, closing_positions = None, []
for index, char in enumerate(command):
    if char == "'":
        quote = None if quote else "'"
    elif char == "}" and quote is None:
        closing_positions.append(index)
assert quote is None and closing_positions == [len(command) - 1]
log.append("TAIL_CUT_STRUCTURE PASS proper_prefixes_without_group_terminator=" + str(len(command) - 1) + "\n")
cuts = sorted({1, 2, 3, 8, 12, 20, 23, len(command)//4, len(command)//2, 3*len(command)//4, command.rfind("'"), command.rfind("'")+1, len(command)-90, len(command)-40, len(command)-4, len(command)-3, len(command)-2, len(command)-1})
for cut in cuts:
    result = subprocess.run(["bash", "-c", command[:cut]], cwd=ROOT, env=environment, capture_output=True, timeout=10)
    assert result.returncode == 2 and not result.stdout
log.append("TAIL_CUT_EXECUTION PASS samples=" + str(len(cuts)) + " syntax_error_no_collector_output\n")

missing = subprocess.run([str(PY), "-B", "-c", envelope["wrapper"]], capture_output=True, timeout=10)
assert missing.returncode != 0 and b"BEGIN" not in missing.stdout
mutant = envelope["wrapper"].replace("p=base64.b64decode(\"", "p=base64.b64decode(\"A", 1)
damaged = subprocess.run([str(PY), "-B", "-c", mutant, envelope["sentinel"]], capture_output=True, timeout=10)
assert damaged.returncode != 0 and b"BEGIN" not in damaged.stdout
log.append("ENVELOPE_GUARD PASS missing_end_token_and_corrupt_payload_rejected_before_collection\n")

changed = bytearray(full.stdout)
changed[40] ^= 1
for bad in (full.stdout[:-10], bytes(changed), full.stdout + b"extra\n", b"".join(full.stdout.splitlines(keepends=True)[:-1])):
    assert not verifier.verify(bad)
log.append("OUTPUT_DAMAGE PASS truncated_body/footer edited_body extra_output_rejected\n")

test_prefix = '''import os,sys
os.environ["ssl_cert_file"]="SYNTHETIC_CREDENTIAL_PATH"
os.environ["https_proxy"]="SYNTHETIC_PROXY_VALUE_NOT_PRINTED"
'''
test_suffix = '''
class Fake:
    def __init__(self,name,version,files): self.metadata={"Name":name};self.version=version;self.files=files
    def read_text(self,*args): raise AssertionError("origin content must not be read")
items=[Fake("public.pkg","1.2.3",[]),Fake("local.pkg","2.0",["x.dist-info/direct_url.json"]),Fake("url.pkg","https:"+chr(47)+chr(47)+"user:SYNTHETIC_CREDENTIAL_TOKEN"+chr(64)+"example.invalid",[]),Fake("path.pkg","/private/SYNTHETIC_CREDENTIAL_PATH",[]),Fake("bad@SYNTHETIC_CREDENTIAL_NAME","1.0",[])]
r=_freeze_rows(items)
assert r["redacted_line_count"]==4 and "SYNTHETIC_CREDENTIAL" not in json.dumps(r)
assert "local.pkg [REDACTED]" in r["rows"] and "url.pkg [REDACTED]" in r["rows"]
assert _environment()["ssl_cert_file"]=="present" and _environment()["https_proxy"]=="present"
assert _path("/srv/token=SYNTHETIC_CREDENTIAL_PATH")=="[REDACTED_UNSAFE_PATH]"
import socket,subprocess,sqlite3
for fn in (lambda: open("/__V002_FORBIDDEN_WRITE__","w"),lambda: open(".env","r"),lambda: socket.socket(),lambda: subprocess.run([sys.executable,"-c","pass"]),lambda: sqlite3.connect(":memory:")):
    try: fn();raise AssertionError("guard allowed side effect")
    except PermissionError as exc: assert str(exc)=="V002_SIDE_EFFECT_BLOCKED"
assert not ({"main","official","repositories","airtable","sqlite_readonly_audit"}&set(sys.modules))
print("SYNTHETIC_SAFETY PASS freeze_redacted_lines=4 lower_env_presence_only unsafe_path_redacted guards=write,dotenv,network,subprocess,sqlite app_not_imported")
'''
source = test_prefix + "\n__name__=\"v002_unit_test\"\n" + payload + test_suffix
unit = subprocess.run([str(PY), "-B", "-c", source], cwd=ROOT, env=environment, capture_output=True, timeout=20)
assert unit.returncode == 0 and not unit.stderr and b"SYNTHETIC_CREDENTIAL" not in unit.stdout
log.append(unit.stdout.decode())
log.extend(["RENDER_EXECUTION NOT_RUN\n", "A2_REVIEW NOT_PERFORMED\n", "CLAUDE_INDEPENDENT_REVIEW PENDING\n"])
content = "".join(log)
ROOT.joinpath("v002-test.raw.log").write_text(content)
print(content, end="")
print("RAW_LOG_SHA256", hashlib.sha256(content.encode()).hexdigest())
