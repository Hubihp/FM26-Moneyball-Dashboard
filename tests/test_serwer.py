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
                plik_nazw=tmp_path / "nazwy.csv", plik_mnoznikow=tmp_path / "mnozniki.csv",
                plik_krajow=tmp_path / "kraje.csv", **kw)


def test_stan_po_wczytaniu_demo(klient):
    stan = klient.get("/api/stan").json()
    assert stan["status"] == "gotowe" and stan["wersja"] == 1
    assert stan["pozycje"]["Napastnik"] == 150
    assert stan["meta"]["demo"] is True


def test_meta_pozycji(klient):
    meta = klient.get("/api/pozycja/Napastnik").json()
    assert meta["liczba"] == 150
    wiersze = klient.post("/api/ranking", json={"pozycja": "Napastnik"}).json()["wiersze"]
    assert "Premier League (ANG 1)" in {w["Liga"] for w in wiersze}
    assert meta["wagi_domyslne"]["Liczba goli na 90 min"] == 20
    assert klient.get("/api/pozycja/Nieznana").status_code == 404
    # filtr pensji (tygodniowej) przez API: wszyscy widoczni maja pensje w zakresie albo brak pensji
    assert meta["pensja_max"] > 0
    prog = meta["pensja_max"] / 4
    nap = klient.post("/api/ranking", json={"pozycja": "Napastnik", "filtry": {"pensja": [prog, None], "min_minut": 0}}).json()
    wszyscy = klient.post("/api/ranking", json={"pozycja": "Napastnik", "filtry": {"min_minut": 0}}).json()
    assert 0 < len(nap["wiersze"]) < len(wszyscy["wiersze"])


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
    wiersze = klient.post("/api/ranking", json={"pozycja": "Prawy Skrzydłowy"}).json()["wiersze"]
    ids = [wiersze[0]["ID"], wiersze[1]["ID"]]
    radar = klient.post("/api/radar", json={"pozycja": "Prawy Skrzydłowy", "ids": ids}).json()
    assert radar["seria"][0]["pilkarz"] == wiersze[0]["Piłkarz"]
    assert len(radar["seria"]) == 2 and len(radar["etykiety"]) == len(radar["seria"][0]["percentyle"])
    assert all(0 <= p <= 100 for p in radar["seria"][0]["percentyle"])
    podobni = klient.post("/api/podobni", json={"pozycja": "Prawy Skrzydłowy", "id": ids[0], "n": 5}).json()["wiersze"]
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
                           ligi=[{"klucz": 999011, "domyslna": "Rozgrywki #999011", "nazwa": None, "liczba": 20,
                                  "kluby": ["A", "B"], "kraj": 9005}])
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
        df['Liga_klucz'] = 999011
        df['Liga_domyslna'] = "Rozgrywki #999011"
    with TestClient(utworz_aplikacje(stan)) as k:
        ligi = k.get("/api/ligi").json()
        assert ligi["ligi"][0]["klucz"] == 999011 and ligi["ligi"][0]["nazwa"] is None
        assert "Premier League" in ligi["znane_nazwy"]
        odp = k.put("/api/ligi/999011", json={"nazwa": "Liga Testowa", "mnoznik": 0.7}).json()
        assert odp["ligi"][0]["nazwa"] == "Liga Testowa" and odp["ligi"][0]["mnoznik"] == 0.7
        assert k.put("/api/ligi/999", json={"nazwa": "X"}).status_code == 404
        wiersze = k.post("/api/ranking", json={"pozycja": "Napastnik"}).json()["wiersze"]
        assert {w["Liga"] for w in wiersze} == {"Liga Testowa"}
    assert "Liga Testowa" in (tmp_path / "nazwy.csv").read_text(encoding="utf-8")
    assert "0.7" in (tmp_path / "mnozniki.csv").read_text(encoding="utf-8")


