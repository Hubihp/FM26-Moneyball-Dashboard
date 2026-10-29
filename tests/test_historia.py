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
    kat = historia.katalog_kariery(tmp_path, "Jan Kowalski")
    assert kat.name == "m_Jan_Kowalski" and historia.katalog_kariery(tmp_path, None).name == "kariera"
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
    assert wynik.loc[0, 'Δ SCORE'] == 8 and wynik.loc[0, 'Δ minut'] == 500
    assert 'Δ wartości' not in wynik.columns and 'Rozwój vs wiek' not in wynik.columns
    assert wynik.loc[0, 'Nowe pozycje'] == "PS"
    # mala proba: zmiana liczona, ale oznaczona (teraz 900 minut, wtedy 999 minut)
    assert wynik.loc[1, 'Δ SCORE'] == 5 and wynik.loc[1, 'Δ_mała_próba']
    assert wynik.loc[2, 'Δ SCORE'] == 1 and wynik.loc[2, 'Δ_mała_próba']
    assert not wynik.loc[0, 'Δ_mała_próba']
    assert np.isnan(wynik.loc[3, 'Δ SCORE']) and not wynik.loc[3, 'Δ_mała_próba']   # inne nazwisko
    scisle = historia.dolicz_rozwoj(teraz, wtedy, wymagaj_minut=True)                 # np. listy w profilu
    assert scisle.loc[0, 'Δ SCORE'] == 8 and scisle[['Δ SCORE']].iloc[1:].isna().all().all()
    assert historia.dolicz_rozwoj(teraz, None)['Δ SCORE'].isna().all()


def test_zmiana_liczona_na_cechach_wspolnych_z_migawka():
    """Starsza migawka nie ma cech dodanych w nowej wersji: Δ SCORE z SCORE liczonego na wspolnych cechach."""
    from fm_moneyball.serwer.obliczenia import wynik_na_wspolnych_cechach
    teraz = _ramka([1, 2, 3]).assign(Minuty=[2000, 2000, 2000], Pozycja=["N"] * 3,
                                     **{"Przechwyty/90": [1.0, 2.0, 3.0], "Kartki/90": [0.9, 0.1, 0.5]})
    from fm_moneyball.analiza import policz_wynik
    wtedy, _ = policz_wynik(_ramka([1, 2, 3]).assign(Minuty=[2000] * 3, **{"Przechwyty/90": [1.0, 2.0, 3.0]}),
                            {"Przechwyty/90": 50}, True, 0)
    wagi = {"Przechwyty/90": 50, "Kartki/90": 50}
    porownywalna = wynik_na_wspolnych_cechach(teraz, wagi, wtedy, True, 0)
    assert porownywalna is not None
    teraz = teraz.assign(SCORE=[30.0, 70.0, 50.0], Percentyl=[33.0, 100, 67])    # pelny SCORE z kartkami
    wynik = historia.dolicz_rozwoj(teraz, wtedy, teraz_porownywalna=porownywalna)
    # te same przechwyty co w migawce -> brak zmiany, mimo innego pelnego SCORE
    assert wynik['Δ SCORE'].abs().max() < 1e-6
    assert wynik_na_wspolnych_cechach(teraz, {"Przechwyty/90": 50}, wtedy, True, 0) is None   # wszystkie cechy sa


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
                           nazwa_zapisu="Kariera", menedzer="Jan Kowalski")
    monkeypatch.setattr(modul, "wczytaj_zapis", atrapa)
    # migawka sprzed sezonu: ci sami zawodnicy, gole 2x mniejsze u pierwszej dziesiatki napastnikow
    poprzednie = dane()
    poprzednie["Napastnik"].loc[:9, 'Liczba goli na 90 min'] /= 2
    for df in poprzednie.values():
        df['Mnożnik_Ligi'] = 0.9
    kat = historia.katalog_kariery(tmp_path / "historia", "Jan Kowalski")
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
    assert "Δ SCORE" in [c["naglowek"] for c in wynik["kolumny"]]
    rozwoj = {w["ID"]: w["Δ SCORE"] for w in wynik["wiersze"]}
    assert all(v is not None for v in rozwoj.values())
    szybcy = k.post("/api/ranking", json={"pozycja": "Napastnik", "filtry": {"min_rozwoj": 3}}).json()["wiersze"]
    assert szybcy and all(w["Δ SCORE"] >= 3 for w in szybcy)
    poprawieni = {f"Demo N {i:03d}" for i in range(10)}
    assert {w["Piłkarz"] for w in szybcy} <= poprawieni | {"Demo N 000"}
    # karta: dwie migawki z SCORE
    hist = k.post("/api/historia", json={"pozycja": "Napastnik", "id": szybcy[0]["ID"]}).json()
    assert hist["brak"] == [] and all(p["mala_proba"] is False for p in hist["punkty"])
    assert hist["delta"]["wzgledem"] == "2026-05-01" and hist["delta"]["mala_proba"] is False
    assert hist["delta"]["wartosc"] == pytest.approx(hist["punkty"][1]["SCORE"] - hist["punkty"][0]["SCORE"])
    wielu = k.post("/api/historia-wielu", json={"pozycja": "Napastnik",
                                                "ids": [szybcy[0]["ID"], szybcy[1]["ID"], "nie ma"]}).json()
    assert [z["pilkarz"] for z in wielu["zawodnicy"]][:2] == [szybcy[0]["Piłkarz"], szybcy[1]["Piłkarz"]]
    assert len(wielu["zawodnicy"][1]["punkty"]) == 2 and wielu["zawodnicy"][2]["punkty"] == []
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
        assert "Δ SCORE" not in [c["naglowek"] for c in wynik["kolumny"]]
        assert k.post("/api/historia", json={"pozycja": "Napastnik", "id": "x"}).json()["punkty"] == []
    assert not (tmp_path / "historia").exists()


