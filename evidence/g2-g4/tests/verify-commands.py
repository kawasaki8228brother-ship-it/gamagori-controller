from pathlib import Path
import base64,hashlib,json

E=Path(__file__).resolve().parents[1]
common=(E/"source/common.py").read_text()
specs={"G2_A5_v002":("G2_A5_V002",["g2"],"g2"),"G3_backup_v002":("G3_BACKUP_DESIGN",["g3"],"g3"),"G4_environment_v002":("G4_ENV",["g4_env"],"g4_env"),"G4_TLS_v002":("G4_TLS",["g4_env","g4_tls"],"g4_tls"),"G4_SQLite_v002":("G4_DB",["g4_db"],"g4_db")}
manifest=[]
for name,(kind,parts,fn) in specs.items():
    code=common+"\n"
    for part in parts:
        code+="\n".join(line for line in (E/('source/'+part+'.py')).read_text().splitlines() if not line.startswith('if __name__=='))+"\n"
    code+='\nif __name__=="__main__": entry('+repr(kind)+','+fn+')\n'
    data=code.encode('ascii');digest=hashlib.sha256(data).hexdigest();sentinel='CERTIFI_G_END_'+digest
    envelope='import sys,base64,hashlib,json\nif sys.argv[1:]!=["'+sentinel+'"]:sys.exit("G_REJECTED_END")\ntry:p=base64.b64decode("'+base64.b64encode(data).decode()+'",validate=True)\nexcept Exception:sys.exit("G_REJECTED_PAYLOAD")\nif not(len(p)=='+str(len(data))+' and hashlib.sha256(p).hexdigest()=="'+digest+'"):sys.exit("G_REJECTED_PAYLOAD")\ntry:exec(compile(p,"<reviewed-g-command>","exec"),{"__name__":"__main__","__builtins__":__builtins__})\nexcept BaseException as error:\n b=(json.dumps({"r":"STOP","e":type(error).__name__},sort_keys=True,separators=(",",":"))+"\\n").encode("ascii")\n end="END CERTIFI_AUDIT_V002 lines=1 bytes="+str(len(b))+" sha256="+hashlib.sha256(b).hexdigest()+"\\n"\n sys.stdout.buffer.write(b"BEGIN CERTIFI_AUDIT_V002\\n"+b+end.encode("ascii"))\n sys.exit(2)\n'
    wrapper='exec('+json.dumps(envelope,ensure_ascii=True)+')'
    assert "'" not in wrapper
    command="{ python -B -c '"+wrapper+"' "+sentinel+"; }"
    assert command.isascii() and '\n' not in command
    (E/('commands/'+name+'.candidate.txt')).write_bytes(command.encode())
    assert (E/('source/'+name+'.payload.py')).read_bytes()==data
    manifest.append({'name':name,'file':'commands/'+name+'.candidate.txt','bytes':len(command),'sha256':hashlib.sha256(command.encode()).hexdigest(),'payload_sha256':digest,'payload_bytes':len(data),'kind':kind,'entry':fn})
print('COMMAND_FILES_VERIFIED count='+str(len(manifest)))