def test_moj_klub_i_moja_kadra(klient):
    stan = klient.get("/api/stan").json()
    uid = stan["meta"]["moj_klub_uid"]
    assert stan["meta"]["moj_klub"] == "Premier FC 1"
    kadra = klient.post("/api/moja-kadra", json={}).json()
    assert kadra["klub"] == "Premier FC 1" and kadra["pozycje"]
    # od bramkarza do napastnika
    from fm_moneyball.stale import POZYCJE
    kolejnosc = [POZYCJE.index(p["pozycja"]) for p in kadra["pozycje"]]
    assert kolejnosc == sorted(kolejnosc)
    for p in kadra["pozycje"]:
        assert all(z["Klub_UID"] == uid for z in p["zawodnicy"])
    bez = klient.post("/api/ranking", json={"pozycja": "Napastnik",
                                             "filtry": {"bez_mojego_klubu": True}}).json()["wiersze"]
    assert all(w["Klub_UID"] != uid for w in bez)
    assert klient.post("/api/moj-klub", json={"uid": uid}).json()["meta"]["moj_klub_uid"] == uid


def test_ranking_ma_kolumny_moneyball(klient):
    wynik = klient.post("/api/ranking", json={"pozycja": "Napastnik"}).json()
    naglowki = [k["naglowek"] for k in wynik["kolumny"]]
    assert "Koszt (3 lata)" in naglowki
    assert "Opłacalność" not in naglowki and "Wiarygodność" not in naglowki
    assert any(w["Pareto"] for w in wynik["wiersze"])
    assert all("Opłacalność" not in w for w in wynik["wiersze"])


def test_serwuje_zbudowany_frontend(klient):
    from fm_moneyball.serwer.api import KATALOG_STATIC
    if not (KATALOG_STATIC / "index.html").is_file():
        pytest.skip("frontend nie jest zbudowany")
    for sciezka in ("/", "/ranking/cokolwiek"):
        odp = klient.get(sciezka)
        assert odp.status_code == 200 and "<div id=\"root\">" in odp.text


def test_nowe_pozycje_w_demo(klient):
    stan = klient.get("/api/stan").json()
    from fm_moneyball.stale import POZYCJE
    assert list(stan["pozycje"]) == POZYCJE and all(n == 150 for n in stan["pozycje"].values())
    # pozycja zawiera tylko zawodnikow, ktorzy ja maja (PS, a nie wszyscy skrzydlowi)
    ps = klient.post("/api/ranking", json={"pozycja": "Prawy Skrzydłowy"}).json()["wiersze"]
    assert ps and all("PS" in w["Pozycja"].split(", ") for w in ps)
    meta = klient.get("/api/pozycja/Ofensywny Pomocnik").json()
    assert meta["wagi_domyslne"]["Oczekiwane asysty/90"] == 25
    # cechy tylko z zapisu (100% sytuacje) sa pomijane w danych CSV/demo
    assert "Stworzone 100% sytuacje/90" not in meta["wagi_domyslne"]


def test_narodowosc_w_tabeli_i_filtr(klient):
    meta = klient.get("/api/pozycja/Napastnik").json()
    assert "kraje" not in meta and "ligi" not in meta    # listy krajow i lig sa w zakladce "Ligi i kraje"
    wynik = klient.post("/api/ranking", json={"pozycja": "Napastnik", "filtry": {"kraje": ["Polska"]}}).json()
    assert 0 < wynik["liczba"] < 150 and all(w["Kraj"] == "Polska" for w in wynik["wiersze"])
    assert {"naglowek": "Narodowość", "pole": "Kraj"}.items() <= next(
        k for k in wynik["kolumny"] if k["pole"] == "Kraj").items()


def test_kraje_w_demo_z_kolumny_kraj(klient):
    kraje = klient.get("/api/kraje").json()["kraje"]
    assert kraje and all(k["id"] is None and k["nazwa"] for k in kraje)
    liczby = [k["liczba"] for k in kraje]
    assert liczby == sorted(liczby, reverse=True) and "Polska" in {k["nazwa"] for k in kraje}


