from pathlib import Path
from datetime import datetime, timedelta, timezone
import hashlib, ipaddress, json, os, platform, sys
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID, ExtendedKeyUsageOID

if len(sys.argv) != 2: raise SystemExit("isolated WORK argument required")
ROOT = Path(sys.argv[1]).resolve() / "tls-fixtures"
ROOT.mkdir(exist_ok=True)
os.chmod(ROOT, 0o700)
now = datetime.now(timezone.utc)
ca_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
leaf_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
ca_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Codex Phase 1 Local Test CA")])
ca = (x509.CertificateBuilder().subject_name(ca_name).issuer_name(ca_name).public_key(ca_key.public_key()).serial_number(x509.random_serial_number()).not_valid_before(now - timedelta(days=5)).not_valid_after(now + timedelta(days=5)).add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True).add_extension(x509.SubjectKeyIdentifier.from_public_key(ca_key.public_key()), critical=False).add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()), critical=False).add_extension(x509.KeyUsage(digital_signature=True, content_commitment=False, key_encipherment=False, data_encipherment=False, key_agreement=False, key_cert_sign=True, crl_sign=True, encipher_only=False, decipher_only=False), critical=True).sign(ca_key, hashes.SHA256()))
ROOT.joinpath("ca.pem").write_bytes(ca.public_bytes(serialization.Encoding.PEM))
key_path = ROOT / "leaf.key"
key_path.write_bytes(leaf_key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
os.chmod(key_path, 0o600)
for name in ("valid", "expired", "wrong-host", "self-signed"):
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "localhost")])
    issuer, signing_key = (subject, leaf_key) if name == "self-signed" else (ca_name, ca_key)
    san = [x509.DNSName("wrong.invalid")] if name == "wrong-host" else [x509.DNSName("localhost"), x509.IPAddress(ipaddress.ip_address("127.0.0.1"))]
    start, end = (now - timedelta(days=3), now - timedelta(days=2)) if name == "expired" else (now - timedelta(minutes=5), now + timedelta(days=2))
    cert = (x509.CertificateBuilder().subject_name(subject).issuer_name(issuer).public_key(leaf_key.public_key()).serial_number(x509.random_serial_number()).not_valid_before(start).not_valid_after(end).add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True).add_extension(x509.SubjectKeyIdentifier.from_public_key(leaf_key.public_key()), critical=False).add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(signing_key.public_key()), critical=False).add_extension(x509.KeyUsage(digital_signature=True, content_commitment=False, key_encipherment=True, data_encipherment=False, key_agreement=False, key_cert_sign=False, crl_sign=False, encipher_only=False, decipher_only=False), critical=True).add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), critical=False).add_extension(x509.SubjectAlternativeName(san), critical=False).sign(signing_key, hashes.SHA256()))
    ROOT.joinpath(name + ".pem").write_bytes(cert.public_bytes(serialization.Encoding.PEM))
print(json.dumps({"python": sys.version, "os": platform.platform(), "fixture_count": 4, "scope": "generated loopback-only test certificates; no production keys", "public_cert_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(ROOT.glob("*.pem"))}}, sort_keys=True))
