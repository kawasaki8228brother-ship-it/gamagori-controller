"""Run tests with existing dependencies, disabled network/cache, no app start."""
import argparse
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import socket
import ssl
import sqlite3
import sys
import xml.etree.ElementTree as ET


def blocked(*args, **kwargs):
    raise AssertionError("NETWORK_DISABLED_DURING_HEALTH_SYNTHETIC_TESTS")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--junit-output", type=Path, required=True)
    args = parser.parse_args()
    repository, report = args.repo.resolve(), args.junit_output.resolve()
    socket.socket.connect = socket.socket.connect_ex = socket.create_connection = socket.getaddrinfo = blocked
    os.environ["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"  # Process-local guard only.
    os.environ.pop("PYTEST_ADDOPTS", None)
    sys.dont_write_bytecode = True
    os.chdir(repository)
    sys.path.insert(0, str(repository))
    names = ("pytest", "pytest-asyncio", "httpx", "beautifulsoup4", "pydantic", "certifi")
    print("HEALTH_OFFLINE_SYNTHETIC_TESTS", flush=True)
    print(json.dumps({"python": sys.version, "platform": platform.platform(), "openssl": ssl.OPENSSL_VERSION, "sqlite": sqlite3.sqlite_version,
        "packages": {name: importlib.metadata.version(name) for name in names},
        "network": "BLOCKED_IN_PROCESS", "http_transport": "MOCKED_ONLY_NO_REAL_SOURCE_OR_TLS_TEST",
        "dependencies_installed_or_changed": False, "production_go": False}, sort_keys=True), flush=True)
    import pytest
    class SessionTotals:
        collected = None
        categories = None
        def pytest_sessionfinish(self, session, exitstatus):
            self.collected = session.testscollected
            reporter = session.config.pluginmanager.getplugin("terminalreporter")
            self.categories = {key: len(value) for key, value in reporter.stats.items()
                               if key in ("passed", "failed", "error", "skipped", "subtests passed", "subtests failed")}
    totals = SessionTotals()
    exit_code = pytest.main(["-p", "pytest_asyncio.plugin", "-p", "no:cacheprovider", "-q", "--tb=short",
                             "--junitxml=" + str(report), "tests"], plugins=[totals])
    counts = {"tests": None, "failures": None, "errors": None, "skipped": None}
    if report.is_file():
        tree = ET.parse(report).getroot()
        suites = list(tree) if tree.tag == "testsuites" else [tree]
        counts = {key: sum(int(suite.get(key, "0")) for suite in suites) for key in counts}
    junit_count = counts["tests"]
    counts["tests"] = totals.collected
    print(json.dumps({"status": ("PASS_WITH_UNVERIFIED_SKIPS" if counts["skipped"] else "PASS") if exit_code == 0 else "FAIL", **counts,
        "pytest_result_categories": totals.categories, "junit_testcase_records_including_subtests": junit_count,
        "exit_code": int(exit_code), "scope": "ISOLATED_SYNTHETIC_AND_PRESERVED_BASE_TESTS_ONLY",
        "actual_11_05_source": "NOT_OBTAINED", "unexecuted_tests": "UNVERIFIED_NOT_PASS", "production_go": False}, sort_keys=True))
    raise SystemExit(int(exit_code))
