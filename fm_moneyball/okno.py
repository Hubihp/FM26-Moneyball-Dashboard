"""
Program we wlasnym oknie (pywebview + WebView2 w Windows) zamiast przegladarki i konsoli.

- Serwer (uvicorn) dziala w watku w tle; okno pokazuje ekran ladowania, dopoki serwer nie odpowie.
- Bez konsoli (PyInstaller console=False) sys.stdout/stderr to None - wszystko idzie do dziennika
  ~/.fm_moneyball/logi/aplikacja.log, a bledy startu do okienka komunikatu.
- Dane okna (localStorage WebView2) sa w ~/.fm_moneyball/webview, a pamiec interfejsu w pamiec.json -
  oba poza folderem programu, wiec aktualizacja ich nie nadpisuje.
- Zamkniecie okna konczy program.
"""
import logging
import logging.handlers
import os
import sys
import threading
import time
import urllib.request

from fm_moneyball import __version__
from fm_moneyball.mapy import KATALOG_DOMOWY

log = logging.getLogger("fm_moneyball")

KATALOG_LOGOW = KATALOG_DOMOWY / "logi"
KATALOG_WEBVIEW = KATALOG_DOMOWY / "webview"
ADRES_WEBVIEW2 = "https://developer.microsoft.com/microsoft-edge/webview2/"
EKRAN_LADOWANIA = """<html><body style="background:#1a1b1e;color:#c1c2c5;font-family:Segoe UI,sans-serif;
display:flex;align-items:center;justify-content:center;height:100vh;margin:0">
<div style="text-align:center"><h2 style="color:#38d9a9;margin:0 0 8px">FM26 Moneyball</h2>Uruchamianie...</div>
</body></html>"""


def ustaw_dziennik():
    """Dziennik do pliku (rotacja 3 x 2 MB); bez konsoli takze stdout/stderr trafiaja do niego."""
    KATALOG_LOGOW.mkdir(parents=True, exist_ok=True)
    plik = KATALOG_LOGOW / "aplikacja.log"
    obsluga = logging.handlers.RotatingFileHandler(plik, maxBytes=2 * 2**20, backupCount=3, encoding="utf-8")
    obsluga.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    logging.basicConfig(level=logging.INFO, handlers=[obsluga], force=True)
    if sys.stdout is None or sys.stderr is None:
        strumien = open(plik.with_name("wyjscie.log"), "a", encoding="utf-8", buffering=1)
        sys.stdout = sys.stdout or strumien
        sys.stderr = sys.stderr or strumien
    log.info("FM26 Moneyball %s - start", __version__)


def komunikat(tekst, tytul="FM26 Moneyball"):
    """Okienko komunikatu Windows (bez konsoli print jest niewidoczny)."""
    log.warning(tekst)
    if sys.platform == "win32":
        import ctypes
        ctypes.windll.user32.MessageBoxW(None, tekst, tytul, 0x40)
    else:
        print(tekst, file=sys.stderr)


def _czekaj_na_serwer(adres, limit=60):
    koniec = time.time() + limit
    while time.time() < koniec:
        try:
            with urllib.request.urlopen(adres + "/api/system", timeout=2):
                return True
        except Exception:
            time.sleep(0.2)
    return False


def uruchom(app, host, port):
    """Serwer w tle + okno programu. Wraca po zamknieciu okna."""
    import uvicorn
    import webview

    serwer = uvicorn.Server(uvicorn.Config(app, host=host, port=port, log_config=None, log_level="warning"))
    watek = threading.Thread(target=serwer.run, daemon=True, name="serwer")
    watek.start()
    adres = f"http://localhost:{port}"
    okno = webview.create_window(f"FM26 Moneyball {__version__}", html=EKRAN_LADOWANIA, width=1500, height=950,
                                 min_size=(1100, 700), text_select=True)

    def zamknij_program():
        # wywolywane przez instalator aktualizacji: zamkniecie okna konczy program
        try:
            okno.destroy()
        finally:
            os._exit(0)

    app.state.aktualizacje.zamknij_program = zamknij_program

    def po_starcie():
        if _czekaj_na_serwer(adres):
            okno.load_url(adres)
        else:
            komunikat("Serwer aplikacji nie wystartował. Szczegóły w pliku "
                      f"{KATALOG_LOGOW / 'aplikacja.log'}.")
            okno.destroy()

    KATALOG_WEBVIEW.mkdir(parents=True, exist_ok=True)
    try:
        webview.start(po_starcie, private_mode=False, storage_path=str(KATALOG_WEBVIEW))
    except Exception as e:
        log.exception("Nie udało się otworzyć okna")
        komunikat("Nie udało się otworzyć okna programu (brak składnika Microsoft Edge WebView2?).\n\n"
                  f"Zainstaluj WebView2 Runtime: {ADRES_WEBVIEW2}\n\nSzczegóły: {e}")
    serwer.should_exit = True
