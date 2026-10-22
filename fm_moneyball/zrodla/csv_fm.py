"""Zrodlo: eksport widoku z FM do CSV (jeden plik = jedna pozycja) oraz syntetyczne dane demo."""
import io
import re

import numpy as np
import pandas as pd

from fm_moneyball.parsery import do_liczb, fmt_eur, parse_age, parse_market_value, parse_wages
from fm_moneyball.schemat import dopelnij_schemat
from fm_moneyball.stale import (KOLUMNY_PER_POZYCJA, KOLUMNY_STATYSTYK, NAZWY_KOLUMNY_MINUT, POZYCJE,
                                TLUMACZENIE_KOLUMN, WSKAZOWKI_NAZW_PLIKOW)


def wczytaj_csv(plik_bajty):
    """
    Bajty pliku CSV z FM -> (kanoniczny DataFrame, liczba odrzuconych wierszy).
    Rzuca ValueError, gdy brak kolumny 'Piłkarz'.
    """
    try:
        df = pd.read_csv(io.BytesIO(plik_bajty), sep=None, engine='python', dtype=str, encoding='utf-8-sig')
    except UnicodeDecodeError:
        df = pd.read_csv(io.BytesIO(plik_bajty), sep=None, engine='python', dtype=str, encoding='cp1250')

    df.columns = df.columns.astype(str).str.replace('﻿', '', regex=False).str.strip()
    df = df.rename(columns=TLUMACZENIE_KOLUMN)

    # Kolumna z minutami (opcjonalna) -> 'Minuty'
    for nazwa in NAZWY_KOLUMNY_MINUT:
        if nazwa in df.columns and 'Minuty' not in df.columns:
            df = df.rename(columns={nazwa: 'Minuty'})
            break

    if 'Piłkarz' not in df.columns:
        raise ValueError("Brak kolumny 'Piłkarz' - czy to na pewno eksport z FM?")
    df = df[df['Piłkarz'].notna()].copy()

    odrzucone = 0
    if 'Wiek' in df.columns:
        df['Wiek'] = df['Wiek'].apply(parse_age)
        odrzucone = int((df['Wiek'] <= 0).sum())
        df = df[df['Wiek'] > 0]

    # Cena i placa: NaN oznacza "brak danych / nie na sprzedaz" (a nie 0 EUR)
    df['Wartość_Numeryczna'] = df['Cena'].apply(parse_market_value) if 'Cena' in df.columns else np.nan
    df['Zarobki_Numeryczne'] = df['Płaca'].apply(parse_wages) if 'Płaca' in df.columns else np.nan

    # Statystyki -> liczby (raz, tutaj)
    for kol in KOLUMNY_STATYSTYK:
        if kol in df.columns:
            df[kol] = do_liczb(df[kol])
    if 'Minuty' in df.columns:
        df['Minuty'] = do_liczb(df['Minuty'], tysiace_z_kropka=True)

    return dopelnij_schemat(df), odrzucone


def wykryj_pozycje(nazwa_pliku, df):
    """Probuje odgadnac pozycje: po kolumnie 'Pozycja' (BR = bramkarz) lub po nazwie pliku."""
    if 'Pozycja' in df.columns:
        kody = df['Pozycja'].dropna().astype(str).str.strip().str.upper()
        if len(kody) and kody.str.startswith('BR').mean() > 0.9:
            return "Bramkarz"
    nazwa = re.sub(r'\.csv$', '', nazwa_pliku, flags=re.I).strip().lower()
    nazwa = re.sub(r'[\s_\-]*\(?\d+\)?$', '', nazwa)   # "BR (1)" -> "br"
    return WSKAZOWKI_NAZW_PLIKOW.get(nazwa)


# =============================================================================
# DANE DEMO (SYNTETYCZNE) - generowane w formacie zblizonym do eksportu z FM
# =============================================================================
def generuj_demo_csv(pozycja, n=150):
    rng = np.random.default_rng(100 + POZYCJE.index(pozycja))
    ligi = ["Premier League", "LaLiga", "Bundesliga", "Ekstraklasa", "Eredivisie", "Ligue 1"]
    liga = rng.choice(ligi, n)
    klub = [f"{l.split()[0]} FC {rng.integers(1, 9)}" for l in liga]
    nazwy = [f"Demo {pozycja.split()[0]} {i:03d}" for i in range(n)]
    nazwy[1] = nazwy[0]   # celowo dwa takie same nazwiska (test unikalnego ID)

    generatory = {
        'xA/90': lambda: rng.gamma(2, 0.05, n),
        'KPzG/90': lambda: rng.gamma(2, 0.6, n),
        'Liczba goli na 90 min': lambda: rng.gamma(1.2, 0.12, n),
        'xG/strzał': lambda: np.clip(rng.normal(0.11, 0.04, n), 0.02, 0.5),
        'Skut (%)': lambda: np.clip(rng.normal(45, 12, n), 0, 100),
        'Ud Pres/90': lambda: rng.gamma(3, 1.2, n),
        'Prz/90': lambda: rng.gamma(3, 0.5, n),
        'Odz Płk/90': lambda: rng.gamma(6, 0.9, n),
        'Str Płk/90': lambda: rng.gamma(5, 1.2, n),
        'Pod/90': lambda: rng.gamma(8, 4, n),
        '% Głw': lambda: np.clip(rng.normal(60, 15, n), 0, 100),
        'Drb/90': lambda: rng.gamma(2, 0.9, n),
        'ZxG/90': lambda: np.round(rng.normal(0.0, 0.25, n), 1),
    }
    aktywne = set(KOLUMNY_PER_POZYCJA[pozycja])
    dane = {
        'Piłkarz': nazwy,
        'Wiek': rng.integers(18, 37, n).astype(str),
        'Klub': klub,
        'Liga': liga,
        'Pozycja': ['BR' if pozycja == "Bramkarz" else pozycja] * n,
        'Preferowana noga': rng.choice(["Wyłącznie prawonożny", "Wyłącznie lewonożny", "Obunożny"], n),
    }
    wartosc = np.exp(rng.normal(14.5, 1.5, n))
    dane['Szacowana wartość'] = [
        "Nie na sprzedaż" if rng.random() < 0.1 else f"{fmt_eur(v * 0.7)} - {fmt_eur(v * 1.6)}"
        for v in wartosc
    ]
    dane['Płaca'] = [f"{fmt_eur(v / 100)} tyg." for v in wartosc]
    dane['Wygasa'] = [f"30.6.{rng.integers(2027, 2032)}" for _ in range(n)]
    dane['Min'] = rng.integers(150, 3300, n).astype(str)
    for surowa, polska in TLUMACZENIE_KOLUMN.items():
        if polska == "Cena":
            continue
        if polska in aktywne:
            wart = generatory[surowa]()
            if '%' in surowa:
                dane[surowa] = [f"{v:.0f} %" for v in wart]
            else:
                dane[surowa] = [f"{v:.2f}".replace('.', ',') for v in wart]
        else:
            dane[surowa] = ["0"] * n
    return pd.DataFrame(dane).to_csv(sep=';', index=False).encode('utf-8-sig')
