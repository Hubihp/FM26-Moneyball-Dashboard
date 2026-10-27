"""
Analiza puli zawodnikow jednej pozycji: wynik, filtry, kolumny tabeli, radar, sobowtor.

Czyste funkcje na kanonicznym DataFrame (bez interfejsu) - uzywane przez serwer API.
"""
from dataclasses import dataclass, field
from datetime import date

import numpy as np
import pandas as pd

from fm_moneyball.model import maska_odniesienia, macierz_stylu, oblicz_score, percentyl_w_puli
from fm_moneyball.stale import (KOLUMNY_PER_POZYCJA, MAPOWANIE_NAZW_LIG, MERYTORYKA_WAG,
                                NEUTRALNE, NIE_STATYSTYKI, NIZSZE_LEPSZE, kolumna_oceny)


@dataclass
class Filtry:
    ligi: list = field(default_factory=list)
    nogi: list = field(default_factory=list)
    kraje: list = field(default_factory=list)    # narodowosci (kolumna 'Kraj')
    wiek: tuple | None = None            # (min, max)
    cena: tuple | None = None            # (min, max) w EUR; None = bez ograniczen
    bez_ceny: bool = True                # czy pokazywac zawodnikow bez ceny ("Nie na sprzedaz")
    szukaj: str = ""
    kontrakt_mies: int | None = None     # kontrakt wygasa w ciagu N miesiecy od daty w grze
    min_minut: int = 0
    bez_mojego_klubu: bool = False
    okazje: list = field(default_factory=list)   # zawodnik musi miec ktorykolwiek z tych znacznikow
    tylko_z_okazja: bool = False                 # zawodnik musi miec jakakolwiek okazje (karta Okazje)
    min_rozwoj: float | None = None              # zmiana SCORE wzgledem poprzedniego sezonu (historia)
    min_niedowartosciowanie: float | None = None  # wycena wg wyniku / cena
    kandydaci: bool = False                      # pokaz kandydatow do przekwalifikowania z innych pozycji
    min_score_kandydata: float = 60.0
    kandydaci_z: list = field(default_factory=list)  # pozycje, z ktorych pochodza kandydaci (puste = wszystkie)


# --- Moneyball: koszt, okazje -------------------------------------------------------------------
OKAZJE = ("niedowartościowany", "kontrakt ≤ 6 mies.", "kontrakt ≤ 12 mies.", "szybki rozwój")
PROG_NIEDOWARTOSCIOWANIA = 2.0   # wycena wg wyniku co najmniej 2x wyzsza niz cena...
MIN_SCORE_NIEDOWARTOSCIOWANEGO = 55.0   # ...u zawodnika wyraznie powyzej przecietnej
PROG_SZYBKIEGO_ROZWOJU = 5.0     # wzrost SCORE wzgledem poprzedniego sezonu (historia zapisow)...
MAKS_WIEK_ROZWOJU = 23           # ...u mlodego zawodnika
# Do tego wieku cena zawiera potencjal, ktorego model wyceny nie widzi (zna tylko wynik, wiek i kontrakt):
# "Niedowartosciowanie" jest u nich zanizone - interfejs oznacza je jako U21
MAKS_WIEK_U21 = 21
# Werdykt porownania z moim zawodnikiem: roznica SCORE, od ktorej kandydat jest wzmocnieniem
PROG_WZMOCNIENIA = 3.0


