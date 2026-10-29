import numpy as np
import pandas as pd
import pytest

from fm_moneyball.model import macierz_stylu, oblicz_score, oblicz_z
from fm_moneyball.schemat import dopelnij_schemat
from fm_moneyball.stale import MNOZNIK_NIEZNANEJ_LIGI, MNOZNIKI_LIG


def _pula(n=200, seed=1):
    rng = np.random.default_rng(seed)
    return pd.DataFrame({
        'Piłkarz': [f"Z{i}" for i in range(n)],
        'Liga': rng.choice(["Premier League", "I liga"], n),
        'Oczekiwane asysty/90': rng.gamma(2, 0.1, n),
        'Przechwyty/90': rng.gamma(3, 0.5, n),
        'Minuty': rng.integers(90, 3000, n).astype(float),
    })


def test_nieznana_liga_nie_jest_premiowana():
    df = dopelnij_schemat(pd.DataFrame({'Piłkarz': ['A', 'B'], 'Liga': ['Premier League', 'Liga Marsjańska']}))
    assert df.loc[1, 'Mnożnik_Ligi'] == MNOZNIK_NIEZNANEJ_LIGI
    assert df.loc[1, 'Mnożnik_Ligi'] < df.loc[0, 'Mnożnik_Ligi']
    assert bool(df.loc[1, 'Liga_bez_mnoznika'])


def test_korekta_ligowa_jest_addytywna():
    df = dopelnij_schemat(_pula())
    wagi = {'Oczekiwane asysty/90': 50, 'Przechwyty/90': 50}
    bez, _ = oblicz_score(df, wagi, ignoruj_mnoznik=True, k_baza=5)
    z, _ = oblicz_score(df, wagi, ignoruj_mnoznik=False, k_baza=5)
    roznica = (z - bez).round(9)
    oczekiwana = 50 * (df['Liga'].map({"Premier League (ANG 1)": MNOZNIKI_LIG["Premier League"],
                                       "I liga (POL 2)": MNOZNIKI_LIG["I liga"]}) - 1)
    # Kara zalezy tylko od ligi, nie od poziomu wyniku
    assert np.allclose(roznica, oczekiwana)


def test_skurczenie_przyciaga_mala_probe_do_sredniej():
    df = _pula()
    df.loc[0, ['Oczekiwane asysty/90', 'Minuty']] = [5.0, 10]      # kosmiczna wartosc po 10 minutach
    df.loc[1, ['Oczekiwane asysty/90', 'Minuty']] = [0.6, 3000]
    z, n90 = oblicz_z(df, ['Oczekiwane asysty/90'], k_baza=5)
    assert z['Oczekiwane asysty/90'][0] < z['Oczekiwane asysty/90'][1]
    assert n90 is not None


def test_odchylenie_wazone_minutami_odporne_na_mala_probe():
    df = _pula()
    df.loc[:4, 'Oczekiwane asysty/90'] = 50.0     # kilku zawodnikow z absurdalnymi wartosciami...
    df.loc[:4, 'Minuty'] = 1.0                    # ...po jednej minucie
    z, _ = oblicz_z(df, ['Oczekiwane asysty/90'], k_baza=0)
    # bez wazenia odchylenie urosloby kilkadziesiat razy i splaszczylo z-score reszty do ~0
    assert z['Oczekiwane asysty/90'].iloc[5:].std() > 0.5


def test_brak_minut_dziala_jak_dawniej():
    df = _pula().drop(columns='Minuty')
    score, pominiete = oblicz_score(dopelnij_schemat(df), {'Przechwyty/90': 1}, True, 5)
    assert score.mean() == pytest.approx(50) and pominiete == []


def test_macierz_stylu_pomija_stale_kolumny():
    df = _pula()
    df['Stała/90'] = 1.0
    m = macierz_stylu(df, ['Oczekiwane asysty/90', 'Przechwyty/90', 'Stała/90'], k_baza=5)
    assert list(m.columns) == ['Oczekiwane asysty/90', 'Przechwyty/90']


def test_ustaw_ligi_po_wczytaniu():
    from fm_moneyball.schemat import ustaw_ligi
    df = dopelnij_schemat(pd.DataFrame({'Piłkarz': ['A', 'B', 'C'], 'Liga': ['Rozgrywki #32', 'Rozgrywki #9', 'Wolny agent'],
                                        'Liga_klucz': [32, 9, None],
                                        'Liga_domyslna': ['Rozgrywki #32', 'Rozgrywki #9', 'Wolny agent']}))
    wynik = ustaw_ligi(df, {32: "Serie A", 9: "Liga Testowa"}, {**MNOZNIKI_LIG, "Liga Testowa": 0.7})
    assert list(wynik['Liga']) == ["Serie A (WLO 1)", "Liga Testowa", "Wolny agent"]
    assert list(wynik['Mnożnik_Ligi']) == [MNOZNIKI_LIG["Serie A"], 0.7, MNOZNIK_NIEZNANEJ_LIGI]
    assert list(wynik['Liga_bez_mnoznika']) == [False, False, True]


def test_skala_wyniku_bez_zawodnikow_z_brakami():
    """Zawodnicy bez danych (uzupelniani srednia) nie zawezaja skali wyniku pozostalych."""
    rng = np.random.default_rng(1)
    pelni = pd.DataFrame({"Przechwyty/90": rng.normal(2, 0.5, 100), "Odzyskane piłki/90": rng.normal(8, 2, 100)})
    braki = pd.DataFrame({"Przechwyty/90": [np.nan] * 300, "Odzyskane piłki/90": [np.nan] * 300})
    wagi = {"Przechwyty/90": 50, "Odzyskane piłki/90": 50}
    sami, _ = oblicz_score(pelni, wagi, True, 0)
    razem, _ = oblicz_score(pd.concat([pelni, braki], ignore_index=True), wagi, True, 0)
    assert np.allclose(razem[:100], sami)                  # ta sama skala dla zawodnikow z danymi
    assert np.allclose(razem[100:], 50, atol=0.1)          # brak danych = przecietny
