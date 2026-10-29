"""
Historia zawodnikow: migawki kolejnych wczytan zapisu kariery i wskazniki rozwoju.

Zapis gry ma statystyki tylko biezacego sezonu, wiec historia powstaje z migawek: przy kazdym
wczytaniu zapisu kariery zapisujemy jeden wiersz na zawodnika (UID) do pliku
~/.fm_moneyball/historia/<menedzer>/<RRRR-MM-DD>.csv.gz (data w grze). Kariera to menedzer, a nie
klub - po zmianie klubu (np. Tottenham -> Barcelona) historia jest dalej jedna. W obrebie miesiaca zostaje
najnowsza migawka. Zapisujemy surowe dane (statystyki /90, minuty, wartosc), a nie SCORE, wiec
po zmianie wag historia przelicza sie sama.

Rozwoj = porownanie z ostatnia migawka z poprzedniego sezonu (sezon od 1 lipca). Wskazniki licza
sie tylko dla zawodnikow z co najmniej MIN_MINUT minutami w obu sezonach.
"""
import re
import shutil
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from fm_moneyball.mapy import KATALOG_DOMOWY
from fm_moneyball.stale import CECHY, KOLUMNY_STATYSTYK

KATALOG_HISTORII = KATALOG_DOMOWY / "historia"
MIN_MINUT = 1000             # prog minut w obu okresach, od ktorego liczymy rozwoj
KARIERA_BEZ_MENEDZERA = "kariera"   # katalog, gdy zapis nie podaje menedzera
POLA_MIGAWKI = ['ID', 'UID', 'Piłkarz', 'Wiek', 'Klub', 'Klub_UID', 'Liga', 'Mnożnik_Ligi', 'Pozycja', 'Pule',
                'Minuty', 'Wartość_Numeryczna', 'Zarobki_Numeryczne', 'Wygasa_Data', 'Średnia ocena']
KOLUMNY_ROZWOJU = ['Δ SCORE', 'Δ percentyl', 'Δ minut', 'Nowe pozycje', 'Δ_mała_próba']

_pamiec = {}                 # sciezka -> (mtime, ramka)


def sezon(data):
    """Sezon (rok rozpoczecia): od 1 lipca. 15.01.2027 -> 2026, 1.08.2027 -> 2027."""
    return data.year if data.month >= 7 else data.year - 1


def katalog_kariery(katalog, menedzer):
    """
    Katalog historii kariery. Kariera = menedzer z zapisu (nie klub, ktory prowadzi), wiec zapisy
    sprzed i po zmianie klubu laduja w jednym miejscu. Bez menedzera - wspolny katalog.
    """
    if katalog is None:
        return None
    nazwa = re.sub(r"[^\w-]+", "_", str(menedzer), flags=re.UNICODE).strip("_") if menedzer else ""
    return Path(katalog) / (f"m_{nazwa}" if nazwa else KARIERA_BEZ_MENEDZERA)


_STARY_KATALOG = re.compile(r"^\d+_")    # dawny klucz kariery: <uid klubu>_<nazwa klubu>


def przenies_stare(katalog, cel):
    """
    Jednorazowa migracja: migawki z dawnych katalogow klubowych trafiaja do katalogu kariery
    (przy tej samej dacie zostaje nowszy plik, potem zasada "jedna migawka na miesiac").
    """
    if katalog is None or cel is None or not Path(katalog).is_dir():
        return
    cel = Path(cel)
    for stary in Path(katalog).iterdir():
        if not stary.is_dir() or not _STARY_KATALOG.match(stary.name) or stary == cel:
            continue
        cel.mkdir(parents=True, exist_ok=True)
        for plik, _ in migawki(stary):
            docelowy = cel / plik.name
            if not docelowy.exists() or plik.stat().st_mtime > docelowy.stat().st_mtime:
                shutil.move(str(plik), docelowy)
            else:
                plik.unlink()
        shutil.rmtree(stary, ignore_errors=True)
    # zasada "jedna migawka na miesiac" po polaczeniu katalogow (zostaje najpozniejsza data)
    najnowsza = {}
    for plik, dzien in migawki(cel):
        klucz = (dzien.year, dzien.month)
        if klucz in najnowsza:
            najnowsza[klucz].unlink(missing_ok=True)
        najnowsza[klucz] = plik