def wzbogac(pula, data_gry=None, horyzont_lat=3):
    """
    Dolicza kolumny Moneyball (wymaga kolumny SCORE):
      Lata_kontraktu    - do konca kontraktu, od daty w grze
      Koszt             - wartosc transferowa + placa roczna x horyzont (wolny agent: sama placa)
      Okazje            - znaczniki okazji transferowych (tekst rozdzielony "; ")
    """
    pula = pula.copy()
    dzis = pd.Timestamp(data_gry or date.today())
    lata = (pula['Wygasa_Data'] - dzis).dt.days / 365.25
    pula['Lata_kontraktu'] = lata.clip(lower=0)
    wartosc = pula['Wartość_Numeryczna']
    placa = pula['Zarobki_Numeryczne'].fillna(0)
    pula['Koszt'] = wartosc + placa * horyzont_lat

    wolny = pula['Wolny_agent'].fillna(False).astype(bool) if 'Wolny_agent' in pula.columns else pd.Series(False, index=pula.index)
    znaczniki = {}
    if 'Niedowartościowanie' in pula.columns:
        znaczniki["niedowartościowany"] = ((pula['Niedowartościowanie'] >= PROG_NIEDOWARTOSCIOWANIA)
                                           & (pula['SCORE'] >= MIN_SCORE_NIEDOWARTOSCIOWANEGO))
    znaczniki |= {
        "kontrakt ≤ 6 mies.": (lata > 0) & (lata <= 0.5) & ~wolny,
        "kontrakt ≤ 12 mies.": (lata > 0) & (lata <= 1) & ~wolny,
    }
    if 'Δ SCORE' in pula.columns:
        znaczniki["szybki rozwój"] = (pula['Δ SCORE'] >= PROG_SZYBKIEGO_ROZWOJU) & (pula['Wiek'] <= MAKS_WIEK_ROZWOJU)
    okazje = pd.Series("", index=pula.index, dtype=object)
    for znacznik, maska in znaczniki.items():
        maska = maska.fillna(False).astype(bool)
        okazje = okazje.where(~maska, okazje.where(okazje == "", okazje + "; ") + znacznik)
    pula['Okazje'] = okazje
    pula['U21'] = pula['Wiek'] <= MAKS_WIEK_U21 if 'Wiek' in pula.columns else False
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


def policz_wynik(df, wagi, ignoruj_mnoznik=False, k_baza=5, odniesienie=None):
    """
    Pula -> kopia z kolumnami SCORE i Percentyl; plus lista pominietych cech.
    `odniesienie` (maska) - zawodnicy pozycji; pozostali (kandydaci z innych pozycji) sa oceniani
    na ich skali, a ich percentyl to miejsce wsrod zawodnikow pozycji.
    """
    pula = df.copy()
    score, pominiete = oblicz_score(pula, wagi, ignoruj_mnoznik, k_baza, odniesienie)
    pula['SCORE'] = score
    if odniesienie is None:
        pula['Percentyl'] = score.rank(pct=True) * 100
    else:
        ref = maska_odniesienia(pula, odniesienie)
        nominalni = np.sort(score[ref].dropna().to_numpy())
        percentyl = pd.Series(np.nan, index=pula.index)
        percentyl[ref] = score[ref].rank(pct=True) * 100
        if len(nominalni):
            inni = score[~ref]
            mniej = np.searchsorted(nominalni, inni.to_numpy(), side='left')
            rowne = np.searchsorted(nominalni, inni.to_numpy(), side='right') - mniej
            percentyl[~ref] = np.where(inni.notna(), (mniej + 0.5 * rowne) / len(nominalni) * 100, np.nan)
        pula['Percentyl'] = percentyl
    return pula, pominiete


