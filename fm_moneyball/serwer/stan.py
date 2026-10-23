"""
Stan serwera: wybrane zrodlo danych, wczytane pule zawodnikow, wczytywanie w tle i sledzenie
folderu zapisow.

Odczyt zapisu FM26 trwa kilkadziesiat sekund, wiec dzieje sie w osobnym watku; interfejs pyta
o stan (albo slucha zdarzen SSE) i odswieza sie, gdy `wersja` wzrosnie.
"""
import json
import logging
import threading
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

from fm_moneyball.stale import POZYCJE
from fm_moneyball.zrodla import folder as folder_zapisow
from fm_moneyball.zrodla.csv_fm import generuj_demo_csv, wczytaj_csv
from fm_moneyball.zrodla.zapis_fm import PLIK_NAZW_ROZGRYWEK, OpcjeZapisu, wczytaj_zapis

log = logging.getLogger("fm_moneyball")

PLIK_USTAWIEN = Path.home() / ".fm_moneyball" / "ustawienia.json"
CO_ILE_SPRAWDZAC = 15   # sekundy miedzy sprawdzeniami folderu zapisow


@dataclass
class Konfiguracja:
    typ: str = "brak"              # brak | folder | plik | demo
    folder: str | None = None      # folder zapisow (typ folder)
    plik: str | None = None        # konkretny zapis; w trybie folderu None = zawsze najnowszy
    sledz: bool = True             # sledzenie nowych zapisow w folderze
    opcje: dict = field(default_factory=lambda: asdict(OpcjeZapisu()))

    def opcje_zapisu(self):
        znane = OpcjeZapisu.__dataclass_fields__
        return OpcjeZapisu(**{k: v for k, v in self.opcje.items() if k in znane})


def _wersja_nazw_lig():
    try:
        return PLIK_NAZW_ROZGRYWEK.stat().st_mtime
    except OSError:
        return 0.0


