"""Local pytest guard only; no production integration."""
import socket
def denied(*args,**kwargs):
 raise RuntimeError("SYS19_NETWORK_DISABLED")
def pytest_configure(config):
 socket.socket.connect=denied
 socket.socket.connect_ex=denied
 socket.getaddrinfo=denied
