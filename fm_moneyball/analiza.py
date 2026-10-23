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
    okazje: list = field(default_factory=list)   # zawodnik musi miec ktorykolwiek z tych znacznikow
    max_ryzyko: int | None = None
    min_oplacalnosc: float | None = None


# --- Moneyball: koszt, oplacalnosc, okazje, ryzyko ----------------------------------------------
OKAZJE = ("kontrakt ≤ 6 mies.", "kontrakt ≤ 12 mies.", "wolny agent", "koniec wypożyczenia", "talent bez minut")
POZIOM_ODNIESIENIA = 50.0   # SCORE przecietnego zawodnika pozycji
DUZY_KLUB = 7000            # reputacja klubu (1-10000), od ktorej klub uznajemy za duzy


def wzbogac(pula, data_gry=None, horyzont_lat=3):
    """
    Dolicza kolumny Moneyball (wymaga kolumny SCORE):
      Lata_kontraktu    - do konca kontraktu, od daty w grze
      Koszt             - wartosc transferowa + placa roczna x horyzont (wolny agent: sama placa)
      Opłacalność       - punkty SCORE ponad przecietnego (50) na 1 mln EUR kosztu
      Okazje            - znaczniki okazji transferowych (tekst rozdzielony "; ")
      Ryzyko            - 0-100 z danych ukrytych (podatnosc na kontuzje, regularnosc, wazne mecze,
                          wiek, kontuzje w 2 lata); brak, gdy zrodlo nie ma danych ukrytych
    """
    pula = pula.copy()
    dzis = pd.Timestamp(data_gry or date.today())
    lata = (pula['Wygasa_Data'] - dzis).dt.days / 365.25
    pula['Lata_kontraktu'] = lata.clip(lower=0)
    wartosc = pula['Wartość_Numeryczna']
    placa = pula['Zarobki_Numeryczne'].fillna(0)
    pula['Koszt'] = wartosc + placa * horyzont_lat
    with np.errstate(divide='ignore', invalid='ignore'):
        oplacalnosc = (pula['SCORE'] - POZIOM_ODNIESIENIA).clip(lower=0) / (pula['Koszt'] / 1e6)
    pula['Opłacalność'] = oplacalnosc.where(pula['Koszt'] > 0)

    wolny = pula['Wolny_agent'].fillna(False).astype(bool) if 'Wolny_agent' in pula.columns else pd.Series(False, index=pula.index)
    znaczniki = {
        "kontrakt ≤ 6 mies.": (lata > 0) & (lata <= 0.5) & ~wolny,
        "kontrakt ≤ 12 mies.": (lata > 0) & (lata <= 1) & ~wolny,
        "wolny agent": wolny,
    }
    if 'Wypożyczenie_do' in pula.columns:
        do_konca = (pula['Wypożyczenie_do'] - dzis).dt.days
        znaczniki["koniec wypożyczenia"] = do_konca.between(0, 183)
    if 'Reputacja_klubu' in pula.columns and 'Minuty' in pula.columns:
        znaczniki["talent bez minut"] = ((pula['Wiek'] <= 21) & (pula['Minuty'] < 900)
                                         & (pula['Reputacja_klubu'].fillna(0) >= DUZY_KLUB))
    tablica = pd.DataFrame({k: v.fillna(False).astype(bool) for k, v in znaczniki.items()}, index=pula.index)
    pula['Okazje'] = tablica.apply(lambda w: "; ".join(k for k, v in w.items() if v), axis=1) if len(pula) else []

    if 'Podatność na kontuzje' in pula.columns and pula['Podatność na kontuzje'].notna().any():
        skala = lambda kol, odwroc=False: ((20 - pula[kol]) if odwroc else (pula[kol] - 1)) / 19
        kontuzje = (pula['Kontuzje_2_lata'].fillna(0) / 4).clip(0, 1) if 'Kontuzje_2_lata' in pula.columns else 0
        ryzyko = (35 * skala('Podatność na kontuzje') + 20 * skala('Regularność', True)
                  + 15 * skala('Ważne mecze', True) + 15 * ((pula['Wiek'] - 30) / 5).clip(0, 1)
                  + 15 * kontuzje)
        pula['Ryzyko'] = ryzyko.round()
    return pula


def oznacz_pareto(widoczni):
    """Pareto = nikt nie ma jednoczesnie wyzszego SCORE i nizszego kosztu (sposrod widocznych)."""
    widoczni = widoczni.copy()
    z_kosztem = widoczni[widoczni['Koszt'].notna()].sort_values(['Koszt', 'SCORE'], ascending=[True, False])
    najlepszy = -np.inf
    pareto = []
    for idx, score in z_kosztem['SCORE'].items():
        if score > najlepszy:
            pareto.append(idx)
            najlepszy = score
    widoczni['Pareto'] = widoczni.index.isin(pareto)
    return widoczni


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
    if filtry.okazje and 'Okazje' in wynik.columns:
        maska = pd.Series(False, index=wynik.index)
        for znacznik in filtry.okazje:
            maska |= wynik['Okazje'].str.contains(znacznik, regex=False, na=False)
        wynik = wynik[maska]
    if filtry.max_ryzyko is not None and 'Ryzyko' in wynik.columns:
        wynik = wynik[wynik['Ryzyko'].isna() | (wynik['Ryzyko'] <= filtry.max_ryzyko)]
    if filtry.min_oplacalnosc and 'Opłacalność' in wynik.columns:
        wynik = wynik[wynik['Opłacalność'] >= filtry.min_oplacalnosc]
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
            'CA': 'int', 'PA': 'int', 'Strata piłek na podanie': 'dec2', 'Opłacalność': 'dec2', 'Ryzyko': 'int'}