class Stan:
    def __init__(self, plik_ustawien=PLIK_USTAWIEN, sledzenie=True):
        self._blokada = threading.RLock()
        self._blokada_wczytywania = threading.Lock()
        self.plik_ustawien = Path(plik_ustawien) if plik_ustawien else None
        self.konfig = self._wczytaj_ustawienia()
        self.dane = {}
        self.meta = {}
        self.status = "pusto"          # pusto | wczytywanie | gotowe | blad
        self.komunikat = ""
        self.wersja = 0
        self._klucz = None             # (sciezka, mtime, rozmiar, opcje, wersja nazw) wczytanego zapisu
        self._zatrzymaj = threading.Event()
        self._watek = None
        if sledzenie:
            self._watek = threading.Thread(target=self._petla_sledzenia, daemon=True, name="sledzenie-zapisow")
            self._watek.start()

    # --- ustawienia ----------------------------------------------------------------------------
    def _wczytaj_ustawienia(self):
        if self.plik_ustawien and self.plik_ustawien.is_file():
            try:
                dane = json.loads(self.plik_ustawien.read_text(encoding="utf-8"))
                konfig = Konfiguracja(**{k: v for k, v in dane.items() if k in Konfiguracja.__dataclass_fields__})
                konfig.opcje = {**asdict(OpcjeZapisu()), **konfig.opcje}
                return konfig
            except Exception:
                log.warning("Nie udało się odczytać ustawień, używam domyślnych.")
        domyslny = folder_zapisow.domyslny_folder()
        if domyslny:
            return Konfiguracja(typ="folder", folder=str(domyslny))
        return Konfiguracja()

    def _zapisz_ustawienia(self):
        if not self.plik_ustawien:
            return
        try:
            self.plik_ustawien.parent.mkdir(parents=True, exist_ok=True)
            self.plik_ustawien.write_text(json.dumps(asdict(self.konfig), ensure_ascii=False, indent=1),
                                          encoding="utf-8")
        except OSError:
            log.warning("Nie udało się zapisać ustawień.")

    # --- publiczne API -------------------------------------------------------------------------
    def migawka(self):
        with self._blokada:
            return {
                "status": self.status, "komunikat": self.komunikat, "wersja": self.wersja,
                "zrodlo": asdict(self.konfig), "meta": self.meta,
                "pozycje": {p: len(self.dane[p]) for p in POZYCJE if p in self.dane},
            }

    def pula(self, pozycja):
        with self._blokada:
            return self.dane.get(pozycja)

    def ustaw_zrodlo(self, typ, folder=None, plik=None, sledz=None, opcje=None, w_tle=True):
        with self._blokada:
            self.konfig.typ = typ
            if folder is not None:
                self.konfig.folder = folder
            self.konfig.plik = plik
            if sledz is not None:
                self.konfig.sledz = sledz
            if opcje:
                self.konfig.opcje = {**self.konfig.opcje, **opcje}
            self._klucz = None
            self._zapisz_ustawienia()
        self.przeladuj(w_tle=w_tle)

    def przeladuj(self, w_tle=True, wymus=False):
        if wymus:
            with self._blokada:
                self._klucz = None
        if w_tle:
            threading.Thread(target=self._wczytaj, daemon=True, name="wczytywanie").start()
        else:
            self._wczytaj()

    def zatrzymaj(self):
        self._zatrzymaj.set()

    # --- wczytywanie ---------------------------------------------------------------------------
    def _ustaw(self, **pola):
        with self._blokada:
            for k, v in pola.items():
                setattr(self, k, v)

    def _sciezka_zapisu(self):
        """(sciezka do odczytu, opis) dla trybu folder/plik albo (None, komunikat bledu)."""
        konfig = self.konfig
        if konfig.typ == "plik":
            if konfig.plik and Path(konfig.plik).is_file():
                return Path(konfig.plik), Path(konfig.plik).name
            return None, "Nie znaleziono wgranego pliku zapisu."
        if konfig.plik:
            zapis = next((p for p in folder_zapisow.lista_zapisow(konfig.folder or "")
                          if str(p.sciezka) == konfig.plik), None)
        else:
            zapis = folder_zapisow.najnowszy_zapis(konfig.folder or "")
        if zapis is None:
            return None, "Nie znaleziono plików .fm w folderze zapisów."
        if not folder_zapisow.czy_stabilny(zapis.sciezka, odstep=0.5):
            return None, "Gra właśnie zapisuje plik - spróbuję ponownie za chwilę."
        return folder_zapisow.bezpieczna_kopia(zapis), zapis.nazwa

    def _wczytaj(self):
        if not self._blokada_wczytywania.acquire(blocking=False):
            return   # wczytywanie juz trwa; petla sledzenia sprobuje ponownie
        try:
            konfig = self.konfig
            if konfig.typ == "brak":
                self._ustaw(status="pusto", komunikat="Wybierz źródło danych.")
                return
            if konfig.typ == "demo":
                if self._klucz == ("demo",):
                    return
                self._ustaw(status="wczytywanie", komunikat="Generowanie danych demo...")
                dane = {p: wczytaj_csv(generuj_demo_csv(p))[0] for p in POZYCJE}
                self._zakoncz(("demo",), dane, {"nazwa_zapisu": "Dane demo (syntetyczne)", "demo": True})
                return
            sciezka, opis = self._sciezka_zapisu()
            if sciezka is None:
                if self.status != "gotowe":
                    self._ustaw(status="blad", komunikat=opis)
                return
            stat = sciezka.stat()
            klucz = (str(sciezka), stat.st_mtime, stat.st_size, json.dumps(konfig.opcje, sort_keys=True),
                     _wersja_nazw_lig())
            if klucz == self._klucz:
                return
            self._ustaw(status="wczytywanie", komunikat=f"Odczyt zapisu {opis} (zwykle 30-60 s)...")
            start = time.perf_counter()
            wynik = wczytaj_zapis(sciezka, konfig.opcje_zapisu())
            meta = {
                "nazwa_zapisu": wynik.nazwa_zapisu, "plik": opis, "build": wynik.build,
                "data_gry": wynik.data_gry.isoformat() if wynik.data_gry else None,
                "moj_klub": wynik.moj_klub, "moj_klub_uid": wynik.moj_klub_uid,
                "ostrzezenia": wynik.ostrzezenia, "liczniki": wynik.liczniki,
                "czas_odczytu_s": round(time.perf_counter() - start, 1),
                "wczytano": datetime.now().isoformat(timespec="seconds"),
            }
            self._zakoncz(klucz, wynik.dane, meta)
        except Exception as e:
            log.exception("Błąd wczytywania danych")
            self._ustaw(status="blad", komunikat=f"Nie udało się wczytać danych: {e}")
        finally:
            self._blokada_wczytywania.release()

    def _zakoncz(self, klucz, dane, meta):
        with self._blokada:
            self.dane, self.meta, self._klucz = dane, meta, klucz
            self.status, self.komunikat = "gotowe", ""
            self.wersja += 1

    # --- sledzenie folderu ---------------------------------------------------------------------
    def _petla_sledzenia(self):
        self.przeladuj(w_tle=False)
        while not self._zatrzymaj.wait(CO_ILE_SPRAWDZAC):
            konfig = self.konfig
            if konfig.typ == "folder" and konfig.sledz and not konfig.plik:
                self._wczytaj()   # nic nie robi, gdy najnowszy zapis sie nie zmienil
