"""
Aktualizacje programu z GitHub Releases.

Przy starcie (w tle) pytamy API GitHuba o najnowsze wydanie. Gdy jego wersja jest wyzsza niz
`fm_moneyball.__version__`, interfejs pokazuje pasek z opisem zmian. "Zainstaluj teraz" pobiera
instalator, sprawdza sume SHA-256 z pliku `.sha256` wydania, uruchamia instalator w trybie cichym
i zamyka program - instalator po skonczeniu uruchamia nowa wersje. Dane uzytkownika sa w
~/.fm_moneyball, ktorego instalator nie dotyka.

Bledy sieci sa ciche: brak internetu = brak paska.
"""
import hashlib
import json
import logging
import re
import subprocess
import sys
import tempfile
import threading
import urllib.request
from pathlib import Path

from fm_moneyball import __version__

log = logging.getLogger("fm_moneyball")

REPOZYTORIUM = "Hubihp/FM26-Moneyball-Dashboard"
ADRES_WYDANIA = f"https://api.github.com/repos/{REPOZYTORIUM}/releases/latest"
STRONA_WYDAN = f"https://github.com/{REPOZYTORIUM}/releases/latest"
NAZWA_INSTALATORA = "FM26Moneyball-Setup.exe"
ARGUMENTY_INSTALATORA = ["/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/CLOSEAPPLICATIONS"]
LIMIT_CZASU = 5


def wersja_krotka(tekst):
    """'v1.10.2' -> (1, 10, 2); nieczytelna wersja -> None."""
    liczby = re.findall(r"\d+", str(tekst or ""))
    return tuple(int(x) for x in liczby[:3]) + (0,) * (3 - len(liczby[:3])) if liczby else None


def nowsza(zdalna, lokalna=__version__):
    z, l = wersja_krotka(zdalna), wersja_krotka(lokalna)
    return z is not None and l is not None and z > l


def mozna_instalowac():
    """Instalacja z programu tylko w wersji zainstalowanej instalatorem (Windows, .exe)."""
    return sys.platform == "win32" and getattr(sys, "frozen", False)


def _pobierz_json(adres):
    zapytanie = urllib.request.Request(adres, headers={"Accept": "application/vnd.github+json",
                                                       "User-Agent": f"FM26Moneyball/{__version__}"})
    with urllib.request.urlopen(zapytanie, timeout=LIMIT_CZASU) as odp:
        return json.loads(odp.read().decode("utf-8"))


def opis_wydania(wydanie):
    """Odpowiedz API releases/latest -> slownik dla interfejsu (bez sieci, do testow)."""
    zasoby = {z.get("name"): z for z in wydanie.get("assets") or []}
    instalator = zasoby.get(NAZWA_INSTALATORA)
    suma = zasoby.get(NAZWA_INSTALATORA + ".sha256")
    wersja = str(wydanie.get("tag_name") or "").lstrip("v")
    return {
        "wersja": wersja, "notatki": wydanie.get("body") or "", "strona": wydanie.get("html_url") or STRONA_WYDAN,
        "instalator": instalator.get("browser_download_url") if instalator else None,
        "rozmiar": instalator.get("size") if instalator else None,
        "suma": suma.get("browser_download_url") if suma else None,
    }


class Aktualizacje:
    def __init__(self, pobierz_json=_pobierz_json, zamknij_program=None):
        self._pobierz_json = pobierz_json
        self.zamknij_program = zamknij_program      # ustawiane przez okno programu
        self._blokada = threading.Lock()
        self.wydanie = None
        self.sprawdzono = False
        self.postep = None          # {"etap": "pobieranie"|"instalacja"|"blad", "proc": 0-100, "komunikat"}

    def sprawdz_w_tle(self):
        threading.Thread(target=self.sprawdz, daemon=True, name="aktualizacje").start()

    def sprawdz(self):
        try:
            wydanie = opis_wydania(self._pobierz_json(ADRES_WYDANIA))
        except Exception as e:      # brak sieci, limit API, zla odpowiedz - po cichu
            log.info("Sprawdzanie aktualizacji nie powiodło się: %s", e)
            wydanie = None
        with self._blokada:
            self.wydanie, self.sprawdzono = wydanie, True
        return wydanie

    def stan(self):
        with self._blokada:
            w = self.wydanie
            dostepna = bool(w and nowsza(w["wersja"]))
            return {"wersja_programu": __version__, "sprawdzono": self.sprawdzono, "dostepna": dostepna,
                    "wersja": w["wersja"] if dostepna else None, "notatki": w["notatki"] if dostepna else None,
                    "strona": w["strona"] if w else STRONA_WYDAN, "rozmiar": w["rozmiar"] if dostepna else None,
                    "mozna_instalowac": dostepna and mozna_instalowac() and bool(w["instalator"]),
                    "postep": self.postep}

    def instaluj(self):
        with self._blokada:
            w = self.wydanie
            if not (w and nowsza(w["wersja"]) and w["instalator"] and mozna_instalowac()):
                return False
            if self.postep and self.postep["etap"] in ("pobieranie", "instalacja"):
                return True
            self.postep = {"etap": "pobieranie", "proc": 0, "komunikat": "Pobieranie..."}
        threading.Thread(target=self._instaluj, args=(w,), daemon=True, name="instalacja").start()
        return True

    def _ustaw_postep(self, **pola):
        with self._blokada:
            self.postep = {**(self.postep or {}), **pola}

    def _instaluj(self, w):
        try:
            katalog = Path(tempfile.mkdtemp(prefix="fm26_aktualizacja_"))
            plik = katalog / f"FM26Moneyball-Setup-{w['wersja']}.exe"
            skrot = pobierz(w["instalator"], plik, lambda proc: self._ustaw_postep(proc=proc))
            if w["suma"]:
                with urllib.request.urlopen(w["suma"], timeout=LIMIT_CZASU * 4) as odp:
                    oczekiwana = odp.read().decode("utf-8").split()[0].lower()
                if skrot != oczekiwana:
                    raise ValueError("Suma kontrolna pobranego instalatora się nie zgadza - plik uszkodzony.")
            self._ustaw_postep(etap="instalacja", proc=100, komunikat="Instalacja - program uruchomi się ponownie.")
            flagi = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
            subprocess.Popen([str(plik), *ARGUMENTY_INSTALATORA], creationflags=flagi, close_fds=True)
            if self.zamknij_program:
                threading.Timer(1.0, self.zamknij_program).start()
        except Exception as e:
            log.exception("Instalacja aktualizacji nie powiodła się")
            self._ustaw_postep(etap="blad", komunikat=f"Nie udało się zainstalować aktualizacji: {e}")


def pobierz(adres, cel, postep=None):
    """Pobiera plik z postepem (0-100); zwraca SHA-256 (hex)."""
    skrot = hashlib.sha256()
    zapytanie = urllib.request.Request(adres, headers={"User-Agent": f"FM26Moneyball/{__version__}"})
    with urllib.request.urlopen(zapytanie, timeout=LIMIT_CZASU * 6) as odp, open(cel, "wb") as plik:
        razem = int(odp.headers.get("Content-Length") or 0)
        pobrano = 0
        while blok := odp.read(1 << 16):
            plik.write(blok)
            skrot.update(blok)
            pobrano += len(blok)
            if postep and razem:
                postep(round(pobrano * 100 / razem))
    return skrot.hexdigest()
