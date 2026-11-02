"""Generate private, disposable loopback fixtures; never upload the keys."""
from pathlib import Path
from datetime import datetime,timedelta,timezone
import os,sys,json,hashlib,ipaddress,platform,ssl
from cryptography import x509
from cryptography.hazmat.primitives import hashes,serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID,ExtendedKeyUsageOID

if len(sys.argv)!=2:raise SystemExit('one new WORK argument required')
root=Path(sys.argv[1]).resolve()/'tls-fixtures'
root.mkdir(parents=True,exist_ok=False);os.chmod(root,0o700)
now=datetime.now(timezone.utc)
keys={name:rsa.generate_private_key(public_exponent=65537,key_size=2048) for name in ('trusted','untrusted','intermediate','leaf')}
def build(name,key,issuer,issuer_key,ca=False,expired=False,wrong=False):
    subject=x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,name)])
    start,end=(now-timedelta(days=4),now-timedelta(days=2)) if expired else (now-timedelta(days=1),now+timedelta(days=2))
    b=(x509.CertificateBuilder().subject_name(subject).issuer_name(issuer or subject).public_key(key.public_key()).serial_number(x509.random_serial_number()).not_valid_before(start).not_valid_after(end)
       .add_extension(x509.BasicConstraints(ca=ca,path_length=None),True)
       .add_extension(x509.SubjectKeyIdentifier.from_public_key(key.public_key()),False)
       .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(issuer_key.public_key()),False)
       .add_extension(x509.KeyUsage(digital_signature=True,content_commitment=False,key_encipherment=not ca,data_encipherment=False,key_agreement=False,key_cert_sign=ca,crl_sign=ca,encipher_only=False,decipher_only=False),True))
    if not ca:
        names=[x509.DNSName('wrong.invalid')] if wrong else [x509.DNSName('localhost'),x509.IPAddress(ipaddress.ip_address('127.0.0.1'))]
        b=b.add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]),False).add_extension(x509.SubjectAlternativeName(names),False)
    return b.sign(issuer_key,hashes.SHA256())
trusted=build('Local trusted root',keys['trusted'],None,keys['trusted'],ca=True)
untrusted=build('Local untrusted root',keys['untrusted'],None,keys['untrusted'],ca=True)
inter=build('Local intermediate',keys['intermediate'],untrusted.subject,keys['untrusted'],ca=True)
pem=lambda c:c.public_bytes(serialization.Encoding.PEM)
for name,cert in (('trusted',trusted),('untrusted',untrusted),('intermediate',inter)):
    (root/(name+'.pem')).write_bytes(pem(cert))
for name,issuer,signer,expired,wrong in (
    ('valid',trusted.subject,keys['trusted'],False,False),
    ('expired',trusted.subject,keys['trusted'],True,False),
    ('wrong-host',trusted.subject,keys['trusted'],False,True),
    ('unknown-issuer',untrusted.subject,keys['untrusted'],False,False),
    ('intermediate-leaf',inter.subject,keys['intermediate'],False,False),
    ('self-signed',None,keys['leaf'],False,False),
):
    cert=build('Local leaf',keys['leaf'],issuer,signer,expired=expired,wrong=wrong)
    (root/(name+'.pem')).write_bytes(pem(cert))
(root/'untrusted-chain.pem').write_bytes((root/'unknown-issuer.pem').read_bytes()+pem(untrusted))
(root/'intermediate-chain.pem').write_bytes((root/'intermediate-leaf.pem').read_bytes()+pem(inter))
key=root/'leaf.key';key.write_bytes(keys['leaf'].private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()));os.chmod(key,0o600)
print(json.dumps({'python':sys.version.split()[0],'openssl':ssl.OPENSSL_VERSION,'os':platform.system(),'scope':'PRIVATE_SYNTHETIC_LOOPBACK_FIXTURES_ONLY','public_cert_count':len(list(root.glob('*.pem'))),'private_keys_published':False},sort_keys=True))
