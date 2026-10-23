"""Start aplikacji: drugi start przy dzialajacej instancji otwiera przegladarke zamiast bledu."""
import socket
import sys

from fm_moneyball import __main__ as start


def test_port_zajety_otwiera_przegladarke(monkeypatch):
    gniazdo = socket.socket()
    gniazdo.bind(("127.0.0.1", 0))
    gniazdo.listen()
    port = gniazdo.getsockname()[1]
    otwarte = []
    monkeypatch.setattr(start.webbrowser, "open", otwarte.append)
    monkeypatch.setattr(sys, "argv", ["fm_moneyball", "--port", str(port)])
    try:
        assert start.port_zajety("127.0.0.1", port)
        start.main()          # konczy sie bez uruchamiania serwera
    finally:
        gniazdo.close()
    assert otwarte == [f"http://localhost:{port}"]
    assert not start.port_zajety("127.0.0.1", port)
