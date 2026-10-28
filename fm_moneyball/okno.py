"""
Program we wlasnym oknie (pywebview + WebView2 w Windows) zamiast przegladarki i konsoli.

- Okno pojawia sie od razu z ekranem ladowania; ciezkie biblioteki (pandas, FastAPI) laduja sie
  w tle, potem startuje serwer (uvicorn, watek w tle) i okno przechodzi do interfejsu.
  Czasy etapow trafiaja do dziennika ("Czas startu: ...").
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
<div style="text-align:center"><h2 style="color:#38d9a9;margin:0 0 8px">FM26 Moneyball</h2>
<div id="etap">Uruchamianie...</div></div>
</body></html>"""
ETAPY = {}          # nazwa etapu -> sekundy od startu procesu (do dziennika i /api/system/gotowe)


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


def etap(nazwa, start):
    ETAPY[nazwa] = round(time.time() - start, 2)


def uruchom(utworz_app, host, port, start):
    """
    Okno programu od razu, a w tle: utworz_app() (ciezkie importy), serwer i przejscie do interfejsu.
    Wraca po zamknieciu okna.
    """
    import webview

    adres = f"http://localhost:{port}"
    okno = webview.create_window(f"FM26 Moneyball {__version__}", html=EKRAN_LADOWANIA, width=1500, height=950,
                                 min_size=(1100, 700), text_select=True)
    serwer = None

    def pokaz(tekst):
        try:
            okno.evaluate_js(f"document.getElementById('etap').textContent = {tekst!r}")
        except Exception:
            pass        # okno jeszcze niegotowe - ekran ladowania i tak sie zmieni

    def zamknij_program():
        # wywolywane przez instalator aktualizacji: zamkniecie okna konczy program
        try:
            okno.destroy()
        finally:
            os._exit(0)

    def po_starcie():
        nonlocal serwer
        etap("okno", start)
        try:
            pokaz("Ładowanie bibliotek...")
            import uvicorn
            app = utworz_app()
            etap("biblioteki", start)
            app.state.aktualizacje.zamknij_program = zamknij_program
            pokaz("Uruchamianie serwera...")
            serwer = uvicorn.Server(uvicorn.Config(app, host=host, port=port, log_config=None, log_level="warning"))
            threading.Thread(target=serwer.run, daemon=True, name="serwer").start()
        except Exception as e:
            log.exception("Start programu nie powiódł się")
            komunikat(f"Nie udało się uruchomić programu: {e}\n\nSzczegóły w pliku {KATALOG_LOGOW / 'aplikacja.log'}.")
            okno.destroy()
            return
        if _czekaj_na_serwer(adres):
            etap("serwer", start)
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
    if serwer is not None:
        serwer.should_exit = True