def test_historia_po_zmianie_klubu(tmp_path, monkeypatch):
    """Trzy zapisy jednego menedzera: dwa z Tottenhamem, trzeci z Barcelona (zgloszony blad)."""
    import fm_moneyball.serwer.stan as modul
    from fm_moneyball.zrodla.zapis_fm import WynikZapisu
    zapisy = [(date(2028, 3, 31), 1, "Tottenham"), (date(2030, 4, 17), 1, "Tottenham"), (date(2032, 3, 24), 2, "Barcelona")]
    biezacy = {}

    def atrapa(sciezka, opcje, nazwy=None, postep=None):
        dzien, klub_uid, klub = biezacy["zapis"]
        ramki, _ = modul._demo()
        for i, (p, df) in enumerate(ramki.items()):
            df['UID'] = range(1000 * i, 1000 * i + len(df))
            df['Pule'] = p
            df['Minuty'] = 2500.0
        return WynikZapisu(dane=ramki, data_gry=dzien, moj_klub=klub, moj_klub_uid=klub_uid, nazwa_zapisu=klub,
                           menedzer="Jan Kowalski", moje_kluby=[{"uid": klub_uid, "nazwa": klub}])
    monkeypatch.setattr(modul, "wczytaj_zapis", atrapa)
    # migawka zapisana przez poprzednia wersje (katalog po klubie) - ma trafic do wspolnej historii
    stary = tmp_path / "historia" / "1_Tottenham"
    historia.zapisz_migawke(stary, {"Napastnik": _ramka([1, 2])}, date(2027, 2, 1))
    for nr, zapis in enumerate(zapisy):
        biezacy["zapis"] = zapis
        plik = tmp_path / f"zapis{nr}.fm"
        plik.write_bytes(b"x" * (10 + nr))
        stan = Stan(plik_ustawien=tmp_path / "u.json", sledzenie=False, katalog_cache=None,
                    plik_nazw=tmp_path / "n.csv", plik_mnoznikow=tmp_path / "m.csv", plik_krajow=tmp_path / "k.csv",
                    katalog_historii=tmp_path / "historia")
        stan.ustaw_zrodlo("plik", plik=str(plik), w_tle=False)
        assert stan.migawka()["meta"]["moj_klub"] == zapis[2]        # moj klub z biezacego zapisu
    kat = historia.katalog_kariery(tmp_path / "historia", "Jan Kowalski")
    assert [d for _, d in historia.migawki(kat)] == [date(2027, 2, 1)] + [z[0] for z in zapisy]
    assert not stary.exists()
    with TestClient(utworz_aplikacje(stan)) as k:
        meta = k.get("/api/pozycja/Napastnik").json()
        assert meta["data_porownania"] == "2030-04-17"               # zapis z Tottenhamem
        wiersze = k.post("/api/ranking", json={"pozycja": "Napastnik"}).json()["wiersze"]
        assert all(w["Δ SCORE"] is not None for w in wiersze)
        hist = k.post("/api/historia", json={"pozycja": "Napastnik", "id": wiersze[0]["ID"]}).json()
        assert [p["data"] for p in hist["punkty"]][-3:] == ["2028-03-31", "2030-04-17", "2032-03-24"]


def test_mala_proba_w_historii(tmp_path):
    """Okresy ponizej 1000 minut sa w historii (z flaga), a delta ma oznaczenie malej proby."""
    from fm_moneyball.serwer.obliczenia import _zmiana_sezonowa
    punkty = [{"data": "2026-03-01", "sezon": 2025, "SCORE": 50.0, "Minuty": 600.0, "mala_proba": True},
              {"data": "2027-01-15", "sezon": 2026, "SCORE": 58.0, "Minuty": 2000.0, "mala_proba": False}]
    delta = _zmiana_sezonowa(punkty)
    assert delta["wartosc"] == 8 and delta["mala_proba"] is True and delta["wzgledem"] == "2026-03-01"
    assert _zmiana_sezonowa(punkty[1:]) is None
