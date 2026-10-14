"""
FM26 Moneyball Dashboard - wersja 2 (punkty 1-5 planu ulepszen).

Najwazniejsze zmiany wzgledem wersji 1:
  1. Poprawki bledow: parser plac ("tyg."), "Nie na sprzedaz" jako brak ceny (NaN), unikalny
     klucz zawodnika (ID), odwrocony kierunek "strat pilek" w radarze, filtr kontraktow z data
     w grze, "Moj klub" jako ustawienie, usuniety mnoznik `retention` i stala 900 mln.
  2. Parsowanie raz (cache), walidacja schematu + raport wczytania, wiele plikow naraz z
     rozpoznawaniem pozycji, dane demo (syntetyczne).
  3. Obsluga kolumny z minutami (Min / Minuty), jesli jest w eksporcie z FM.
  4. SCORE w z-score w obrebie pozycji, wagi normalizowane do sumy 1, skurczenie (shrinkage)
     cech per 90 przy malej liczbie minut.
  5. Nowy wynik dla bramkarzy (ZxG, odzyskane pilki, bezpieczenstwo podan).

Wymagania: streamlit, pandas, numpy, altair, plotly, matplotlib (scikit-learn nie jest juz potrzebny).
"""
import io
import re

import altair as alt
import matplotlib.colors as mcolors
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# Konfiguracja strony
st.set_page_config(
    page_title="FM26 Moneyball Dashboard",
    page_icon="⚽",
    layout="wide"
)

# Ukrywanie alertów po 5 sekundach, usuwanie ikon hiperłączy, poprawa odstępów w sidebarze oraz modyfikacja uploada
st.markdown("""
    <style>
    [data-testid="stAlert"] {
        animation: fadeOut 5s ease-in-out forwards;
    }
    @keyframes fadeOut {
        0% { opacity: 1; height: auto; }
        80% { opacity: 1; height: auto; }
        100% { opacity: 0; height: 0; padding: 0; margin: 0; overflow: hidden; display: none; }
    }
    a.header-anchor {
        display: none !important;
    }

    /* --- ZMNIEJSZENIE ODSTĘPÓW W SIDEBARZE --- */
    [data-testid="stSidebar"] hr {
        margin-top: 0.5rem !important;
        margin-bottom: 1.5rem !important;
    }
    [data-testid="stSidebar"] h3 {
        padding-top: 0.5rem !important;
        padding-bottom: 1rem !important;
    }

    /* --- UPLOAD WIDGET: PRZYCISK PO LEWEJ, TEKST PO PRAWEJ --- */
    [data-testid="stFileUploaderDropzone"] {
        display: flex !important;
        flex-direction: row !important;
        align-items: center !important;
        justify-content: flex-start !important;
        padding: 10px 15px !important;
        min-height: auto !important;
    }
    [data-testid="stFileUploaderDropzone"] button {
        order: -1 !important;
        margin-right: 15px !important;
        margin-top: 0 !important;
    }
    [data-testid="stFileUploaderDropzoneInstructions"] {
        display: flex !important;
        align-items: center !important;
        margin: 0 !important;
    }
    [data-testid="stFileUploaderDropzone"] svg {
        display: none !important;
    }
    [data-testid="stFileUploaderDropzoneInstructions"] > div > span {
        display: none !important;
    }
    </style>
""", unsafe_allow_html=True)


# =============================================================================
# KOMPATYBILNOSC Z RÓŻNYMI WERSJAMI STREAMLITA
# (nowsze wersje zastepuja use_container_width parametrem width="stretch")
# =============================================================================
try:
    _NOWY_STREAMLIT = tuple(int(x) for x in st.__version__.split(".")[:2]) >= (1, 50)
except Exception:
    _NOWY_STREAMLIT = False


def szeroki(funkcja, *args, **kwargs):
    """Wywoluje funkcje Streamlita tak, aby element zajmowal cala szerokosc kontenera."""
    if _NOWY_STREAMLIT:
        try:
            return funkcja(*args, width="stretch", **kwargs)
        except (TypeError, st.errors.StreamlitAPIException):
            pass
    return funkcja(*args, use_container_width=True, **kwargs)


# =============================================================================
# STALE I SLOWNIKI
# =============================================================================
POZYCJE = ["Bramkarz", "Środkowy Obrońca", "Boczny Obrońca", "Defensywny Pomocnik",
           "Środkowy Pomocnik", "Skrzydłowy", "Napastnik"]

WYBIERZ = "— wybierz —"

# Slownik tlumaczen kolumn statystycznych (nazwa w pliku CSV -> nazwa w aplikacji)
TLUMACZENIE_KOLUMN = {
    "xA/90": "Oczekiwane asysty/90",
    "KPzG/90": "Kluczowe podania z gry/90",
    "Liczba goli na 90 min": "Liczba goli na 90 min",
    "xG/strzał": "Oczekiwane gole na strzał",
    "Skut (%)": "Skuteczność strzałów (%)",
    "Ud Pres/90": "Udane próby pressingu/90",
    "Prz/90": "Przechwyty/90",
    "Odz Płk/90": "Odzyskane piłki/90",
    "Str Płk/90": "Stracone piłki/90",
    "Pod/90": "Próby podań/90",
    "% Głw": "% wygranych pojedynków główkowych",
    "Drb/90": "Liczba dryblingów/90",
    "ZxG/90": "Uniknięte oczekiwane gole/90",
    "Szacowana wartość": "Cena"
}

# Mozliwe nazwy kolumny z minutami w eksporcie z FM (zostanie zmieniona na "Minuty")
NAZWY_KOLUMNY_MINUT = ["Min", "Minuty", "Rozegrane minuty", "Min."]

# Kolumny liczbowe, ktore konwertujemy raz, przy wczytywaniu
KOLUMNY_STATYSTYK = [v for v in TLUMACZENIE_KOLUMN.values() if v != "Cena"]

# Kolumny, ktorych NIE traktujemy jako statystyk meczowych
NIE_STATYSTYKI = {
    'SCORE', 'Percentyl', 'Wiarygodność', 'Piłkarz', 'ID', 'Wiek', 'Klub', 'Liga', 'Pozycja', 'Cena',
    'Preferowana noga', 'Kraj', 'Wartość_Numeryczna', 'Zarobki_Numeryczne', 'Płaca', 'Wygasa',
    'Wygasa_Data', 'Minuty', 'Mnożnik_Ligi'
}

# Statystyki, w ktorych MNIEJ znaczy LEPIEJ (uzywane w radarze i wykresach Top 10)
NIZSZE_LEPSZE = {'Stracone piłki/90', 'Strata piłek na podanie'}

# Cechy uzywane w wyniku: nazwa -> (kierunek, wspolczynnik skurczenia)
# kierunek: +1 = wiecej znaczy lepiej, -1 = mniej znaczy lepiej
# skurczenie: 0 = bez skurczenia (statystyka nie jest "per 90"), 1.0 = standard, 2.0 = bardziej losowa
CECHY = {
    'Oczekiwane asysty/90': (1, 2.0),
    'Kluczowe podania z gry/90': (1, 1.0),
    'Liczba goli na 90 min': (1, 2.0),
    'Oczekiwane gole na strzał': (1, 0.0),
    'Skuteczność strzałów (%)': (1, 0.0),
    'Udane próby pressingu/90': (1, 1.0),
    'Przechwyty/90': (1, 1.0),
    'Odzyskane piłki/90': (1, 1.0),
    '% wygranych pojedynków główkowych': (1, 0.0),
    'Uniknięte oczekiwane gole/90': (1, 2.0),
    'Liczba dryblingów/90': (1, 1.0),
    'Strata piłek na podanie': (-1, 1.0),
}

