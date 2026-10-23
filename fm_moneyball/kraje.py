"""
Nazwy krajow (narodowosci) zawodnikow z zapisu.

Zapis FM26 nie zawiera nazw krajow, tylko ich identyfikatory (nation_id). Nazwy bierzemy:
1. recznie wpisane (dane/nazwy_krajow.csv i ~/.fm_moneyball/nazwy_krajow.csv),
2. automatycznie z nazwanych lig: liga "Ekstraklasa (POL 1)" gra w kraju o id dominujacym
   wsrod jej klubow, wiec ten id to Polska,
3. w pozostalych przypadkach "Kraj #id" (do nazwania w zakladce Ligi).
"""
import re
from collections import Counter

from fm_moneyball.mapy import KATALOG_DANYCH, KATALOG_DOMOWY, wczytaj_mape, zapisz_mape
from fm_moneyball.stale import MAPOWANIE_NAZW_LIG

PLIK_KRAJOW = KATALOG_DANYCH / "nazwy_krajow.csv"
PLIK_KRAJOW_UZYTKOWNIKA = KATALOG_DOMOWY / "nazwy_krajow.csv"

# Kod kraju z etykiety ligi, np. "(POL 1)" -> nazwa kraju
KRAJ_Z_KODU = {
    "ANG": "Anglia", "ARG": "Argentyna", "BEL": "Belgia", "BRA": "Brazylia", "CHO": "Chorwacja",
    "FRA": "Francja", "HIS": "Hiszpania", "HOL": "Holandia", "JAP": "Japonia", "KOL": "Kolumbia",
    "KOR": "Korea Płd.", "MEX": "Meksyk", "NIE": "Niemcy", "POL": "Polska", "POR": "Portugalia",
    "USA": "USA", "WLO": "Włochy",
}
_KOD_LIGI = re.compile(r"\(([A-Z]{3}) \d+\)")


def etykieta_kraju(kraj_id):
    return f"Kraj #{kraj_id}"


def nazwy_auto(ligi):
    """[{nazwa, kraj}] (podsumowanie lig) -> {nation_id: nazwa kraju} z kodow w etykietach lig."""
    glosy = {}
    for liga in ligi:
        if not liga.get("nazwa") or liga.get("kraj") is None:
            continue
        m = _KOD_LIGI.search(MAPOWANIE_NAZW_LIG.get(liga["nazwa"], liga["nazwa"]))
        if m and m.group(1) in KRAJ_Z_KODU:
            glosy.setdefault(liga["kraj"], Counter())[KRAJ_Z_KODU[m.group(1)]] += 1
    return {kraj: licznik.most_common(1)[0][0] for kraj, licznik in glosy.items()}


def wczytaj_nazwy_krajow(plik_uzytkownika=PLIK_KRAJOW_UZYTKOWNIKA, domyslny=PLIK_KRAJOW):
    """Reczne nazwy krajow: domyslne z repozytorium nadpisane edycjami uzytkownika."""
    return {**wczytaj_mape(domyslny), **wczytaj_mape(plik_uzytkownika)}


def zapisz_nazwe_kraju(kraj_id, nazwa, sciezka=PLIK_KRAJOW_UZYTKOWNIKA):
    """Dopisuje lub zmienia nazwe kraju; pusta nazwa usuwa wpis uzytkownika."""
    mapa = wczytaj_mape(sciezka)
    if nazwa:
        mapa[int(kraj_id)] = nazwa
    else:
        mapa.pop(int(kraj_id), None)
    return zapisz_mape(mapa, sciezka, ("nation_id", "nazwa"))


def podsumuj_kraje(zawodnicy, nazwy, reczne=(), przyklady=3):
    """
    Zawodnicy wszystkich pozycji (z 'Kraj_ID') -> [{id, nazwa, reczna, liczba, przyklady}]:
    kraje bez nazwy najpierw, potem wg liczby zawodnikow. Przyklady to najdrozsi zawodnicy -
    po nich najlatwiej rozpoznac kraj w grze.
    """
    if zawodnicy is None or 'Kraj_ID' not in zawodnicy.columns:
        return []
    wynik = []
    for kraj_id, grupa in zawodnicy.dropna(subset=['Kraj_ID']).groupby('Kraj_ID'):
        kraj_id = int(kraj_id)
        najlepsi = grupa.sort_values('Wartość_Numeryczna', ascending=False, na_position='last').head(przyklady)
        wynik.append({
            "id": kraj_id, "nazwa": nazwy.get(kraj_id), "reczna": kraj_id in reczne, "liczba": int(len(grupa)),
            "przyklady": [f"{w['Piłkarz']} ({w.get('Klub') or '?'})" for _, w in najlepsi.iterrows()],
        })
    return sorted(wynik, key=lambda k: (k["nazwa"] is not None, -k["liczba"]))
