"""
Optymalizator budzetu (Moneyball): najlepszy ZESTAW wzmocnien za dany budzet, a nie jedna gwiazda.

Zysk z zawodnika na pozycji = o ile jego SCORE przewyzsza mojego najlepszego zawodnika na tej pozycji
(SCORE jest w skali T w obrebie pozycji, wiec zyski z roznych pozycji sa porownywalne).
Ograniczenia: suma cen <= budzet transferowy, suma pensji (tygodniowych) <= budzet placowy,
na pozycji co najwyzej jeden nowy zawodnik, kazdy zawodnik wybrany najwyzej raz (bywa w kilku pulach).

To wielowyborowy problem plecakowy z dwoma ograniczeniami. Kandydaci na pozycji sa najpierw
przycinani do niezdominowanych (nikt inny nie daje wiecej za mniej), a potem przeszukiwanie
z odcinaniem (branch & bound) znajduje optimum dokladnie - pozycji jest kilka, wiec to ulamek sekundy.
"""
from dataclasses import dataclass, field

MAKS_KANDYDATOW = 60            # na pozycje po przycieciu do niezdominowanych
LIMIT_WEZLOW = 2_000_000        # zabezpieczenie czasu; zwykle wystarcza kilka tysiecy


@dataclass
class Kandydat:
    klucz: str                  # UID zawodnika (ten sam zawodnik w kilku pulach = jeden klucz)
    zysk: float                 # przyrost SCORE ponad mojego najlepszego na pozycji
    cena: float                 # EUR
    pensja: float               # EUR na tydzien
    dane: dict = field(default_factory=dict, compare=False)


def niezdominowani(kandydaci):
    """Odrzuca kandydatow, od ktorych ktos inny daje co najmniej tyle samo za nie wiecej (cena i pensja)."""
    wynik = []
    for k in sorted(kandydaci, key=lambda k: (-k.zysk, k.cena, k.pensja)):
        if not any(z.zysk >= k.zysk and z.cena <= k.cena and z.pensja <= k.pensja for z in wynik):
            wynik.append(k)
    if len(wynik) > MAKS_KANDYDATOW:
        # bardzo dlugi front: najwieksze zyski i najtansze opcje
        po_zysku = wynik[:MAKS_KANDYDATOW // 2]
        tani = sorted(wynik, key=lambda k: (k.cena, k.pensja))[:MAKS_KANDYDATOW // 2]
        wynik = list({id(k): k for k in po_zysku + tani}.values())
    return wynik


def optymalizuj(kandydaci_pozycji, budzet, budzet_plac):
    """
    kandydaci_pozycji: {pozycja: [Kandydat]} -> (wybor {pozycja: Kandydat}, suma zysku, czy optimum pewne).
    Pozycja bez oplacalnego kandydata zostaje bez wzmocnienia.
    """
    pozycje = []
    for poz, lista in kandydaci_pozycji.items():
        dostepni = [k for k in lista if k.zysk > 0 and k.cena <= budzet and k.pensja <= budzet_plac]
        if dostepni:
            pozycje.append((poz, niezdominowani(dostepni)))
    # najpierw pozycje z najwiekszym mozliwym zyskiem: szybciej dobre rozwiazanie, lepsze odcinanie
    pozycje.sort(key=lambda p: -p[1][0].zysk)
    najlepszy_reszty = [0.0] * (len(pozycje) + 1)
    for i in range(len(pozycje) - 1, -1, -1):
        najlepszy_reszty[i] = najlepszy_reszty[i + 1] + pozycje[i][1][0].zysk

    najlepszy = {"zysk": 0.0, "wybor": {}}
    wezly = 0
    wybor, uzyci = {}, set()

    def szukaj(i, zysk, zostalo, zostalo_plac):
        nonlocal wezly
        wezly += 1
        if zysk > najlepszy["zysk"] + 1e-9:
            najlepszy["zysk"], najlepszy["wybor"] = zysk, dict(wybor)
        if i == len(pozycje) or wezly > LIMIT_WEZLOW:
            return
        if zysk + najlepszy_reszty[i] <= najlepszy["zysk"] + 1e-9:
            return              # nawet najlepsi z pozostalych pozycji nie pobija wyniku
        poz, lista = pozycje[i]
        for k in lista:         # malejaco po zysku
            if k.cena <= zostalo and k.pensja <= zostalo_plac and k.klucz not in uzyci:
                wybor[poz] = k
                uzyci.add(k.klucz)
                szukaj(i + 1, zysk + k.zysk, zostalo - k.cena, zostalo_plac - k.pensja)
                uzyci.discard(k.klucz)
                del wybor[poz]
        szukaj(i + 1, zysk, zostalo, zostalo_plac)      # nikogo na tej pozycji

    szukaj(0, 0.0, budzet, budzet_plac)
    return najlepszy["wybor"], najlepszy["zysk"], wezly <= LIMIT_WEZLOW


def jedna_gwiazda(kandydaci_pozycji, budzet, budzet_plac):
    """Dla porownania: najlepszy pojedynczy zawodnik mieszczacy sie w calym budzecie -> (pozycja, Kandydat)."""
    najlepszy = None
    for poz, lista in kandydaci_pozycji.items():
        for k in lista:
            if k.cena <= budzet and k.pensja <= budzet_plac and k.zysk > 0 and (
                    najlepszy is None or k.zysk > najlepszy[1].zysk):
                najlepszy = (poz, k)
    return najlepszy
