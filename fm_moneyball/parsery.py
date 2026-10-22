"""Parsery tekstu z FM (czyste funkcje, bez Streamlita)."""
import re

import numpy as np
import pandas as pd

# Separator widelek: zwykly myslnik, polpauza lub pauza, z dowolnymi (rowniez twardymi) spacjami
_SEPARATOR_WIDELEK = re.compile(r'\s+[-–—]\s+|\s*[–—]\s*')
# "1.234" / "12.345.678" - kropka jako separator tysiecy (bez czesci dziesietnej)
_TYSIACE_Z_KROPKA = re.compile(r'^\d{1,3}(\.\d{3})+$')


def parse_age(val_str):
    if pd.isna(val_str):
        return 0
    first_part = str(val_str).split('-')[0].strip()
    try:
        return int(first_part)
    except (ValueError, TypeError):
        return 0


def eur(tekst):
    """'6,25 tys. €' -> 6250.0; '1,9 mln €' -> 1900000.0; '750 €' -> 750.0. Rzuca ValueError przy bledzie."""
    t = str(tekst).replace('€', '').replace('\xa0', '').replace(' ', '').lower()
    mnoznik = 1_000_000 if 'mln' in t else 1_000 if 'tys' in t else 1
    t = re.sub(r'mln|tys\.?', '', t)
    return float(t.replace(',', '.')) * mnoznik


def _widelki(tekst):
    return _SEPARATOR_WIDELEK.split(str(tekst).replace('\xa0', ' ').strip())


def parse_market_value(val_str):
    """Szacowana wartosc -> srodek geometryczny widelek (EUR). 'Nie na sprzedaz' / brak -> NaN."""
    if pd.isna(val_str) or 'sprzeda' in str(val_str).lower():
        return np.nan
    try:
        wartosci = [eur(p) for p in _widelki(val_str)]
    except ValueError:
        return np.nan
    lo, hi = wartosci[0], wartosci[-1]
    return (lo * hi) ** 0.5 if lo > 0 else (lo + hi) / 2


def parse_wages(val_str):
    """Placa -> kwota roczna w EUR. Rozpoznaje stawke tygodniowa ('tyg.', '/w') i miesieczna ('mies.', '/m')."""
    if pd.isna(val_str):
        return np.nan
    t = _widelki(str(val_str).lower())[0]
    if re.search(r'tyg|tydz|/w', t):
        okresy = 52
    elif re.search(r'mies|/m', t):
        okresy = 12
    else:
        okresy = 1
    t = re.sub(r'tyg\.?|tydz\.?|mies\.?|/w|/m|/rok|/y|na', '', t)
    try:
        return eur(t) * okresy
    except ValueError:
        return np.nan


def do_liczb(seria, tysiace_z_kropka=False):
    """
    Tekst z FM ('45 %', '0,35', '1 234') -> liczba; bledy -> NaN.
    tysiace_z_kropka=True: '1.234' traktuj jako 1234 (tylko dla liczb calkowitych, np. minut).
    """
    oczyszczone = (seria.astype(str)
                   .str.replace('\xa0', '', regex=False)
                   .str.replace(' ', '', regex=False)
                   .str.replace('%', '', regex=False)
                   .str.strip())
    if tysiace_z_kropka:
        oczyszczone = oczyszczone.where(~oczyszczone.str.match(_TYSIACE_Z_KROPKA),
                                        oczyszczone.str.replace('.', '', regex=False))
    oczyszczone = oczyszczone.str.replace(',', '.', regex=False)
    return pd.to_numeric(oczyszczone, errors='coerce')


def fmt_eur(x):
    """Kwota w EUR -> tekst w stylu FM ('1,9 mln €', '250 tys. €', '750 €')."""
    if x is None or pd.isna(x):
        return None
    if x >= 1_000_000:
        return f"{x / 1_000_000:.1f}".replace('.', ',').replace(',0', '') + " mln €"
    if x >= 1_000:
        return f"{round(x / 1_000)} tys. €"
    return f"{round(x)} €"
