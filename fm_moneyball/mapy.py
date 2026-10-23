"""
Mapy `id,nazwa` w plikach CSV: wartosci domyslne w repozytorium (dane/) i edycje uzytkownika
w katalogu domowym (~/.fm_moneyball). Edycje uzytkownika sa poza repozytorium, wiec pobranie
nowej wersji aplikacji (np. ZIP) ich nie nadpisuje.
"""
import csv
from pathlib import Path

KATALOG_DANYCH = Path(__file__).resolve().parents[1] / "dane"
KATALOG_DOMOWY = Path.home() / ".fm_moneyball"


def wczytaj_mape(sciezka):
    """Plik CSV `id,nazwa` -> {int: str}. Akceptuje klucze ujemne; pomija naglowek, puste i bledne wiersze."""
    sciezka = Path(sciezka)
    if not sciezka.is_file():
        return {}
    mapa = {}
    with open(sciezka, encoding="utf-8-sig", newline="") as plik:
        for wiersz in csv.reader(plik):
            if len(wiersz) < 2 or not wiersz[1].strip():
                continue
            try:
                mapa[int(wiersz[0].strip())] = wiersz[1].strip()
            except ValueError:
                continue   # naglowek albo smiec
    return mapa


def zapisz_mape(mapa, sciezka, naglowek=("id", "nazwa")):
    sciezka = Path(sciezka)
    sciezka.parent.mkdir(parents=True, exist_ok=True)
    with open(sciezka, "w", encoding="utf-8", newline="") as plik:
        pisarz = csv.writer(plik)
        pisarz.writerow(naglowek)
        for klucz in sorted(mapa):
            pisarz.writerow([klucz, mapa[klucz]])
    return mapa