def dolacz_kandydatow(pula, wszyscy, pozycja, z_pozycji=()):
    """
    Pula pozycji + zawodnicy nominalnie z innych pozycji (kandydaci do przekwalifikowania).
    `z_pozycji` zaweza kandydatow do zawodnikow majacych ktoras z tych pozycji (puste = wszyscy).
    Bramkarze sa kandydatami tylko na bramkarza i odwrotnie. Zwraca (ramka, maska nominalnych):
    maske podaje sie do policz_wynik, zeby kandydaci nie zmieniali skali wyniku pozycji.
    Kolumny: 'Kandydat', 'Kandydat z pozycji' (pozycja glowna), 'Ocena na pozycji' (1-20, z zapisu).
    """
    nominalni = pula.assign(Kandydat=False)
    if wszyscy is None or wszyscy.empty:
        ramka = nominalni
    else:
        klucz = 'UID' if 'UID' in pula.columns and 'UID' in wszyscy.columns else 'ID'
        inni = wszyscy[~wszyscy[klucz].isin(pula[klucz])]
        glowna = (inni['Pula_główna'] if 'Pula_główna' in inni.columns
                  else pd.Series(None, index=inni.index, dtype=object)).astype(object)
        if 'Pula' in inni.columns:
            glowna = glowna.where(glowna.notna(), inni['Pula'].astype(object))
        bramkarz = glowna == 'Bramkarz'
        wybrani = bramkarz if pozycja == 'Bramkarz' else ~bramkarz
        z_pozycji = [p for p in z_pozycji if p != pozycja]
        if z_pozycji:
            # wszystkie pozycje zawodnika: 'Pule' (zapis gry) albo jedna 'Pula' (demo, CSV)
            pule = (inni['Pule'] if 'Pule' in inni.columns else pd.Series(None, index=inni.index, dtype=object))
            pule = pule.where(pule.notna(), glowna).fillna("").astype(str).str.split("; ")
            pasujaca = pule.map(lambda lista: next((p for p in lista if p in z_pozycji), None))
            wybrani &= pasujaca.notna()
            glowna = pasujaca.where(pasujaca.notna(), glowna)
        inni = inni[wybrani].assign(Kandydat=True, **{'Kandydat z pozycji': glowna[wybrani]})
        ramka = pd.concat([nominalni, inni], ignore_index=True)
    if kolumna_oceny(pozycja) in ramka.columns:
        ramka['Ocena na pozycji'] = ramka[kolumna_oceny(pozycja)]
    return ramka, ~ramka['Kandydat'].astype(bool)


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
    if 'Kandydat' in wynik.columns:
        kandydat = wynik['Kandydat'].fillna(False).astype(bool)
        wynik = wynik[~kandydat | (wynik['SCORE'] >= filtry.min_score_kandydata)]
    if filtry.kraje and 'Kraj' in wynik.columns:
        wynik = wynik[wynik['Kraj'].isin(filtry.kraje)]
    if filtry.nogi and 'Preferowana noga' in wynik.columns:
        wynik = wynik[wynik['Preferowana noga'].isin(filtry.nogi)]
    if filtry.min_minut and 'Minuty' in wynik.columns and wynik['Minuty'].notna().any():
        wynik = wynik[wynik['Minuty'].fillna(0) >= filtry.min_minut]
    if filtry.kontrakt_mies:
        start = pd.Timestamp(data_gry or date.today())
        koniec = start + pd.DateOffset(months=int(filtry.kontrakt_mies))
        wygasa = wynik['Wygasa_Data']
        wynik = wynik[wygasa.notna() & (wygasa >= start) & (wygasa <= koniec)]
    if filtry.tylko_z_okazja and 'Okazje' in wynik.columns:
        wynik = wynik[wynik['Okazje'].fillna("") != ""]
    if filtry.okazje and 'Okazje' in wynik.columns:
        maska = pd.Series(False, index=wynik.index)
        for znacznik in filtry.okazje:
            maska |= wynik['Okazje'].str.contains(znacznik, regex=False, na=False)
        wynik = wynik[maska]
    if filtry.min_rozwoj is not None and 'Δ SCORE' in wynik.columns:
        wynik = wynik[wynik['Δ SCORE'] >= filtry.min_rozwoj]
    if filtry.min_niedowartosciowanie and 'Niedowartościowanie' in wynik.columns:
        wynik = wynik[wynik['Niedowartościowanie'] >= filtry.min_niedowartosciowanie]
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
_FORMATY = {'SCORE': 'score', 'Percentyl': 'pasek', 'Wiek': 'int', 'Minuty': 'int',
            'Ocena na pozycji': 'int', 'Strata piłek na podanie': 'dec2',
            'Niedowartościowanie': 'mnoznik', 'Wycena wg wyniku': 'eur', 'Δ SCORE': 'zmiana'}
