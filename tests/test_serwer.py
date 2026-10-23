"""API serwera na danych demo (bez prawdziwego zapisu)."""
import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from fm_moneyball.serwer.api import utworz_aplikacje  # noqa: E402
from fm_moneyball.serwer.stan import Stan  # noqa: E402


@pytest.fixture()
def klient(tmp_path):
    stan = _stan(tmp_path)
    stan.ustaw_zrodlo("demo", w_tle=False)
    with TestClient(utworz_aplikacje(stan)) as k:
        yield k


def _stan(tmp_path, **kw):
    return Stan(plik_ustawien=tmp_path / "ustawienia.json", sledzenie=False, katalog_cache=tmp_path / "cache",
                plik_nazw=tmp_path / "nazwy.csv", plik_mnoznikow=tmp_path / "mnozniki.csv", **kw)


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
    odp = klient.post("/api/wgraj", params={"nazwa": "notatka.txt"}, content=b"x")
    assert odp.status_code == 400


def test_ustawienia_sa_zapamietywane_bez_wczytywania_przy_starcie(tmp_path):
    _stan(tmp_path).ustaw_zrodlo("demo", w_tle=False)
    drugi = _stan(tmp_path)
    assert drugi.konfig.typ == "demo"
    # zrodlo jest zapamietane, ale nic sie nie wczytuje, dopoki uzytkownik nie wybierze
    drugi._wczytaj()
    assert drugi.migawka()["status"] == "pusto" and drugi.dane == {}


def test_wczytaj_przy_starcie(tmp_path):
    _stan(tmp_path).ustaw_zrodlo("demo", w_tle=False, wczytaj_przy_starcie=True)
    drugi = _stan(tmp_path)
    assert drugi.aktywny
    drugi._wczytaj()
    assert drugi.migawka()["status"] == "gotowe"


def _sztuczny_zapis(tmp_path, monkeypatch, wywolania, przy_wczytaniu=None):
    """Podmienia wczytaj_zapis na szybka atrape zwracajaca dane demo."""
    import fm_moneyball.serwer.stan as modul
    from fm_moneyball.zrodla.zapis_fm import WynikZapisu
    plik = tmp_path / "kariera.fm"
    plik.write_bytes(b"x" * 10)

    def atrapa(sciezka, opcje, nazwy=None, postep=None):
        wywolania.append(sciezka)
        if postep:
            postep(0, "Otwieranie zapisu")
        if przy_wczytaniu:
            przy_wczytaniu()
        dane, _ = modul._demo()
        return WynikZapisu(dane=dane, moj_klub="Premier FC 1", moj_klub_uid=1000, nazwa_zapisu="Kariera",
                           ligi=[{"klucz": 11, "domyslna": "Rozgrywki #11", "nazwa": None, "liczba": 20,
                                  "kluby": ["A", "B"]}])
    monkeypatch.setattr(modul, "wczytaj_zapis", atrapa)
    return plik


def test_cache_drugi_odczyt_bez_parsowania(tmp_path, monkeypatch):
    wywolania = []
    plik = _sztuczny_zapis(tmp_path, monkeypatch, wywolania)
    _stan(tmp_path).ustaw_zrodlo("plik", plik=str(plik), w_tle=False)
    drugi = _stan(tmp_path)
    drugi.ustaw_zrodlo("plik", plik=str(plik), w_tle=False)
    assert len(wywolania) == 1
    m = drugi.migawka()
    assert m["status"] == "gotowe" and m["meta"]["z_cache"] is True
    assert m["meta"]["moj_klub"] == "Premier FC 1"