# Domyslne WAZNOSCI cech per pozycja (0-100). W obliczeniach sa normalizowane do sumy 1,
# wiec liczy sie tylko ich wzajemna proporcja. To propozycja startowa - dostrój pod swoj styl.
MERYTORYKA_WAG = {
    "Bramkarz": {
        'Uniknięte oczekiwane gole/90': 50, 'Odzyskane piłki/90': 20, 'Strata piłek na podanie': 30},
    "Środkowy Obrońca": {
        '% wygranych pojedynków główkowych': 15, 'Przechwyty/90': 20, 'Udane próby pressingu/90': 10,
        'Kluczowe podania z gry/90': 10, 'Odzyskane piłki/90': 25, 'Strata piłek na podanie': 20},
    "Boczny Obrońca": {
        'Oczekiwane asysty/90': 30, 'Kluczowe podania z gry/90': 20, 'Przechwyty/90': 15,
        'Odzyskane piłki/90': 10, 'Udane próby pressingu/90': 10, 'Strata piłek na podanie': 15},
    "Defensywny Pomocnik": {
        'Oczekiwane asysty/90': 10, 'Kluczowe podania z gry/90': 15, 'Przechwyty/90': 20,
        'Odzyskane piłki/90': 25, 'Udane próby pressingu/90': 15,
        '% wygranych pojedynków główkowych': 5, 'Strata piłek na podanie': 10},
    "Środkowy Pomocnik": {
        'Oczekiwane asysty/90': 25, 'Liczba goli na 90 min': 10, 'Kluczowe podania z gry/90': 20,
        'Liczba dryblingów/90': 10, 'Odzyskane piłki/90': 10, 'Udane próby pressingu/90': 10,
        'Strata piłek na podanie': 15},
    "Skrzydłowy": {
        'Oczekiwane asysty/90': 25, 'Liczba goli na 90 min': 20, 'Oczekiwane gole na strzał': 10,
        'Kluczowe podania z gry/90': 15, 'Liczba dryblingów/90': 15, 'Udane próby pressingu/90': 5,
        'Odzyskane piłki/90': 5, 'Strata piłek na podanie': 5},
    "Napastnik": {
        'Liczba goli na 90 min': 35, 'Oczekiwane gole na strzał': 10, 'Oczekiwane asysty/90': 15,
        'Kluczowe podania z gry/90': 10, 'Liczba dryblingów/90': 10, 'Udane próby pressingu/90': 5,
        'Odzyskane piłki/90': 5, 'Skuteczność strzałów (%)': 10},
}

KOLUMNY_PER_POZYCJA = {
    "Bramkarz": ['SCORE', 'Percentyl', 'Piłkarz', 'Wiek', 'Kraj', 'Pozycja', 'Preferowana noga', 'Liga', 'Klub', 'Cena', 'Odzyskane piłki/90', 'Stracone piłki/90', 'Strata piłek na podanie', 'Próby podań/90', 'Uniknięte oczekiwane gole/90'],
    "Środkowy Obrońca": ['SCORE', 'Percentyl', 'Piłkarz', 'Wiek', 'Kraj', 'Pozycja', 'Preferowana noga', 'Liga', 'Klub', 'Cena', 'Kluczowe podania z gry/90', 'Udane próby pressingu/90', 'Przechwyty/90', 'Odzyskane piłki/90', 'Stracone piłki/90', 'Strata piłek na podanie', 'Próby podań/90', '% wygranych pojedynków główkowych'],
    "Boczny Obrońca": ['SCORE', 'Percentyl', 'Piłkarz', 'Wiek', 'Kraj', 'Pozycja', 'Preferowana noga', 'Liga', 'Klub', 'Cena', 'Oczekiwane asysty/90', 'Kluczowe podania z gry/90', 'Udane próby pressingu/90', 'Przechwyty/90', 'Odzyskane piłki/90', 'Stracone piłki/90', 'Strata piłek na podanie', 'Próby podań/90'],
    "Defensywny Pomocnik": ['SCORE', 'Percentyl', 'Piłkarz', 'Wiek', 'Kraj', 'Pozycja', 'Preferowana noga', 'Liga', 'Klub', 'Cena', 'Oczekiwane asysty/90', 'Kluczowe podania z gry/90', 'Udane próby pressingu/90', 'Przechwyty/90', 'Odzyskane piłki/90', 'Stracone piłki/90', 'Strata piłek na podanie', 'Próby podań/90', '% wygranych pojedynków główkowych'],
    "Środkowy Pomocnik": ['SCORE', 'Percentyl', 'Piłkarz', 'Wiek', 'Kraj', 'Pozycja', 'Preferowana noga', 'Liga', 'Klub', 'Cena', 'Oczekiwane asysty/90', 'Kluczowe podania z gry/90', 'Liczba goli na 90 min', 'Udane próby pressingu/90', 'Odzyskane piłki/90', 'Stracone piłki/90', 'Strata piłek na podanie', 'Próby podań/90', 'Liczba dryblingów/90'],
    "Skrzydłowy": ['SCORE', 'Percentyl', 'Piłkarz', 'Wiek', 'Kraj', 'Pozycja', 'Preferowana noga', 'Liga', 'Klub', 'Cena', 'Oczekiwane asysty/90', 'Kluczowe podania z gry/90', 'Liczba goli na 90 min', 'Oczekiwane gole na strzał', 'Udane próby pressingu/90', 'Odzyskane piłki/90', 'Stracone piłki/90', 'Strata piłek na podanie', 'Próby podań/90', 'Liczba dryblingów/90'],
    "Napastnik": ['SCORE', 'Percentyl', 'Piłkarz', 'Wiek', 'Kraj', 'Pozycja', 'Preferowana noga', 'Liga', 'Klub', 'Cena', 'Oczekiwane asysty/90', 'Kluczowe podania z gry/90', 'Liczba goli na 90 min', 'Oczekiwane gole na strzał', 'Skuteczność strzałów (%)', 'Udane próby pressingu/90', 'Odzyskane piłki/90', 'Stracone piłki/90', 'Strata piłek na podanie', 'Próby podań/90', 'Liczba dryblingów/90']
}

# Wskazowki do rozpoznawania pozycji po nazwie pliku (bez rozszerzenia, malymi literami).
# "br" jest potwierdzone na Twoim pliku; pozostale skroty to ZALOZENIE - dopisz swoje nazwy plikow.
WSKAZOWKI_NAZW_PLIKOW = {
    "br": "Bramkarz", "bramkarz": "Bramkarz", "gk": "Bramkarz",
    "so": "Środkowy Obrońca", "śo": "Środkowy Obrońca", "cb": "Środkowy Obrońca",
    "bo": "Boczny Obrońca", "fb": "Boczny Obrońca", "po": "Boczny Obrońca", "lo": "Boczny Obrońca",
    "dp": "Defensywny Pomocnik", "dm": "Defensywny Pomocnik",
    "sp": "Środkowy Pomocnik", "śp": "Środkowy Pomocnik", "cm": "Środkowy Pomocnik",
    "sk": "Skrzydłowy", "skrzydłowy": "Skrzydłowy", "w": "Skrzydłowy",
    "n": "Napastnik", "nap": "Napastnik", "st": "Napastnik", "napastnik": "Napastnik",
}

