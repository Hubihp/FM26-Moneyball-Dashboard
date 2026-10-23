"""
Wykrywacz niedowartosciowanych zawodnikow: model ceny rynkowej w obrebie puli pozycji.

    log(cena) ~ SCORE + wiek + wiek^2 + min(lata kontraktu, 5)

"Wycena wg wyniku" to cena typowa dla zawodnika z takim wynikiem, wiekiem i kontraktem.
Model celowo nie zna ligi, reputacji klubu ani CA: zawodnik z mniejszej ligi czy klubu, ktory
gra tak samo dobrze, a kosztuje mniej, to wlasnie okazja, ktorej szukamy (SCORE ma juz korekte
sily ligi). "Niedowartosciowanie" = wycena / cena: 2,0 znaczy, ze gra jak zawodnik dwa razy drozszy.

Przy danych ukrytych dochodzi "Wynik ponad CA": o ile SCORE zawodnika przewyzsza wynik typowy
dla jego CA w tej puli (statystyki lepsze niz atrybuty - albo odwrotnie, gdy ujemny).
"""
from datetime import date

import numpy as np
import pandas as pd

from fm_moneyball.model import maska_odniesienia

MIN_ZAWODNIKOW = 40         # mniej zawodnikow z cena = brak modelu (za malo danych)
PROG_ODSTAJACYCH = 3.0      # reszty powyzej tylu odchylen nie ucza modelu (druga iteracja)
MAKS_LAT_KONTRAKTU = 5.0


def _lata_kontraktu(pula, data_gry):
    if 'Lata_kontraktu' in pula.columns:
        return pula['Lata_kontraktu'].astype(float)
    if 'Wygasa_Data' in pula.columns:
        dzis = pd.Timestamp(data_gry or date.today())
        return (pula['Wygasa_Data'] - dzis).dt.days / 365.25
    return pd.Series(np.nan, index=pula.index)


def _cechy(pula, data_gry=None):
    wiek = pula['Wiek'].astype(float)
    lata = _lata_kontraktu(pula, data_gry)
    lata = lata.clip(0, MAKS_LAT_KONTRAKTU).fillna(lata.median() if lata.notna().any() else 0.0)
    return pd.DataFrame({'stala': 1.0, 'SCORE': pula['SCORE'].astype(float), 'wiek': wiek,
                         'wiek2': (wiek - 25.0) ** 2, 'lata': lata}, index=pula.index)


def _dopasuj(X, y):
    """Najmniejsze kwadraty z jedna iteracja odrzucenia odstajacych; zwraca (wspolczynniki, maska uzytych)."""
    uzyte = np.ones(len(y), dtype=bool)
    beta = None
    for _ in range(2):
        beta, *_ = np.linalg.lstsq(X[uzyte], y[uzyte], rcond=None)
        reszty = y - X @ beta
        odchylenie = reszty[uzyte].std()
        if not np.isfinite(odchylenie) or odchylenie == 0:
            break
        uzyte = np.abs(reszty) <= PROG_ODSTAJACYCH * odchylenie
    return beta, uzyte


def wycen(pula, odniesienie=None, data_gry=None):
    """
    Pula z SCORE -> (kopia z kolumnami
    'Wycena wg wyniku', 'Niedowartościowanie', opcjonalnie 'Wynik ponad CA'; opis modelu).
    Model uczy sie na zawodnikach pozycji (`odniesienie`) z cena > 0; wycene dostaja wszyscy.
    """
    pula = pula.copy()
    pula['Wycena wg wyniku'] = np.nan
    pula['Niedowartościowanie'] = np.nan
    opis = {"r2": None, "liczba": 0, "proc_za_10_score": None, "proc_za_rok_mlodszy": None}
    if not {'SCORE', 'Wiek', 'Wartość_Numeryczna'} <= set(pula.columns):
        return pula, opis

    cena = pula['Wartość_Numeryczna'].astype(float)
    cechy = _cechy(pula, data_gry)
    kompletne = cechy.notna().all(axis=1)
    ref = maska_odniesienia(pula, odniesienie)
    uczace = ref & kompletne & (cena > 0)
    if 'Wolny_agent' in pula.columns:
        uczace &= ~pula['Wolny_agent'].fillna(False).astype(bool)
    if uczace.sum() >= MIN_ZAWODNIKOW:
        X, y = cechy[uczace].to_numpy(), np.log(cena[uczace].to_numpy())
        beta, uzyte = _dopasuj(X, y)
        przewidywane = cechy[kompletne].to_numpy() @ beta
        pula.loc[kompletne, 'Wycena wg wyniku'] = np.exp(przewidywane)
        z_cena = kompletne & (cena > 0)
        pula.loc[z_cena, 'Niedowartościowanie'] = pula.loc[z_cena, 'Wycena wg wyniku'] / cena[z_cena]
        reszty = y[uzyte] - X[uzyte] @ beta
        wariancja = y[uzyte].var()
        wiek_sr = float(cechy.loc[uczace, 'wiek'].mean())
        # efekt roku wieku przy sredniej wieku puli (z czlonem kwadratowym)
        za_rok = beta[2] + beta[3] * (2 * (wiek_sr - 25.0) - 1)
        opis = {"r2": round(float(1 - reszty.var() / wariancja), 3) if wariancja > 0 else None,
                "liczba": int(uczace.sum()),
                "proc_za_10_score": round(float(np.expm1(10 * beta[1]) * 100), 1),
                "proc_za_rok_mlodszy": round(float(np.expm1(-za_rok) * 100), 1)}

    if 'CA' in pula.columns and pula.loc[ref, 'CA'].notna().sum() >= MIN_ZAWODNIKOW:
        ca = pula['CA'].astype(float)
        uczace_ca = ref & ca.notna() & pula['SCORE'].notna()
        a, b = np.polyfit(ca[uczace_ca], pula.loc[uczace_ca, 'SCORE'].astype(float), 1)
        pula['Wynik ponad CA'] = pula['SCORE'] - (a * ca + b)
    return pula, opis
