"""Funkcje Moneyball z analiza.py na sztucznych danych."""
from datetime import date

import numpy as np
import pandas as pd

from fm_moneyball import analiza

DZIS = date(2030, 1, 1)


def _pula():
    return pd.DataFrame({
        'Piłkarz': ["Tani", "Drogi", "Słaby", "Wolny", "Junior"],
        'SCORE': [60.0, 70.0, 40.0, 55.0, 52.0],
        'Wartość_Numeryczna': [1e6, 20e6, 0.5e6, 0.0, 2e6],
        'Zarobki_Numeryczne': [100e3, 2e6, 50e3, 300e3, 20e3],
        'Wygasa_Data': pd.to_datetime(["2030-05-01", "2033-06-30", "2030-11-01", None, "2032-06-30"]),
        'Wolny_agent': [False, False, False, True, False],
        'Wypożyczenie_do': pd.to_datetime([None, None, "2030-03-01", None, None]),
        'Wiek': [24, 33, 28, 30, 19],
        'Minuty': [2500, 2800, 1500, 1200, 300],
        'Kontuzje_2_lata': [0, 8, 1, 0, 0],
    })


def test_koszt_i_pareto():
    p = analiza.wzbogac(_pula(), DZIS)
    assert p.loc[0, 'Koszt'] == 1e6 + 3 * 100e3
    assert 'Opłacalność' not in p.columns
    assert p.loc[3, 'Koszt'] == 900e3             # wolny agent: sama placa
    pareto = analiza.oznacz_pareto(p)
    # Slaby (najtanszy), Wolny, Tani, Drogi (najlepszy) - Junior jest zdominowany przez Taniego
    assert list(pareto['Pareto']) == [True, True, True, True, False]


def test_okazje():
    okazje = analiza.wzbogac(_pula(), DZIS)['Okazje']
    assert "kontrakt ≤ 6 mies." in okazje[0] and "kontrakt ≤ 12 mies." in okazje[0]
    assert "kontrakt ≤ 6 mies." not in okazje[2] and "kontrakt ≤ 12 mies." in okazje[2]
    assert okazje[1] == "" and okazje[3] == "" and okazje[4] == ""     # bez "wolny agent" i "talent bez minut"
    assert set(analiza.OKAZJE) == {"niedowartościowany", "kontrakt ≤ 6 mies.", "kontrakt ≤ 12 mies.", "szybki rozwój"}
    f = analiza.Filtry(okazje=["kontrakt ≤ 6 mies."], bez_ceny=True)
    assert list(analiza.filtruj(analiza.wzbogac(_pula(), DZIS), f, DZIS)['Piłkarz']) == ["Tani"]


def test_szybki_rozwoj_i_filtr_rozwoju():
    pula = _pula().assign(**{'Δ SCORE': [2.0, 8.0, np.nan, 6.0, 7.0]})
    okazje = analiza.wzbogac(pula, DZIS)['Okazje']
    assert "szybki rozwój" in okazje[4]                 # +7 i 19 lat
    assert "szybki rozwój" not in okazje[1]             # +8, ale 33 lata
    widoczni = analiza.filtruj(analiza.wzbogac(pula, DZIS), analiza.Filtry(min_rozwoj=5, bez_ceny=True), DZIS)
    assert set(widoczni['Piłkarz']) == {"Drogi", "Wolny", "Junior"}


def test_bez_danych_ukrytych():
    p = analiza.wzbogac(_pula().assign(**{'Podatność na kontuzje': 20.0}), DZIS)
    assert 'Ryzyko' not in p.columns
    assert not any(k in analiza.POLA_WIERSZA for k in ('Ryzyko', 'Podatność na kontuzje', 'Determinacja'))


def test_filtr_minut_bez_kolumny_minut():
    pula = analiza.wzbogac(_pula().assign(Minuty=np.nan), DZIS)
    assert len(analiza.filtruj(pula, analiza.Filtry(min_minut=1000, bez_ceny=True), DZIS)) == 5
    pelna = analiza.wzbogac(_pula(), DZIS)
    assert set(analiza.filtruj(pelna, analiza.Filtry(min_minut=1000, bez_ceny=True), DZIS)['Piłkarz']) == \
        {"Tani", "Drogi", "Słaby", "Wolny"}