# Mnozniki lig bazowe (wartosci heurystyczne - nie sa walidowane na danych)
MNOZNIKI_LIG = {
    "Premier League": 0.918,
    "EFL Championship": 0.811,
    "Liga Profesional de Fútbol": 0.809,
    "Liga Profesional": 0.809,
    "Primera Nacional": 0.749,
    "Jupiler Pro League": 0.816,
    "Profvoetbal 1A": 0.816,
    "Challenger Pro League": 0.695,
    "Profvoetbal 1B": 0.695,
    "Série A": 0.826,
    "Brasileirão": 0.826,
    "Série B": 0.721,
    "Brasileirão Série B": 0.721,
    "Hrvatska nogometna liga": 0.792,
    "HNL": 0.792,
    "Prva nogometa liga": 0.673,
    "1. NL": 0.673,
    "Ligue 1": 0.856,
    "Ligue 2": 0.758,
    "LaLiga": 0.866,
    "LaLiga 2": 0.777,
    "Eredivisie": 0.783,
    "Eerste Divisie": 0.66,
    "J1 League": 0.777,
    "J2 League": 0.695,
    "Liga MX": 0.778,
    "Liga Rozwojowa": 0.7,
    "Liga de Expansión MX": 0.7,
    "Bundesliga": 0.867,
    "2. Bundesliga": 0.778,
    "Ekstraklasa": 0.795,
    "I liga": 0.686,
    "1. Liga": 0.686,
    "Liga Portugal": 0.814,
    "Liga Portugal 2": 0.726,
    "MLS": 0.784,
    "Serie A": 0.86,
    "Serie B": 0.759
}

# Slownik mapujacy wyswietlane nazwy lig w aplikacji
MAPOWANIE_NAZW_LIG = {
    "Premier League": "Premier League (ANG 1)",
    "EFL Championship": "EFL Championship (ANG 2)",
    "Liga Profesional de Fútbol": "Liga Profesional de Fútbol (ARG 1)",
    "Liga Profesional": "Liga Profesional de Fútbol (ARG 1)",
    "Primera Nacional": "Primera Nacional (ARG 2)",
    "Jupiler Pro League": "Jupiler Pro League (BEL 1)",
    "Profvoetbal 1A": "Jupiler Pro League (BEL 1)",
    "Challenger Pro League": "Challenger Pro League (BEL 2)",
    "Profvoetbal 1B": "Challenger Pro League (BEL 2)",
    "Série A": "Série A (BRA 1)",
    "Brasileirão": "Série A (BRA 1)",
    "Série B": "Série B (BRA 2)",
    "Brasileirão Série B": "Série B (BRA 2)",
    "Hrvatska nogometna liga": "Hrvatska nogometna liga (CHO 1)",
    "HNL": "Hrvatska nogometna liga (CHO 1)",
    "Prva nogometa liga": "Prva nogometa liga (CHO 2)",
    "1. NL": "Prva nogometa liga (CHO 2)",
    "Ligue 1": "Ligue 1 (FRA 1)",
    "Ligue 2": "Ligue 2 (FRA 2)",
    "LaLiga": "LaLiga (HIS 1)",
    "LaLiga 2": "LaLiga 2 (HIS 2)",
    "Eredivisie": "Eredivisie (HOL 1)",
    "Eerste Divisie": "Eerste Divisie (HOL 2)",
    "J1 League": "J1 League (JAP 1)",
    "J2 League": "J2 League (JAP 2)",
    "Liga MX": "Liga MX (MEX 1)",
    "Liga Rozwojowa": "Liga Rozwojowa (MEX 2)",
    "Liga de Expansión MX": "Liga Rozwojowa (MEX 2)",
    "Bundesliga": "Bundesliga (NIE 1)",
    "2. Bundesliga": "2. Bundesliga (NIE 2)",
    "Ekstraklasa": "Ekstraklasa (POL 1)",
    "I liga": "I liga (POL 2)",
    "1. Liga": "I liga (POL 2)",
    "Liga Portugal": "Liga Portugal (POR 1)",
    "Liga Portugal 2": "Liga Portugal 2 (POR 2)",
    "MLS": "MLS (USA 1)",
    "Serie A": "Serie A (WLO 1)",
    "Serie B": "Serie B (WLO 2)"
}


# =============================================================================
# PARSERY (czyste funkcje, bez Streamlita)
# =============================================================================
def parse_age(val_str):
    if pd.isna(val_str):
        return 0
    first_part = str(val_str).split('-')[0].strip()
    try:
        return int(first_part)
    except (ValueError, TypeError):
        return 0


def _eur(tekst):
    """'6,25 tys. €' -> 6250.0; '1,9 mln €' -> 1900000.0; '750 €' -> 750.0. Rzuca ValueError przy bledzie."""
    t = str(tekst).replace('€', '').replace('\xa0', '').replace(' ', '').lower()
    mnoznik = 1_000_000 if 'mln' in t else 1_000 if 'tys' in t else 1
    t = re.sub(r'mln|tys\.?', '', t)
    return float(t.replace(',', '.')) * mnoznik


def parse_market_value(val_str):
    """Szacowana wartosc -> srodek geometryczny widelek (EUR). 'Nie na sprzedaz' / brak -> NaN."""
    if pd.isna(val_str) or 'sprzeda' in str(val_str).lower():
        return np.nan
    try:
        wartosci = [_eur(p) for p in str(val_str).split(' - ')]
    except ValueError:
        return np.nan
    lo, hi = wartosci[0], wartosci[-1]
    return (lo * hi) ** 0.5 if lo > 0 else (lo + hi) / 2


def parse_wages(val_str):
    """Placa -> kwota roczna w EUR. Rozpoznaje 'tyg.', 'tydz', '/w' jako stawke tygodniowa."""
    if pd.isna(val_str):
        return np.nan
    t = str(val_str).lower().split(' - ')[0]
    tygodniowa = bool(re.search(r'tyg|tydz|/w', t))
    t = re.sub(r'tyg\.?|tydz\.?|/w|/rok|/y', '', t)
    try:
        return _eur(t) * (52 if tygodniowa else 1)
    except ValueError:
        return np.nan


def do_liczb(seria):
    """Tekst z FM ('45 %', '0,35', '1 234') -> liczba; bledy -> NaN."""
    oczyszczone = (seria.astype(str)
                   .str.replace('\xa0', '', regex=False)
                   .str.replace(' ', '', regex=False)
                   .str.replace('%', '', regex=False)
                   .str.replace(',', '.', regex=False)
                   .str.strip())
    return pd.to_numeric(oczyszczone, errors='coerce')


