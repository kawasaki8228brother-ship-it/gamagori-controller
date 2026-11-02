"""Rebuild in memory and compare only. Never writes frozen or candidate files."""
from pathlib import Path
import base64,hashlib,json,sys

V=Path(__file__).resolve().parents[1]
E=V.parent

def command_bytes(kind,parts,entry):
    code=(E/'source/common.py').read_text(encoding='ascii')+'\n'
    for path in parts:
        code+='\n'.join(line for line in path.read_text(encoding='ascii').splitlines() if not line.startswith('if __name__=='))+'\n'
    code+='\nif __name__=="__main__": entry('+repr(kind)+','+entry+')\n'
    data=code.encode('ascii');digest=hashlib.sha256(data).hexdigest();sentinel='CERTIFI_G_END_'+digest
    envelope='import sys,base64,hashlib,json\nif sys.argv[1:]!=["'+sentinel+'"]:sys.exit("G_REJECTED_END")\ntry:p=base64.b64decode("'+base64.b64encode(data).decode()+'",validate=True)\nexcept Exception:sys.exit("G_REJECTED_PAYLOAD")\nif not(len(p)=='+str(len(data))+' and hashlib.sha256(p).hexdigest()=="'+digest+'"):sys.exit("G_REJECTED_PAYLOAD")\ntry:exec(compile(p,"<reviewed-g-command>","exec"),{"__name__":"__main__","__builtins__":__builtins__})\nexcept BaseException as error:\n b=(json.dumps({"r":"STOP","e":type(error).__name__},sort_keys=True,separators=(",",":"))+"\\n").encode("ascii")\n end="END CERTIFI_AUDIT_V002 lines=1 bytes="+str(len(b))+" sha256="+hashlib.sha256(b).hexdigest()+"\\n"\n sys.stdout.buffer.write(b"BEGIN CERTIFI_AUDIT_V002\\n"+b+end.encode("ascii"))\n sys.exit(2)\n'
    wrapper='exec('+json.dumps(envelope,ensure_ascii=True)+')'
    assert "'" not in wrapper
    command="{ python -B -c '"+wrapper+"' "+sentinel+"; }"
    assert command.isascii() and '\n' not in command
    return command.encode('ascii'),data

def specifications():
    old=[('G2_A5_v002','G2_A5_V002',['g2'],'g2'),('G3_backup_v002','G3_BACKUP_DESIGN',['g3'],'g3'),('G4_environment_v002','G4_ENV',['g4_env'],'g4_env'),('G4_TLS_v002','G4_TLS',['g4_env','g4_tls'],'g4_tls'),('G4_SQLite_v002','G4_DB',['g4_db'],'g4_db')]
    values=[(E,name,kind,[E/('source/'+p+'.py') for p in parts],entry) for name,kind,parts,entry in old]
    F=E/'v003-final'
    values.extend([
        (F,'G4_TLS_v003','G4_TLS_V003',[E/'source/g4_env.py',F/'source/g4_tls_v003.py'],'g4_tls_v003'),
        (F,'G4_baseline_v003','G4_BASELINE_V003',[F/'source/baseline_gate_v003.py',F/'source/g4_tls_v003.py'],'g4_baseline_v003'),
        (V,'G4_TLS_v003_F1F2','G4_TLS_V003',[E/'source/g4_env.py',V/'source/g4_tls_revised.py'],'g4_tls_v003'),
        (V,'G4_baseline_v003_F1F2','G4_BASELINE_V003',[V/'source/baseline_gate_v003.py',V/'source/g4_tls_revised.py'],'g4_baseline_v003'),
        (V,'G3_backup_v003','G3_BACKUP_DESIGN',[V/'source/g3_v003.py'],'g3'),
    ])
    return values

def verify():
    for directory,name,kind,parts,entry in specifications():
        command,payload=command_bytes(kind,parts,entry)
        assert (directory/('commands/'+name+'.candidate.txt')).read_bytes()==command
        assert (directory/('source/'+name+'.payload.py')).read_bytes()==payload
    assert (V/'source/G3_backup_v003.payload.py').read_bytes()==(E/'source/G3_backup_v002.payload.py').read_bytes().replace(b'3.50.4',b'3.40.1')
    print('COMMAND_FILES_VERIFIED frozen=7 new=3 writes=0 G3_LITERAL_REPLACEMENT=1')

if __name__=='__main__':verify()