def test_lista_zyczen_po_id(klient):
    wiersze = klient.post("/api/ranking", json={"pozycja": "Napastnik"}).json()["wiersze"]
    wpisy = [{"klucz": wiersze[3]["ID"], "pozycja": "Napastnik", "pilkarz": wiersze[3]["Piłkarz"]},
             {"klucz": "nie ma takiego", "pozycja": "Bramkarz"},
             {"klucz": "x", "pozycja": "Nieznana"}]
    lista = klient.post("/api/lista-zyczen", json={"wpisy": wpisy}).json()
    assert [w["ID"] for w in lista["wiersze"]] == [wiersze[3]["ID"]]
    assert lista["wiersze"][0]["Pozycja na liście"] == "Napastnik"
    assert lista["wiersze"][0]["SCORE"] == pytest.approx(wiersze[3]["SCORE"])
    assert lista["nieznalezieni"] == ["nie ma takiego", "x"]
    assert "Narodowość" in [k["naglowek"] for k in lista["kolumny"]]
    pusta = klient.post("/api/lista-zyczen", json={"wpisy": []}).json()
    assert pusta["wiersze"] == [] and pusta["nieznalezieni"] == []


def test_lista_zyczen_po_uid_i_kraje(tmp_path, monkeypatch):
    plik = _sztuczny_zapis(tmp_path, monkeypatch, [])
    stan = _stan(tmp_path)
    stan.ustaw_zrodlo("plik", plik=str(plik), w_tle=False)
    for p, df in stan.surowe.items():      # atrapa zapisu: UID i narodowosc jak z fmsave
        df['UID'] = range(len(df))
        df['Kraj_ID'] = [9005 if i % 2 else 9006 for i in range(len(df))]
    stan.zastosuj_ligi()
    with TestClient(utworz_aplikacje(stan)) as k:
        nap = stan.pula("Napastnik").iloc[7]
        lista = k.post("/api/lista-zyczen", json={"wpisy": [
            {"klucz": str(nap["UID"]), "pozycja": "Napastnik", "pilkarz": nap["Piłkarz"]},
            {"klucz": str(nap["UID"]), "pozycja": "Napastnik", "pilkarz": "Ktoś inny"}]}).json()
        assert [w["UID"] for w in lista["wiersze"]] == [int(nap["UID"])]
        assert lista["nieznalezieni"] == [str(nap["UID"])]

        kraje = k.get("/api/kraje").json()["kraje"]
        assert {kr["id"] for kr in kraje} == {9005, 9006} and all(kr["nazwa"] is None for kr in kraje)
        assert stan.pula("Napastnik")["Kraj"].iloc[1] == "Kraj #9005"
        kraje = k.put("/api/kraje/9005", json={"nazwa": "Ghana"}).json()["kraje"]
        assert next(kr for kr in kraje if kr["id"] == 9005)["nazwa"] == "Ghana"
        assert stan.pula("Napastnik")["Kraj"].iloc[1] == "Ghana"
        # liga z nazwa nadaje nazwe krajowi (kraj 5 z atrapy ligi)
        k.put("/api/ligi/999011", json={"nazwa": "K League 1"})
        kraje = {kr["id"]: kr["nazwa"] for kr in k.get("/api/kraje").json()["kraje"]}
        assert kraje[9005] == "Ghana"           # reczna nazwa wygrywa z automatyczna
    assert "Ghana" in (tmp_path / "kraje.csv").read_text(encoding="utf-8")