# =============================================================================
# WCZYTYWANIE I CZYSZCZENIE DANYCH (raz, w cache)
# =============================================================================
@st.cache_data(show_spinner="Przetwarzanie pliku CSV...")
def load_and_clean_data(plik_bajty):
    try:
        df = pd.read_csv(io.BytesIO(plik_bajty), sep=None, engine='python', dtype=str, encoding='utf-8-sig')
    except UnicodeDecodeError:
        df = pd.read_csv(io.BytesIO(plik_bajty), sep=None, engine='python', dtype=str, encoding='cp1250')

    df.columns = df.columns.astype(str).str.replace('\ufeff', '', regex=False).str.strip()
    df = df.rename(columns=TLUMACZENIE_KOLUMN)

    # Kolumna z minutami (opcjonalna) -> 'Minuty'
    for nazwa in NAZWY_KOLUMNY_MINUT:
        if nazwa in df.columns and 'Minuty' not in df.columns:
            df = df.rename(columns={nazwa: 'Minuty'})
            break

    if 'Piłkarz' not in df.columns:
        raise ValueError("Brak kolumny 'Piłkarz' - czy to na pewno eksport z FM?")
    df = df[df['Piłkarz'].notna()].copy()

    if 'Wiek' in df.columns:
        df['Wiek'] = df['Wiek'].apply(parse_age)
        df = df[df['Wiek'] > 0]

    # Cena i placa: NaN oznacza "brak danych / nie na sprzedaz" (a nie 0 EUR)
    df['Wartość_Numeryczna'] = df['Cena'].apply(parse_market_value) if 'Cena' in df.columns else np.nan
    df['Zarobki_Numeryczne'] = df['Płaca'].apply(parse_wages) if 'Płaca' in df.columns else np.nan

    # Statystyki -> liczby (raz, tutaj)
    for kol in KOLUMNY_STATYSTYK + ['Minuty']:
        if kol in df.columns:
            df[kol] = do_liczb(df[kol])

    # Cecha pochodna: odsetek podan konczacych sie strata pilki (mniej = lepiej)
    if 'Stracone piłki/90' in df.columns and 'Próby podań/90' in df.columns:
        podania = df['Próby podań/90'].where(df['Próby podań/90'] > 0)
        df['Strata piłek na podanie'] = df['Stracone piłki/90'] / podania

    # Liga: mnoznik liczony na surowej nazwie, potem nazwa wyswietlana
    if 'Liga' in df.columns:
        liga_surowa = df['Liga'].astype(str).str.replace('\xa0', ' ', regex=False).str.strip()
        df['Mnożnik_Ligi'] = liga_surowa.map(MNOZNIKI_LIG)
        df['Liga_bez_mnoznika'] = df['Mnożnik_Ligi'].isna()
        df['Mnożnik_Ligi'] = df['Mnożnik_Ligi'].fillna(1.0)
        df['Liga'] = liga_surowa.map(MAPOWANIE_NAZW_LIG).fillna(liga_surowa)
    else:
        df['Mnożnik_Ligi'] = 1.0
        df['Liga_bez_mnoznika'] = False

    # Data wygasniecia kontraktu (format d.m.rrrr)
    if 'Wygasa' in df.columns:
        df['Wygasa_Data'] = pd.to_datetime(df['Wygasa'], dayfirst=True, errors='coerce')
    else:
        df['Wygasa_Data'] = pd.NaT

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


def wykryj_pozycje(nazwa_pliku, df):
    """Probuje odgadnac pozycje: po kolumnie 'Pozycja' (BR = bramkarz) lub po nazwie pliku."""
    if 'Pozycja' in df.columns:
        kody = df['Pozycja'].dropna().astype(str).str.strip().str.upper()
        if len(kody) and kody.str.startswith('BR').mean() > 0.9:
            return "Bramkarz"
    nazwa = re.sub(r'\.csv$', '', nazwa_pliku, flags=re.I).strip().lower()
    nazwa = re.sub(r'[\s_\-]*\(?\d+\)?$', '', nazwa)   # "BR (1)" -> "br"
    return WSKAZOWKI_NAZW_PLIKOW.get(nazwa)


def raport_wczytania(df, pozycja):
    """Zwraca liste (poziom, tekst) opisujaca jakosc wczytanych danych."""
    wynik = []
    wynik.append(("info", f"Liczba zawodników: {len(df)}"))
    brakujace = [k for k in ('Piłkarz', 'Wiek', 'Klub', 'Liga') if k not in df.columns]
    if brakujace:
        wynik.append(("warn", f"Brak kolumn podstawowych: {', '.join(brakujace)}"))
    brak_cech = [c for c in MERYTORYKA_WAG[pozycja] if c not in df.columns]
    if brak_cech:
        wynik.append(("warn", "Brak kolumn potrzebnych do wyniku (cechy pominięte): " + ", ".join(brak_cech)))
    if 'Minuty' in df.columns and df['Minuty'].notna().any():
        wynik.append(("info", "Znaleziono kolumnę z minutami - włączone skurczenie cech przy małej próbie."))
    else:
        wynik.append(("warn", "Brak kolumny z minutami (np. 'Min') - wynik bez korekty na małą próbę. "
                              "Dodaj ją do widoku w FM i wyeksportuj ponownie."))
    if 'Liga_bez_mnoznika' in df.columns and df['Liga_bez_mnoznika'].any():
        nieznane = sorted(df.loc[df['Liga_bez_mnoznika'], 'Liga'].unique())
        wynik.append(("warn", "Ligi bez zdefiniowanego mnożnika (przyjęto 1.0): " + ", ".join(nieznane)))
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


# =============================================================================
# MODEL: WYNIK (SCORE) W Z-SCORE, ZE SKURCZENIEM PRZY MALEJ LICZBIE MINUT
# =============================================================================
def oblicz_z(df, nazwy_cech, k_baza):
    """
    Dla kazdej cechy liczy z-score w obrebie calej puli (df). Jesli dostepne sa minuty, cechy per 90
    sa skurczone w strone sredniej puli: x* = (n90*x + k*srednia) / (n90 + k), gdzie n90 to liczba
    pelnych meczow, a k = k_baza * wspolczynnik cechy. Odchylenie standardowe liczone jest na
    surowych wartosciach, wiec skurczenie realnie przyciaga niepewnych zawodnikow do zera.
    Zwraca (slownik z-score'ow, n90 lub None).
    """
    n90 = None
    if 'Minuty' in df.columns and df['Minuty'].notna().any():
        n90 = df['Minuty'] / 90.0
        n90 = n90.fillna(n90.median())

    z = {}
    for nazwa in nazwy_cech:
        if nazwa not in df.columns:
            continue
        x = df[nazwa].astype(float)
        if x.notna().sum() < 2:
            continue
        srednia, odchylenie = x.mean(), x.std(ddof=0)
        if not np.isfinite(odchylenie) or odchylenie == 0:
            continue
        kierunek, skurcz = CECHY.get(nazwa, (1, 0.0))
        xs = x.fillna(srednia)
        if n90 is not None and skurcz > 0 and k_baza > 0:
            k = k_baza * skurcz
            xs = (n90 * xs + k * srednia) / (n90 + k)
        z[nazwa] = ((xs - srednia) / odchylenie * kierunek).clip(-3, 3)
    return z, n90


