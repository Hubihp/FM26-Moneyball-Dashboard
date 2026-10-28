"""
Pamiec interfejsu po stronie serwera: lista zyczen, filtry, wagi, ustawienia i uklad tabel.

Wczesniej te dane byly tylko w localStorage przegladarki - przypisane do jednej przegladarki i adresu.
Okno programu (WebView2) ma wlasny localStorage, wiec zrodlem prawdy jest plik
~/.fm_moneyball/pamiec.json (poza folderem programu - aktualizacja go nie nadpisuje).
Zapis atomowy: plik tymczasowy + replace, wiec awaria w trakcie zapisu nie psuje danych.
"""
import json
import logging
import os
import threading
from pathlib import Path

from fm_moneyball.mapy import KATALOG_DOMOWY

log = logging.getLogger("fm_moneyball")

PLIK_PAMIECI = KATALOG_DOMOWY / "pamiec.json"
MAKS_DLUGOSC = 2_000_000        # znakow na jedna wartosc (uklad tabeli to kilka KB)


class Pamiec:
    def __init__(self, plik=PLIK_PAMIECI):
        self.plik = Path(plik)
        self._blokada = threading.Lock()
        self._dane = self._wczytaj()

    def _wczytaj(self):
        if not self.plik.is_file():
            return {}
        try:
            dane = json.loads(self.plik.read_text(encoding="utf-8"))
            return {str(k): str(v) for k, v in dane.items()} if isinstance(dane, dict) else {}
        except (OSError, ValueError):
            # uszkodzony plik zostaje obok jako kopia, zeby niczego nie stracic
            log.exception("Nie udało się odczytać %s", self.plik)
            try:
                self.plik.replace(self.plik.with_suffix(".uszkodzony.json"))
            except OSError:
                pass
            return {}

    def _zapisz(self):
        self.plik.parent.mkdir(parents=True, exist_ok=True)
        tymczasowy = self.plik.with_suffix(".tmp")
        tymczasowy.write_text(json.dumps(self._dane, ensure_ascii=False), encoding="utf-8")
        os.replace(tymczasowy, self.plik)

    def wszystko(self):
        with self._blokada:
            return dict(self._dane)

    def ustaw(self, zmiany):
        """zmiany: {klucz: tekst JSON albo None (usun)}."""
        with self._blokada:
            for klucz, wartosc in zmiany.items():
                if wartosc is None:
                    self._dane.pop(klucz, None)
                elif len(wartosc) <= MAKS_DLUGOSC:
                    self._dane[klucz] = wartosc
            self._zapisz()
            return len(self._dane)
