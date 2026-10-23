"""
Uruchomienie aplikacji:  py -m fm_moneyball   (Windows)   /   python3 -m fm_moneyball

Startuje lokalny serwer i otwiera przegladarke. Aplikacja dziala tylko na tym komputerze
(nasluchuje na 127.0.0.1), wiec moze czytac zapisy gry z dysku.
"""
import argparse
import logging
import sys
import threading
import webbrowser


def main():
    if sys.version_info < (3, 12):
        sys.exit(f"Potrzebny jest Python 3.12 lub nowszy (masz {sys.version.split()[0]}).")
    try:
        import uvicorn
    except ImportError:
        sys.exit("Brakuje bibliotek. Zainstaluj je poleceniem:\n    py -m pip install -r requirements.txt")

    from fm_moneyball.serwer.api import utworz_aplikacje
    from fm_moneyball.serwer.stan import Stan

    parser = argparse.ArgumentParser(description="FM26 Moneyball - lokalny serwer aplikacji")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--bez-przegladarki", action="store_true", help="nie otwieraj przeglądarki")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    app = utworz_aplikacje(Stan())
    adres = f"http://{'localhost' if args.host in ('127.0.0.1', '0.0.0.0') else args.host}:{args.port}"
    print(f"FM26 Moneyball działa pod adresem {adres}  (Ctrl+C kończy)")
    if not args.bez_przegladarki:
        threading.Timer(1.5, lambda: webbrowser.open(adres)).start()
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