def test_kandydaci_do_przekwalifikowania(klient):
    zwykly = klient.post("/api/ranking", json={"pozycja": "Prawy Obrońca"}).json()
    z_kandydatami = klient.post("/api/ranking", json={
        "pozycja": "Prawy Obrońca", "filtry": {"kandydaci": True, "min_score_kandydata": 55}}).json()
    assert z_kandydatami["pozycja"] == "Prawy Obrońca"
    nominalni = {w["ID"]: w["SCORE"] for w in z_kandydatami["wiersze"] if not w["Kandydat"]}
    kandydaci = [w for w in z_kandydatami["wiersze"] if w["Kandydat"]]
    # kandydaci nie zmieniaja wyniku zawodnikow pozycji
    assert nominalni == pytest.approx({w["ID"]: w["SCORE"] for w in zwykly["wiersze"]})
    assert kandydaci and all(w["SCORE"] >= 55 for w in kandydaci)
    assert z_kandydatami["liczba_wszystkich"] == 150 and z_kandydatami["liczba_kandydatow"] == len(kandydaci)
    from fm_moneyball.stale import POZYCJE
    assert {w["Kandydat z pozycji"] for w in kandydaci} <= set(POZYCJE) - {"Bramkarz", "Prawy Obrońca"}
    assert "Kandydat z pozycji" in [k["naglowek"] for k in z_kandydatami["kolumny"]]
    assert all(0 <= w["Percentyl"] <= 100 for w in kandydaci)
    # radar i podobni dla kandydata
    kid = kandydaci[0]["ID"]
    radar = klient.post("/api/radar", json={"pozycja": "Prawy Obrońca", "ids": [kid], "kandydaci": True}).json()
    assert radar["seria"][0]["id"] == kid
    podobni = klient.post("/api/podobni", json={"pozycja": "Prawy Obrońca", "id": kid, "n": 3,
                                                "filtry": {"kandydaci": True}}).json()["wiersze"]
    assert len(podobni) == 3
    # bramkarz nie ma kandydatow z pola
    gk = klient.post("/api/ranking", json={"pozycja": "Bramkarz", "filtry": {"kandydaci": True,
                                                                             "min_score_kandydata": 0}}).json()
    assert not any(w["Kandydat"] for w in gk["wiersze"])
    # kandydaci tylko z wybranych pozycji
    wybrane = klient.post("/api/ranking", json={"pozycja": "Prawy Obrońca", "filtry": {
        "kandydaci": True, "min_score_kandydata": 0, "kandydaci_z": ["Lewy Obrońca", "Prawy Wahadłowy"]}}).json()
    zrodla = {w["Kandydat z pozycji"] for w in wybrane["wiersze"] if w["Kandydat"]}
    assert zrodla == {"Lewy Obrońca", "Prawy Wahadłowy"}


def test_lista_zyczen_kandydat_i_stara_pozycja(klient):
    # zawodnik dodany jako kandydat z innej pozycji (blad: "Nie znaleziono")
    wiersze = klient.post("/api/ranking", json={"pozycja": "Prawy Skrzydłowy", "filtry": {
        "kandydaci": True, "min_score_kandydata": 0}}).json()["wiersze"]
    kandydat = next(w for w in wiersze if w["Kandydat"])
    stary = klient.post("/api/ranking", json={"pozycja": "Lewy Obrońca"}).json()["wiersze"][0]
    lista = klient.post("/api/lista-zyczen", json={"wpisy": [
        {"klucz": kandydat["ID"], "pozycja": "Prawy Skrzydłowy", "pilkarz": kandydat["Piłkarz"]},
        {"klucz": stary["ID"], "pozycja": "Boczny Obrońca", "pilkarz": stary["Piłkarz"]}]}).json()
    assert lista["nieznalezieni"] == []
    pozycje = {w["ID"]: w["Pozycja na liście"] for w in lista["wiersze"]}
    assert pozycje == {kandydat["ID"]: "Prawy Skrzydłowy", stary["ID"]: "Lewy Obrońca"}


def test_index_bez_cache(klient):
    from fm_moneyball.serwer.api import KATALOG_STATIC
    if not (KATALOG_STATIC / "index.html").is_file():
        pytest.skip("frontend nie jest zbudowany")
    assert klient.get("/").headers["cache-control"] == "no-cache"
    zasob = next((KATALOG_STATIC / "assets").glob("*.js")).name
    assert "immutable" in klient.get(f"/assets/{zasob}").headers["cache-control"]