# Kolumny prezentowane z pol liczbowych (sortowanie po liczbie, nie po tekscie)
_POLA = {'Cena': ('Wartość_Numeryczna', 'eur'), 'Płaca': ('Zarobki_Numeryczne', 'eur_tyg'),
         'Wygasa': ('Wygasa_Data', 'data'), 'Koszt (3 lata)': ('Koszt', 'eur')}
_TEKSTOWE = {'Piłkarz', 'Klub', 'Liga', 'Pozycja', 'Kraj', 'Preferowana noga', 'Okazje', 'Pozycja na liście',
             'Kandydat z pozycji'}
# Naglowki inne niz nazwa kolumny w danych
_NAGLOWKI = {'Kraj': 'Narodowość', 'Pozycja': 'Pozycje', 'Δ SCORE': 'Δ SCORE (sezon)'}
# Kolumny Moneyball (z wzbogac), nie sa statystykami meczowymi
_MONEYBALL = {'Koszt (3 lata)', 'Okazje', 'Ocena na pozycji', 'Wycena wg wyniku',
              'Niedowartościowanie', 'Δ SCORE'}


def _wstaw_po(lista, nowy, po):
    if nowy not in lista:
        lista.insert(lista.index(po) + 1 if po in lista else len(lista), nowy)


def kolumny_tabeli(pozycja, pula):
    """Lista kolumn tabeli: [{naglowek, pole, format, statystyka, nizsze_lepsze}]."""
    nazwy = [c for c in KOLUMNY_PER_POZYCJA.get(pozycja, []) if c in pula.columns]
    if 'Minuty' in pula.columns and pula['Minuty'].notna().any():
        _wstaw_po(nazwy, 'Minuty', 'Klub')
    if 'Płaca' in pula.columns:
        _wstaw_po(nazwy, 'Płaca', 'Cena')
    if 'Wygasa' in pula.columns:
        _wstaw_po(nazwy, 'Wygasa', 'Płaca' if 'Płaca' in nazwy else 'Cena')
    if 'Koszt' in pula.columns:
        po = 'Wygasa' if 'Wygasa' in nazwy else 'Cena'
        for kol in ('Okazje', 'Koszt (3 lata)'):
            _wstaw_po(nazwy, kol, po)
    # rozwoj wzgledem poprzedniego sezonu (historia zapisow)
    if 'Δ SCORE' in pula.columns and pula['Δ SCORE'].notna().any():
        _wstaw_po(nazwy, 'Δ SCORE', 'Percentyl')
    if 'Niedowartościowanie' in pula.columns and pula['Niedowartościowanie'].notna().any():
        _wstaw_po(nazwy, 'Wycena wg wyniku', 'Cena')
        _wstaw_po(nazwy, 'Niedowartościowanie', 'Wycena wg wyniku')
    if 'Kandydat' in pula.columns and pula['Kandydat'].any():
        _wstaw_po(nazwy, 'Kandydat z pozycji', 'Piłkarz')
        if 'Ocena na pozycji' in pula.columns and pula['Ocena na pozycji'].notna().any():
            _wstaw_po(nazwy, 'Ocena na pozycji', 'Kandydat z pozycji')
    return [_opis_kolumny(nazwa) for nazwa in nazwy]


def _opis_kolumny(nazwa):
    pole, fmt = _POLA.get(nazwa, (nazwa, _FORMATY.get(nazwa, 'tekst' if nazwa in _TEKSTOWE else 'dec1')))
    return {'naglowek': _NAGLOWKI.get(nazwa, nazwa), 'pole': pole, 'format': fmt,
            'statystyka': nazwa not in NIE_STATYSTYKI and nazwa not in _MONEYBALL and nazwa not in _TEKSTOWE,
            'nizsze_lepsze': nazwa in NIZSZE_LEPSZE}


