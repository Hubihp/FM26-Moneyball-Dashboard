"""Historia zawodnikow: migawki kolejnych wczytan zapisu i wskazniki rozwoju."""
from datetime import date

import numpy as np
import pandas as pd
import pytest

from fm_moneyball import historia

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from fm_moneyball.serwer.api import utworz_aplikacje  # noqa: E402
from fm_moneyball.serwer.stan import Stan  # noqa: E402


def test_sezon_od_lipca():
    assert historia.sezon(date(2027, 1, 15)) == 2026
    assert historia.sezon(date(2027, 7, 1)) == 2027


def _ramka(uidy, minuty=2000, pule="Napastnik"):
    return pd.DataFrame({'ID': [f"G{u}" for u in uidy], 'UID': uidy, 'Piłkarz': [f"Gracz {u}" for u in uidy],
                         'Wiek': 22, 'Minuty': minuty, 'Pule': pule, 'Pozycja': "N", 'Wartość_Numeryczna': 1e6,
                         'Liczba goli na 90 min': 0.5})


def test_zapis_przycinanie_i_porownanie(tmp_path):
    kat = historia.katalog_kariery(tmp_path, 7, "FC Barcelona")
    assert kat.name == "7_FC_Barcelona"
    for dzien in (date(2026, 5, 1), date(2026, 5, 20), date(2026, 9, 3), date(2027, 1, 10)):
        historia.zapisz_migawke(kat, {"Napastnik": _ramka([1, 2, 2])}, dzien)
    lista = historia.migawki(kat)
    # w obrebie miesiaca zostaje najnowsza migawka
    assert [d for _, d in lista] == [date(2026, 5, 20), date(2026, 9, 3), date(2027, 1, 10)]
    df = historia.wczytaj(lista[0][0])
    assert list(df['UID']) == [1, 2]                     # jeden wiersz na zawodnika
    # porownanie: ostatnia migawka z wczesniejszego sezonu
    assert historia.migawka_porownania(lista, date(2027, 1, 10))[1] == date(2026, 5, 20)
    assert historia.migawka_porownania(lista, date(2027, 8, 1))[1] == date(2027, 1, 10)
    assert historia.migawka_porownania(lista[1:], date(2027, 1, 10)) is None


def test_dolicz_rozwoj_prog_minut_i_nazwisko():
    teraz = _ramka([1, 2, 3, 4]).assign(SCORE=[60.0, 55.0, 50.0, 70.0], Percentyl=[80.0, 60, 50, 95],
                                        Minuty=[2000, 900, 2000, 2000], Pozycja=["N, PS", "N", "N", "N"])
    teraz.loc[3, 'Piłkarz'] = "Ktoś inny"                # UID z innej kariery
    wtedy = _ramka([1, 2, 3, 4]).assign(SCORE=[52.0, 50.0, 49.0, 60.0], Percentyl=[60.0, 50, 49, 80],
                                        Minuty=[1500, 2000, 999, 2000], Wartość_Numeryczna=[5e5, 1e6, 1e6, 1e6])
    wynik = historia.dolicz_rozwoj(teraz, wtedy)
    assert wynik.loc[0, 'Δ SCORE'] == 8 and wynik.loc[0, 'Δ wartości'] == 100 and wynik.loc[0, 'Δ minut'] == 500
    assert wynik.loc[0, 'Nowe pozycje'] == "PS"
    assert np.isnan(wynik.loc[1, 'Δ SCORE'])            # teraz 900 minut < 1000
    assert np.isnan(wynik.loc[2, 'Δ SCORE'])            # wtedy 999 minut
    assert np.isnan(wynik.loc[3, 'Δ SCORE'])            # inne nazwisko
    assert historia.dolicz_rozwoj(teraz, None)['Δ SCORE'].isna().all()