def oblicz_score(df, wagi, ignoruj_mnoznik, k_baza):
    """
    SCORE = 50 + 10 * (skladana z-score'ow - srednia) / odchylenie, czyli skala typu T-score:
    50 = przecietny zawodnik na tej pozycji w wgranej probie, +10 = jedno odchylenie wyzej
    (po wlaczeniu mnoznika ligowego wynik jest dodatkowo mnozony przez wspolczynnik ligi).
    Wagi sa normalizowane do sumy 1. Zwraca (SCORE, Wiarygodnosc w %, lista pominietych cech).
    """
    nazwy = [n for n, w in wagi.items() if w > 0]
    z, n90 = oblicz_z(df, nazwy, k_baza)
    uzyte = [n for n in nazwy if n in z]
    pominiete = [n for n in nazwy if n not in z]
    suma = sum(wagi[n] for n in uzyte)

    if not uzyte or suma <= 0:
        return pd.Series(np.nan, index=df.index), pd.Series(np.nan, index=df.index), pominiete

    kompozyt = sum(z[n] * (wagi[n] / suma) for n in uzyte)
    odch = kompozyt.std(ddof=0)
    if np.isfinite(odch) and odch > 0:
        score = 50.0 + 10.0 * (kompozyt - kompozyt.mean()) / odch
    else:
        score = pd.Series(50.0, index=df.index)

    if not ignoruj_mnoznik and 'Mnożnik_Ligi' in df.columns:
        score = score * df['Mnożnik_Ligi']

    if n90 is not None and k_baza > 0:
        wiarygodnosc = n90 / (n90 + k_baza) * 100.0
    else:
        wiarygodnosc = pd.Series(np.nan, index=df.index)
    return score, wiarygodnosc, pominiete


def percentyl_w_puli(pula, wartosc):
    """Percentyl (0-100, ranga srednia przy remisach) wartosci w puli."""
    x = pula.dropna()
    if x.empty or pd.isna(wartosc):
        return 0.0
    return float(((x < wartosc).mean() + 0.5 * (x == wartosc).mean()) * 100)


def macierz_stylu(pula, kolumny):
    """Macierz z-score'ow (braki = srednia puli, czyli 0; stale kolumny pomijane) do szukania sobowtora."""
    kolumny_ok = {}
    for c in kolumny:
        x = pula[c].astype(float)
        odch = x.std(ddof=0)
        if not np.isfinite(odch) or odch == 0:
            continue
        kolumny_ok[c] = ((x.fillna(x.mean()) - x.mean()) / odch).clip(-3, 3)
    return pd.DataFrame(kolumny_ok, index=pula.index)


def wstaw_po(lista, nowy, po):
    if nowy in lista:
        return
    i = lista.index(po) + 1 if po in lista else len(lista)
    lista.insert(i, nowy)


# =============================================================================
# DANE DEMO (SYNTETYCZNE) - generowane w formacie zblizonym do eksportu z FM
# =============================================================================
def _fmt_eur(x):
    if x >= 1_000_000:
        return f"{x / 1_000_000:.1f}".replace('.', ',').replace(',0', '') + " mln €"
    if x >= 1_000:
        return f"{round(x / 1_000)} tys. €"
    return f"{round(x)} €"


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
        "Nie na sprzedaż" if rng.random() < 0.1 else f"{_fmt_eur(v * 0.7)} - {_fmt_eur(v * 1.6)}"
        for v in wartosc
    ]
    dane['Płaca'] = [f"{_fmt_eur(v / 100)} tyg." for v in wartosc]
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


@st.cache_data(show_spinner="Generowanie danych demo...")
def demo_dane(pozycja):
    return load_and_clean_data(generuj_demo_csv(pozycja))


# =============================================================================
# KLUCZE WIDGETOW I CZYSZCZENIE FILTROW
# =============================================================================
def klucz(nazwa, pozycja, sygnatura):
    # Sygnatura danych w kluczu chroni przed bledem, gdy po wgraniu nowego pliku
    # zapamietana wartosc suwaka/listy wykracza poza nowy zakres.
    return f"{nazwa}_{pozycja}_{sygnatura}"


def clear_filters(pozycja, sygnatura, min_a, max_a, max_p_mln):
    st.session_state[klucz("search", pozycja, sygnatura)] = ""
    st.session_state[klucz("ligi", pozycja, sygnatura)] = []
    st.session_state[klucz("noga", pozycja, sygnatura)] = []
    st.session_state[klucz("age", pozycja, sygnatura)] = (min_a, max_a)
    st.session_state[klucz("price", pozycja, sygnatura)] = (0.0, float(max_p_mln))
    st.session_state[klucz("bez_ceny", pozycja, sygnatura)] = True
    st.session_state[klucz("ignore_mult", pozycja, sygnatura)] = False
    k_kontrakt = klucz("contract", pozycja, sygnatura)
    if k_kontrakt in st.session_state:
        st.session_state[k_kontrakt] = False
    for stat_name, default_val in MERYTORYKA_WAG.get(pozycja, {}).items():
        k_wagi = f"weight_{pozycja}_{stat_name}"
        if k_wagi in st.session_state:
            st.session_state[k_wagi] = int(default_val)


def wlacz_demo():
    st.session_state["demo_aktywne"] = True


def wylacz_demo():
    st.session_state["demo_aktywne"] = False


# =============================================================================
# INTERFEJS
# =============================================================================
if "demo_aktywne" not in st.session_state:
    st.session_state["demo_aktywne"] = False

st.markdown("<div style='font-size: 2.7rem; font-weight: bold; margin-top: -3.5rem; margin-bottom: 1rem;'>FM26 Moneyball Dashboard</div>", unsafe_allow_html=True)

# --- SIDEBAR: kontener na wybor pozycji (wypelniony po wczytaniu plikow) ---
kontener_pozycji = st.sidebar.container()

dane = {}      # pozycja -> DataFrame
zrodla = {}    # pozycja -> nazwa pliku lub "DEMO"

with st.sidebar:
    st.markdown("---")
    st.markdown("<div style='font-size: 1.15rem; font-weight: 600; margin-bottom: 0.5rem;'>Dane (pliki CSV)</div>", unsafe_allow_html=True)
    pliki = st.file_uploader("Wgraj pliki CSV", type=["csv"], accept_multiple_files=True,
                             key="uploader_wiele", label_visibility="collapsed")

    for plik in (pliki or []):
        surowe = plik.getvalue()
        try:
            df_pliku = load_and_clean_data(surowe)
        except Exception as e:
            st.error(f"Nie udało się wczytać pliku {plik.name}: {e}")
            continue
        k_przyp = f"przypisanie_{plik.name}_{len(surowe)}"
        if k_przyp not in st.session_state:
            st.session_state[k_przyp] = wykryj_pozycje(plik.name, df_pliku) or WYBIERZ
        wybor = st.selectbox(f"{plik.name} ({len(df_pliku)} zawodników) - pozycja:",
                             [WYBIERZ] + POZYCJE, key=k_przyp)
        if wybor != WYBIERZ:
            if wybor in dane:
                st.warning(f"Pozycja {wybor} jest przypisana do więcej niż jednego pliku - użyto {plik.name}.")
            dane[wybor] = df_pliku
            zrodla[wybor] = plik.name

    if st.session_state["demo_aktywne"]:
        for p in POZYCJE:
            if p not in dane:
                dane[p] = demo_dane(p)
                zrodla[p] = "DEMO"
        st.button("Usuń dane demo", on_click=wylacz_demo, key="btn_demo_off")
    else:
        st.button("Wczytaj dane demo (syntetyczne)", on_click=wlacz_demo, key="btn_demo_on")

    with st.expander("Ustawienia", expanded=False):
        moj_klub = st.text_input("Mój klub (podświetlenie w tabelach):", value="Tottenham", key="moj_klub")
        k_baza = st.slider(
            "Siła skurczenia przy małej próbie (mecze):", 0, 15, 5, key="k_baza",
            help="Działa tylko, gdy plik zawiera minuty. Zawodnik z małą liczbą minut jest przyciągany do średniej "
                 "pozycji: im większa wartość, tym mocniej. 0 = wyłączone."
        )
    st.markdown("---")