# Kolumny listy zyczen (zawodnicy z roznych pozycji - tylko kolumny wspolne)
KOLUMNY_LISTY = ['SCORE', 'Piłkarz', 'Pozycja na liście', 'Wiek', 'Kraj', 'Klub', 'Liga', 'Cena', 'Wycena wg wyniku',
                 'Niedowartościowanie', 'Płaca', 'Wygasa', 'Koszt (3 lata)', 'Okazje']


def kolumny_listy(pula):
    return [_opis_kolumny(n) for n in KOLUMNY_LISTY
            if n == 'Pozycja na liście' or _POLA.get(n, (n,))[0] in pula.columns]


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


POLA_WIERSZA = ['ID', 'UID', 'Piłkarz', 'Klub', 'Klub_UID', 'Liga', 'Kraj', 'Wiek', 'Pozycja', 'Preferowana noga', 'Minuty',
                'SCORE', 'Percentyl', 'Wartość_Numeryczna', 'Zarobki_Numeryczne', 'Wygasa_Data',
                'Mnożnik_Ligi', 'Wypożyczony', 'Wypożyczenie_do', 'Wolny_agent', 'Lata_kontraktu', 'Koszt',
                'Okazje', 'Pareto', 'Kandydat', 'Kandydat z pozycji', 'Ocena na pozycji',
                'Wycena wg wyniku', 'Niedowartościowanie', 'Kontuzje_2_lata', 'Δ SCORE', 'Δ percentyl',
                'Δ minut', 'Nowe pozycje', 'U21']


def pola_wiersza(pozycja, pula):
    return POLA_WIERSZA + [k['pole'] for k in kolumny_tabeli(pozycja, pula)]


def kolejnosc_lig(ligi):
    znane = list(MAPOWANIE_NAZW_LIG.values())
    return sorted(ligi, key=lambda x: (znane.index(x) if x in znane else 999, str(x)))


# --- radar i sobowtor ---------------------------------------------------------------------------
def radar(pozycja, pula, ids, inni=None):
    """
    Percentyle statystyk (0-100, odwrocone dla 'mniej = lepiej') wybranych zawodnikow wzgledem puli
    pozycji. Zawodnika spoza puli (kandydat do przekwalifikowania) szukamy w `inni`.
    """
    kolumny = [c for c in kolumny_statystyk(pozycja, pula) if c not in NEUTRALNE]
    seria = []
    for id_ in ids:
        wiersz = pula[pula['ID'] == id_]
        if wiersz.empty and inni is not None:
            wiersz = inni[inni['ID'] == id_]
        if wiersz.empty:
            continue
        wiersz = wiersz.iloc[0]
        wartosci = []
        for c in kolumny:
            p = percentyl_w_puli(pula[c], wiersz.get(c))
            wartosci.append(round(100.0 - p if c in NIZSZE_LEPSZE else p, 1))
        surowe = [None if pd.isna(wiersz.get(c)) else round(float(wiersz.get(c)), 3) for c in kolumny]
        seria.append({'id': id_, 'pilkarz': wiersz.get('Piłkarz'), 'percentyle': wartosci, 'wartosci': surowe})
    etykiety = [c + " (mniej strat = wyżej)" if c in NIZSZE_LEPSZE else c for c in kolumny]
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