def test_migracja_ustawien_naturalne_pozycje(tmp_path):
    import json
    plik = tmp_path / "ustawienia.json"
    plik.write_text(json.dumps({"typ": "demo", "opcje": {"wszystkie_naturalne_pozycje": False}}), encoding="utf-8")
    stan = _stan(tmp_path)
    assert stan.konfig.opcje["wszystkie_naturalne_pozycje"] is True and stan.konfig.wersja_ustawien == 2
    # po migracji wybor uzytkownika jest szanowany
    stan.ustaw_zrodlo("demo", opcje={"wszystkie_naturalne_pozycje": False}, w_tle=False)
    assert _stan(tmp_path).konfig.opcje["wszystkie_naturalne_pozycje"] is False


def test_wycena_wg_wyniku_w_rankingu(klient):
    wynik = klient.post("/api/ranking", json={"pozycja": "Napastnik"}).json()
    naglowki = [k["naglowek"] for k in wynik["kolumny"]]
    assert "Wycena wg wyniku" in naglowki and "Niedowartościowanie" in naglowki
    assert 0 <= wynik["model_wyceny"]["r2"] <= 1 and wynik["model_wyceny"]["liczba"] > 40
    tanie = klient.post("/api/ranking", json={"pozycja": "Napastnik",
                                               "filtry": {"min_niedowartosciowanie": 2}}).json()["wiersze"]
    assert tanie and all(w["Niedowartościowanie"] >= 2 for w in tanie)
    assert "niedowartościowany" in klient.get("/api/pozycja/Napastnik").json()["okazje"]


def test_okazje_spojne_z_tabela(klient):
    """Znacznik okazji w tabeli i filtr tej okazji daja ten sam zbior zawodnikow (kazda pozycja, kazda okazja)."""
    from fm_moneyball.stale import POZYCJE
    okazje = klient.get("/api/pozycja/Napastnik").json()["okazje"]
    for pozycja in POZYCJE:
        wszyscy = klient.post("/api/ranking", json={"pozycja": pozycja}).json()["wiersze"]
        for okazja in okazje:
            ze_znacznikiem = {w["ID"] for w in wszyscy if okazja in (w["Okazje"] or "").split("; ")}
            z_filtrem = klient.post("/api/ranking", json={"pozycja": pozycja, "filtry": {"okazje": [okazja]}}).json()
            assert {w["ID"] for w in z_filtrem["wiersze"]} == ze_znacznikiem, (pozycja, okazja)
        z_jakakolwiek = klient.post("/api/ranking", json={"pozycja": pozycja,
                                                          "filtry": {"tylko_z_okazja": True}}).json()["wiersze"]
        assert {w["ID"] for w in z_jakakolwiek} == {w["ID"] for w in wszyscy if w["Okazje"]}


def test_ukryci_zawodnicy_mojego_klubu(klient):
    uid = klient.get("/api/stan").json()["meta"]["moj_klub_uid"]
    wszyscy = klient.post("/api/ranking", json={"pozycja": "Napastnik"}).json()
    moi = [w for w in wszyscy["wiersze"] if w["Klub_UID"] == uid]
    bez = klient.post("/api/ranking", json={"pozycja": "Napastnik", "filtry": {"bez_mojego_klubu": True}}).json()
    assert moi and bez["liczba_ukrytych_mojego_klubu"] == len(moi)
    assert bez["liczba"] == wszyscy["liczba"] - len(moi)