with kontener_pozycji:
    st.markdown("### Wybierz pozycję")
    pozycja_nazwa = st.radio(
        "Pozycja", POZYCJE,
        format_func=lambda p: f"{p} ({len(dane[p])})" if p in dane else p,
        label_visibility="collapsed"
    )

df = dane.get(pozycja_nazwa)

if df is None or df.empty:
    st.info(f"Brak danych dla pozycji: {pozycja_nazwa}. Wgraj plik CSV w panelu bocznym "
            "(po wgraniu wskaż, której pozycji dotyczy) albo użyj danych demo.")
    with st.expander("Jak przygotować eksport z FM?", expanded=True):
        st.markdown(
            "- Widok z kolumnami: **Piłkarz, Wiek, Klub, Liga, Pozycja, Preferowana noga, Szacowana wartość, "
            "Płaca, Wygasa** oraz statystyki per 90 (xA, KPzG, gole, ZxG itd.).\n"
            "- **Dodaj kolumnę z minutami** (np. *Min*) - dzięki niej wynik uwzględni niepewność przy małej próbie.\n"
            "- Wyeksportuj widok do CSV osobno dla każdej pozycji i wgraj pliki (można kilka naraz)."
        )
    st.stop()

if zrodla.get(pozycja_nazwa) == "DEMO":
    st.warning("Wyświetlane są syntetyczne dane demonstracyjne, a nie dane z Twojej gry.")

sygnatura = f"{len(df)}_{int(df['Wiek'].sum()) if 'Wiek' in df.columns else 0}"
K = lambda nazwa: klucz(nazwa, pozycja_nazwa, sygnatura)

# --- DYNAMICZNE FILTRY W SIDEBARZE ---
zdefiniowana_kolejnosc = list(MAPOWANIE_NAZW_LIG.values())
unikalne_ligi = df['Liga'].dropna().unique().tolist() if 'Liga' in df.columns else []
dostepne_ligi = sorted(unikalne_ligi, key=lambda x: zdefiniowana_kolejnosc.index(x) if x in zdefiniowana_kolejnosc else 999)
dostepne_nogi = sorted(df['Preferowana noga'].dropna().unique()) if 'Preferowana noga' in df.columns else []

min_age = int(df['Wiek'].min()) if 'Wiek' in df.columns else 15
max_age = int(df['Wiek'].max()) if 'Wiek' in df.columns else 45
if min_age >= max_age:
    max_age = min_age + 1

ceny_ok = df['Wartość_Numeryczna'].dropna()
max_price_avail = float(ceny_ok.max()) if not ceny_ok.empty and ceny_ok.max() > 0 else 100_000_000.0
max_price_mln = max(max_price_avail / 1_000_000, 0.1)
liczba_bez_ceny = int(df['Wartość_Numeryczna'].isna().sum())

with st.sidebar:
    st.markdown("### Filtry wyszukiwania")
    ignore_mult = st.toggle("Ignoruj mnożnik ligowy", key=K("ignore_mult"),
                            help="Mnożniki lig są wartościami heurystycznymi (nie weryfikowanymi na danych).")
    search = st.text_input("Szukaj (Piłkarz / Klub):", key=K("search"))
    wybrane_ligi = st.multiselect("Wybierz ligi:", options=dostepne_ligi, key=K("ligi"))
    wybrana_noga = st.multiselect("Lepsza noga:", options=dostepne_nogi, key=K("noga"))

    # --- FILTR KOŃCA KONTRAKTU (z datą w grze) ---
    filtr_kontraktu = False
    data_gry = None
    miesiace = 6
    if df['Wygasa_Data'].notna().any():
        filtr_kontraktu = st.checkbox("Tylko kontrakty wygasające wkrótce", key=K("contract"))
        if filtr_kontraktu:
            data_gry = st.date_input(
                "Data w grze:", value=df['Wygasa_Data'].min().date(), key=K("data_gry"),
                help="Ustaw bieżącą datę z gry. Domyślnie wpisano najwcześniejszy koniec kontraktu z pliku."
            )
            miesiace = st.number_input("W ciągu (miesięcy):", min_value=1, max_value=36, value=6, key=K("miesiace"))

    age_filter = st.slider("Wiek:", min_age, max_age, (min_age, max_age), key=K("age"))
    price_filter_mln = st.slider("Cena (mln €):", 0.0, float(max_price_mln), (0.0, float(max_price_mln)), key=K("price"))
    pokaz_bez_ceny = True
    if liczba_bez_ceny:
        pokaz_bez_ceny = st.toggle(f"Uwzględnij zawodników bez ceny ({liczba_bez_ceny})", value=True, key=K("bez_ceny"),
                                   help="Zawodnicy oznaczeni jako 'Nie na sprzedaż' nie mają ceny i nie są traktowani jako darmowi.")
    price_min = price_filter_mln[0] * 1_000_000
    price_max = price_filter_mln[1] * 1_000_000 + 1   # +1 EUR chroni przed bledem zaokraglenia

    # --- EDYTOR WAG ---
    st.markdown("### Zaawansowane wagi")
    custom_weights = {}
    with st.expander("Modyfikuj wagi statystyk", expanded=False):
        st.caption("Ważność 0-100. Wagi są normalizowane do sumy 1, więc liczą się tylko proporcje.")
        for stat_name, default_val in MERYTORYKA_WAG[pozycja_nazwa].items():
            if stat_name not in df.columns:
                continue
            custom_weights[stat_name] = st.slider(
                f"{stat_name}:", min_value=0, max_value=100, value=int(default_val), step=5,
                key=f"weight_{pozycja_nazwa}_{stat_name}"
            )
        suma_wag = sum(custom_weights.values())
        if suma_wag > 0:
            udzialy = ", ".join(f"{n.split('/')[0]}: {w / suma_wag * 100:.0f}%" for n, w in custom_weights.items() if w > 0)
            st.caption("Udział po normalizacji - " + udzialy)

    szeroki(st.button, "Wyczyść filtry", key=f"btn_clear_{pozycja_nazwa}", on_click=clear_filters,
            args=(pozycja_nazwa, sygnatura, min_age, max_age, max_price_mln))

# --- RAPORT WCZYTANIA ---
with st.expander("Raport wczytania danych", expanded=False):
    for poziom, tekst in raport_wczytania(df, pozycja_nazwa):
        if poziom == "warn":
            st.warning(tekst)
        else:
            st.caption(tekst)

# --- REKALKULACJA I FILTROWANIE ---
base_df = df.copy()
score, wiarygodnosc, pominiete = oblicz_score(base_df, custom_weights, ignore_mult, k_baza)
if score.isna().all():
    st.error("Nie można obliczyć wyniku: brak kolumn statystycznych dla wybranych wag (lub wszystkie wagi = 0).")
    st.stop()
if pominiete:
    st.caption("Pominięte cechy (brak danych lub brak zróżnicowania): " + ", ".join(pominiete))

