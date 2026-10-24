"""Dopasowanie do rol FM26 (IP/OOP) i zakladka "Moja taktyka"."""
import numpy as np
import pandas as pd
import pytest

from fm_moneyball import role

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from fm_moneyball.serwer.api import utworz_aplikacje  # noqa: E402
from fm_moneyball.serwer.stan import Stan  # noqa: E402


def _pula(atrybuty, minuty=0, **statystyki):
    wiersz = {role.KOLUMNA_ATRYBUTU.format(a): atrybuty.get(a, 1) for a in role.ATRYBUTY_PL}
    return pd.DataFrame([{**wiersz, 'Minuty': minuty, **statystyki}])


def test_wynik_atrybutow_skrajne_i_wagi():
    pressing = role.znajdz_role("CM", "OOP", "Pressing Central Midfielder")
    assert role.dopasuj(_pula({a: 20 for a in role.ATRYBUTY_PL}), pressing).iloc[0] == 100
    assert role.dopasuj(_pula({}), pressing).iloc[0] == 0
    # same kluczowe na 20, dodatkowe na 1: 5 kluczowych x2 / (5x2 + 3x1)
    kluczowe = {role._Z_POLSKIEJ[n]: 20 for n in pressing["kluczowe"]}
    assert role.dopasuj(_pula(kluczowe), pressing).iloc[0] == pytest.approx(10 / 13 * 100, abs=0.1)


def test_statystyki_wazone_minutami():
    rola = role.znajdz_role("ST", "IP", "Poacher")
    srednie = {a: 10 for a in role.ATRYBUTY_PL}
    pula = pd.concat([_pula(srednie, minuty=m, **{'Oczekiwane gole bez karnych/90': x})
                      for m, x in ((0, 1.0), (2000, 1.0), (2000, 0.1))], ignore_index=True)
    wynik = role.dopasuj(pula, rola)
    atrybuty = role.wynik_atrybutow(pula, rola).iloc[0]
    assert wynik.iloc[0] == pytest.approx(atrybuty, abs=0.1)      # 0 minut: same atrybuty
    assert wynik.iloc[1] > atrybuty > wynik.iloc[2]                # najlepszy / najslabszy w puli


def test_bez_atrybutow_brak_kolumn():
    pula = pd.DataFrame({'Piłkarz': ['A'], 'Minuty': [900]})
    assert role.dopasowania(pula, "Napastnik").equals(pula)


def test_role_pozycji_bez_powtorzen():
    skrzydlowy = role.role_pozycji("Skrzydłowy")
    nazwy = [r["nazwa"] for r in skrzydlowy["IP"]]
    assert len(nazwy) == len(set(nazwy)) and "Inside Forward" in nazwy and "Wide Midfielder" in nazwy


# --- API na atrapie zapisu z atrybutami i taktyka ---------------------------------------------------
TAKTYKA = {"klub_uid": None, "indeks": 0, "nazwa": "4-3-3 Barca", "mentalnosc": "POSITIVE",
           "miejsca": [{"nr": 0, "ip_pozycje": [0], "oop_pozycje": [0], "ip_rola": 1, "oop_rola": 2},
                       {"nr": 1, "ip_pozycje": [3, 20], "oop_pozycje": [3], "ip_rola": 4, "oop_rola": 7}]}


@pytest.fixture()
def klient_zapisu(tmp_path, monkeypatch):
    import fm_moneyball.serwer.stan as modul
    from fm_moneyball.zrodla.zapis_fm import WynikZapisu
    plik = tmp_path / "kariera.fm"
    plik.write_bytes(b"x" * 10)

    def atrapa(sciezka, opcje, nazwy=None, postep=None):
        dane, _ = modul._demo()
        rng = np.random.default_rng(1)
        for df in dane.values():
            for a in role.ATRYBUTY_PL:
                df[role.KOLUMNA_ATRYBUTU.format(a)] = rng.integers(1, 21, len(df))
            df['UID'] = df['ID']
        return WynikZapisu(dane=dane, moj_klub="Premier FC 1", moj_klub_uid=1000, nazwa_zapisu="Kariera",
                           taktyki=[{**TAKTYKA, "klub_uid": 1000}])
    monkeypatch.setattr(modul, "wczytaj_zapis", atrapa)
    stan = Stan(plik_ustawien=tmp_path / "u.json", sledzenie=False, katalog_cache=tmp_path / "cache",
                plik_nazw=tmp_path / "n.csv", plik_mnoznikow=tmp_path / "m.csv", plik_krajow=tmp_path / "k.csv",
                plik_kalibracji=tmp_path / "role_taktyki.json")
    stan.ustaw_zrodlo("plik", plik=str(plik), w_tle=False)
    with TestClient(utworz_aplikacje(stan)) as k:
        yield k