def test_porownanie_z_moim_api(klient):
    uid = klient.get("/api/stan").json()["meta"]["moj_klub_uid"]
    wiersze = klient.post("/api/ranking", json={"pozycja": "Napastnik", "filtry": {"min_minut": 0}}).json()["wiersze"]
    obcy = next(w for w in wiersze if w["Klub_UID"] != uid)
    wynik = klient.post("/api/porownanie-z-moim", json={"pozycja": "Napastnik", "id": obcy["ID"]}).json()
    assert wynik["moj"]["SCORE"] == max(w["SCORE"] for w in wiersze if w["Klub_UID"] == uid)
    assert wynik["werdykt"] in {"wzmocnienie", "podobny poziom", "nie wzmacnia"}
    assert wynik["roznica"] == pytest.approx(obcy["SCORE"] - wynik["moj"]["SCORE"])
    assert {c["nazwa"] for c in wynik["cechy"]} == set(klient.get("/api/pozycja/Napastnik").json()["wagi_domyslne"])
    moj = next(w for w in wiersze if w["Klub_UID"] == uid)
    assert klient.post("/api/porownanie-z-moim", json={"pozycja": "Napastnik", "id": moj["ID"]}).json()["werdykt"] \
        == "twój zawodnik"
    assert klient.post("/api/porownanie-z-moim", json={"pozycja": "Napastnik", "id": "nie ma"}).status_code == 404


def test_nastepca(klient):
    uid = klient.get("/api/stan").json()["meta"]["moj_klub_uid"]
    kadra = klient.post("/api/moja-kadra", json={}).json()
    moj = next(z for p in kadra["pozycje"] if p["pozycja"] == "Napastnik" for z in p["zawodnicy"])
    filtry = {"min_minut": 1000, "wiek": [18, 25]}
    wynik = klient.post("/api/nastepca", json={"pozycja": "Napastnik", "id": moj["ID"], "filtry": filtry}).json()
    w = wynik["wiersze"]
    assert 0 < len(w) <= 15 and wynik["kolumny"][1]["pole"] == "Podobieństwo" and wynik["kolumny"][1]["sortuj"]
    assert all(x["Klub_UID"] != uid and x["Minuty"] >= 1000 and 18 <= x["Wiek"] <= 25 for x in w)
    podobienstwa = [x["Podobieństwo"] for x in w]
    assert podobienstwa == sorted(podobienstwa, reverse=True) and all(0 <= p <= 100 for p in podobienstwa)
    # tez zawodnicy z innych pozycji (kandydaci)
    szersze = klient.post("/api/nastepca", json={"pozycja": "Napastnik", "id": moj["ID"], "n": 60}).json()["wiersze"]
    assert any(x["Kandydat"] for x in szersze)
    assert klient.post("/api/nastepca", json={"pozycja": "Napastnik", "id": "nie ma"}).status_code == 404


def test_lista_zyczen_kolumny_jak_ranking(klient):
    nap = klient.post("/api/ranking", json={"pozycja": "Napastnik"}).json()
    bo = klient.post("/api/ranking", json={"pozycja": "Lewy Obrońca"}).json()["wiersze"][0]
    lista = klient.post("/api/lista-zyczen", json={"pozycja": "Napastnik", "wpisy": [
        {"klucz": nap["wiersze"][0]["ID"], "pozycja": "Napastnik"}, {"klucz": bo["ID"], "pozycja": "Lewy Obrońca"}]}).json()
    pola = [k["pole"] for k in lista["kolumny"]]
    oczekiwane = [k["pole"] for k in nap["kolumny"]]
    oczekiwane.insert(oczekiwane.index("Piłkarz") + 1, "Pozycja na liście")
    assert pola == oczekiwane
    assert {w["Pozycja na liście"] for w in lista["wiersze"]} == {"Napastnik", "Lewy Obrońca"}