base_df['SCORE'] = score
base_df['Percentyl'] = score.rank(pct=True) * 100
base_df['Wiarygodność'] = wiarygodnosc

filtered_df = base_df
if 'Wiek' in filtered_df.columns:
    filtered_df = filtered_df[(filtered_df['Wiek'] >= age_filter[0]) & (filtered_df['Wiek'] <= age_filter[1])]

cena = filtered_df['Wartość_Numeryczna']
filtered_df = filtered_df[cena.between(price_min, price_max) | (cena.isna() & pokaz_bez_ceny)]

if wybrane_ligi:
    filtered_df = filtered_df[filtered_df['Liga'].isin(wybrane_ligi)]
if wybrana_noga:
    filtered_df = filtered_df[filtered_df['Preferowana noga'].isin(wybrana_noga)]
if filtr_kontraktu and data_gry is not None:
    start = pd.Timestamp(data_gry)
    koniec = start + pd.DateOffset(months=int(miesiace))
    wygasa = filtered_df['Wygasa_Data']
    filtered_df = filtered_df[wygasa.notna() & (wygasa >= start) & (wygasa <= koniec)]

if search:
    warunek = pd.Series(False, index=filtered_df.index)
    if 'Piłkarz' in filtered_df.columns:
        warunek |= filtered_df['Piłkarz'].str.contains(search, case=False, na=False, regex=False)
    if 'Klub' in filtered_df.columns:
        warunek |= filtered_df['Klub'].str.contains(search, case=False, na=False, regex=False)
    filtered_df = filtered_df[warunek]

filtered_df = filtered_df.sort_values(by="SCORE", ascending=False)

# --- TABELA GŁÓWNA WYNIKÓW ---
dedykowane_kolumny = KOLUMNY_PER_POZYCJA.get(pozycja_nazwa, [])
cols_to_show = [c for c in dedykowane_kolumny if c in filtered_df.columns]
if len(cols_to_show) <= 2:
    cols_to_show = [c for c in ['SCORE', 'Percentyl', 'Piłkarz', 'Wiek', 'Preferowana noga', 'Klub', 'Liga', 'Cena']
                    if c in filtered_df.columns]

if filtered_df['Wiarygodność'].notna().any():
    wstaw_po(cols_to_show, 'Wiarygodność', 'Percentyl')
if 'Minuty' in filtered_df.columns and filtered_df['Minuty'].notna().any():
    wstaw_po(cols_to_show, 'Minuty', 'Klub')
if 'Płaca' in filtered_df.columns:
    wstaw_po(cols_to_show, 'Płaca', 'Cena')
if 'Wygasa' in filtered_df.columns:
    wstaw_po(cols_to_show, 'Wygasa', 'Płaca' if 'Płaca' in cols_to_show else 'Cena')

TEKSTOWE = ['Percentyl', 'Piłkarz', 'Klub', 'Liga', 'Pozycja', 'Cena', 'Płaca', 'Wygasa', 'Kraj', 'Preferowana noga']
format_dict = {}
for col in cols_to_show:
    if col == 'SCORE' or col in ('Wiek', 'Minuty'):
        format_dict[col] = '{:.0f}'
    elif col == 'Wiarygodność':
        format_dict[col] = '{:.0f}%'
    elif col == 'Strata piłek na podanie':
        format_dict[col] = '{:.2f}'
    elif col not in TEKSTOWE and pd.api.types.is_numeric_dtype(filtered_df[col]):
        format_dict[col] = '{:.1f}'

jasna_paleta = mcolors.LinearSegmentedColormap.from_list("jasne_kolory", ["#ff9999", "#ffff99", "#99ff99"])


def podswietl_moj_klub(row):
    if moj_klub and 'Klub' in row.index and pd.notna(row['Klub']) and moj_klub.lower() in str(row['Klub']).lower():
        return ['background-color: #282933;' for _ in row]
    return ['' for _ in row]


df_style = filtered_df[cols_to_show].style.format(format_dict, na_rep="–")
df_style = df_style.apply(podswietl_moj_klub, axis=1)
if 'SCORE' in cols_to_show:
    df_style = df_style.background_gradient(subset=['SCORE'], cmap=jasna_paleta)
    df_style = df_style.set_properties(subset=['SCORE'], **{'color': 'black', 'text-align': 'center'})
df_style = df_style.set_table_styles([{'selector': 'th', 'props': [('text-align', 'center')]}], overwrite=False)

col_config = {}
if 'SCORE' in cols_to_show:
    col_config['SCORE'] = st.column_config.Column(
        "SCORE", alignment="center",
        help="Skala typu T-score: 50 = przeciętny zawodnik na tej pozycji w wgranej próbie, +10 = jedno odchylenie standardowe wyżej. Przy włączonym mnożniku ligowym wartości są dodatkowo skalowane przez ligę (średnia spada poniżej 50).")
if 'Percentyl' in cols_to_show:
    col_config['Percentyl'] = st.column_config.ProgressColumn(
        "Percentyl", help="0-100: pozycja w wgranej próbie (nie w całej lidze).",
        format="%.0f", min_value=0, max_value=100, width="small")
if 'Wiarygodność' in cols_to_show:
    col_config['Wiarygodność'] = st.column_config.ProgressColumn(
        "Wiarygodność", help="Ile wyniku pochodzi z faktycznych statystyk zawodnika, a ile ze średniej pozycji (zależy od minut).",
        format="%.0f", min_value=0, max_value=100, width="small")

szeroki(st.dataframe, df_style, height=400, hide_index=True, column_config=col_config)

# --- PORÓWNANIE ZAWODNIKÓW (RADAR) ---
st.markdown("---")
st.subheader("Porównanie zawodników", anchor=False)

zawodnicy_do_porownania = st.multiselect(
    "Wybierz dokładnie dwóch zawodników z tabeli, aby nałożyć ich statystyki na radar percentylowy:",
    options=filtered_df['ID'].tolist(), max_selections=2, key=K("compare")
)

stat_cols = [c for c in dedykowane_kolumny if c not in NIE_STATYSTYKI and c in base_df.columns]

if len(zawodnicy_do_porownania) == 2:
    df_compare = filtered_df[filtered_df['ID'].isin(zawodnicy_do_porownania)]
    if stat_cols:
        fig = go.Figure()
        etykiety = [c + " (odwrócone)" if c in NIZSZE_LEPSZE else c for c in stat_cols]
        for _, row in df_compare.iterrows():
            procenty = []
            for c in stat_cols:
                p = percentyl_w_puli(base_df[c], row[c])
                procenty.append(100.0 - p if c in NIZSZE_LEPSZE else p)   # mniej strat = lepiej
            fig.add_trace(go.Scatterpolar(
                r=procenty + [procenty[0]], theta=etykiety + [etykiety[0]], fill='toself',
                name=row['ID'], mode='lines+markers', opacity=0.5, marker=dict(size=8),
                hovertemplate="<b>%{fullData.name}</b><br>%{theta}: %{r:.1f}%<extra></extra>"
            ))
        fig.update_layout(
            paper_bgcolor='#262730', plot_bgcolor='#262730',
            polar=dict(
                bgcolor='#262730',
                radialaxis=dict(visible=True, showticklabels=False, range=[0, 100], gridcolor='rgba(255, 255, 255, 0.15)'),
                angularaxis=dict(gridcolor='rgba(255, 255, 255, 0.15)', tickfont=dict(color='white'))
            ),
            font=dict(family="Arial", size=14, color="white"),
            legend=dict(orientation="v", x=-0.2, y=0.5, xanchor='right', yanchor='middle', font=dict(size=16, color="white")),
            showlegend=True, height=500, margin=dict(t=40, b=40, l=120, r=40)
        )
        szeroki(st.plotly_chart, fig)
    else:
        st.info("Brak szczegółowych statystyk meczowych do wygenerowania radaru.")
