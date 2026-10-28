"""
Uruchomienie aplikacji:  py -m fm_moneyball   (Windows)   /   python3 -m fm_moneyball

Domyslnie program otwiera sie we wlasnym oknie (pywebview); gdy pywebview nie jest zainstalowany
albo podano --przegladarka - w przegladarce. Aplikacja dziala tylko na tym komputerze
(nasluchuje na 127.0.0.1), wiec moze czytac zapisy gry z dysku.
"""
import argparse
import importlib.util
import logging
import socket
import sys
import threading
import webbrowser

# W pliku .exe (PyInstaller) bez konsoli komunikaty pokazuje okienko, nie print/input
ZAMROZONY = getattr(sys, "frozen", False)
BEZ_KONSOLI = ZAMROZONY and sys.stdout is None


def port_zajety(host, port):
    """Czy cos juz nasluchuje na porcie (np. aplikacja uruchomiona drugi raz)."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as gniazdo:
        gniazdo.settimeout(0.5)
        return gniazdo.connect_ex(("127.0.0.1" if host in ("0.0.0.0", "") else host, port)) == 0


def _zakoncz(komunikat):
    if BEZ_KONSOLI:
        from fm_moneyball.okno import komunikat as okienko
        okienko(komunikat)
        sys.exit(1)
    if ZAMROZONY:
        print(komunikat)
        input("Naciśnij Enter, aby zamknąć okno...")
        sys.exit(1)
    sys.exit(komunikat)


def _jest_pywebview():
    return importlib.util.find_spec("webview") is not None


def main():
    if sys.version_info < (3, 12):
        _zakoncz(f"Potrzebny jest Python 3.12 lub nowszy (masz {sys.version.split()[0]}).")
    try:
        import uvicorn
    except ImportError:
        _zakoncz("Brakuje bibliotek. Zainstaluj je poleceniem:\n    py -m pip install -r requirements.txt")

    parser = argparse.ArgumentParser(description="FM26 Moneyball - lokalny serwer aplikacji")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--przegladarka", action="store_true", help="otwórz w przeglądarce zamiast w oknie")
    parser.add_argument("--bez-przegladarki", action="store_true", help="tylko serwer: bez okna i przeglądarki")
    args = parser.parse_args()
    w_oknie = not args.przegladarka and not args.bez_przegladarki and _jest_pywebview()

    if BEZ_KONSOLI or w_oknie:
        from fm_moneyball.okno import ustaw_dziennik
        ustaw_dziennik()
    else:
        logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    adres = f"http://{'localhost' if args.host in ('127.0.0.1', '0.0.0.0') else args.host}:{args.port}"
    if port_zajety(args.host, args.port):
        if w_oknie or BEZ_KONSOLI:
            _zakoncz("FM26 Moneyball już działa (okno może być zminimalizowane na pasku zadań).")
        # tryb przegladarki: aplikacja juz dziala (np. drugi start) - wystarczy otworzyc przegladarke
        print(f"FM26 Moneyball już działa pod adresem {adres} - otwieram przeglądarkę.")
        if not args.bez_przegladarki:
            webbrowser.open(adres)
        return

    from fm_moneyball.aktualizacje import Aktualizacje
    from fm_moneyball.serwer.api import utworz_aplikacje
    from fm_moneyball.serwer.stan import Stan

    aktualizacje = Aktualizacje()
    app = utworz_aplikacje(Stan(), aktualizacje=aktualizacje, okno={"okno": w_oknie, "port": args.port})
    aktualizacje.sprawdz_w_tle()
    if w_oknie:
        from fm_moneyball.okno import uruchom
        uruchom(app, args.host, args.port)
        return

    print(f"FM26 Moneyball działa pod adresem {adres}  "
          f"({'zamknięcie tego okna' if ZAMROZONY else 'Ctrl+C'} kończy aplikację)")
    if not args.bez_przegladarki:
        threading.Timer(1.5, lambda: webbrowser.open(adres)).start()
    try:
        bez_logow_konsoli = {"log_config": None} if BEZ_KONSOLI else {}
        uvicorn.run(app, host=args.host, port=args.port, log_level="warning", **bez_logow_konsoli)
    except Exception as e:      # np. brak uprawnien do portu - komunikat zamiast znikajacego okna
        _zakoncz(f"Nie udało się uruchomić serwera: {e}")


if __name__ == "__main__":
    main()
