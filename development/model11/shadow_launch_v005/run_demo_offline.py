"""Reproduce the invented 12-race demo with network calls blocked in-process."""
import json
from pathlib import Path
import platform
import socket
import sqlite3
import ssl
import sys


def blocked(*args, **kwargs):
    raise AssertionError("NETWORK_DISABLED_DURING_SYNTHETIC_DEMO")


if __name__ == "__main__":
    socket.socket.connect = socket.create_connection = socket.getaddrinfo = blocked
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    print(json.dumps({"python": sys.version, "platform": platform.platform(),
        "openssl": ssl.OPENSSL_VERSION, "sqlite": sqlite3.sqlite_version,
        "data": "SYNTHETIC_ONLY", "network": "BLOCKED_IN_PROCESS",
        "production_go": False}, sort_keys=True), flush=True)
    from model11.shadow_launch.cli import main
    raise SystemExit(main(["demo", *sys.argv[1:]]))