def test_optymalizator_i_sprzedaj_drogo(klient):
    w = klient.post("/api/optymalizator", json={"budzet": 3e7, "budzet_plac": 1e5,
                                                "pozycje": ["Napastnik", "Prawy Skrzydłowy", "Środkowy Obrońca"],
                                                "filtry": {"min_minut": 0}}).json()
    assert w["wydane"] <= 3e7 and w["pensje"] <= 1e5 and w["optimum_pewne"]
    assert w["zysk"] == pytest.approx(sum(z["zysk"] for z in w["zestaw"]))
    for z in w["zestaw"]:
        assert z["zawodnik"]["SCORE"] == pytest.approx(z["moj_score"] + z["zysk"])
        assert z["zawodnik"]["Klub_UID"] != klient.get("/api/stan").json()["meta"]["moj_klub_uid"]
    if w["jedna_gwiazda"]:
        assert w["zysk"] >= w["jedna_gwiazda"]["zysk"]
    s = klient.post("/api/sprzedaj-drogo", json={"filtry": {"min_minut": 0}}).json()
    assert "wymiany" in s and s["podobienstwo"] == 0.85
    for x in s["wymiany"]:
        assert (x["zastepca"] is None and x["zysk"] is None) or (x["zysk"] > 0 and x["zastepca"]["Podobieństwo"] >= 0.85)


def test_profil_druzyny_demo(klient):
    p = klient.post("/api/profil-druzyny", json={}).json()
    assert p["klub"] and not p["z_zapisu"] and p["kluby"] >= 2
    nazwy = [s["nazwa"] for s in p["sekcje"]]
    assert "Z piłką" in nazwy and "Bez piłki" in nazwy
    for s in p["sekcje"]:
        for m in s["metryki"]:
            assert 1 <= m["miejsce"] <= m["n"] == p["kluby"]
    assert p["atletyzm"] is None                      # demo nie ma dystansu i sprintow
    assert p["zmiany"]["historia"] is False


def test_sklad_i_tylko_pierwsza(klient):
    s = klient.post("/api/sklad", json={}).json()
    assert s["zawodnicy"] and set(s["pozycje"]) >= {"Bramkarz", "Napastnik"}
    for z in s["zawodnicy"]:
        assert z["score"] and set(z["score"]) <= set(s["pozycje"]) and set(z["id_w_pulach"]) >= set(z["score"])
    k1 = klient.post("/api/moja-kadra", json={}).json()
    k2 = klient.post("/api/moja-kadra", json={"tylko_pierwsza": False}).json()
    assert [p["liczba"] for p in k1["pozycje"]] == [p["liczba"] for p in k2["pozycje"]]   # demo: bez rezerw
    assert all(p["ukryci"] == 0 for p in k1["pozycje"])


def test_zawodnik_ponizej_progu_i_sredni_score(klient):
    wiersze = klient.post("/api/ranking", json={"pozycja": "Napastnik", "filtry": {"min_minut": 0}}).json()["wiersze"]
    malo = min(wiersze, key=lambda w: w["Minuty"])
    w = klient.post("/api/zawodnik", json={"pozycja": "Napastnik", "id": malo["ID"]}).json()
    assert w["ID"] == malo["ID"] and w["SCORE"] == pytest.approx(malo["SCORE"])
    assert klient.post("/api/zawodnik", json={"pozycja": "Napastnik", "id": "nie ma"}).status_code == 404
    for p in klient.post("/api/moja-kadra", json={}).json()["pozycje"]:
        if p["zawodnicy"]:
            assert p["sredni_score"] == pytest.approx(sum(z["SCORE"] for z in p["zawodnicy"]) / len(p["zawodnicy"]))


def test_pula_migawki_z_wagami_domyslnymi(tmp_path):
    # regresja: profil druzyny przy migawce z poprzedniego sezonu i domyslnych wagach (wagi None) dawal blad 500
    from fm_moneyball.serwer.obliczenia import Obliczenia
    stan = _stan(tmp_path)
    stan.ustaw_zrodlo("demo", w_tle=False)
    df = stan.pula("Napastnik").assign(UID=lambda d: range(len(d)), Pule="Napastnik")
    sciezka = tmp_path / "2026-03-01.csv.gz"
    df.to_csv(sciezka, index=False, compression="gzip")
    wynik = Obliczenia(stan).pula_migawki(sciezka, "Napastnik", None, False, 5)
    assert wynik is not None and wynik['SCORE'].notna().any()
