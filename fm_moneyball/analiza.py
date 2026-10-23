"""
Analiza puli zawodnikow jednej pozycji: wynik, filtry, kolumny tabeli, radar, sobowtor.

Czyste funkcje na kanonicznym DataFrame (bez interfejsu) - uzywane przez serwer API.
"""
from dataclasses import dataclass, field
from datetime import date

import numpy as np
import pandas as pd

from fm_moneyball.model import macierz_stylu, oblicz_score, percentyl_w_puli
from fm_moneyball.stale import (KOLUMNY_PER_POZYCJA, KOLUMNY_UKRYTE, MAPOWANIE_NAZW_LIG, MERYTORYKA_WAG,
                                NEUTRALNE, NIE_STATYSTYKI, NIZSZE_LEPSZE)


@dataclass
class Filtry:
    ligi: list = field(default_factory=list)
    nogi: list = field(default_factory=list)
    wiek: tuple | None = None            # (min, max)
    cena: tuple | None = None            # (min, max) w EUR; None = bez ograniczen
    bez_ceny: bool = True                # czy pokazywac zawodnikow bez ceny ("Nie na sprzedaz")
    szukaj: str = ""
    kontrakt_mies: int | None = None     # kontrakt wygasa w ciagu N miesiecy od daty w grze
    min_minut: int = 0
    bez_mojego_klubu: bool = False


def wagi_domyslne(pozycja, df):
    """Domyslne wagi pozycji, tylko dla cech obecnych w danych."""
    return {c: w for c, w in MERYTORYKA_WAG.get(pozycja, {}).items() if c in df.columns}


def policz_wynik(df, wagi, ignoruj_mnoznik=False, k_baza=5):
    """Pula -> kopia z kolumnami SCORE, Percentyl, Wiarygodnosc; plus lista pominietych cech."""
    pula = df.copy()
    score, wiarygodnosc, pominiete = oblicz_score(pula, wagi, ignoruj_mnoznik, k_baza)
    pula['SCORE'] = score
    pula['Percentyl'] = score.rank(pct=True) * 100
    pula['Wiarygodność'] = wiarygodnosc
    return pula, pominiete


def filtruj(pula, filtry, data_gry=None, moj_klub_uid=None):
    """Zastosowanie filtrow; zwraca widok posortowany malejaco po SCORE."""
    wynik = pula
    if filtry.wiek and 'Wiek' in wynik.columns:
        wynik = wynik[wynik['Wiek'].between(*filtry.wiek)]
    if filtry.cena is not None:
        cena = wynik['Wartość_Numeryczna']
        lo, hi = filtry.cena
        w_zakresie = cena.between(lo if lo is not None else -np.inf, hi if hi is not None else np.inf)
        wynik = wynik[w_zakresie | (cena.isna() & filtry.bez_ceny)]
    elif not filtry.bez_ceny:
        wynik = wynik[wynik['Wartość_Numeryczna'].notna()]
    if filtry.ligi and 'Liga' in wynik.columns:
        wynik = wynik[wynik['Liga'].isin(filtry.ligi)]
    if filtry.nogi and 'Preferowana noga' in wynik.columns:
        wynik = wynik[wynik['Preferowana noga'].isin(filtry.nogi)]
    if filtry.min_minut and 'Minuty' in wynik.columns:
        wynik = wynik[wynik['Minuty'].fillna(0) >= filtry.min_minut]
    if filtry.kontrakt_mies:
        start = pd.Timestamp(data_gry or date.today())
        koniec = start + pd.DateOffset(months=int(filtry.kontrakt_mies))
        wygasa = wynik['Wygasa_Data']
        wynik = wynik[wygasa.notna() & (wygasa >= start) & (wygasa <= koniec)]
    if filtry.bez_mojego_klubu and moj_klub_uid is not None and 'Klub_UID' in wynik.columns:
        wynik = wynik[wynik['Klub_UID'] != moj_klub_uid]
    if filtry.szukaj:
        warunek = pd.Series(False, index=wynik.index)
        for kol in ('Piłkarz', 'Klub'):
            if kol in wynik.columns:
                warunek |= wynik[kol].astype(str).str.contains(filtry.szukaj, case=False, na=False, regex=False)
        wynik = wynik[warunek]
    return wynik.sort_values('SCORE', ascending=False)


# --- kolumny tabeli -----------------------------------------------------------------------------
# Format wartosci dla interfejsu: score, pasek (0-100), int, dec1, dec2, eur, eur_tyg, data, tekst
_FORMATY = {'SCORE': 'score', 'Percentyl': 'pasek', 'Wiarygodność': 'pasek', 'Wiek': 'int', 'Minuty': 'int',
            'CA': 'int', 'PA': 'int', 'Strata piłek na podanie': 'dec2'}
# Kolumny prezentowane z pol liczbowych (sortowanie po liczbie, nie po tekscie)
_POLA = {'Cena': ('Wartość_Numeryczna', 'eur'), 'Płaca': ('Zarobki_Numeryczne', 'eur_tyg'),
         'Wygasa': ('Wygasa_Data', 'data')}
_TEKSTOWE = {'Piłkarz', 'Klub', 'Liga', 'Pozycja', 'Kraj', 'Preferowana noga'}


def _wstaw_po(lista, nowy, po):
    if nowy not in lista:
        lista.insert(lista.index(po) + 1 if po in lista else len(lista), nowy)