def test_ranking_ma_najlepsze_role_i_filtr_roli(klient_zapisu):
    meta = klient_zapisu.get("/api/pozycja/Środkowy Pomocnik").json()
    assert meta["ma_atrybuty"] and {r["nazwa"] for r in meta["role"]["OOP"]} >= {"Pressing Central Midfielder"}
    wynik = klient_zapisu.post("/api/ranking", json={"pozycja": "Środkowy Pomocnik"}).json()
    pola = [k["pole"] for k in wynik["kolumny"]]
    assert {"Rola IP", "Dopasowanie IP", "Rola OOP", "Dopasowanie OOP"} <= set(pola)
    w = wynik["wiersze"][0]
    assert w["Dopasowanie OOP"] == max(v for k, v in w.items() if k.startswith("Rola|OOP|"))

    kol = "Rola|OOP|Pressing Central Midfielder"
    filtr = {"rola": "OOP|Pressing Central Midfielder", "min_dopasowania": 50}
    wynik = klient_zapisu.post("/api/ranking", json={"pozycja": "Środkowy Pomocnik", "filtry": filtr}).json()
    assert wynik["kolumny"][1]["pole"] == kol and wynik["kolumny"][1]["sortuj"] is True
    wartosci = [w[kol] for w in wynik["wiersze"]]
    assert wartosci and min(wartosci) >= 50 and wartosci == sorted(wartosci, reverse=True)


def test_demo_bez_kolumn_rol(tmp_path):
    stan = Stan(plik_ustawien=tmp_path / "u.json", sledzenie=False, katalog_cache=None,
                plik_kalibracji=tmp_path / "r.json")
    stan.ustaw_zrodlo("demo", w_tle=False)
    with TestClient(utworz_aplikacje(stan)) as k:
        wynik = k.post("/api/ranking", json={"pozycja": "Napastnik"}).json()
        assert "Rola IP" not in [c["pole"] for c in wynik["kolumny"]]
        assert k.get("/api/taktyka").json()["taktyki"] == []


def test_taktyka_kalibracja_i_ranking(klient_zapisu, tmp_path):
    t = klient_zapisu.get("/api/taktyka").json()
    assert t["taktyki"][0]["nazwa"] == "4-3-3 Barca" and len(t["miejsca"]) == 2
    miejsce = t["miejsca"][1]
    assert miejsce["IP"]["grupa"] is None and miejsce["zawodnicy"] == []
    assert miejsce["IP"]["klucz_pozycji"] == "3,20"

    put = lambda **b: klient_zapisu.put("/api/taktyka/kalibracja", json=b)  # noqa: E731
    assert put(rodzaj="pozycja", klucz="3,20", wartosc="XX").status_code == 400
    assert put(rodzaj="pozycja", klucz="3,20", wartosc="CM").status_code == 200
    assert put(rodzaj="pozycja", klucz="3", wartosc="CM").status_code == 200
    assert put(rodzaj="rola", klucz="IP|CM|4", wartosc="Poacher").status_code == 400   # rola innej pozycji
    assert put(rodzaj="rola", klucz="IP|CM|4", wartosc="Midfield Playmaker").status_code == 200
    assert put(rodzaj="rola", klucz="OOP|CM|7", wartosc="Pressing Central Midfielder").status_code == 200

    miejsce = klient_zapisu.get("/api/taktyka").json()["miejsca"][1]
    assert miejsce["IP"]["rola"] == "Midfield Playmaker" and miejsce["OOP"]["rola"] == "Pressing Central Midfielder"
    zawodnicy = miejsce["zawodnicy"]
    assert zawodnicy and any(z["moj"] for z in zawodnicy) and any(not z["moj"] for z in zawodnicy)
    razem = [z["razem"] for z in zawodnicy]
    assert razem == sorted(razem, reverse=True)
    assert all(z["razem"] == pytest.approx((z["ip"] + z["oop"]) / 2, abs=0.1) for z in zawodnicy)
    # usuniecie kalibracji
    assert put(rodzaj="rola", klucz="IP|CM|4").status_code == 200
    assert klient_zapisu.get("/api/taktyka").json()["miejsca"][1]["IP"]["rola"] is None
