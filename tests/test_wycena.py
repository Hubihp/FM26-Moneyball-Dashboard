"""Model wyceny wg wyniku (wykrywacz niedowartosciowanych) na danych sztucznych."""
from datetime import date

import numpy as np
import pandas as pd
import pytest

from fm_moneyball import analiza
from fm_moneyball.wycena import MIN_ZAWODNIKOW, wycen

DZIS = date(2030, 1, 1)


def _pula(n=400, seed=7):
    rng = np.random.default_rng(seed)
    score = rng.normal(50, 10, n)
    wiek = rng.integers(18, 35, n).astype(float)
    lata = rng.uniform(0.3, 5, n)
    # cena rosnie z wynikiem, spada z wiekiem po 25 r.z., rosnie z dlugoscia kontraktu; szum ~10%
    log_cena = 14 + 0.08 * score - 0.01 * (wiek - 25) ** 2 + 0.15 * lata + rng.normal(0, 0.1, n)
    return pd.DataFrame({
        'ID': [f"Z{i}" for i in range(n)], 'SCORE': score, 'Wiek': wiek,
        'Wartość_Numeryczna': np.exp(log_cena), 'Zarobki_Numeryczne': np.exp(log_cena) / 20,
        'Wygasa_Data': pd.Timestamp(DZIS) + pd.to_timedelta(lata * 365.25, unit='D'),
    })


def test_wykrywa_podstawionego_tanszego_zawodnika():
    pula = _pula()
    pula.loc[0, 'Wartość_Numeryczna'] /= 3          # gra tak samo, kosztuje 3x mniej
    wynik, opis = wycen(pula, data_gry=DZIS)
    assert wynik.loc[0, 'Niedowartościowanie'] == pytest.approx(3, rel=0.25)
    assert wynik['Niedowartościowanie'].iloc[1:].median() == pytest.approx(1, rel=0.05)
    assert opis["liczba"] == 400 and opis["r2"] > 0.9
    assert opis["proc_za_10_score"] == pytest.approx(np.expm1(0.8) * 100, rel=0.05)


def test_bez_ceny_wolni_agenci_i_mala_pula():
    pula = _pula()
    pula.loc[1, 'Wartość_Numeryczna'] = np.nan
    pula['Wolny_agent'] = False
    pula.loc[2, ['Wartość_Numeryczna', 'Wolny_agent']] = [0.0, True]
    wynik, _ = wycen(pula, data_gry=DZIS)
    assert pd.isna(wynik.loc[1, 'Niedowartościowanie']) and pd.isna(wynik.loc[2, 'Niedowartościowanie'])
    assert wynik.loc[1, 'Wycena wg wyniku'] > 0          # wycena jest, brak tylko ilorazu
    mala, opis = wycen(_pula(n=MIN_ZAWODNIKOW - 1), data_gry=DZIS)
    assert mala['Niedowartościowanie'].isna().all() and opis["r2"] is None


def test_kandydaci_nie_zmieniaja_wyceny_pozycji():
    pula = _pula()
    obcy = _pula(n=50, seed=9).assign(ID=lambda d: "K" + d['ID'])
    obcy['Wartość_Numeryczna'] *= 50                    # zupelnie inny rynek
    sama, _ = wycen(pula, data_gry=DZIS)
    razem = pd.concat([pula, obcy], ignore_index=True)
    maska = pd.Series([True] * len(pula) + [False] * len(obcy))
    z_obcymi, _ = wycen(razem, maska, data_gry=DZIS)
    assert np.allclose(z_obcymi.loc[maska, 'Wycena wg wyniku'].to_numpy(), sama['Wycena wg wyniku'].to_numpy())
    assert z_obcymi.loc[~maska, 'Niedowartościowanie'].median() < 0.1


def test_znacznik_okazji_i_brak_ca():
    pula = _pula()
    pula['CA'] = 120.0                                  # CA nie jest juz uzywane
    pula.loc[6, 'Wartość_Numeryczna'] /= 4
    pula.loc[6, 'SCORE'] = max(pula.loc[6, 'SCORE'], 60.0)
    wynik, _ = wycen(pula, data_gry=DZIS)
    assert 'Wynik ponad CA' not in wynik.columns
    wzbogacona = analiza.wzbogac(wynik, DZIS)
    assert "niedowartościowany" in wzbogacona.loc[6, 'Okazje']
    widoczni = analiza.filtruj(wzbogacona, analiza.Filtry(min_niedowartosciowanie=2), DZIS)
    assert 6 in widoczni.index and (widoczni['Niedowartościowanie'] >= 2).all()


def test_bez_ekstrapolacji_poza_zakres_danych():
    pula = _pula()
    # kandydat spoza pozycji z SCORE daleko powyzej puli (bez ceny) i najmlodszy zawodnik
    pula.loc[len(pula)] = {'ID': "K", 'SCORE': 140.0, 'Wiek': 16.0, 'Wartość_Numeryczna': np.nan,
                           'Zarobki_Numeryczne': np.nan, 'Wygasa_Data': pd.Timestamp(DZIS) + pd.Timedelta(days=900)}
    maska = pd.Series([True] * (len(pula) - 1) + [False])
    wynik, opis = wycen(pula, maska, data_gry=DZIS)
    k = wynik.iloc[-1]
    # dawniej exp(0.08 * 90 ponad srednia) ~ x1300; teraz nie wiecej niz najdrozszy w puli
    assert k['Wycena wg wyniku'] <= pula['Wartość_Numeryczna'].max() + 1 and k['Wycena_ograniczona']
    # wewnatrz zakresu wycena bez zmian (oznaczonych tylko kilka skrajnych)
    assert wynik['Wycena_ograniczona'].iloc[:-1].mean() < 0.05
    assert opis["ograniczone"] >= 1 and opis["zakres_score"][1] < 140
