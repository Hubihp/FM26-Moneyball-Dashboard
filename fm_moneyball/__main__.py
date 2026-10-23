"""
Uruchomienie aplikacji:  py -m fm_moneyball   (Windows)   /   python3 -m fm_moneyball

Startuje lokalny serwer i otwiera przegladarke. Aplikacja dziala tylko na tym komputerze
(nasluchuje na 127.0.0.1), wiec moze czytac zapisy gry z dysku.
"""
import argparse
import logging
import socket
import sys
import threading
import webbrowser

# W pliku .exe (PyInstaller) okno konsoli znika od razu po bledzie - wtedy czekamy na Enter
ZAMROZONY = getattr(sys, "frozen", False)


def port_zajety(host, port):
    """Czy cos juz nasluchuje na porcie (np. aplikacja uruchomiona drugi raz)."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as gniazdo:
        gniazdo.settimeout(0.5)
        return gniazdo.connect_ex(("127.0.0.1" if host in ("0.0.0.0", "") else host, port)) == 0


def _zakoncz(komunikat):
    if ZAMROZONY:
        print(komunikat)
        input("Naciśnij Enter, aby zamknąć okno...")
        sys.exit(1)
    sys.exit(komunikat)


def main():
    if sys.version_info < (3, 12):
        _zakoncz(f"Potrzebny jest Python 3.12 lub nowszy (masz {sys.version.split()[0]}).")
    try:
        import uvicorn
    except ImportError:
        _zakoncz("Brakuje bibliotek. Zainstaluj je poleceniem:\n    py -m pip install -r requirements.txt")

    from fm_moneyball.serwer.api import utworz_aplikacje
    from fm_moneyball.serwer.stan import Stan

    parser = argparse.ArgumentParser(description="FM26 Moneyball - lokalny serwer aplikacji")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--bez-przegladarki", action="store_true", help="nie otwieraj przeglądarki")
    args = parser.parse_args()

    adres = f"http://{'localhost' if args.host in ('127.0.0.1', '0.0.0.0') else args.host}:{args.port}"
    if port_zajety(args.host, args.port):
        # aplikacja juz dziala (np. drugi dwuklik na .exe) - wystarczy otworzyc przegladarke
        print(f"FM26 Moneyball już działa pod adresem {adres} - otwieram przeglądarkę.")
        if not args.bez_przegladarki:
            webbrowser.open(adres)
        return

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    app = utworz_aplikacje(Stan())
    print(f"FM26 Moneyball działa pod adresem {adres}  "
          f"({'zamknięcie tego okna' if ZAMROZONY else 'Ctrl+C'} kończy aplikację)")
    if not args.bez_przegladarki:
        threading.Timer(1.5, lambda: webbrowser.open(adres)).start()
    try:
        uvicorn.run(app, host=args.host, port=args.port, log_level="warning")
    except Exception as e:      # np. brak uprawnien do portu - komunikat zamiast znikajacego okna
        _zakoncz(f"Nie udało się uruchomić serwera: {e}")


if __name__ == "__main__":
    main()