def test_moja_kadra():
    pula = _pula()
    pula['Klub_UID'] = [1, 1, 2, 3, 4]
    kadra = analiza.moja_kadra("Napastnik", pula, 1, DZIS)
    assert kadra["liczba"] == 2 and kadra["najlepszy"] == 70
    assert "luka" not in kadra and "cel" not in kadra
    assert kadra["konczace_kontrakty"] == 1
    assert [z["Piłkarz"] for z in kadra["zawodnicy"]] == ["Drogi", "Tani"]
    pusta = analiza.moja_kadra("Napastnik", pula, 99, DZIS)
    assert pusta["liczba"] == 0 and pusta["najlepszy"] is None


def test_maska_odniesienia_nie_zmienia_wyniku_nominalnych():
    rng = np.random.default_rng(3)
    pula = pd.DataFrame({'ID': [f"N{i}" for i in range(60)], 'Przechwyty/90': rng.gamma(3, 0.5, 60),
                         'Minuty': rng.integers(500, 3000, 60).astype(float)})
    inni = pd.DataFrame({'ID': ["K1", "K2"], 'Przechwyty/90': [20.0, 0.0], 'Minuty': [2500.0, 2500.0],
                         'Pula': ["Napastnik", "Napastnik"]})
    wagi = {'Przechwyty/90': 1}
    sama, _ = analiza.policz_wynik(pula, wagi, True, 5)
    ramka, maska = analiza.dolacz_kandydatow(pula, inni, "Środkowy Obrońca")
    razem, _ = analiza.policz_wynik(ramka, wagi, True, 5, maska)
    assert np.allclose(razem.loc[maska, 'SCORE'].to_numpy(), sama['SCORE'].to_numpy())
    assert np.allclose(razem.loc[maska, 'Percentyl'].to_numpy(), sama['Percentyl'].to_numpy())
    k1, k2 = razem[razem['ID'] == "K1"].iloc[0], razem[razem['ID'] == "K2"].iloc[0]
    assert k1['SCORE'] > sama['SCORE'].max() - 1 and k1['Percentyl'] == 100 and k2['Percentyl'] < 10
    assert k1['Kandydat z pozycji'] == "Napastnik"


def test_porownanie_z_moim_zawodnikiem():
    pula = _pula().assign(Klub_UID=[1, 1, 2, 3, 4], **{'Przechwyty/90': [2.0, 1.0, 3.0, 0.5, 1.5],
                                                       'Strata piłek na podanie': [0.1, 0.3, 0.2, 0.2, 0.05]})
    pula['ID'] = pula['Piłkarz']
    analiza.MERYTORYKA_WAG["Test"] = {'Przechwyty/90': 50, 'Strata piłek na podanie': 50}
    try:
        lepszy = pula.iloc[2].copy()
        lepszy['SCORE'] = 80.0
        wynik = analiza.porownaj_z_moim("Test", pula, lepszy, 1)
        assert wynik["moj"]["Piłkarz"] == "Drogi" and wynik["werdykt"] == "wzmocnienie" and wynik["roznica"] == 10
        cechy = {c["nazwa"]: c for c in wynik["cechy"]}
        assert cechy['Przechwyty/90']["lepszy"] == "kandydat"
        # mniej strat = lepiej: Drogi 0.3 vs kandydat 0.2
        assert cechy['Strata piłek na podanie']["nizsze_lepsze"] and cechy['Strata piłek na podanie']["lepszy"] == "kandydat"
        assert analiza.porownaj_z_moim("Test", pula, pula.iloc[4], 1)["werdykt"] == "nie wzmacnia"
        podobny = pula.iloc[4].copy()
        podobny['SCORE'] = 71.0
        assert analiza.porownaj_z_moim("Test", pula, podobny, 1)["werdykt"] == "podobny poziom"
        assert analiza.porownaj_z_moim("Test", pula, pula.iloc[0], 1)["werdykt"] == "twój zawodnik"
        assert analiza.porownaj_z_moim("Test", pula, pula.iloc[0], 99)["werdykt"] == "brak zawodnika"
    finally:
        del analiza.MERYTORYKA_WAG["Test"]


def test_oznaczenie_u21_i_brak_wiarygodnosci():
    p = analiza.wzbogac(_pula(), DZIS)
    assert list(p['U21']) == [False, False, False, False, True]
    assert 'Wiarygodność' not in analiza.POLA_WIERSZA
