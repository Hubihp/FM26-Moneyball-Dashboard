"""
Mnozniki lig ustawiane przez uzytkownika (plik CSV: nazwa,mnoznik).

Uzupelniaja i nadpisuja wbudowana tabele MNOZNIKI_LIG - np. dla lig, ktorych w niej nie ma.
Domyslne dodatki sa w dane/mnozniki_lig.csv (repozytorium), edycje uzytkownika w
~/.fm_moneyball/mnozniki_lig.csv - poza repozytorium, wiec aktualizacja aplikacji ich nie kasuje.
Nazwy lig (id rozgrywek -> nazwa) sa w nazwy_rozgrywek.csv (patrz zrodla/zapis_fm.py).
"""
import csv
from pathlib import Path

from fm_moneyball.mapy import KATALOG_DANYCH, KATALOG_DOMOWY
from fm_moneyball.stale import MNOZNIKI_LIG

PLIK_MNOZNIKOW = KATALOG_DANYCH / "mnozniki_lig.csv"
PLIK_MNOZNIKOW_UZYTKOWNIKA = KATALOG_DOMOWY / "mnozniki_lig.csv"


def wczytaj_mnozniki_uzytkownika(sciezka=PLIK_MNOZNIKOW_UZYTKOWNIKA):
    sciezka = Path(sciezka)
    if not sciezka.is_file():
        return {}
    wynik = {}
    with open(sciezka, encoding="utf-8-sig", newline="") as plik:
        for wiersz in csv.reader(plik):
            if len(wiersz) < 2 or not wiersz[0].strip():
                continue
            try:
                wynik[wiersz[0].strip()] = float(wiersz[1].replace(",", "."))
            except ValueError:
                continue   # naglowek albo smiec
    return wynik


def zapisz_mnoznik(nazwa, mnoznik, sciezka=PLIK_MNOZNIKOW_UZYTKOWNIKA):
    """Dopisuje lub zmienia mnoznik ligi; None usuwa wpis (wraca wartosc wbudowana)."""
    sciezka = Path(sciezka)
    mnozniki = wczytaj_mnozniki_uzytkownika(sciezka)
    if mnoznik is None:
        mnozniki.pop(nazwa, None)
    else:
        mnozniki[nazwa] = float(mnoznik)
    sciezka.parent.mkdir(parents=True, exist_ok=True)
    with open(sciezka, "w", encoding="utf-8", newline="") as plik:
        pisarz = csv.writer(plik)
        pisarz.writerow(["nazwa", "mnoznik"])
        for n in sorted(mnozniki):
            pisarz.writerow([n, mnozniki[n]])
    return mnozniki


def wszystkie_mnozniki(sciezka=PLIK_MNOZNIKOW_UZYTKOWNIKA, domyslny=PLIK_MNOZNIKOW):
    return {**MNOZNIKI_LIG, **wczytaj_mnozniki_uzytkownika(domyslny), **wczytaj_mnozniki_uzytkownika(sciezka)}
