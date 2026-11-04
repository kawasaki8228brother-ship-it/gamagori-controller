"""Run stdlib tests offline, record actual runtime and exit nonzero on failure."""
import json
import platform
import socket
import ssl
import sys
import unittest


def blocked(*args, **kwargs):
    raise AssertionError("NETWORK_DISABLED_DURING_SYNTHETIC_TESTS")


if __name__ == "__main__":
    socket.create_connection = blocked
    socket.socket.connect = blocked
    print("MODEL11_SYNTHETIC_OFFLINE_TESTS", flush=True)
    print(json.dumps({"python": sys.version, "platform": platform.platform(),
                      "openssl": ssl.OPENSSL_VERSION, "network": "BLOCKED_IN_PROCESS",
                      "data": "SYNTHETIC_ONLY", "production_go": False}, sort_keys=True), flush=True)
    suite = unittest.defaultTestLoader.discover("tests")
    result = unittest.TextTestRunner(stream=sys.stdout, verbosity=2).run(suite)
    print(json.dumps({"tests_run": result.testsRun, "failures": len(result.failures),
                      "errors": len(result.errors), "skipped": len(result.skipped),
                      "status": "PASS" if result.wasSuccessful() else "FAIL",
                      "scope": "SYNTHETIC_SOFTWARE_ONLY", "real_performance": "UNVERIFIED"}, sort_keys=True))
    raise SystemExit(0 if result.wasSuccessful() else 1)