def porownaj_z_moim(pozycja, pula, kandydat, moj_klub_uid):
    """
    Kandydat na tle najlepszego (SCORE) zawodnika mojego klubu w puli pozycji: werdykt i kluczowe
    statystyki pozycji (te z wagami) z wartoscia i percentylem w puli ("mniej = lepiej" odwrocone).
    `kandydat` to wiersz (Series) z SCORE - takze spoza puli (kandydat z innej pozycji).
    """
    wynik = {"moj": None, "werdykt": None, "roznica": None, "cechy": []}
    if moj_klub_uid is None or 'Klub_UID' not in pula.columns:
        wynik["werdykt"] = "nieznany klub"
        return wynik
    if kandydat.get('Klub_UID') == moj_klub_uid:
        wynik["werdykt"] = "twój zawodnik"
        return wynik
    moi = pula[(pula['Klub_UID'] == moj_klub_uid) & pula['SCORE'].notna()].sort_values('SCORE', ascending=False)
    if moi.empty:
        wynik["werdykt"] = "brak zawodnika"
        return wynik
    moj = moi.iloc[0]
    roznica = float(kandydat['SCORE'] - moj['SCORE']) if pd.notna(kandydat.get('SCORE')) else None
    wynik["moj"] = do_json(moi.head(1), ['ID', 'Piłkarz', 'Wiek', 'SCORE', 'Minuty', 'Klub'])[0]
    wynik["roznica"] = roznica
    wynik["werdykt"] = (None if roznica is None else "wzmocnienie" if roznica >= PROG_WZMOCNIENIA
                        else "podobny poziom" if roznica > -PROG_WZMOCNIENIA else "nie wzmacnia")
    for cecha in wagi_domyslne(pozycja, pula):
        k, m = kandydat.get(cecha), moj.get(cecha)
        pk = percentyl_w_puli(pula[cecha], k) if pd.notna(k) else None
        pm = percentyl_w_puli(pula[cecha], m) if pd.notna(m) else None
        if cecha in NIZSZE_LEPSZE:
            pk, pm = (None if pk is None else 100 - pk), (None if pm is None else 100 - pm)
        wynik["cechy"].append({
            "nazwa": cecha, "nizsze_lepsze": cecha in NIZSZE_LEPSZE,
            "kandydat": None if pd.isna(k) else float(k), "moj": None if pd.isna(m) else float(m),
            "percentyl_kandydata": pk, "percentyl_moj": pm,
            "lepszy": None if pk is None or pm is None or pk == pm else ("kandydat" if pk > pm else "moj"),
        })
    return wynik


def znajdz_zawodnika(pula, klucz, pilkarz=""):
    """
    Wiersz zawodnika z listy zyczen: po UID z zapisu (z kontrola nazwiska - uid moze sie roznic
    miedzy karierami) albo po ID (CSV, demo). Pusta ramka, gdy nie ma.
    """
    if 'UID' in pula.columns and str(klucz).isdigit():
        wynik = pula[pula['UID'] == int(klucz)]
        if pilkarz:
            wynik = wynik[wynik['Piłkarz'] == pilkarz]
    else:
        wynik = pula[pula['ID'] == klucz]
    return wynik.head(1)


# --- moja kadra -----------------------------------------------------------------------------------
POLA_KADRY = ['ID', 'Piłkarz', 'Klub', 'Klub_UID', 'Liga', 'Wiek', 'Pozycja', 'Preferowana noga', 'Minuty', 'SCORE',
              'Percentyl', 'Wartość_Numeryczna', 'Zarobki_Numeryczne', 'Wygasa_Data', 'Lata_kontraktu',
              'Wypożyczony', 'Koszt', 'Okazje']


def moja_kadra(pozycja, pula_policzona, moj_klub_uid, data_gry=None):
    """Moi zawodnicy na pozycji na tle puli: najlepszy SCORE, sredni wiek, konczace sie kontrakty."""
    pula = wzbogac(pula_policzona, data_gry)
    moi = pula[pula['Klub_UID'] == moj_klub_uid].sort_values('SCORE', ascending=False) \
        if 'Klub_UID' in pula.columns else pula.iloc[0:0]
    return {
        "pozycja": pozycja,
        "liczba": int(len(moi)),
        "najlepszy": float(moi['SCORE'].max()) if not moi.empty else None,
        "sredni_wiek": float(moi['Wiek'].mean()) if not moi.empty else None,
        "konczace_kontrakty": int((moi['Lata_kontraktu'] <= 1).sum()) if not moi.empty else 0,
        "zawodnicy": do_json(moi, POLA_KADRY),
    }
