"""
Wspolny krok po kazdym zrodle danych (CSV, zapis .fm, demo).

Zrodlo dostarcza DataFrame z polskimi nazwami kolumn i liczbami w kolumnach statystyk;
`dopelnij_schemat` dolicza kolumny pochodne, z ktorych korzysta model i interfejs:
'Strata piłek na podanie', 'Mnożnik_Ligi', 'Liga_bez_mnoznika', 'Wygasa_Data' oraz unikalne 'ID'.
"""
import numpy as np
import pandas as pd

from fm_moneyball.stale import MAPOWANIE_NAZW_LIG, MERYTORYKA_WAG, MNOZNIK_NIEZNANEJ_LIGI, MNOZNIKI_LIG


def dopelnij_schemat(df, mnoznik_nieznanej=MNOZNIK_NIEZNANEJ_LIGI):
    df = df.copy()

    # Cecha pochodna: odsetek podan konczacych sie strata pilki (mniej = lepiej)
    if 'Stracone piłki/90' in df.columns and 'Próby podań/90' in df.columns:
        podania = df['Próby podań/90'].where(df['Próby podań/90'] > 0)
        df['Strata piłek na podanie'] = df['Stracone piłki/90'] / podania

    # Liga: mnoznik liczony na surowej nazwie, potem nazwa wyswietlana
    if 'Liga' in df.columns:
        liga_surowa = df['Liga'].astype(str).str.replace('\xa0', ' ', regex=False).str.strip()
        df['Mnożnik_Ligi'] = liga_surowa.map(MNOZNIKI_LIG)
        df['Liga_bez_mnoznika'] = df['Mnożnik_Ligi'].isna()
        df['Mnożnik_Ligi'] = df['Mnożnik_Ligi'].fillna(mnoznik_nieznanej)
        df['Liga'] = liga_surowa.map(MAPOWANIE_NAZW_LIG).fillna(liga_surowa).where(df['Liga'].notna())
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


def raport_wczytania(df, pozycja, odrzucone=0):
    """Zwraca liste (poziom, tekst) opisujaca jakosc wczytanych danych."""
    wynik = []
    wynik.append(("info", f"Liczba zawodników: {len(df)}"))
    if odrzucone:
        wynik.append(("warn", f"Pominięto {odrzucone} wierszy z nieczytelnym wiekiem."))
    brakujace = [k for k in ('Piłkarz', 'Wiek', 'Klub', 'Liga') if k not in df.columns]
    if brakujace:
        wynik.append(("warn", f"Brak kolumn podstawowych: {', '.join(brakujace)}"))
    brak_cech = [c for c in MERYTORYKA_WAG[pozycja] if c not in df.columns]
    if brak_cech:
        wynik.append(("info", "Cechy niedostępne w tych danych (pominięte w wyniku): " + ", ".join(brak_cech)))
    if 'Minuty' in df.columns and df['Minuty'].notna().any():
        wynik.append(("info", "Znaleziono kolumnę z minutami - włączone skurczenie cech przy małej próbie."))
    else:
        wynik.append(("warn", "Brak kolumny z minutami (np. 'Min') - wynik bez korekty na małą próbę. "
                              "Dodaj ją do widoku w FM i wyeksportuj ponownie."))
    if 'Liga_bez_mnoznika' in df.columns and df['Liga_bez_mnoznika'].any():
        nieznane = sorted(df.loc[df['Liga_bez_mnoznika'], 'Liga'].dropna().astype(str).unique())
        wynik.append(("warn", f"Ligi bez zdefiniowanego mnożnika (przyjęto najniższy znany, "
                              f"{MNOZNIK_NIEZNANEJ_LIGI}): " + ", ".join(nieznane[:30])
                      + (f" i {len(nieznane) - 30} innych" if len(nieznane) > 30 else "")))
    bez_ceny = int(df['Wartość_Numeryczna'].isna().sum())
    if bez_ceny:
        wynik.append(("info", f"Bez ceny (np. 'Nie na sprzedaż'): {bez_ceny} zawodników - nie są liczeni jako darmowi."))
    if 'Płaca' in df.columns:
        sprawdzone = int(df['Zarobki_Numeryczne'].notna().sum())
        wynik.append(("info", f"Płace rozpoznane: {sprawdzone} z {len(df)}"))
    powtorzone = int(df['Piłkarz'].duplicated(keep=False).sum())
    if powtorzone:
        wynik.append(("info", f"Zawodnicy o tych samych nazwiskach: {powtorzone} - rozróżniani po klubie i wieku (kolumna ID)."))
    return wynik
