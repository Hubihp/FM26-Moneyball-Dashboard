"""
Stan serwera: wybrane zrodlo danych, wczytane pule zawodnikow, wczytywanie w tle, cache na dysku
i sledzenie folderu zapisow.

- Nic nie jest wczytywane przy starcie (chyba ze wlaczono `wczytaj_przy_starcie`) - uzytkownik
  wybiera zrodlo w interfejsie.
- Wczytywanie odbywa sie w jednym watku roboczym. Kazda zmiana zrodla zwieksza `pokolenie`;
  wynik wczytany dla starszego pokolenia jest odrzucany i wczytywanie rusza od nowa.
- Odczytany zapis trafia do cache (~/.fm_moneyball/cache), wiec ponowne otwarcie tego samego
  stanu zapisu - takze po restarcie - jest natychmiastowe.
- Nazwy i mnozniki lig sa nakladane po wczytaniu (schemat.ustaw_ligi), wiec ich edycja nie wymaga
  ponownego odczytu zapisu.
"""
import hashlib
import json
import logging
import pickle
import threading
import time
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from pathlib import Path

from fm_moneyball.ligi import PLIK_MNOZNIKOW, wszystkie_mnozniki
from fm_moneyball.schemat import ustaw_ligi
from fm_moneyball.stale import POZYCJE
from fm_moneyball.zrodla import folder as folder_zapisow
from fm_moneyball.zrodla.csv_fm import generuj_demo_csv, wczytaj_csv
from fm_moneyball.zrodla.zapis_fm import (ETAPY_WCZYTYWANIA, PLIK_NAZW_ROZGRYWEK, OpcjeZapisu, wczytaj_nazwy_rozgrywek,
                                         wczytaj_zapis)

log = logging.getLogger("fm_moneyball")

KATALOG_DOMOWY = Path.home() / ".fm_moneyball"
CO_ILE_SPRAWDZAC = 15        # sekundy miedzy sprawdzeniami folderu zapisow
WERSJA_CACHE = 3             # zmiana formatu wyniku = nowy klucz cache
ILE_W_CACHE = 3
DEMO_DATA_GRY = date(2027, 1, 15)


@dataclass
class Konfiguracja:
    typ: str = "brak"              # brak | folder | plik | demo
    folder: str | None = None      # folder zapisow (typ folder)
    plik: str | None = None        # konkretny zapis; w trybie folderu None = zawsze najnowszy
    sledz: bool = True             # sledzenie nowych zapisow w folderze
    wczytaj_przy_starcie: bool = False
    moj_klub_uid: int | None = None   # wybrany recznie, gdy prowadzimy kilka druzyn
    opcje: dict = field(default_factory=lambda: asdict(OpcjeZapisu()))

    def opcje_zapisu(self):
        znane = OpcjeZapisu.__dataclass_fields__
        return OpcjeZapisu(**{k: v for k, v in self.opcje.items() if k in znane})


def _demo():
    """Dane demo z 'moim klubem' i data w grze, zeby wyroznienie i analiza kadry dzialaly."""
    dane = {}
    kluby = {}
    for p in POZYCJE:
        df = wczytaj_csv(generuj_demo_csv(p))[0]
        for klub in sorted(df['Klub'].dropna().unique()):
            kluby.setdefault(klub, 1000 + len(kluby))
        df['Klub_UID'] = df['Klub'].map(kluby)
        dane[p] = df
    moj = "Premier FC 1" if "Premier FC 1" in kluby else next(iter(kluby))
    meta = {"nazwa_zapisu": "Dane demo (syntetyczne)", "demo": True, "data_gry": DEMO_DATA_GRY.isoformat(),
            "moje_kluby": [{"uid": kluby[moj], "nazwa": moj}]}
    return dane, meta


