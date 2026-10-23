"""API serwera na danych demo (bez prawdziwego zapisu)."""
import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from fm_moneyball.serwer.api import utworz_aplikacje  # noqa: E402
from fm_moneyball.serwer.stan import Stan  # noqa: E402


@pytest.fixture()
def klient(tmp_path):
    stan = Stan(plik_ustawien=tmp_path / "ustawienia.json", sledzenie=False)
    stan.ustaw_zrodlo("demo", w_tle=False)
    with TestClient(utworz_aplikacje(stan)) as k:
        yield k


def test_stan_po_wczytaniu_demo(klient):
    stan = klient.get("/api/stan").json()
    assert stan["status"] == "gotowe" and stan["wersja"] == 1
    assert stan["pozycje"]["Napastnik"] == 150
    assert stan["meta"]["demo"] is True


def test_meta_pozycji(klient):
    meta = klient.get("/api/pozycja/Napastnik").json()
    assert meta["liczba"] == 150 and "Premier League (ANG 1)" in meta["ligi"]
    assert meta["wagi_domyslne"]["Liczba goli na 90 min"] == 20
    assert klient.get("/api/pozycja/Nieznana").status_code == 404


def test_ranking_filtry_i_kolumny(klient):
    wszystko = klient.post("/api/ranking", json={"pozycja": "Napastnik"}).json()
    assert wszystko["liczba"] == wszystko["liczba_wszystkich"] == 150
    wyniki = [w["SCORE"] for w in wszystko["wiersze"]]
    assert wyniki == sorted(wyniki, reverse=True)
    pola = {k["naglowek"]: k for k in wszystko["kolumny"]}
    assert pola["Cena"]["pole"] == "Wartość_Numeryczna" and pola["Cena"]["format"] == "eur"
    assert pola["Liczba goli na 90 min"]["statystyka"] is True

    filtr = {"pozycja": "Napastnik", "filtry": {"ligi": ["Ekstraklasa (POL 1)"], "wiek": [18, 25],
                                                 "cena": [0, 5_000_000], "bez_ceny": False}}
    czesc = klient.post("/api/ranking", json=filtr).json()
    assert 0 < czesc["liczba"] < 150
    for w in czesc["wiersze"]:
        assert w["Liga"] == "Ekstraklasa (POL 1)" and 18 <= w["Wiek"] <= 25
        assert w["Wartość_Numeryczna"] is not None and w["Wartość_Numeryczna"] <= 5_000_000


def test_wagi_zmieniaja_ranking(klient):
    tylko_drybling = klient.post("/api/ranking", json={
        "pozycja": "Napastnik", "wagi": {"Liczba dryblingów/90": 100}, "k_baza": 0,
        "ignoruj_mnoznik": True}).json()["wiersze"]
    najlepszy = max(tylko_drybling, key=lambda w: w["Liczba dryblingów/90"] or 0)
    # z-score jest obcinany do +-3, wiec skrajni zawodnicy moga remisowac na szczycie
    assert tylko_drybling[0]["SCORE"] == pytest.approx(najlepszy["SCORE"])
    assert tylko_drybling[-1]["Liczba dryblingów/90"] <= tylko_drybling[0]["Liczba dryblingów/90"]


def test_kontrakty_wygasajace(klient):
    # demo ma kontrakty do 30.6.2027-2031; bez daty w grze liczymy od dzis
    wynik = klient.post("/api/ranking", json={"pozycja": "Bramkarz", "filtry": {"kontrakt_mies": 1}}).json()
    assert wynik["liczba"] <= 150


def test_radar_i_podobni(klient):
    wiersze = klient.post("/api/ranking", json={"pozycja": "Skrzydłowy"}).json()["wiersze"]
    ids = [wiersze[0]["ID"], wiersze[1]["ID"]]
    radar = klient.post("/api/radar", json={"pozycja": "Skrzydłowy", "ids": ids}).json()
    assert len(radar["seria"]) == 2 and len(radar["etykiety"]) == len(radar["seria"][0]["percentyle"])
    assert all(0 <= p <= 100 for p in radar["seria"][0]["percentyle"])
    podobni = klient.post("/api/podobni", json={"pozycja": "Skrzydłowy", "id": ids[0], "n": 5}).json()["wiersze"]
    assert len(podobni) == 5 and ids[0] not in [p["ID"] for p in podobni]
    assert podobni[0]["Podobieństwo"] >= podobni[-1]["Podobieństwo"]


def test_zrodlo_folder_bez_zapisow(klient, tmp_path):
    stan = klient.post("/api/zrodlo", json={"typ": "folder", "folder": str(tmp_path)}).json()
    assert stan["zrodlo"]["typ"] == "folder"
    zapisy = klient.get("/api/zapisy", params={"folder": str(tmp_path)}).json()
    assert zapisy["pliki"] == []


def test_wgraj_odrzuca_inne_pliki(klient):
    odp = klient.post("/api/wgraj", files={"plik": ("notatka.txt", b"x")})
    assert odp.status_code == 400


def test_ustawienia_sa_zapamietywane(tmp_path):
    plik = tmp_path / "ustawienia.json"
    Stan(plik_ustawien=plik, sledzenie=False).ustaw_zrodlo("demo", w_tle=False)
    assert Stan(plik_ustawien=plik, sledzenie=False).konfig.typ == "demo"


def test_serwuje_zbudowany_frontend(klient):
    from fm_moneyball.serwer.api import KATALOG_STATIC
    if not (KATALOG_STATIC / "index.html").is_file():
        pytest.skip("frontend nie jest zbudowany")
    for sciezka in ("/", "/ranking/cokolwiek"):
        odp = klient.get(sciezka)
        assert odp.status_code == 200 and "<div id=\"root\">" in odp.text
