"""
Stan serwera: wybrane zrodlo danych, wczytane pule zawodnikow, wczytywanie w tle, cache na dysku
i sledzenie folderu zapisow.

- Nic nie jest wczytywane przy starcie (chyba ze wlaczono `wczytaj_przy_starcie`) - uzytkownik
  wybiera zrodlo w interfejsie.
- Wczytywanie odbywa sie w jednym watku roboczym. Kazda zmiana zrodla zwieksza `pokolenie`;
  wynik wczytany dla starszego pokolenia jest odrzucany i wczytywanie rusza od nowa.
- Odczytany zapis trafia do cache (~/.fm_moneyball/cache), wiec ponowne otwarcie tego samego
  stanu zapisu - takze po restarcie - jest natychmiastowe.
- Nazwy i mnozniki lig oraz nazwy krajow sa nakladane po wczytaniu (schemat.ustaw_ligi,
  schemat.ustaw_kraje), wiec ich edycja nie wymaga ponownego odczytu zapisu.
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

import pandas as pd

from fm_moneyball import historia
from fm_moneyball.historia import KATALOG_HISTORII
from fm_moneyball.kraje import PLIK_KRAJOW_UZYTKOWNIKA, nazwa_auto_ligi, nazwy_auto, wczytaj_nazwy_krajow
from fm_moneyball.ligi import (KOREKTA_REZERW, PLIK_MNOZNIKOW_UZYTKOWNIKA, korekta_ligi, mnoznik_z_korekty,
                               plik_mnoznikow_klucz, wczytaj_korekty, wczytaj_mnozniki_klucz,
                               wczytaj_mnozniki_uzytkownika, wszystkie_mnozniki)
from fm_moneyball.mapy import KATALOG_DOMOWY
from fm_moneyball.schemat import ustaw_kraje, ustaw_ligi
from fm_moneyball.stale import POZYCJE
from fm_moneyball.zrodla import folder as folder_zapisow
from fm_moneyball.zrodla.csv_fm import generuj_demo_csv, wczytaj_csv
from fm_moneyball.zrodla.zapis_fm import (ETAPY_WCZYTYWANIA, PLIK_NAZW_UZYTKOWNIKA, OpcjeZapisu, komunikat_bledu,
                                         wczytaj_nazwy_rozgrywek, wczytaj_zapis)

log = logging.getLogger("fm_moneyball")

CO_ILE_SPRAWDZAC = 15        # sekundy miedzy sprawdzeniami folderu zapisow
# 2: domyslnie zawodnik we wszystkich pulach, w ktorych jest naturalny (wczesniej tylko glowna)
WERSJA_USTAWIEN = 2
WERSJA_CACHE = 20            # zmiana formatu wyniku = nowy klucz cache (20: aktywna taktyka z gry)
ILE_W_CACHE = 3
MAKS_ODCZYTOW_HISTORII_NA_RAZ = 6   # starsze zapisy folderu czytane na jedno wczytanie (historia z folderu)
PRZERWA_HISTORII_S = 3.0            # przerwa miedzy nimi - serwer odpowiada w tym czasie bez opoznien
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
    wersja_ustawien: int = WERSJA_USTAWIEN

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


def przygotuj_dane(surowe, ligi, kraje_auto, kraje_baza, plik_nazw, plik_mnoznikow, plik_krajow):
    """
    Surowe ramki zapisu -> ramki z nazwami lig, mnoznikami i krajami. Uzupelnia wpisy `ligi` (nazwa, mnoznik
    automatyczny). Zwraca (dane, nazwy_krajow, zrodla_krajow). Wspolne dla biezacego zapisu i migawek historii
    budowanych ze starszych zapisow folderu.
    """
    nazwy, mnozniki = wczytaj_nazwy_rozgrywek(plik_nazw), wszystkie_mnozniki(plik_mnoznikow)
    for liga in ligi:
        liga["nazwa"] = nazwy.get(liga["klucz"]) if liga["klucz"] is not None else None
    # zrodla nazw krajow, od najslabszego: kluby-kotwice, kraj nazwanej ligi, nazwa reczna
    zrodla = (("kluby", kraje_auto), ("liga", nazwy_auto(ligi)), ("baza", kraje_baza),
              ("ręcznie", wczytaj_nazwy_krajow(plik_krajow)))
    nazwy_krajow, zrodla_krajow = {}, {}
    for zrodlo, mapa in zrodla:
        nazwy_krajow.update(mapa)
        zrodla_krajow.update(dict.fromkeys(mapa, zrodlo))
    # liga bez nazwy w tabeli (np. nowa w kolejnej wersji gry): nazwa z kraju jej klubow, bez recznego wpisywania
    nazwy = dict(nazwy)
    for liga in ligi:
        liga["nazwa_auto"] = False
        if liga["nazwa"] is None and liga["klucz"] is not None:
            kraj = nazwy_krajow.get(liga.get("kraj"))
            liga["nazwa"] = nazwa_auto_ligi(kraj, liga.get("liczba"))
            liga["nazwa_auto"] = True
            nazwy[liga["klucz"]] = liga["nazwa"]
    # korekta ligowa z danych: transfery (dane/korekty_lig.csv) + reputacja ligi z zapisu; reczne mnozniki
    # uzytkownika (Ligi i kraje) maja pierwszenstwo
    korekty = wczytaj_korekty()
    mnozniki_klucz = {}
    for liga in ligi:
        korekta, zrodlo = korekta_ligi(liga["klucz"], liga.get("reputacja"), korekty)
        liga["mnoznik_auto"] = round(mnoznik_z_korekty(korekta), 3)
        liga["zrodlo_mnoznika"] = zrodlo
        if liga["klucz"] is not None:
            mnozniki_klucz[liga["klucz"]] = liga["mnoznik_auto"]
    mnozniki_klucz.update(wczytaj_mnozniki_klucz(plik_mnoznikow_klucz(plik_mnoznikow)))   # reczne po numerze ligi
    if ligi:   # zapis gry; CSV i demo - wbudowana tabela mnoznikow po nazwie
        mnozniki = wczytaj_mnozniki_uzytkownika(plik_mnoznikow)
        opcje_lig = {"mnoznik_nieznanej": mnoznik_z_korekty(KOREKTA_REZERW), "mnozniki_klucz": mnozniki_klucz}
    else:
        opcje_lig = {}
    dane = {p: ustaw_kraje(ustaw_ligi(df, nazwy, mnozniki, **opcje_lig), nazwy_krajow)
            for p, df in surowe.items()}
    return dane, nazwy_krajow, zrodla_krajow


class Stan:
    def __init__(self, plik_ustawien=KATALOG_DOMOWY / "ustawienia.json", sledzenie=True,
                 katalog_cache=KATALOG_DOMOWY / "cache", plik_nazw=PLIK_NAZW_UZYTKOWNIKA,
                 plik_mnoznikow=PLIK_MNOZNIKOW_UZYTKOWNIKA, plik_krajow=PLIK_KRAJOW_UZYTKOWNIKA,
                 katalog_historii=KATALOG_HISTORII):
        self._blokada = threading.RLock()
        self._blokada_wczytywania = threading.Lock()
        self.plik_ustawien = Path(plik_ustawien) if plik_ustawien else None
        self.katalog_cache = Path(katalog_cache) if katalog_cache else None
        # edycje uzytkownika (nakladane na mapy domyslne z dane/)
        self.plik_nazw, self.plik_mnoznikow = Path(plik_nazw), Path(plik_mnoznikow)
        self.plik_krajow = Path(plik_krajow)
        self.katalog_historii = Path(katalog_historii) if katalog_historii else None
        self.nazwy_krajow = {}         # nation_id -> nazwa (reczne, z lig i z klubow-kotwic)
        self.zrodla_krajow = {}        # nation_id -> skad nazwa: ręcznie | liga | kluby
        self.kraje_auto = {}           # nation_id -> nazwa z klubow-kotwic (z odczytu zapisu)
        self.kraje_baza = {}           # nation_id -> nazwa z tabeli po numerze bazy gry
        self.taktyki = {}              # club_uid -> taktyki pierwszej druzyny odczytane z zapisu
        self._watek_historii = None    # budowanie migawek ze starszych zapisow folderu
        self._wszyscy = None           # (wersja, zawodnicy wszystkich pul) - pamiec wszyscy_zawodnicy()
        self._watek_rozgrzewania = None
        self.po_wczytaniu = []         # funkcje(wersja) wolane w tle po kazdej nowej wersji danych (rozgrzewanie)
        self.konfig = self._wczytaj_ustawienia()
        self.surowe = {}               # ramki prosto ze zrodla (przed nalozeniem nazw lig)
        self.dane = {}
        self.meta = {}
        self.ligi = []                 # podsumowanie lig z zapisu
        self.druzyny = {}              # club_uid -> sumy statystyk sezonu (tylko zapis gry)
        self.tabele = {}               # club_uid prowadzonego klubu -> tabela jego ligi (tylko zapis gry)
        self.oceny_poprzednie = {}     # player_uid -> (srednia ocena, minuty) w poprzednim sezonie (tylko zapis gry)
        self.oceny_status = "brak"     # brak | wczytywanie | gotowe | blad - historia ocen czytana w tle
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
                if dane.get("wersja_ustawien", 1) < 2:
                    # ustawienia sprzed zmiany domyslnej: zawodnik ma trafiac na wszystkie naturalne pozycje
                    konfig.opcje["wszystkie_naturalne_pozycje"] = True
                konfig.wersja_ustawien = WERSJA_USTAWIEN
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

    def wszyscy_zawodnicy(self):
        """
        Zawodnicy wszystkich pozycji bez powtorzen (zawodnik moze byc w kilku pulach) albo None. Zapamietani do
        zmiany wersji danych (laczenie 14 pul trwa ~1 s, a korzysta z niego kilka kart). Nie modyfikowac wyniku.
        """
        with self._blokada:
            wersja = self.wersja
            if self._wszyscy is not None and self._wszyscy[0] == wersja:
                return self._wszyscy[1]
            ramki = [df.assign(Pula=p) for p, df in self.dane.items() if not df.empty]
        if not ramki:
            return None
        wszyscy = pd.concat(ramki, ignore_index=True)
        wszyscy = wszyscy.drop_duplicates('UID' if 'UID' in wszyscy.columns else 'ID')
        with self._blokada:
            if self.wersja == wersja:
                self._wszyscy = (wersja, wszyscy)
        return wszyscy

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
        self._rozgrzej()

    def zastosuj_ligi(self):
        """Ponownie naklada nazwy i mnozniki lig na wczytane dane (po ich edycji)."""
        with self._blokada:
            self._zastosuj_ligi()
            self.wersja += 1
        self._rozgrzej()

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
                    self._ustaw(status="blad", komunikat=komunikat_bledu(e), etap=None)
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
            return self._zakoncz(pokolenie, ("demo",), dane, meta, [], None, {}, {}, {})

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
            "menedzer": getattr(wynik, "menedzer", None),
            "menedzer_nazwa": getattr(wynik, "menedzer_nazwa", None) or getattr(wynik, "menedzer", None),
            "moje_kluby": wynik.moje_kluby or ([{"uid": wynik.moj_klub_uid, "nazwa": wynik.moj_klub}]
                                               if wynik.moj_klub_uid is not None else []),
            "ostrzezenia": wynik.ostrzezenia, "liczniki": wynik.liczniki,
            "budzety": {str(k): v for k, v in (getattr(wynik, "budzety", None) or {}).items()},
            "czas_odczytu_s": round(time.time() - start, 1),
            "z_cache": z_cache,
            "wczytano": datetime.now().isoformat(timespec="seconds"),
        }
        return self._zakoncz(pokolenie, klucz, wynik.dane, meta, wynik.ligi, sciezka_odczytu, wynik.kraje_auto,
                             getattr(wynik, "druzyny", {}), getattr(wynik, "tabele", {}),
                             getattr(wynik, "kraje_baza", {}), getattr(wynik, "taktyki", {}))

    def _zakoncz(self, pokolenie, klucz, dane, meta, ligi, sciezka_odczytu, kraje_auto, druzyny=None, tabele=None,
                 kraje_baza=None, taktyki=None):
        with self._blokada:
            if pokolenie != self.pokolenie:
                return False
            self.surowe, self.meta, self.ligi, self._klucz = dane, meta, ligi, klucz
            self.druzyny, self.tabele = druzyny or {}, tabele or {}
            self.oceny_poprzednie, self.oceny_status = {}, "brak"
            self.kraje_auto = kraje_auto or {}
            self.kraje_baza = kraje_baza or {}
            self.taktyki = taktyki or {}
            self._sciezka_odczytu = sciezka_odczytu
            self._uzupelnij_moj_klub()
            self._zastosuj_ligi()
            self._zapisz_historie()
            self.status, self.komunikat, self.etap = "gotowe", "", None
            self.wersja += 1
        self._rozgrzej()
        self._uruchom_oceny(pokolenie, klucz)
        self._uruchom_historie_folderu(pokolenie)
        return True

    def _rozgrzej(self):
        """Funkcje `po_wczytaniu` (np. liczenie SCORE wszystkich pozycji) w tle dla biezacej wersji danych."""
        if not self.po_wczytaniu:
            return
        wersja = self.wersja

        def praca():
            for funkcja in list(self.po_wczytaniu):
                if self.wersja != wersja:
                    return
                try:
                    funkcja(wersja)
                except Exception as e:   # tylko przyspieszenie - bez wplywu na dzialanie
                    log.warning("Rozgrzewanie obliczeń przerwane: %s", e)
        self._watek_rozgrzewania = threading.Thread(target=praca, daemon=True, name="rozgrzewanie")
        self._watek_rozgrzewania.start()

    # --- historia ocen z poprzedniego sezonu (w tle, po wczytaniu zapisu) -----------------------------
    def _uruchom_oceny(self, pokolenie, klucz):
        data_gry = self.meta.get("data_gry")
        if self.meta.get("demo") or not self._sciezka_odczytu or not data_gry or not self.meta.get("moje_kluby"):
            return
        moje = {m["uid"] for m in self.meta["moje_kluby"]}
        gracze = set()
        for df in self.dane.values():
            if not df.empty and {'UID', 'Klub_UID'} <= set(df.columns):
                gracze |= set(df.loc[df['Klub_UID'].isin(moje), 'UID'].dropna().astype(int))
        self.oceny_status = "wczytywanie"
        threading.Thread(target=self._wczytaj_oceny, daemon=True, name="historia-ocen",
                         args=(pokolenie, klucz, self._sciezka_odczytu, gracze, date.fromisoformat(data_gry),
                               self.konfig.opcje_zapisu().rodzaj_statystyk)).start()

    def _wczytaj_oceny(self, pokolenie, klucz, sciezka, gracze, data_gry, rodzaj):
        plik = self._plik_cache(("oceny", klucz))
        try:
            if plik is not None and plik.is_file():
                with open(plik, "rb") as f:
                    oceny = pickle.load(f)
            else:
                from fm_moneyball.zrodla.zapis_fm import oceny_poprzedniego_sezonu
                oceny = oceny_poprzedniego_sezonu(sciezka, gracze, data_gry, rodzaj)
                if plik is not None:
                    plik.parent.mkdir(parents=True, exist_ok=True)
                    with open(plik, "wb") as f:
                        pickle.dump(oceny, f)
            status = "gotowe"
        except Exception as e:   # dodatek (profil druzyny) - brak nie blokuje aplikacji
            log.warning("Nie udało się odczytać historii ocen: %s", e)
            oceny, status = {}, "blad"
        with self._blokada:
            if pokolenie == self.pokolenie:
                self.oceny_poprzednie, self.oceny_status = oceny, status

    def katalog_kariery(self):
        """Katalog historii biezacej kariery (tylko zapis gry, nie demo/CSV) albo None."""
        if self.meta.get("demo") or not self.meta.get("data_gry") or self.katalog_historii is None:
            return None
        # osobny katalog dla FM27 - historia nie miesza sie z dawnymi karierami FM26 tego samego menedzera
        return historia.katalog_kariery(self.katalog_historii / "FM27", self.meta.get("menedzer"))

    # --- migawki historii ze starszych zapisow folderu (w tle, raz na kazdy plik) ----------------------
    def _uruchom_historie_folderu(self, pokolenie):
        konfig, katalog = self.konfig, self.katalog_kariery()
        if not self._sledzenie or konfig.typ != "folder" or not konfig.folder or katalog is None:
            return
        if not self.meta.get("menedzer"):
            return     # bez menedzera nie da sie odroznic zapisow tej kariery od innych w tym samym folderze
        if self._watek_historii is not None and self._watek_historii.is_alive():
            return
        self._watek_historii = threading.Thread(
            target=self._historia_z_folderu, daemon=True, name="historia-z-folderu",
            args=(pokolenie, Path(konfig.folder), katalog, date.fromisoformat(self.meta["data_gry"]),
                  self.meta.get("menedzer"), konfig.opcje_zapisu()))
        self._watek_historii.start()

    def _historia_z_folderu(self, pokolenie, folder, katalog, data_gry, menedzer, opcje):
        """
        Starsze zapisy folderu (po jednym na miesiac gry) -> migawki historii tej kariery, zeby Δ SCORE, wykresy
        i prognoza mialy dane od razu, a nie dopiero po kolejnych wczytaniach. Zapis innej kariery (inny menedzer)
        jest pomijany; przejrzane pliki sa zapamietane, wiec kazdy czyta sie najwyzej raz.
        """
        import warnings

        import fmsave

        zapisy = []
        for plik in folder_zapisow.lista_zapisow(folder):
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    with fmsave.open(plik.sciezka) as zapis:     # sama data w grze - odczyt natychmiastowy
                        zapisy.append((plik, zapis.info.game_date))
            except Exception:
                continue
        # najwyzej kilka odczytow na raz (kazdy to ok. minuty obliczen w procesie serwera - interfejs zwalnia);
        # reszta przy kolejnych wczytaniach, bo przejrzane pliki sa zapamietane
        lista = historia.do_uzupelnienia(zapisy, katalog, data_gry)[:MAKS_ODCZYTOW_HISTORII_NA_RAZ]
        if not lista:
            return
        rozgrzewanie = self._watek_rozgrzewania
        if rozgrzewanie is not None:
            rozgrzewanie.join()      # najpierw obliczenia dla interfejsu, potem dlugi odczyt starszych zapisow
        przejrzane, dodane = historia.przejrzane(katalog), 0
        log.info("Historia z folderu: zapisy do odczytu: %d", len(lista))
        for nr, (plik, dzien) in enumerate(lista):
            if nr and self._zatrzymaj.wait(PRZERWA_HISTORII_S):
                break        # przerwa miedzy odczytami: interfejs dostaje procesor; zatrzymanie programu konczy prace
            if pokolenie != self.pokolenie:
                break
            if not folder_zapisow.czy_stabilny(plik.sciezka, odstep=0.5):
                continue     # gra wlasnie zapisuje ten plik - sprobujemy przy kolejnym wczytaniu
            try:
                wynik = wczytaj_zapis(plik.sciezka, opcje)
                if wynik.menedzer != menedzer:
                    przejrzane[historia.klucz_pliku(plik)] = "inna kariera"
                    continue
                dane, _, _ = przygotuj_dane(wynik.dane, wynik.ligi, wynik.kraje_auto, wynik.kraje_baza,
                                            self.plik_nazw, self.plik_mnoznikow, self.plik_krajow)
                if historia.zapisz_migawke(katalog, dane, wynik.data_gry) is not None:
                    dodane += 1
                przejrzane[historia.klucz_pliku(plik)] = "ok"
            except (OSError, MemoryError) as e:   # przejsciowe (plik zablokowany, brak pamieci) - bez zapamietania
                log.warning("Historia z folderu: %s na razie nieczytelny (%s)", plik.nazwa, e)
            except Exception as e:   # dodatek - uszkodzony albo obcy zapis nie blokuje reszty
                log.warning("Historia z folderu: pominięto %s (%s)", plik.nazwa, e)
                przejrzane[historia.klucz_pliku(plik)] = "błąd"
            finally:
                try:
                    historia.zapisz_przejrzane(katalog, przejrzane)
                except OSError:
                    pass
        if dodane:
            log.info("Historia z folderu: dodane migawki: %d", dodane)
            with self._blokada:
                if pokolenie == self.pokolenie:
                    self.wersja += 1     # nowe migawki zmieniaja Δ SCORE i prognoze - interfejs odswieza dane
            self._rozgrzej()

    def _zapisz_historie(self):
        # migawka do historii rozwoju; jej brak (np. brak miejsca na dysku) nie blokuje wczytania
        try:
            if self.katalog_historii is None:
                return
            historia.przenies_stare(self.katalog_historii / "FM27", self.katalog_kariery())
            historia.zapisz_migawke(self.katalog_kariery(), self.dane, date.fromisoformat(self.meta["data_gry"]))
        except Exception as e:
            log.warning("Nie udało się zapisać migawki historii: %s", e)

    def _uzupelnij_moj_klub(self):
        moje = self.meta.get("moje_kluby") or []
        wybrany = next((m for m in moje if m["uid"] == self.konfig.moj_klub_uid), moje[0] if moje else None)
        self.meta["moj_klub"] = wybrany["nazwa"] if wybrany else None
        self.meta["moj_klub_uid"] = wybrany["uid"] if wybrany else None
        self.meta["budzet"] = (self.meta.get("budzety") or {}).get(str(wybrany["uid"])) if wybrany else None

    def _zastosuj_ligi(self):
        self.dane, self.nazwy_krajow, self.zrodla_krajow = przygotuj_dane(
            self.surowe, self.ligi, self.kraje_auto, self.kraje_baza, self.plik_nazw, self.plik_mnoznikow,
            self.plik_krajow)
