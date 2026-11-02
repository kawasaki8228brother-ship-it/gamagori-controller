import asyncio, hashlib, os, ssl, sys
from pathlib import Path
from importlib.metadata import version
import certifi
import httpx

bundle = Path(certifi.where()).read_bytes()

print("=== SHADOW TLS BASELINE ===")
print("Python:", sys.version.split()[0])
print("OpenSSL:", ssl.OPENSSL_VERSION)
print("HTTPX:", version("httpx"))
print("Certifi:", version("certifi"))
print("CA_SHA256:", hashlib.sha256(bundle).hexdigest())
print("Affected_G3_present:", b"emSign ECC Root CA - G3" in bundle)
print("Custom_CA:", bool(os.getenv("SSL_CERT_FILE") or os.getenv("SSL_CERT_DIR")))
print("=== HTTPS TESTS ===")

def cert_error(exc):
    for _ in range(10):
        if exc is None:
            break
        if isinstance(exc, ssl.SSLCertVerificationError):
            return True
        s = str(exc).upper()
        if "CERTIFICATE_VERIFY_FAILED" in s or "CERTIFICATE VERIFY FAILED" in s:
            return True
        exc = exc.__cause__ or exc.__context__
    return False

async def run():
    tests = [
        ("NEGATIVE_1", "https://dv-g3b-emudhra.we-have-a-problem.com/", True),
        ("NEGATIVE_2", "https://dv-g3b-aaa-emudhra.we-have-a-problem.com/", True),
        ("OFFICIAL", "https://www.boatrace.jp/", False),
        ("FALLBACK", "https://boatraceopenapi.github.io/", False),
    ]
    async with httpx.AsyncClient(
        timeout=8.0, verify=True,
        trust_env=True, follow_redirects=True
    ) as client:
        for name, url, negative in tests:
            try:
                response = await client.get(url)
                status = "FAIL_CERTIFICATE_ACCEPTED" if negative else "PASS_TLS_CONNECTED"
                print(name, status, response.status_code)
            except httpx.TransportError as exc:
                if cert_error(exc):
                    status = "PASS_CERTIFICATE_REJECTED" if negative else "FAIL_VALID_CERT_REJECTED"
                else:
                    status = "UNVERIFIED_NETWORK_ERROR"
                print(name, status, type(exc).__name__)
            except Exception as exc:
                print(name, "UNVERIFIED_ERROR", type(exc).__name__)

asyncio.run(run())
print("=== TEST COMPLETE / NO CHANGES ===")