class Stan:
    def __init__(self, plik_ustawien=KATALOG_DOMOWY / "ustawienia.json", sledzenie=True,
                 katalog_cache=KATALOG_DOMOWY / "cache", plik_nazw=PLIK_NAZW_ROZGRYWEK, plik_mnoznikow=PLIK_MNOZNIKOW):
        self._blokada = threading.RLock()
        self._blokada_wczytywania = threading.Lock()
        self.plik_ustawien = Path(plik_ustawien) if plik_ustawien else None
        self.katalog_cache = Path(katalog_cache) if katalog_cache else None
        self.plik_nazw, self.plik_mnoznikow = Path(plik_nazw), Path(plik_mnoznikow)
        self.konfig = self._wczytaj_ustawienia()
        self.surowe = {}               # ramki prosto ze zrodla (przed nalozeniem nazw lig)
        self.dane = {}
        self.meta = {}
        self.ligi = []                 # podsumowanie lig z zapisu
        self.status = "pusto"          # pusto | wczytywanie | gotowe | blad
        self.komunikat = "Wybierz źródło danych."
        self.etap = None               # {"nr", "z", "nazwa", "start"} podczas wczytywania
        self.wersja = 0
        self.pokolenie = 0
        self.aktywny = self.konfig.wczytaj_przy_starcie and self.konfig.typ != "brak"
        self._klucz = None
        self._sciezka_odczytu = None
        self._sygnal = threading.Event()
        self._zatrzymaj = threading.Event()
        self._sledzenie = sledzenie
        self._watek = threading.Thread(target=self._petla, daemon=True, name="wczytywanie")
        self._watek.start()
        if self.aktywny:
            self._sygnal.set()

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
        return Konfiguracja(folder=str(domyslny) if domyslny else None)

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
                "status": self.status, "komunikat": self.komunikat, "wersja": self.wersja, "etap": self.etap,
                "zrodlo": asdict(self.konfig), "meta": self.meta,
                "pozycje": {p: len(self.dane[p]) for p in POZYCJE if p in self.dane},
            }

    def pula(self, pozycja):
        with self._blokada:
            return self.dane.get(pozycja)

    def ustaw_zrodlo(self, typ, folder=None, plik=None, sledz=None, opcje=None, wczytaj_przy_starcie=None,
                     w_tle=True):
        with self._blokada:
            self.konfig.typ = typ
            if folder is not None:
                self.konfig.folder = folder
            self.konfig.plik = plik
            if sledz is not None:
                self.konfig.sledz = sledz
            if wczytaj_przy_starcie is not None:
                self.konfig.wczytaj_przy_starcie = wczytaj_przy_starcie
            if opcje:
                self.konfig.opcje = {**self.konfig.opcje, **opcje}
            self.pokolenie += 1
            self.aktywny = True
            self._klucz = None
            self._zapisz_ustawienia()
        self.przeladuj(w_tle=w_tle)

    def przeladuj(self, w_tle=True, wymus=False):
        if wymus:
            with self._blokada:
                self._klucz = None
                self.pokolenie += 1
        if w_tle:
            self._sygnal.set()
        else:
            self._wczytaj()

    def ustaw_moj_klub(self, uid):
        with self._blokada:
            self.konfig.moj_klub_uid = uid
            self._zapisz_ustawienia()
            self._uzupelnij_moj_klub()
            self.wersja += 1

    def zastosuj_ligi(self):
        """Ponownie naklada nazwy i mnozniki lig na wczytane dane (po ich edycji)."""
        with self._blokada:
            self._zastosuj_ligi()
            self.wersja += 1

    def zatrzymaj(self):
        self._zatrzymaj.set()
        self._sygnal.set()

    # --- watek roboczy -------------------------------------------------------------------------
    def _petla(self):
        while not self._zatrzymaj.is_set():
            obudzony = self._sygnal.wait(CO_ILE_SPRAWDZAC)
            if self._zatrzymaj.is_set():
                return
            self._sygnal.clear()
            konfig = self.konfig
            sledzenie = (self._sledzenie and self.aktywny and konfig.typ == "folder" and konfig.sledz
                         and not konfig.plik)
            if obudzony or sledzenie:
                self._wczytaj()   # w trybie sledzenia nic nie robi, gdy najnowszy zapis sie nie zmienil

    def _ustaw(self, **pola):
        with self._blokada:
            for k, v in pola.items():
                setattr(self, k, v)

    def _postep(self, nr, nazwa):
        with self._blokada:
            start = self.etap["start"] if self.etap else time.time()
            self.etap = {"nr": nr, "z": len(ETAPY_WCZYTYWANIA), "nazwa": nazwa, "start": start}
            self.komunikat = f"Odczyt zapisu: {nazwa} ({nr + 1}/{len(ETAPY_WCZYTYWANIA)})"

    def _znajdz_zapis(self):
        """(oryginalny plik zapisu, opis) albo (None, komunikat bledu)."""
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
        return zapis.sciezka, zapis.nazwa

    def _plik_cache(self, klucz):
        if not self.katalog_cache:
            return None
        return self.katalog_cache / (hashlib.sha1(repr(klucz).encode()).hexdigest() + ".pkl")

    def _z_cache(self, klucz):
        plik = self._plik_cache(klucz)
        if plik and plik.is_file():
            try:
                with open(plik, "rb") as f:
                    return pickle.load(f)
            except Exception:
                log.warning("Uszkodzony plik cache - wczytuję zapis od nowa.")
        return None

    def _do_cache(self, klucz, wynik):
        plik = self._plik_cache(klucz)
        if not plik:
            return
        try:
            plik.parent.mkdir(parents=True, exist_ok=True)
            with open(plik.with_suffix(".tmp"), "wb") as f:
                pickle.dump(wynik, f, protocol=pickle.HIGHEST_PROTOCOL)
            plik.with_suffix(".tmp").replace(plik)
            for stary in sorted(plik.parent.glob("*.pkl"), key=lambda p: p.stat().st_mtime, reverse=True)[ILE_W_CACHE:]:
                stary.unlink(missing_ok=True)
        except OSError:
            log.warning("Nie udało się zapisać cache.")

    def _wczytaj(self):
        with self._blokada_wczytywania:
            while True:
                pokolenie = self.pokolenie
                try:
                    gotowe = self._wczytaj_raz(pokolenie)
                except Exception as e:
                    log.exception("Błąd wczytywania danych")
                    self._ustaw(status="blad", komunikat=f"Nie udało się wczytać danych: {e}", etap=None)
                    gotowe = True
                if gotowe or pokolenie == self.pokolenie:
                    return
                # w trakcie wczytywania zmieniono zrodlo - wczytaj od nowa dla nowej konfiguracji

    def _wczytaj_raz(self, pokolenie):
        """Zwraca False, gdy wynik jest nieaktualny (zmieniono zrodlo w trakcie)."""
        konfig = self.konfig
        if konfig.typ == "brak" or not self.aktywny:
            self._ustaw(status="pusto", komunikat="Wybierz źródło danych.", etap=None)
            return True
        if konfig.typ == "demo":
            if self._klucz == ("demo",):
                return True
            dane, meta = _demo()
            return self._zakoncz(pokolenie, ("demo",), dane, meta, [], None)

        oryginal, opis = self._znajdz_zapis()
        if oryginal is None:
            if self.status != "gotowe":
                self._ustaw(status="blad", komunikat=opis, etap=None)
            return True
        stat = oryginal.stat()
        klucz = (WERSJA_CACHE, str(oryginal), stat.st_mtime, stat.st_size, json.dumps(konfig.opcje, sort_keys=True))
        if klucz == self._klucz:
            return True

        start = time.time()
        wynik = self._z_cache(klucz)
        z_cache = wynik is not None
        if z_cache:
            sciezka_odczytu = str(oryginal)
        else:
            if konfig.typ == "folder" and not folder_zapisow.czy_stabilny(oryginal, odstep=0.5):
                # gra wlasnie zapisuje plik; petla sledzenia sprobuje ponownie przy nastepnym sprawdzeniu
                self._ustaw(komunikat="Gra właśnie zapisuje plik - spróbuję ponownie za chwilę.")
                return True
            if konfig.typ == "folder":
                kopia = folder_zapisow.bezpieczna_kopia(folder_zapisow.PlikZapisu(oryginal, stat.st_size, stat.st_mtime))
            else:
                kopia = oryginal
            sciezka_odczytu = str(kopia)
            self._ustaw(status="wczytywanie", etap={"nr": 0, "z": len(ETAPY_WCZYTYWANIA), "nazwa": "Start",
                                                     "start": start},
                        komunikat=f"Odczyt zapisu {opis}...")
            wynik = wczytaj_zapis(kopia, konfig.opcje_zapisu(), postep=self._postep)
            self._do_cache(klucz, wynik)
        meta = {
            "nazwa_zapisu": wynik.nazwa_zapisu, "plik": opis, "build": wynik.build,
            "data_gry": wynik.data_gry.isoformat() if wynik.data_gry else None,
            "moje_kluby": wynik.moje_kluby or ([{"uid": wynik.moj_klub_uid, "nazwa": wynik.moj_klub}]
                                               if wynik.moj_klub_uid is not None else []),
            "ostrzezenia": wynik.ostrzezenia, "liczniki": wynik.liczniki,
            "czas_odczytu_s": round(time.time() - start, 1),
            "z_cache": z_cache,
            "wczytano": datetime.now().isoformat(timespec="seconds"),
        }
        return self._zakoncz(pokolenie, klucz, wynik.dane, meta, wynik.ligi, sciezka_odczytu)

    def _zakoncz(self, pokolenie, klucz, dane, meta, ligi, sciezka_odczytu):
        with self._blokada:
            if pokolenie != self.pokolenie:
                return False
            self.surowe, self.meta, self.ligi, self._klucz = dane, meta, ligi, klucz
            self._sciezka_odczytu = sciezka_odczytu
            self._uzupelnij_moj_klub()
            self._zastosuj_ligi()
            self.status, self.komunikat, self.etap = "gotowe", "", None
            self.wersja += 1
            return True

    def _uzupelnij_moj_klub(self):
        moje = self.meta.get("moje_kluby") or []
        wybrany = next((m for m in moje if m["uid"] == self.konfig.moj_klub_uid), moje[0] if moje else None)
        self.meta["moj_klub"] = wybrany["nazwa"] if wybrany else None
        self.meta["moj_klub_uid"] = wybrany["uid"] if wybrany else None

    def _zastosuj_ligi(self):
        nazwy, mnozniki = wczytaj_nazwy_rozgrywek(self.plik_nazw), wszystkie_mnozniki(self.plik_mnoznikow)
        self.dane = {p: ustaw_ligi(df, nazwy, mnozniki) for p, df in self.surowe.items()}
        for liga in self.ligi:
            liga["nazwa"] = nazwy.get(liga["klucz"]) if liga["klucz"] is not None else None