elif len(zawodnicy_do_porownania) == 1:
    st.info("Wybierz jeszcze drugiego zawodnika z listy.")

# --- ZNAJDŹ SOBOWTÓRA ---
st.markdown("---")
st.subheader("Znajdź sobowtóra", anchor=False)
st.markdown("Wybierz zawodnika (np. gwiazdę swojej drużyny). Algorytm porówna profil statystyk per 90 minut "
            "(podobieństwo kosinusowe w obrębie tej pozycji) i wskaże 5 najbardziej podobnych graczy spośród "
            "widocznych w tabeli. Profil jest liczony na pełnej wgranej próbie, więc filtry nie zniekształcają wyniku.")

zawodnik_do_zastapienia = st.selectbox("Kogo chcesz zastąpić?", options=[""] + sorted(base_df['ID'].tolist()), key=K("klon"))

if zawodnik_do_zastapienia:
    macierz = macierz_stylu(base_df, stat_cols)
    if macierz.shape[1] < 2:
        st.info("Za mało zróżnicowanych kolumn liczbowych do porównania stylu gry.")
    else:
        M = macierz.values
        poz = int(np.flatnonzero(base_df['ID'].values == zawodnik_do_zastapienia)[0])
        wektor = M[poz]
        normy = np.linalg.norm(M, axis=1) * np.linalg.norm(wektor)
        with np.errstate(divide='ignore', invalid='ignore'):
            podobienstwo = np.where(normy > 0, M @ wektor / normy, 0.0)
        wyniki = base_df.copy()
        wyniki['Podobieństwo'] = podobienstwo
        wyniki = wyniki[wyniki.index.isin(filtered_df.index) & (wyniki['ID'] != zawodnik_do_zastapienia)]
        top5 = wyniki.sort_values('Podobieństwo', ascending=False).head(5).copy()
        top5['Zgodność'] = (top5['Podobieństwo'].clip(0, 1) * 100).round(1).astype(str) + "%"

        st.success(f"Oto 5 najlepszych alternatyw dla: **{zawodnik_do_zastapienia}** (wśród widocznych w tabeli zawodników)")
        kolumny_ml = [c for c in ['SCORE', 'Zgodność', 'Piłkarz', 'Wiek', 'Preferowana noga', 'Klub', 'Liga', 'Pozycja',
                                  'Cena', 'Płaca', 'Wygasa'] if c in top5.columns]
        format_ml = {c: '{:.0f}' for c in ('SCORE', 'Wiek') if c in kolumny_ml}
        stylowana = top5[kolumny_ml].style.format(format_ml, na_rep="–").apply(podswietl_moj_klub, axis=1)
        if 'SCORE' in kolumny_ml:
            stylowana = stylowana.background_gradient(subset=['SCORE'], cmap=jasna_paleta)
            stylowana = stylowana.set_properties(subset=['SCORE'], **{'color': 'black', 'text-align': 'center'})
        stylowana = stylowana.set_table_styles([{'selector': 'th', 'props': [('text-align', 'center')]}], overwrite=False)
        szeroki(st.dataframe, stylowana, hide_index=True, column_config={
            'Zgodność': st.column_config.TextColumn("Zgodność", help="Podobieństwo kształtu statystyk meczowych do wybranego zawodnika."),
            'SCORE': st.column_config.Column("SCORE", alignment="center")
        })

# --- WYKRES: SCORE VS CENA ---
tooltip_cols = [
    alt.Tooltip('ID:N', title='Piłkarz'),
    alt.Tooltip('Wiek:Q', title='Wiek', format='.0f'),
    alt.Tooltip('Klub:N', title='Klub'),
    alt.Tooltip('Cena:N', title='Cena'),
    alt.Tooltip('SCORE:Q', title='SCORE', format='.0f'),
    alt.Tooltip('Percentyl:Q', title='Percentyl', format='.0f'),
    alt.Tooltip('Liga:N', title='Liga')
]
if 'Płaca' in filtered_df.columns:
    tooltip_cols.append(alt.Tooltip('Płaca:N', title='Płaca'))

chart_data = filtered_df[filtered_df['Wartość_Numeryczna'].notna()].head(30)
if not chart_data.empty:
    st.markdown("---")
    st.subheader("Score vs Cena (Top 30, tylko zawodnicy z ceną)", anchor=False)
    min_score, max_score = float(chart_data['SCORE'].min()), float(chart_data['SCORE'].max())
    margines = (max_score - min_score) * 0.05 or 1.0
    wykres = alt.Chart(chart_data).mark_circle(size=300).encode(
        x=alt.X('Wartość_Numeryczna:Q', title='Cena (€, środek widełek)', axis=alt.Axis(format='~s'),
                scale=alt.Scale(zero=False)),
        y=alt.Y('SCORE:Q', title='Score', axis=alt.Axis(format='.0f'),
                scale=alt.Scale(zero=False, domain=[min_score - margines, max_score + margines])),
        color=alt.Color('Wiek:Q', scale=alt.Scale(scheme='viridis'), title='Wiek'),
        tooltip=tooltip_cols
    ).properties(height=500)
    szeroki(st.altair_chart, wykres.interactive())

# --- TOP 10 W POSZCZEGÓLNYCH STATYSTYKACH ---
kolumny_statystyk = [c for c in dedykowane_kolumny if c not in NIE_STATYSTYKI and c in filtered_df.columns]
if kolumny_statystyk and not filtered_df.empty:
    st.markdown("---")
    st.subheader("Najlepsi zawodnicy w poszczególnych statystykach (Top 10)", anchor=False)
    kolumny_ui = st.columns(2)
    for idx, stat_col in enumerate(kolumny_statystyk):
        with kolumny_ui[idx % 2]:
            seria = filtered_df[stat_col].astype(float).dropna()
            if seria.empty:
                continue
            if stat_col in NIZSZE_LEPSZE:
                top10 = seria.nsmallest(10).index
                sort_order = 'x'
            else:
                top10 = seria.nlargest(10).index
                sort_order = '-x'
            dane_slupkow = filtered_df.loc[top10].copy()
            format_stat = '.0f' if '%' in stat_col else ('.2f' if stat_col == 'Strata piłek na podanie' else '.1f')
            wykres_slupkowy = alt.Chart(dane_slupkow).mark_bar().encode(
                x=alt.X(field=stat_col, type='quantitative', title=stat_col),
                y=alt.Y('ID', type='nominal', sort=sort_order, title=''),
                color=alt.Color('SCORE:Q', scale=alt.Scale(scheme='blues'), legend=None),
                tooltip=tooltip_cols + [alt.Tooltip(f'{stat_col}:Q', title=stat_col, format=format_stat)]
            ).properties(height=350, title=stat_col)
            szeroki(st.altair_chart, wykres_slupkowy.interactive())