# Kolumny prezentowane z pol liczbowych (sortowanie po liczbie, nie po tekscie)
_POLA = {'Cena': ('Wartość_Numeryczna', 'eur'), 'Płaca': ('Zarobki_Numeryczne', 'eur_tyg'),
         'Wygasa': ('Wygasa_Data', 'data'), 'Koszt (3 lata)': ('Koszt', 'eur')}
_TEKSTOWE = {'Piłkarz', 'Klub', 'Liga', 'Pozycja', 'Kraj', 'Preferowana noga', 'Okazje'}
# Kolumny Moneyball (z wzbogac), nie sa statystykami meczowymi
_MONEYBALL = {'Koszt (3 lata)', 'Opłacalność', 'Okazje', 'Ryzyko'}


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
    if 'Koszt' in pula.columns:
        po = 'Wygasa' if 'Wygasa' in nazwy else 'Cena'
        for kol in ('Okazje', 'Opłacalność', 'Koszt (3 lata)'):
            _wstaw_po(nazwy, kol, po)
        if pokaz_ukryte and 'Ryzyko' in pula.columns:
            _wstaw_po(nazwy, 'Ryzyko', 'Okazje')
    kolumny = []
    for nazwa in nazwy:
        pole, fmt = _POLA.get(nazwa, (nazwa, _FORMATY.get(nazwa, 'tekst' if nazwa in _TEKSTOWE else 'dec1')))
        kolumny.append({'naglowek': nazwa, 'pole': pole, 'format': fmt,
                        'statystyka': nazwa not in NIE_STATYSTYKI and nazwa not in _MONEYBALL,
                        'nizsze_lepsze': nazwa in NIZSZE_LEPSZE or nazwa == 'Ryzyko'})
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
                'Mnożnik_Ligi', 'Wypożyczony', 'Wypożyczenie_do', 'Wolny_agent', 'Lata_kontraktu', 'Koszt',
                'Opłacalność', 'Okazje', 'Pareto']
# Dane, ktorych gracz nie widzi wprost w grze - wysylane tylko przy wlaczonym przelaczniku
POLA_UKRYTE = ['CA', 'PA', 'Ryzyko', 'Regularność', 'Ważne mecze', 'Podatność na kontuzje', 'Determinacja',
               'Profesjonalizm', 'Ambicja', 'Adaptacja', 'Kontuzje_2_lata']


def pola_wiersza(pozycja, pula, pokaz_ukryte=False):
    pola = POLA_WIERSZA + (POLA_UKRYTE if pokaz_ukryte else []) + [
        k['pole'] for k in kolumny_tabeli(pozycja, pula, pokaz_ukryte)]
    if not pokaz_ukryte:
        pola = [p for p in pola if p not in POLA_UKRYTE]
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


# --- moja kadra -----------------------------------------------------------------------------------
POLA_KADRY = ['ID', 'Piłkarz', 'Klub_UID', 'Wiek', 'Pozycja', 'Minuty', 'SCORE', 'Percentyl', 'Wiarygodność',
              'Wartość_Numeryczna', 'Zarobki_Numeryczne', 'Wygasa_Data', 'Lata_kontraktu', 'Wypożyczony']


def moja_kadra(pozycja, pula_policzona, moj_klub_uid, data_gry=None, percentyl_celu=80):
    """
    Moi zawodnicy na pozycji na tle puli: najlepszy SCORE, wiek, kontrakty, luka do celu
    (`percentyl_celu` puli). Duza luka = priorytet transferowy.
    """
    pula = wzbogac(pula_policzona, data_gry)
    moi = pula[pula['Klub_UID'] == moj_klub_uid].sort_values('SCORE', ascending=False) \
        if 'Klub_UID' in pula.columns else pula.iloc[0:0]
    cel = float(np.nanpercentile(pula['SCORE'], percentyl_celu)) if pula['SCORE'].notna().any() else None
    najlepszy = float(moi['SCORE'].max()) if not moi.empty else None
    return {
        "pozycja": pozycja,
        "liczba": int(len(moi)),
        "najlepszy": najlepszy,
        "cel": cel,
        "luka": (cel - najlepszy) if cel is not None and najlepszy is not None else cel,
        "sredni_wiek": float(moi['Wiek'].mean()) if not moi.empty else None,
        "konczace_kontrakty": int((moi['Lata_kontraktu'] <= 1).sum()) if not moi.empty else 0,
        "zawodnicy": do_json(moi, POLA_KADRY),
    }
