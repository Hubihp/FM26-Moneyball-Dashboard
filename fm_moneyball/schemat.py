"""
Wspolny krok po kazdym zrodle danych (CSV, zapis .fm, demo).

Zrodlo dostarcza DataFrame z polskimi nazwami kolumn i liczbami w kolumnach statystyk;
`dopelnij_schemat` dolicza kolumny pochodne, z ktorych korzysta model i interfejs:
'Strata piłek na podanie', 'Mnożnik_Ligi', 'Liga_bez_mnoznika', 'Wygasa_Data' oraz unikalne 'ID'.
"""
import numpy as np
import pandas as pd

from fm_moneyball.stale import MAPOWANIE_NAZW_LIG, MNOZNIK_NIEZNANEJ_LIGI, MNOZNIKI_LIG


def dopelnij_schemat(df, mnoznik_nieznanej=MNOZNIK_NIEZNANEJ_LIGI):
    df = df.copy()

    # Cecha pochodna: odsetek podan konczacych sie strata pilki (mniej = lepiej)
    if 'Stracone piłki/90' in df.columns and 'Próby podań/90' in df.columns:
        podania = df['Próby podań/90'].where(df['Próby podań/90'] > 0)
        df['Strata piłek na podanie'] = df['Stracone piłki/90'] / podania

    # Liga: mnoznik liczony na surowej nazwie, potem nazwa wyswietlana
    if 'Liga' in df.columns:
        liga_surowa = df['Liga'].astype(str).str.replace('\xa0', ' ', regex=False).str.strip()
        _ustaw_lige(df, liga_surowa.where(df['Liga'].notna()), MNOZNIKI_LIG, mnoznik_nieznanej)
    else:
        df['Mnożnik_Ligi'] = 1.0
        df['Liga_bez_mnoznika'] = False

    # Data wygasniecia kontraktu (format d.m.rrrr), o ile zrodlo nie podalo jej juz jako daty
    if 'Wygasa_Data' not in df.columns:
        if 'Wygasa' in df.columns:
            df['Wygasa_Data'] = pd.to_datetime(df['Wygasa'], dayfirst=True, errors='coerce')
        else:
            df['Wygasa_Data'] = pd.NaT

    for kol in ('Wartość_Numeryczna', 'Zarobki_Numeryczne'):
        if kol not in df.columns:
            df[kol] = np.nan

    # Unikalny klucz zawodnika (nazwiska moga sie powtarzac)
    czesci = df['Piłkarz'].astype(str).str.strip()
    if 'Klub' in df.columns:
        czesci = czesci + ' (' + df['Klub'].fillna('?').astype(str)
        czesci = czesci + (', ' + df['Wiek'].astype(str) + ')' if 'Wiek' in df.columns else ')')
    df['ID'] = czesci
    numer = df.groupby('ID').cumcount() + 1
    duplikaty = df['ID'].duplicated(keep=False)
    df.loc[duplikaty, 'ID'] = df.loc[duplikaty, 'ID'] + ' #' + numer[duplikaty].astype(str)

    return df.reset_index(drop=True)


def _ustaw_lige(df, liga_surowa, mnozniki, mnoznik_nieznanej=MNOZNIK_NIEZNANEJ_LIGI):
    """Surowa nazwa ligi -> Mnożnik_Ligi, Liga_bez_mnoznika i nazwa wyswietlana (w miejscu)."""
    df['Mnożnik_Ligi'] = liga_surowa.map(mnozniki)
    df['Liga_bez_mnoznika'] = df['Mnożnik_Ligi'].isna()
    df['Mnożnik_Ligi'] = df['Mnożnik_Ligi'].fillna(mnoznik_nieznanej).astype(float)
    df['Liga'] = liga_surowa.map(MAPOWANIE_NAZW_LIG).fillna(liga_surowa)


def ustaw_ligi(df, nazwy, mnozniki=None, mnoznik_nieznanej=MNOZNIK_NIEZNANEJ_LIGI):
    """
    Nazwy i mnozniki lig nakladane PO wczytaniu zapisu (bez ponownego parsowania): ramka z zapisu
    ma 'Liga_klucz' (id rozgrywek albo -kraj) i 'Liga_domyslna' ("Rozgrywki #id"). Ramki bez
    tych kolumn (CSV, demo) zwracane sa bez zmian.
    """
    if 'Liga_klucz' not in df.columns:
        return df
    df = df.copy()
    surowa = df['Liga_klucz'].map(lambda k: nazwy.get(int(k)) if pd.notna(k) else None)
    surowa = surowa.where(surowa.notna(), df['Liga_domyslna'])
    _ustaw_lige(df, surowa, MNOZNIKI_LIG if mnozniki is None else mnozniki, mnoznik_nieznanej)
    return df


NIEZNANY_KRAJ = "Nieznana"


def ustaw_kraje(df, nazwy):
    """
    Kolumna 'Kraj' (narodowosc) z 'Kraj_ID' ramki z zapisu: nazwa z mapy, "Kraj #id" albo
    "Nieznana" (zapis nie podal narodowosci - zawodnik nie moze zniknac z filtra).
    Ramki bez 'Kraj_ID' (CSV, demo - maja wlasna kolumne 'Kraj') dostaja tylko "Nieznana" w lukach.
    """
    df = df.copy()
    if 'Kraj_ID' in df.columns:
        df['Kraj'] = df['Kraj_ID'].map(lambda k: (nazwy.get(int(k)) or f"Kraj #{int(k)}") if pd.notna(k) else None)
    if 'Kraj' in df.columns:
        df['Kraj'] = df['Kraj'].where(df['Kraj'].notna() & (df['Kraj'].astype(str).str.strip() != ""), NIEZNANY_KRAJ)
    return df
