"""Optymalizator budzetu i 'Sprzedaj drogo' (Moneyball)."""
import itertools
import random

import numpy as np
import pandas as pd
import pytest

from fm_moneyball import analiza
from fm_moneyball.optymalizator import Kandydat, jedna_gwiazda, niezdominowani, optymalizuj
from fm_moneyball.wycena import wycen
from fm_moneyball.zrodla.csv_fm import generuj_demo_csv, wczytaj_csv


def _losowi(seed, pozycje=4, n=12):
    rng = random.Random(seed)
    wynik = {}
    for p in range(pozycje):
        wynik[f"P{p}"] = [Kandydat(klucz=str(rng.randint(0, 25)), zysk=rng.uniform(0, 20),
                                   cena=rng.choice([0, 1e6, 5e6, 2e7, 5e7]) * rng.uniform(0.5, 1.5),
                                   pensja=rng.uniform(1e3, 1e5)) for _ in range(n)]
    return wynik


def _przeglad_zupelny(kandydaci, budzet, budzet_plac):
    """Wszystkie kombinacje (kazda pozycja: nikt albo jeden kandydat)."""
    najlepszy = 0.0
    listy = [[None] + v for v in kandydaci.values()]
    for kombinacja in itertools.product(*listy):
        wybrani = [k for k in kombinacja if k is not None]
        if len({k.klucz for k in wybrani}) < len(wybrani):
            continue
        if sum(k.cena for k in wybrani) <= budzet and sum(k.pensja for k in wybrani) <= budzet_plac:
            najlepszy = max(najlepszy, sum(k.zysk for k in wybrani))
    return najlepszy


@pytest.mark.parametrize("seed", range(8))
def test_optimum_jak_przeglad_zupelny(seed):
    kandydaci = _losowi(seed)
    budzet, budzet_plac = 4e7, 1.5e5
    wybor, zysk, pewne = optymalizuj(kandydaci, budzet, budzet_plac)
    assert pewne and zysk == pytest.approx(_przeglad_zupelny(kandydaci, budzet, budzet_plac))
    assert sum(k.cena for k in wybor.values()) <= budzet
    assert sum(k.pensja for k in wybor.values()) <= budzet_plac
    assert len({k.klucz for k in wybor.values()}) == len(wybor)          # zawodnik najwyzej raz


def test_zestaw_lepszy_niz_jedna_gwiazda():
    k = {"N": [Kandydat("gwiazda", 20, 9e7, 1e5), Kandydat("n2", 8, 2e7, 3e4)],
         "PS": [Kandydat("ps", 9, 2e7, 3e4)], "SO": [Kandydat("so", 7, 1e7, 2e4), Kandydat("wolny", 6, 0, 1.5e5)]}
    wybor, zysk, _ = optymalizuj(k, 9e7, 2e5)
    poz, gwiazda = jedna_gwiazda(k, 9e7, 2e5)
    assert gwiazda.klucz == "gwiazda" and zysk == pytest.approx(24) and zysk > gwiazda.zysk
    assert {p: x.klucz for p, x in wybor.items()} == {"N": "n2", "PS": "ps", "SO": "so"}
    # wolny agent (cena 0) wchodzi, gdy na transfer nie ma pieniedzy
    wybor, zysk, _ = optymalizuj(k, 0, 2e5)
    assert {p: x.klucz for p, x in wybor.items()} == {"SO": "wolny"}
    assert optymalizuj(k, 0, 0)[0] == {}                                 # bez budzetu - nikt


def test_niezdominowani():
    lista = [Kandydat("a", 10, 1e6, 1e4), Kandydat("b", 9, 2e6, 1e4), Kandydat("c", 12, 5e6, 1e4),
             Kandydat("d", 5, 5e5, 1e4)]
    assert [k.klucz for k in niezdominowani(lista)] == ["c", "a", "d"]   # b: mniej za wiecej niz a


def _pula_napastnikow():
    df = wczytaj_csv(generuj_demo_csv("Napastnik"))[0]
    policzona, _ = analiza.policz_wynik(df, analiza.wagi_domyslne("Napastnik", df))
    policzona, _ = wycen(policzona)
    return policzona.assign(Klub_UID=np.arange(len(policzona)) % 7)


def test_sprzedaj_drogo_i_kandydaci():
    pula = _pula_napastnikow()
    moj = pula.sort_values("SCORE", ascending=False).index[5]
    pula.loc[pula['Klub_UID'] == 99, 'Klub_UID'] = 0
    pula.loc[moj, 'Klub_UID'] = 99
    pula.loc[moj, 'Wartość_Numeryczna'] = pula['Wartość_Numeryczna'].max() * 20      # rynek przeplaca
    # bliźniak stylu (te same statystyki, inny klub, tani) - podobienstwo 100% >= 85%
    klon = pula.loc[[moj]].assign(ID="Klon", Klub_UID=3, **{'Wartość_Numeryczna': 1e6})
    z_klonem = pd.concat([pula, klon], ignore_index=True)
    wymiany = analiza.sprzedaj_drogo("Napastnik", z_klonem, z_klonem.index, 99)
    assert len(wymiany) == 1
    w = wymiany[0]
    assert w["moj"]["ID"] == pula.at[moj, 'ID'] and w["przeplacenie"] >= analiza.PROG_PRZEPLACENIA
    assert w["zastepca"]["ID"] == "Klon" and w["zastepca"]["Podobieństwo"] >= analiza.MIN_PODOBIENSTWA_ZASTEPCY
    assert w["zysk"] == pytest.approx(pula.at[moj, 'Wartość_Numeryczna'] - 1e6)
    # nikt nie spelnia progu (widoczni tylko slabsi) - zawodnik zostaje na liscie, bez zastepcy
    slabsi = pula.index[pula['SCORE'] < pula.at[moj, 'SCORE'] - 10]
    bez = analiza.sprzedaj_drogo("Napastnik", pula, slabsi, 99)
    assert len(bez) == 1 and bez[0]["zastepca"] is None and bez[0]["zysk"] is None

    baza, zastepczy, kandydaci = analiza.kandydaci_optymalizatora(pula, pula.index, 99)
    assert baza == pytest.approx(pula.at[moj, 'SCORE']) and not zastepczy
    assert kandydaci and all(k.zysk > 0 and k.pensja > 0 for k in kandydaci)
    assert str(pula.at[moj, 'ID']) not in {k.klucz for k in kandydaci}
    baza, zastepczy, _ = analiza.kandydaci_optymalizatora(pula, pula.index, 12345)       # brak moich
    assert zastepczy and baza == pytest.approx(pula['SCORE'].quantile(0.25))
