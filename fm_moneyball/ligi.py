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


# --- korekta ligowa z danych (zapisy FM27) ---------------------------------------------------------
# SCORE = wynik za gre + korekta ligi, mnoznik = 1 + korekta / 50 (zgodnie z dawna skala mnoznikow).
# Kalibracja na dwoch sezonach kariery FM27 (zapisy 01.06.2027 i 01.06.2028): 4023 zawodnikow z >= 900 min
# w obu sezonach na tej samej pozycji, w tym 770 po zmianie ligi. Zmiana wyniku za gre tego samego
# zawodnika po przejsciu do innej ligi = roznica efektow lig (+ efekt wieku) - regresja grzbietowa
# ("league equivalency" z sabermetryki). Wynik w dane/korekty_lig.csv (korekta i liczba transferow).
# Ligi bez danych: krzywa z reputacji ligi (mediana reputacji jej klubow w zapisie) dopasowana do 25 lig
# z >= 10 transferami (blad sredni 1,7 pkt wobec 2,9 dawnych mnoznikow). Ponizej zakresu danych krzywa
# opada liniowo, do dolnego limitu.
PLIK_KOREKT = KATALOG_DANYCH / "korekty_lig.csv"
KRZYWA_REPUTACJI = (1.2743, -11.1041, 7.3104)   # korekta = a*r^2 + b*r + c, r = reputacja / 1000
REPUTACJA_WIERZCHOLKA = 4.357     # ponizej krzywa kwadratowa zawracalaby - dalej spadek liniowy
REPUTACJA_MAKS = 7.6              # najwyzsza reputacja w danych
NACHYLENIE_PONIZEJ = 3.9          # pkt korekty na 1000 reputacji (nachylenie dopasowania liniowego)
KOREKTA_MIN = -28.0               # najslabsze ligi (ekstrapolacja poza dane) - ostroznie
K_TRANSFEROW = 30                 # waga krzywej wyrazona w liczbie transferow (laczenie z danymi)
KOREKTA_REZERW = -20.0            # rezerwy, mlodziez i rozgrywki niewykryte (mnoznik 0,60)


def korekta_z_reputacji(reputacja):
    """Mediana reputacji klubow ligi -> korekta SCORE (punkty skali T), monotonicznie rosnaca."""
    if reputacja is None or reputacja != reputacja:
        return KOREKTA_REZERW
    r = min(float(reputacja) / 1000, REPUTACJA_MAKS)
    a, b, c = KRZYWA_REPUTACJI
    if r >= REPUTACJA_WIERZCHOLKA:
        return a * r * r + b * r + c
    dol = a * REPUTACJA_WIERZCHOLKA ** 2 + b * REPUTACJA_WIERZCHOLKA + c
    return max(dol - NACHYLENIE_PONIZEJ * (REPUTACJA_WIERZCHOLKA - r), KOREKTA_MIN)


def wczytaj_korekty(sciezka=PLIK_KOREKT):
    """dane/korekty_lig.csv -> {database_id ligi: (korekta z transferow, liczba transferow)}."""
    wynik = {}
    sciezka = Path(sciezka)
    if not sciezka.is_file():
        return wynik
    with open(sciezka, encoding="utf-8-sig", newline="") as plik:
        for wiersz in csv.DictReader(plik):
            try:
                wynik[int(wiersz["database_id"])] = (float(wiersz["korekta"]), int(wiersz["transferow"]))
            except (KeyError, ValueError):
                continue
    return wynik


def korekta_ligi(klucz, reputacja, korekty=None):
    """
    Korekta ligi: dane o transferach polaczone z krzywa reputacji wagami n / (n + K_TRANSFEROW).
    Zwraca (korekta, zrodlo), zrodlo: "transfery" (n >= K_TRANSFEROW) albo "reputacja".
    """
    z_reputacji = korekta_z_reputacji(reputacja)
    dane = (korekty or {}).get(klucz) if klucz is not None else None
    if not dane:
        return z_reputacji, "reputacja"
    korekta, n = dane
    waga = n / (n + K_TRANSFEROW)
    return waga * korekta + (1 - waga) * z_reputacji, ("transfery" if waga >= 0.5 else "reputacja")


def mnoznik_z_korekty(korekta):
    return 1.0 + korekta / 50.0
