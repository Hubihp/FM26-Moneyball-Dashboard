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
        'Reputacja_klubu': [3000, 9000, 2000, None, 8500],
        'Wiek': [24, 33, 28, 30, 19],
        'Minuty': [2500, 2800, 1500, 1200, 300],
        'Podatność na kontuzje': [1.0, 20.0, 10.0, 10.0, np.nan],
        'Regularność': [20.0, 1.0, 10.0, 10.0, np.nan],
        'Ważne mecze': [20.0, 1.0, 10.0, 10.0, np.nan],
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
    assert "koniec wypożyczenia" in okazje[2]
    assert okazje[3] == "wolny agent"
    assert okazje[4] == "talent bez minut"
    assert okazje[1] == ""
    f = analiza.Filtry(okazje=["wolny agent", "talent bez minut"], bez_ceny=True)
    assert list(analiza.filtruj(analiza.wzbogac(_pula(), DZIS), f, DZIS)['Piłkarz']) == ["Wolny", "Junior"]


def test_ryzyko():
    p = analiza.wzbogac(_pula(), DZIS)
    assert p.loc[0, 'Ryzyko'] == 0
    assert p.loc[1, 'Ryzyko'] > 90
    assert pd.isna(p.loc[4, 'Ryzyko'])
    f = analiza.Filtry(max_ryzyko=50, bez_ceny=True)
    assert "Drogi" not in analiza.filtruj(p, f, DZIS)['Piłkarz'].tolist()


def test_bez_danych_ukrytych_brak_ryzyka():
    p = analiza.wzbogac(_pula().drop(columns=['Podatność na kontuzje']), DZIS)
    assert 'Ryzyko' not in p.columns


def test_moja_kadra_luka():
    pula = _pula()
    pula['Klub_UID'] = [1, 1, 2, 3, 4]
    kadra = analiza.moja_kadra("Napastnik", pula, 1, DZIS, percentyl_celu=80)
    assert kadra["liczba"] == 2 and kadra["najlepszy"] == 70
    assert kadra["cel"] == np.percentile(pula['SCORE'], 80)
    assert kadra["luka"] == kadra["cel"] - 70
    assert kadra["konczace_kontrakty"] == 1
    assert [z["Piłkarz"] for z in kadra["zawodnicy"]] == ["Drogi", "Tani"]
    pusta = analiza.moja_kadra("Napastnik", pula, 99, DZIS)
    assert pusta["liczba"] == 0 and pusta["luka"] == pusta["cel"]


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
