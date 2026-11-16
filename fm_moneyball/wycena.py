"""
Wykrywacz niedowartosciowanych zawodnikow: model ceny rynkowej w obrebie puli pozycji.

    log(cena) ~ SCORE + wiek + wiek^2 + lata kontraktu (odcinkami: zalamanie po 1 i 2 latach, max 5)

"Wycena wg wyniku" to cena typowa dla zawodnika z takim wynikiem, wiekiem i kontraktem.
Model celowo nie zna ligi ani reputacji klubu: zawodnik z mniejszej ligi czy klubu, ktory
gra tak samo dobrze, a kosztuje mniej, to wlasnie okazja, ktorej szukamy (SCORE ma juz korekte
sily ligi). "Niedowartosciowanie" = wycena / cena: 2,0 znaczy, ze gra jak zawodnik dwa razy drozszy.

Bez ekstrapolacji: log(cena) jest liniowy w SCORE, wiec poza zakresem danych wycena rosla wykladniczo
(najlepszy zawodnik pozycji, zwlaszcza bardzo mlody, dostawal wycene kilka razy wyzsza niz ktokolwiek
w puli i wychodzil na mocno niedowartosciowanego). Przy przewidywaniu SCORE i wiek sa obcinane do
zakresu zawodnikow, na ktorych model sie uczyl, a wycena nie przekracza najwyzszej ceny w puli.
Takie wyceny sa oznaczone ('Wycena_ograniczona').

Kontrakt odcinkami: w grze cena zawodnika z kontraktem krotszym niz rok jest bliska zeru niezaleznie od
wyniku, a kazdy kolejny rok podnosi ja coraz mniej - jedna prosta w log(cena) tego nie oddaje.
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
                         'wiek2': (wiek - 25.0) ** 2, 'lata': lata,
                         'lata_po1': (lata - 1.0).clip(lower=0), 'lata_po2': (lata - 2.0).clip(lower=0)},
                        index=pula.index)


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
    'Wycena wg wyniku', 'Niedowartościowanie'; opis modelu).
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
        # bez ekstrapolacji: SCORE i wiek obciete do zakresu danych uczacych, wycena <= najwyzsza cena
        do_wyceny = cechy[kompletne].copy()
        uczace_cechy = cechy[uczace]
        for kol in ('SCORE', 'wiek'):
            do_wyceny[kol] = do_wyceny[kol].clip(uczace_cechy[kol].min(), uczace_cechy[kol].max())
        do_wyceny['wiek2'] = (do_wyceny['wiek'] - 25.0) ** 2
        surowa = np.exp(cechy[kompletne].to_numpy() @ beta)
        wycena = np.minimum(np.exp(do_wyceny.to_numpy() @ beta), float(cena[uczace].max()))
        pula.loc[kompletne, 'Wycena wg wyniku'] = wycena
        pula['Wycena_ograniczona'] = False
        pula.loc[kompletne, 'Wycena_ograniczona'] = np.abs(wycena / surowa - 1) > 0.01
        z_cena = kompletne & (cena > 0)
        pula.loc[z_cena, 'Niedowartościowanie'] = pula.loc[z_cena, 'Wycena wg wyniku'] / cena[z_cena]
        # model do prognozy wartosci (prognoza_wartosci): wspolczynniki i zakres danych uczacych
        pula.attrs["model_ceny"] = {"beta": [float(b) for b in beta],
                                    "zakres": {k: (float(uczace_cechy[k].min()), float(uczace_cechy[k].max()))
                                               for k in ('SCORE', 'wiek')}}
        reszty = y[uzyte] - X[uzyte] @ beta
        wariancja = y[uzyte].var()
        wiek_sr = float(cechy.loc[uczace, 'wiek'].mean())
        # efekt roku wieku przy sredniej wieku puli (z czlonem kwadratowym)
        za_rok = beta[2] + beta[3] * (2 * (wiek_sr - 25.0) - 1)
        opis = {"r2": round(float(1 - reszty.var() / wariancja), 3) if wariancja > 0 else None,
                "liczba": int(uczace.sum()),
                "proc_za_10_score": round(float(np.expm1(10 * beta[1]) * 100), 1),
                "proc_za_rok_mlodszy": round(float(np.expm1(-za_rok) * 100), 1),
                "ograniczone": int(pula['Wycena_ograniczona'].sum()),
                "zakres_score": [round(float(uczace_cechy['SCORE'].min()), 1),
                                 round(float(uczace_cechy['SCORE'].max()), 1)]}
    return pula, opis


LAT_PROGNOZY_WARTOSCI = 2
LATA_KONTRAKTU_PROGNOZY = 3.0     # obie wyceny przy tym samym kontrakcie - zmienia sie tylko wynik i wiek
PROG_WZROSTU_WARTOSCI = 1.3       # okazja "kup teraz": prognoza co najmniej 1,3 x obecna wartosc...
MIN_SCORE_WZROSTU = 55.0          # ...u zawodnika wyraznie powyzej przecietnej juz teraz


def _log_wycena(model, score, wiek, lata):
    beta = np.asarray(model["beta"])
    (s_min, s_max), (w_min, w_max) = model["zakres"]["SCORE"], model["zakres"]["wiek"]
    score, wiek = np.clip(score, s_min, s_max), np.clip(wiek, w_min, w_max)
    cechy = np.column_stack([np.ones_like(score), score, wiek, (wiek - 25.0) ** 2, np.full_like(score, lata),
                             np.full_like(score, max(lata - 1.0, 0.0)), np.full_like(score, max(lata - 2.0, 0.0))])
    return cechy @ beta


def prognoza_wartosci(pula, model, lat=LAT_PROGNOZY_WARTOSCI):
    """
    'Wartość za 2 lata' i 'Zmiana wartości' (mnoznik): obecna wartosc x stosunek wyceny modelu za 2 lata (SCORE
    + typowy rozwoj w tym wieku z krzywej wieku historii kariery, wiek + 2) do wyceny dzis - obie przy tym samym
    kontrakcie. Mnoznik pokazuje wplyw wieku i rozwoju: mlodzi zyskuja, starsi traca. Obecna wartosc zawiera to,
    czego model nie widzi (reputacja, potencjal), wiec prognoza zaczyna od niej. Wymaga 'Rozwój_wiek_2'.
    """
    pula = pula.copy()
    pula['Wartość za 2 lata'] = np.nan
    pula['Zmiana wartości'] = np.nan
    if not model or 'Rozwój_wiek_2' not in pula.columns:
        return pula
    cena = pula['Wartość_Numeryczna'].astype(float)
    score = pula['SCORE'].astype(float).to_numpy()
    s2 = score + pula['Rozwój_wiek_2'].astype(float).to_numpy()
    wiek = pula['Wiek'].astype(float).to_numpy()
    teraz = _log_wycena(model, score, wiek, LATA_KONTRAKTU_PROGNOZY)
    potem = _log_wycena(model, s2, wiek + lat, LATA_KONTRAKTU_PROGNOZY)
    mnoznik = pd.Series(np.exp(potem - teraz), index=pula.index)
    ok = cena.gt(0) & mnoznik.notna()
    pula.loc[ok, 'Zmiana wartości'] = mnoznik[ok]
    pula.loc[ok, 'Wartość za 2 lata'] = cena[ok] * mnoznik[ok]
    return pula