def zapisz_migawke(katalog, dane, data_gry):
    """
    Ramki pozycji z zapisu -> plik migawki (jeden wiersz na UID). Starsze migawki z tego samego
    miesiaca sa usuwane. Zwraca sciezke albo None (brak danych lub daty).
    """
    ramki = [df for df in dane.values() if df is not None and not df.empty]
    if katalog is None or data_gry is None or not ramki:
        return None
    wszyscy = pd.concat(ramki, ignore_index=True)
    if 'UID' not in wszyscy.columns:
        return None
    wszyscy = wszyscy.drop_duplicates('UID')
    statystyki = [c for c in dict.fromkeys(KOLUMNY_STATYSTYK + list(CECHY)) if c in wszyscy.columns]
    kolumny = [c for c in POLA_MIGAWKI if c in wszyscy.columns] + statystyki
    katalog = Path(katalog)
    katalog.mkdir(parents=True, exist_ok=True)
    sciezka = katalog / f"{data_gry.isoformat()}.csv.gz"
    wszyscy[kolumny].to_csv(sciezka, index=False, compression="gzip")
    for inna, dzien in migawki(katalog):
        if inna != sciezka and (dzien.year, dzien.month) == (data_gry.year, data_gry.month):
            inna.unlink(missing_ok=True)
    return sciezka


def migawki(katalog):
    """[(sciezka, data)] migawek kariery, od najstarszej."""
    if katalog is None or not Path(katalog).is_dir():
        return []
    wynik = []
    for plik in Path(katalog).glob("*.csv.gz"):
        try:
            wynik.append((plik, date.fromisoformat(plik.name[:10])))
        except ValueError:
            continue
    return sorted(wynik, key=lambda x: x[1])


def wczytaj(sciezka):
    """Migawka z dysku (pamiec podreczna po czasie modyfikacji pliku)."""
    sciezka = Path(sciezka)
    mtime = sciezka.stat().st_mtime
    zapamietana = _pamiec.get(sciezka)
    if zapamietana and zapamietana[0] == mtime:
        return zapamietana[1]
    df = pd.read_csv(sciezka, compression="gzip")
    if 'Wygasa_Data' in df.columns:
        df['Wygasa_Data'] = pd.to_datetime(df['Wygasa_Data'], errors="coerce")
    _pamiec[sciezka] = (mtime, df)
    return df


def migawka_porownania(lista, data_gry):
    """Ostatnia migawka z wczesniejszego sezonu (najlepiej poprzedniego) albo None."""
    if data_gry is None:
        return None
    biezacy = sezon(data_gry)
    wczesniejsze = [(s, d) for s, d in lista if sezon(d) < biezacy]
    return wczesniejsze[-1] if wczesniejsze else None


def pula_migawki(df, pozycja):
    """Zawodnicy migawki, ktorzy mieli dana pozycje."""
    if 'Pule' not in df.columns:
        return df.iloc[0:0]
    maska = df['Pule'].fillna("").astype(str).str.split("; ").map(lambda pule: pozycja in pule)
    return df[maska].reset_index(drop=True)


def dolicz_rozwoj(teraz, wtedy, min_minut=MIN_MINUT, wymagaj_minut=False):
    """
    Pula biezaca (z SCORE) + policzona pula migawki z poprzedniego sezonu -> kopia z kolumnami
    rozwoju (KOLUMNY_ROZWOJU). Para zawodnikow po UID i nazwisku. Zmiany sa liczone takze przy malej
    liczbie minut; 'Δ_mała_próba' = ponizej min_minut w ktoryms sezonie (wynik mniej pewny).
    wymagaj_minut=True: bez progu minut w obu okresach wskazniki sa puste (np. listy w profilu druzyny).
    """
    teraz = teraz.copy()
    for kol in KOLUMNY_ROZWOJU:
        teraz[kol] = None if kol == 'Nowe pozycje' else False if kol == 'Δ_mała_próba' else np.nan
    if wtedy is None or wtedy.empty or 'UID' not in teraz.columns or 'UID' not in wtedy.columns:
        return teraz
    poprzednie = wtedy.drop_duplicates('UID').set_index('UID')
    uid = teraz['UID']
    znany = uid.isin(poprzednie.index)
    if not znany.any():
        return teraz
    p = poprzednie.reindex(uid)
    p.index = teraz.index
    ten_sam = znany & (p['Piłkarz'].astype(str) == teraz['Piłkarz'].astype(str))
    minuty = (pd.to_numeric(teraz['Minuty'], errors="coerce").fillna(0) >= min_minut) & \
        (pd.to_numeric(p['Minuty'], errors="coerce").fillna(0) >= min_minut)
    ok = ten_sam & minuty if wymagaj_minut else ten_sam
    teraz['Δ SCORE'] = (teraz['SCORE'] - p['SCORE']).where(ok)
    teraz['Δ_mała_próba'] = teraz['Δ SCORE'].notna() & ~minuty
    teraz['Δ percentyl'] = (teraz['Percentyl'] - p['Percentyl']).where(ok)
    teraz['Δ minut'] = (teraz['Minuty'] - p['Minuty']).where(ok)
    teraz['Nowe pozycje'] = [
        ", ".join(s for s in str(t or "").split(", ") if s and s not in str(w or "").split(", ")) or None
        if czy else None
        for t, w, czy in zip(teraz['Pozycja'], p['Pozycja'], ten_sam)]
    return teraz
