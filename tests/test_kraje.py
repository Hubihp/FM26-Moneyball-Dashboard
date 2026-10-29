"""Narodowosci: nazwy z lig, reczne nazwy, kolumna Kraj i filtr."""
import pandas as pd

from fm_moneyball import analiza
from fm_moneyball.kraje import nazwy_auto, podsumuj_kraje, wczytaj_nazwy_krajow, zapisz_nazwe_kraju
from fm_moneyball.ligi import wszystkie_mnozniki, zapisz_mnoznik
from fm_moneyball.schemat import ustaw_kraje
from fm_moneyball.stale import MERYTORYKA_WAG, KOLUMNY_PER_POZYCJA, POZYCJE


def test_nazwy_krajow_z_lig():
    ligi = [{"nazwa": "Ekstraklasa", "kraj": 7}, {"nazwa": "I liga", "kraj": 7},
            {"nazwa": "K League 1", "kraj": 9}, {"nazwa": None, "kraj": 3},        # bez nazwy
            {"nazwa": "Liga Testowa", "kraj": 4}, {"nazwa": "Serie A", "kraj": None}]
    assert nazwy_auto(ligi) == {7: "Polska", 9: "Korea Płd."}


def test_kolumna_kraj_i_filtr():
    df = pd.DataFrame({"Piłkarz": ["A", "B", "C"], "Kraj_ID": [7, 3, None], "SCORE": [60, 50, 40]})
    df = ustaw_kraje(df, {7: "Polska"})
    assert list(df["Kraj"]) == ["Polska", "Kraj #3", "Nieznana"]
    widoczni = analiza.filtruj(df.assign(**{"Wartość_Numeryczna": 1.0}), analiza.Filtry(kraje=["Polska"]))
    assert list(widoczni["Piłkarz"]) == ["A"]
    # ramka bez Kraj_ID (CSV) - bez zmian
    csv = pd.DataFrame({"Kraj": ["Anglia", None, " "]})
    assert list(ustaw_kraje(csv, {})["Kraj"]) == ["Anglia", "Nieznana", "Nieznana"]


def test_reczne_nazwy_i_podsumowanie(tmp_path):
    uzytkownika, domyslny = tmp_path / "u.csv", tmp_path / "d.csv"
    zapisz_nazwe_kraju(3, "Szkocja", domyslny)
    zapisz_nazwe_kraju(3, "Szkocja (poprawiona)", uzytkownika)
    zapisz_nazwe_kraju(5, "Ghana", uzytkownika)
    assert wczytaj_nazwy_krajow(uzytkownika, domyslny) == {3: "Szkocja (poprawiona)", 5: "Ghana"}
    zapisz_nazwe_kraju(5, "", uzytkownika)        # pusta nazwa usuwa wpis
    assert 5 not in wczytaj_nazwy_krajow(uzytkownika, domyslny)

    zawodnicy = pd.DataFrame({"Piłkarz": ["A", "B", "C", "D"], "Klub": ["X", "Y", "Z", "X"],
                              "Kraj_ID": [7, 7, 3, 8], "Wartość_Numeryczna": [1e6, 5e6, 2e6, None]})
    kraje = podsumuj_kraje(zawodnicy, {7: "Polska"}, {7: "ręcznie"})
    assert [k["id"] for k in kraje] == [3, 8, 7]                 # bez nazwy najpierw
    polska = kraje[-1]
    assert polska["liczba"] == 2 and polska["reczna"] and polska["przyklady"] == ["B (Y)", "A (X)"]


def test_mnozniki_uzytkownika_nad_domyslnymi(tmp_path):
    uzytkownika, domyslny = tmp_path / "u.csv", tmp_path / "d.csv"
    zapisz_mnoznik("Liga Testowa", 0.7, domyslny)
    zapisz_mnoznik("Liga Testowa", 0.72, uzytkownika)
    mnozniki = wszystkie_mnozniki(uzytkownika, domyslny)
    assert mnozniki["Liga Testowa"] == 0.72 and mnozniki["Premier League"] == 0.918