def test_zmiana_zrodla_w_trakcie_wczytywania(tmp_path, monkeypatch):
    wywolania = []
    stan = None

    def zmien_na_demo():
        if len(wywolania) == 1:          # tylko przy pierwszym odczycie
            stan.konfig.typ = "demo"
            stan.pokolenie += 1
    plik = _sztuczny_zapis(tmp_path, monkeypatch, wywolania, zmien_na_demo)
    stan = _stan(tmp_path)
    stan.ustaw_zrodlo("plik", plik=str(plik), w_tle=False)
    # wynik z pliku zostal odrzucony, a wczytane jest aktualne zrodlo (demo)
    assert stan.migawka()["meta"].get("demo") is True


def test_ligi_edycja_nazwy_i_mnoznika(tmp_path, monkeypatch):
    wywolania = []
    plik = _sztuczny_zapis(tmp_path, monkeypatch, wywolania)
    stan = _stan(tmp_path)
    stan.ustaw_zrodlo("plik", plik=str(plik), w_tle=False)
    for df in stan.surowe.values():      # atrapa: wszyscy w lidze o kluczu 11 bez nazwy
        df['Liga_klucz'] = 11
        df['Liga_domyslna'] = "Rozgrywki #11"
    with TestClient(utworz_aplikacje(stan)) as k:
        ligi = k.get("/api/ligi").json()
        assert ligi["ligi"][0]["klucz"] == 11 and ligi["ligi"][0]["nazwa"] is None
        assert "Premier League" in ligi["znane_nazwy"]
        odp = k.put("/api/ligi/11", json={"nazwa": "K League 1", "mnoznik": 0.7}).json()
        assert odp["ligi"][0]["nazwa"] == "K League 1" and odp["ligi"][0]["mnoznik"] == 0.7
        assert k.put("/api/ligi/999", json={"nazwa": "X"}).status_code == 404
        meta = k.get("/api/pozycja/Napastnik").json()
        assert meta["ligi"] == ["K League 1"]
    assert "K League 1" in (tmp_path / "nazwy.csv").read_text(encoding="utf-8")
    assert "0.7" in (tmp_path / "mnozniki.csv").read_text(encoding="utf-8")


def test_moj_klub_i_moja_kadra(klient):
    stan = klient.get("/api/stan").json()
    uid = stan["meta"]["moj_klub_uid"]
    assert stan["meta"]["moj_klub"] == "Premier FC 1"
    kadra = klient.post("/api/moja-kadra", json={}).json()
    assert kadra["klub"] == "Premier FC 1" and kadra["pozycje"]
    luki = [p["luka"] or 0 for p in kadra["pozycje"]]
    assert luki == sorted(luki, reverse=True)
    for p in kadra["pozycje"]:
        assert all(z["Klub_UID"] == uid for z in p["zawodnicy"])
    bez = klient.post("/api/ranking", json={"pozycja": "Napastnik",
                                             "filtry": {"bez_mojego_klubu": True}}).json()["wiersze"]
    assert all(w["Klub_UID"] != uid for w in bez)
    assert klient.post("/api/moj-klub", json={"uid": uid}).json()["meta"]["moj_klub_uid"] == uid


def test_ranking_ma_kolumny_moneyball(klient):
    wynik = klient.post("/api/ranking", json={"pozycja": "Napastnik"}).json()
    naglowki = [k["naglowek"] for k in wynik["kolumny"]]
    assert "Koszt (3 lata)" in naglowki and "Opłacalność" in naglowki
    assert any(w["Pareto"] for w in wynik["wiersze"])
    tylko = klient.post("/api/ranking", json={"pozycja": "Napastnik",
                                               "filtry": {"min_oplacalnosc": 1}}).json()["wiersze"]
    assert all(w["Opłacalność"] >= 1 for w in tylko)


def test_serwuje_zbudowany_frontend(klient):
    from fm_moneyball.serwer.api import KATALOG_STATIC
    if not (KATALOG_STATIC / "index.html").is_file():
        pytest.skip("frontend nie jest zbudowany")
    for sciezka in ("/", "/ranking/cokolwiek"):
        odp = klient.get(sciezka)
        assert odp.status_code == 200 and "<div id=\"root\">" in odp.text
