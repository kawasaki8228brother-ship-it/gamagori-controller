"""Run document tests only. No preserved model/evaluator is imported or run."""
import json
from pathlib import Path
import platform
import socket
import ssl
import sys
import unittest


def blocked(*args, **kwargs):
    raise AssertionError("NETWORK_DISABLED_DURING_DOCUMENT_AUDIT")


if __name__ == "__main__":
    socket.socket.connect = socket.create_connection = socket.getaddrinfo = blocked
    print("F5_DOCUMENT_STATIC_TESTS_ONLY", flush=True)
    print(json.dumps({"python": sys.version, "platform": platform.platform(), "openssl": ssl.OPENSSL_VERSION,
        "network": "BLOCKED_IN_PROCESS", "statistical_evaluation_performed": False,
        "source_data": "DOCUMENTS_AND_SYNTHETIC_PARTITION_METADATA_ONLY", "production_go": False}, sort_keys=True), flush=True)
    suite = unittest.defaultTestLoader.discover(str(Path(__file__).resolve().parent / "tests"))
    result = unittest.TextTestRunner(stream=sys.stdout, verbosity=2).run(suite)
    print(json.dumps({"status": "PASS" if result.wasSuccessful() else "FAIL", "tests_run": result.testsRun,
        "failures": len(result.failures), "errors": len(result.errors), "skipped": len(result.skipped),
        "scope": "STATIC_DOCUMENT_AND_BYTE_PRESERVATION_ONLY", "production_go": False}, sort_keys=True))
    raise SystemExit(0 if result.wasSuccessful() else 1)