def test_nowe_pozycje_maja_wagi_i_kolumny():
    assert len(POZYCJE) == 14
    assert MERYTORYKA_WAG["Lewy Skrzydłowy"] == MERYTORYKA_WAG["Prawy Skrzydłowy"]   # rodzina: Skrzydłowy
    assert MERYTORYKA_WAG["Lewy Pomocnik"] == MERYTORYKA_WAG["Prawy Pomocnik"]       # rodzina: Boczny Pomocnik
    assert MERYTORYKA_WAG["Lewy Pomocnik"] != MERYTORYKA_WAG["Lewy Skrzydłowy"]
    for pozycja in POZYCJE:
        wagi = MERYTORYKA_WAG[pozycja]
        assert sum(wagi.values()) == 100
        assert set(wagi) <= set(KOLUMNY_PER_POZYCJA[pozycja])


def test_kraje_z_klubow_kotwic():
    from types import SimpleNamespace as NS

    from fm_moneyball.kraje import klucz_nazwy_klubu, kraje_z_kotwic
    assert klucz_nazwy_klubu("FK Bodø/Glimt") == klucz_nazwy_klubu("Bodø/Glimt") == {"bodo", "glimt"}
    assert klucz_nazwy_klubu("AC Sparta Praha") == klucz_nazwy_klubu("Sparta Praha")
    kluby = [NS(uid=1, name="Hibernian FC"), NS(uid=2, name="Aberdeen"), NS(uid=3, name="AC Sparta Praha"),
             NS(uid=4, name="Motherwell"), NS(uid=5, name="Olimpia"), NS(uid=6, name="CD Olimpia")]

    def kadra(klub, kraje):
        return [NS(club_uid=klub, nation_id=k) for k in kraje]
    zawodnicy = (kadra(1, [30] * 8 + [5] * 4) + kadra(2, [30] * 9 + [6] * 3)     # dwa glosy na 30
                 + kadra(3, [40] * 10 + [7] * 2)                                    # jeden wyrazny glos (83%)
                 + kadra(4, [30] * 4 + [8] * 3)                                     # za malo zawodnikow
                 + kadra(5, [50] * 7 + [51] * 3) + kadra(6, [51] * 6 + [50] * 4))   # Paragwaj vs Honduras
    kotwice = {"Szkocja": ["Hibernian", "Aberdeen", "Motherwell"], "Czechy": ["Sparta Praha"],
               "Paragwaj": ["Olimpia"], "Honduras": ["Olimpia"]}
    wynik = kraje_z_kotwic(kluby, zawodnicy, kotwice)
    assert wynik[30] == "Szkocja" and wynik[40] == "Czechy"
    # "Olimpia" to dwa kluby (dwa kraje) - jeden glos na kraj ponizej progu 70%, wiec bez nazwy
    assert 50 not in wynik and 51 not in wynik


def test_domyslna_mapa_krajow():
    import csv

    from fm_moneyball.kraje import PLIK_KRAJOW
    with open(PLIK_KRAJOW, encoding="utf-8") as plik:
        wiersze = list(csv.reader(plik))[1:]
    ids = [int(w[0]) for w in wiersze]
    nazwy = [w[1].strip() for w in wiersze]
    assert len(ids) == len(set(ids)) and all(nazwy) and len(nazwy) == len(set(nazwy))
    mapa = dict(zip(ids, nazwy))
    assert mapa[33] == "Nigeria" and mapa[173] == "Turcja" and mapa[176] == "Serbia" and mapa[207] == "Montserrat"


def test_pliki_danych_sa_w_repozytorium():
    """Pliki dane/*.csv musza byc sledzone przez gita - inaczej nie trafia do uzytkownika (ZIP, git pull)."""
    import shutil
    import subprocess
    from pathlib import Path

    import pytest
    katalog = Path(__file__).resolve().parents[1]
    if not shutil.which("git") or not (katalog / ".git").exists():
        pytest.skip("brak repozytorium gita")
    for plik in (katalog / "dane").glob("*.csv"):
        wynik = subprocess.run(["git", "ls-files", "--error-unmatch", str(plik.relative_to(katalog))],
                               cwd=katalog, capture_output=True)
        assert wynik.returncode == 0, f"{plik.name} nie jest w repozytorium (sprawdz .gitignore)"