@pytest.fixture()
def klient_z_historia(tmp_path, monkeypatch):
    """Atrapa zapisu kariery: migawka z poprzedniego sezonu ze slabszymi statystykami."""
    import fm_moneyball.serwer.stan as modul
    from fm_moneyball.zrodla.zapis_fm import WynikZapisu
    plik = tmp_path / "kariera.fm"
    plik.write_bytes(b"x" * 10)

    def dane():
        ramki, _ = modul._demo()
        for p, df in ramki.items():
            df['UID'] = range(len(df))
            df['UID'] += 1000 * list(ramki).index(p)
            df['Pule'] = p
            df['Minuty'] = 2500.0
        return ramki

    def atrapa(sciezka, opcje, nazwy=None, postep=None):
        return WynikZapisu(dane=dane(), data_gry=date(2027, 1, 15), moj_klub="Premier FC 1", moj_klub_uid=1000,
                           nazwa_zapisu="Kariera")
    monkeypatch.setattr(modul, "wczytaj_zapis", atrapa)
    # migawka sprzed sezonu: ci sami zawodnicy, gole 2x mniejsze u pierwszej dziesiatki napastnikow
    poprzednie = dane()
    poprzednie["Napastnik"].loc[:9, 'Liczba goli na 90 min'] /= 2
    for df in poprzednie.values():
        df['Mnożnik_Ligi'] = 0.9
    kat = historia.katalog_kariery(tmp_path / "historia", 1000, "Premier FC 1")
    historia.zapisz_migawke(kat, poprzednie, date(2026, 5, 1))
    stan = Stan(plik_ustawien=tmp_path / "u.json", sledzenie=False, katalog_cache=None, plik_nazw=tmp_path / "n.csv",
                plik_mnoznikow=tmp_path / "m.csv", plik_krajow=tmp_path / "k.csv",
                katalog_historii=tmp_path / "historia")
    stan.ustaw_zrodlo("plik", plik=str(plik), w_tle=False)
    with TestClient(utworz_aplikacje(stan)) as k:
        yield k, kat


def test_api_rozwoj_i_historia(klient_z_historia):
    k, kat = klient_z_historia
    # wczytanie zapisu dopisalo biezaca migawke
    assert [d for _, d in historia.migawki(kat)] == [date(2026, 5, 1), date(2027, 1, 15)]
    meta = k.get("/api/pozycja/Napastnik").json()
    assert meta["ma_historie"] and meta["data_porownania"] == "2026-05-01" and meta["min_minut_rozwoju"] == 1000
    wynik = k.post("/api/ranking", json={"pozycja": "Napastnik"}).json()
    assert "Δ SCORE (sezon)" in [c["naglowek"] for c in wynik["kolumny"]]
    rozwoj = {w["ID"]: w["Δ SCORE"] for w in wynik["wiersze"]}
    assert all(v is not None for v in rozwoj.values())
    szybcy = k.post("/api/ranking", json={"pozycja": "Napastnik", "filtry": {"min_rozwoj": 3}}).json()["wiersze"]
    assert szybcy and all(w["Δ SCORE"] >= 3 for w in szybcy)
    poprawieni = {f"Demo N {i:03d}" for i in range(10)}
    assert {w["Piłkarz"] for w in szybcy} <= poprawieni | {"Demo N 000"}
    # karta: dwie migawki z SCORE
    hist = k.post("/api/historia", json={"pozycja": "Napastnik", "id": szybcy[0]["ID"]}).json()
    assert [p["data"] for p in hist["punkty"]] == ["2026-05-01", "2027-01-15"]
    assert hist["punkty"][1]["SCORE"] > hist["punkty"][0]["SCORE"]
    assert "Liczba goli na 90 min" in hist["statystyki"] and hist["min_minut"] == 1000


def test_demo_bez_historii(tmp_path):
    stan = Stan(plik_ustawien=tmp_path / "u.json", sledzenie=False, katalog_cache=None,
                katalog_historii=tmp_path / "historia")
    stan.ustaw_zrodlo("demo", w_tle=False)
    with TestClient(utworz_aplikacje(stan)) as k:
        assert k.get("/api/pozycja/Napastnik").json()["ma_historie"] is False
        wynik = k.post("/api/ranking", json={"pozycja": "Napastnik"}).json()
        assert "Δ SCORE (sezon)" not in [c["naglowek"] for c in wynik["kolumny"]]
        assert k.post("/api/historia", json={"pozycja": "Napastnik", "id": "x"}).json()["punkty"] == []
    assert not (tmp_path / "historia").exists()
