"""Aktualizacje z GitHub Releases i pamiec interfejsu (bez sieci)."""
import json

import pytest

from fm_moneyball import __version__, aktualizacje
from fm_moneyball.aktualizacje import Aktualizacje, nowsza, opis_wydania, wersja_krotka
from fm_moneyball.pamiec import Pamiec

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from fm_moneyball.serwer.api import utworz_aplikacje  # noqa: E402
from fm_moneyball.serwer.stan import Stan  # noqa: E402


def _wydanie(tag):
    return {"tag_name": tag, "body": "Nowe wykresy", "html_url": "https://example/wydanie",
            "assets": [{"name": "FM26Moneyball-Setup.exe", "browser_download_url": "https://example/setup.exe",
                        "size": 60 * 2**20},
                       {"name": "FM26Moneyball-Setup.exe.sha256", "browser_download_url": "https://example/sha"}]}


def test_porownanie_wersji():
    assert wersja_krotka("v1.10.2") == (1, 10, 2) and wersja_krotka("2") == (2, 0, 0)
    assert wersja_krotka("brak") is None
    assert nowsza("v1.10.0", "1.9.9") and not nowsza("1.0.0", "1.0.0") and not nowsza("0.9", "1.0")
    assert not nowsza("najnowsza", "1.0.0")      # stare ruchome wydanie bez numeru


def test_opis_wydania():
    w = opis_wydania(_wydanie("v9.1.0"))
    assert w["wersja"] == "9.1.0" and w["instalator"] == "https://example/setup.exe"
    assert w["suma"] == "https://example/sha" and w["rozmiar"] == 60 * 2**20
    assert opis_wydania({"tag_name": "v9", "assets": []})["instalator"] is None


def test_stan_aktualizacji_i_brak_sieci(monkeypatch):
    a = Aktualizacje(pobierz_json=lambda adres: _wydanie("v99.0.0"))
    a.sprawdz()
    s = a.stan()
    assert s["dostepna"] and s["wersja"] == "99.0.0" and s["wersja_programu"] == __version__
    assert s["mozna_instalowac"] is False          # nie .exe z instalatora - tylko link do strony
    assert a.instaluj() is False

    def bez_sieci(adres):
        raise OSError("brak sieci")
    b = Aktualizacje(pobierz_json=bez_sieci)
    assert b.sprawdz() is None and b.stan()["sprawdzono"] and not b.stan()["dostepna"]
    c = Aktualizacje(pobierz_json=lambda adres: _wydanie(f"v{__version__}"))
    c.sprawdz()
    assert not c.stan()["dostepna"]


def test_pobieranie_z_suma(tmp_path, monkeypatch):
    zrodlo = tmp_path / "setup.exe"
    zrodlo.write_bytes(b"x" * 300_000)
    procenty = []
    skrot = aktualizacje.pobierz(zrodlo.as_uri(), tmp_path / "kopia.exe", procenty.append)
    import hashlib
    assert skrot == hashlib.sha256(b"x" * 300_000).hexdigest()
    assert (tmp_path / "kopia.exe").read_bytes() == zrodlo.read_bytes()


def test_pamiec_zapis_atomowy_i_uszkodzony_plik(tmp_path):
    plik = tmp_path / "pamiec.json"
    p = Pamiec(plik)
    p.ustaw({"fm-lista-zyczen": '[{"klucz": "1"}]', "fm-filtry": "{}"})
    p.ustaw({"fm-filtry": None})
    assert json.loads(plik.read_text(encoding="utf-8")) == {"fm-lista-zyczen": '[{"klucz": "1"}]'}
    assert Pamiec(plik).wszystko() == {"fm-lista-zyczen": '[{"klucz": "1"}]'}
    plik.write_text("{zepsute", encoding="utf-8")
    assert Pamiec(plik).wszystko() == {}
    assert (tmp_path / "pamiec.uszkodzony.json").read_text(encoding="utf-8") == "{zepsute"


def test_trasy_systemu(tmp_path):
    stan = Stan(plik_ustawien=tmp_path / "u.json", sledzenie=False, katalog_cache=tmp_path / "c",
                katalog_historii=tmp_path / "h")
    a = Aktualizacje(pobierz_json=lambda adres: _wydanie("v99.0.0"))
    a.sprawdz()
    app = utworz_aplikacje(stan, pamiec=Pamiec(tmp_path / "pamiec.json"), aktualizacje=a,
                           okno={"okno": True, "port": 8765})
    with TestClient(app) as k:
        s = k.get("/api/system").json()
        assert s["okno"] and s["dostepna"] and s["wersja"] == "99.0.0"
        assert k.post("/api/aktualizacja/instaluj").status_code == 409
        assert k.get("/api/pamiec").json() == {}
        assert k.put("/api/pamiec", json={"zmiany": {"fm-pozycja": '"Bramkarz"'}}).json() == {"liczba": 1}
        assert k.get("/api/pamiec").json() == {"fm-pozycja": '"Bramkarz"'}
    assert json.loads((tmp_path / "pamiec.json").read_text(encoding="utf-8")) == {"fm-pozycja": '"Bramkarz"'}
