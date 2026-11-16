from types import SimpleNamespace

import numpy as np
import pandas as pd

from fm_moneyball import analiza, fm_gra
from fm_moneyball.zrodla.zapis_fm import dane_fm


def _atrybuty(**wartosci):
    baza = {k: 10 for k in fm_gra.ATRYBUTY}
    baza.update(wartosci)
    return {fm_gra.PREFIKS_ATRYBUTU + k: v for k, v in baza.items()}


def test_ocena_roli_skala_atrybutow_i_najlepsza_rola():
    df = pd.DataFrame([_atrybuty(), _atrybuty(heading=20, jumping_reach=20, strength=20, bravery=20, teamwork=20,
                                              balance=20)])
    wynik = fm_gra.dolicz_role(df, "Napastnik")
    assert wynik.loc[0, "Ocena roli"] == 10.0                 # same dziesiatki -> 10
    assert wynik.loc[1, "Rola FM"] == "Target man"            # silny w powietrzu
    assert wynik.loc[1, "Ocena roli"] == wynik.loc[1, "Rola|Target man"]
    wybrana = fm_gra.dolicz_role(df, "Napastnik", rola="Snajper")
    assert (wybrana["Rola FM"] == "Snajper").all()


def test_wagi_silnika_premiuja_szybkosc():
    df = pd.DataFrame([_atrybuty(pace=20, acceleration=20), _atrybuty(technique=20, first_touch=20)])
    rola = fm_gra.ROLE_FM["Lewy Skrzydłowy"][0]
    z_silnikiem = fm_gra.ocena_roli(df, rola, silnik=True)
    bez = fm_gra.ocena_roli(df, rola, silnik=False)
    assert z_silnikiem[0] - z_silnikiem[1] > bez[0] - bez[1]
    # bramkarz bez wag silnika
    assert fm_gra.wagi_roli(fm_gra.ROLE_FM["Bramkarz"][0], True, bramkarz=True)["agility"] == 1.0


def test_bez_atrybutow_bez_zmian():
    df = pd.DataFrame({"SCORE": [50.0]})
    assert fm_gra.dolicz_role(df, "Napastnik") is df


def test_szansa_transferu_z_roznicy_reputacji():
    rep = pd.Series([3000, 5000, 5750, 8000])
    rep_klubu = pd.Series([3000, 5000, 5750, 8000])
    status = pd.Series([4, 4, 4, 4])
    kategoria, udzial = fm_gra.szansa_transferu(rep, rep_klubu, status, 5000)
    assert list(kategoria) == ["wysoka", "wysoka", "niska", "bardzo niska"]
    assert udzial.is_monotonic_decreasing


def test_kluczowy_zawodnik_nie_schodzi_do_slabszego_klubu():
    # jak Buendia: reputacja zawodnika podobna do mojego klubu, ale jego klub wyraznie silniejszy
    kluczowy, _ = fm_gra.szansa_transferu(pd.Series([6923]), pd.Series([7849]), pd.Series([3]), 6751)
    rezerwowy, _ = fm_gra.szansa_transferu(pd.Series([6923]), pd.Series([7849]), pd.Series([20]), 6751)
    assert kluczowy[0] == "bardzo niska"
    assert fm_gra.KOLEJNOSC_SZANSY[rezerwowy[0]] > fm_gra.KOLEJNOSC_SZANSY[kluczowy[0]]
    # wolny agent (bez klubu): tylko reputacja zawodnika
    wolny, _ = fm_gra.szansa_transferu(pd.Series([4000]), pd.Series([np.nan]), pd.Series([np.nan]), 6000)
    assert wolny[0] == "wysoka"


def test_klauzula_wg_kraju_i_daty():
    df = pd.DataFrame({
        "Klub_kraj_ID": [1, 2, 1, 1],
        "Klauzula_ogolna": [np.nan, np.nan, 5e6, np.nan],
        "Klauzula_zagraniczna": [9e6, 9e6, np.nan, np.nan],
        "Klauzula_krajowa": [np.nan, 4e6, 3e6, 2e6],
        "Klauzula_krajowa_do": [pd.NaT, pd.NaT, pd.NaT, pd.Timestamp("2027-01-01")],
    })
    wynik = fm_gra.klauzula_dla_klubu(df, kraj_mojego_klubu=1, data_gry="2028-01-01")
    assert np.isnan(wynik[0])          # klub z mojego kraju: zagraniczna nie obowiazuje
    assert wynik[1] == 9e6             # zagraniczny klub: krajowa nie obowiazuje
    assert wynik[2] == 3e6             # najnizsza z obowiazujacych
    assert np.isnan(wynik[3])          # krajowa wygasla


def test_home_grown_i_filtr():
    df = pd.DataFrame({"HG_kraje": ["1;2", "3", None], "HG_kluby": ["77", "88", None], "SCORE": [1.0, 2.0, 3.0]})
    hg = fm_gra.home_grown(df, 1, 77)
    assert list(hg.fillna("-")) == ["klub", "-", "-"]
    df["HG"] = fm_gra.home_grown(df, 3, 99)
    assert list(df["HG"].fillna("-")) == ["-", "kraj", "-"]
    widoczni = analiza.filtruj(df, analiza.Filtry(home_grown="kraj"))
    assert list(widoczni["SCORE"]) == [2.0]


def test_okazja_klauzuli_i_filtr_szansy():
    df = pd.DataFrame({"SCORE": [60.0, 60.0], "Wygasa_Data": [pd.Timestamp("2031-01-01")] * 2,
                       "Wartość_Numeryczna": [10e6, 10e6], "Zarobki_Numeryczne": [1e5, 1e5], "Wiek": [25, 25],
                       "Klauzula": [8e6, 15e6], "Szansa transferu": ["wysoka", "niska"]})
    wynik = analiza.wzbogac(df, "2028-01-01")
    assert "klauzula ≤ wartość" in wynik.loc[0, "Okazje"]
    assert "klauzula" not in wynik.loc[1, "Okazje"]
    assert len(analiza.filtruj(wynik, analiza.Filtry(min_szansa="średnia"))) == 1


def test_dane_fm_z_rekordu_zapisu():
    klauzule = [SimpleNamespace(kind=SimpleNamespace(raw=0x12), parameter=365, value=1000),
                SimpleNamespace(kind=SimpleNamespace(raw=0x00), parameter=None, value=3000),
                SimpleNamespace(kind=SimpleNamespace(raw=0x20), parameter=None, value=50)]
    zawodnik = SimpleNamespace(
        attributes=SimpleNamespace(pace=15, acceleration=0), reputation=SimpleNamespace(current=4000),
        club_reputation=5000, club_nation_id=137, home_grown_nation_ids=(137, 150), home_grown_club_uids=(5,),
        contract=SimpleNamespace(clauses=klauzule, start=pd.Timestamp("2027-01-01").date()))
    d = dane_fm(zawodnik, kurs=2.0)
    assert d["Atr|pace"] == 15 and d["Atr|acceleration"] is None and d["Atr|finishing"] is None
    assert d["Reputacja"] == 4000 and d["HG_kraje"] == "137;150" and d["HG_kluby"] == "5"
    assert d["Klauzula_krajowa"] == 2000.0 and d["Klauzula_ogolna"] == 6000.0
    assert d["Klauzula_krajowa_do"] == pd.Timestamp("2028-01-01")