def kolumny_tabeli(pozycja, pula, pokaz_ukryte=False):
    """Lista kolumn tabeli: [{naglowek, pole, format, statystyka, nizsze_lepsze}]."""
    nazwy = [c for c in KOLUMNY_PER_POZYCJA.get(pozycja, []) if c in pula.columns]
    if pula['Wiarygodność'].notna().any():
        _wstaw_po(nazwy, 'Wiarygodność', 'Percentyl')
    if 'Minuty' in pula.columns and pula['Minuty'].notna().any():
        _wstaw_po(nazwy, 'Minuty', 'Klub')
    if 'Płaca' in pula.columns:
        _wstaw_po(nazwy, 'Płaca', 'Cena')
    if 'Wygasa' in pula.columns:
        _wstaw_po(nazwy, 'Wygasa', 'Płaca' if 'Płaca' in nazwy else 'Cena')
    if pokaz_ukryte:
        for kol in reversed(KOLUMNY_UKRYTE):
            if kol in pula.columns and pula[kol].notna().any():
                _wstaw_po(nazwy, kol, 'Wiek')
    kolumny = []
    for nazwa in nazwy:
        pole, fmt = _POLA.get(nazwa, (nazwa, _FORMATY.get(nazwa, 'tekst' if nazwa in _TEKSTOWE else 'dec1')))
        kolumny.append({'naglowek': nazwa, 'pole': pole, 'format': fmt,
                        'statystyka': nazwa not in NIE_STATYSTYKI,
                        'nizsze_lepsze': nazwa in NIZSZE_LEPSZE})
    return kolumny


def kolumny_statystyk(pozycja, pula):
    return [c for c in KOLUMNY_PER_POZYCJA.get(pozycja, []) if c not in NIE_STATYSTYKI and c in pula.columns]


def do_json(ramka, pola):
    """Ramka -> lista slownikow (NaN -> None, daty -> ISO), tylko wybrane pola."""
    pola = [p for p in dict.fromkeys(pola) if p in ramka.columns]
    wynik = ramka[pola].copy()
    for kol in pola:
        if pd.api.types.is_datetime64_any_dtype(wynik[kol]):
            wynik[kol] = wynik[kol].dt.strftime('%Y-%m-%d')
    wynik = wynik.astype(object).where(pd.notna(wynik), None)
    rekordy = wynik.to_dict('records')
    for rekord in rekordy:
        for k, v in rekord.items():
            if isinstance(v, (np.integer,)):
                rekord[k] = int(v)
            elif isinstance(v, (np.floating,)):
                rekord[k] = float(v)
            elif isinstance(v, np.bool_):
                rekord[k] = bool(v)
    return rekordy


POLA_WIERSZA = ['ID', 'Piłkarz', 'Klub', 'Klub_UID', 'Liga', 'Wiek', 'Pozycja', 'Preferowana noga', 'Minuty',
                'SCORE', 'Percentyl', 'Wiarygodność', 'Wartość_Numeryczna', 'Zarobki_Numeryczne', 'Wygasa_Data',
                'Mnożnik_Ligi', 'Wypożyczony', 'CA', 'PA']


def pola_wiersza(pozycja, pula, pokaz_ukryte=False):
    pola = POLA_WIERSZA + [k['pole'] for k in kolumny_tabeli(pozycja, pula, pokaz_ukryte)]
    if not pokaz_ukryte:
        pola = [p for p in pola if p not in KOLUMNY_UKRYTE]
    return pola


def kolejnosc_lig(ligi):
    znane = list(MAPOWANIE_NAZW_LIG.values())
    return sorted(ligi, key=lambda x: (znane.index(x) if x in znane else 999, str(x)))


# --- radar i sobowtor ---------------------------------------------------------------------------
def radar(pozycja, pula, ids):
    """Percentyle statystyk (0-100, odwrocone dla 'mniej = lepiej') wybranych zawodnikow."""
    kolumny = [c for c in kolumny_statystyk(pozycja, pula) if c not in NEUTRALNE]
    seria = []
    for id_ in ids:
        wiersz = pula[pula['ID'] == id_]
        if wiersz.empty:
            continue
        wiersz = wiersz.iloc[0]
        wartosci = []
        for c in kolumny:
            p = percentyl_w_puli(pula[c], wiersz[c])
            wartosci.append(round(100.0 - p if c in NIZSZE_LEPSZE else p, 1))
        surowe = [None if pd.isna(wiersz[c]) else round(float(wiersz[c]), 3) for c in kolumny]
        seria.append({'id': id_, 'percentyle': wartosci, 'wartosci': surowe})
    etykiety = [c + " (odwrócone)" if c in NIZSZE_LEPSZE else c for c in kolumny]
    return {'etykiety': etykiety, 'seria': seria}


def podobni(pozycja, pula, widoczni_idx, id_, k_baza=5, n=10):
    """Najbardziej podobni zawodnicy (kosinus na skurczonych z-score'ach) sposrod widocznych."""
    macierz = macierz_stylu(pula, kolumny_statystyk(pozycja, pula), k_baza)
    if macierz.shape[1] < 2 or not (pula['ID'] == id_).any():
        return pula.iloc[0:0].assign(Podobieństwo=[])
    M = macierz.values
    wektor = M[int(np.flatnonzero(pula['ID'].values == id_)[0])]
    normy = np.linalg.norm(M, axis=1) * np.linalg.norm(wektor)
    with np.errstate(divide='ignore', invalid='ignore'):
        podobienstwo = np.where(normy > 0, M @ wektor / normy, 0.0)
    wyniki = pula.assign(Podobieństwo=podobienstwo)
    wyniki = wyniki[wyniki.index.isin(widoczni_idx) & (wyniki['ID'] != id_)]
    return wyniki.sort_values('Podobieństwo', ascending=False).head(n)
