import os
from pathlib import Path

from fm_moneyball.zrodla import folder


def _plik(sciezka, tresc, mtime):
    sciezka.write_bytes(tresc)
    os.utime(sciezka, (mtime, mtime))
    return sciezka


def test_lista_zapisow_od_najnowszego(tmp_path):
    _plik(tmp_path / "stary.fm", b"a", 1_000)
    _plik(tmp_path / "nowy.fm", b"bb", 2_000)
    _plik(tmp_path / "notatka.txt", b"x", 3_000)
    pliki = folder.lista_zapisow(tmp_path)
    assert [p.nazwa for p in pliki] == ["nowy.fm", "stary.fm"]
    assert folder.najnowszy_zapis(tmp_path).rozmiar == 2
    assert folder.lista_zapisow(tmp_path / "brak") == []


def test_bezpieczna_kopia_raz_na_stan_i_sprzatanie(tmp_path):
    zrodlo, kopie = tmp_path / "games", tmp_path / "kopie"
    zrodlo.mkdir()
    sciezka = _plik(zrodlo / "kariera.fm", b"stan1", 1_000)
    k1 = folder.bezpieczna_kopia(folder.najnowszy_zapis(zrodlo), kopie)
    assert k1.read_bytes() == b"stan1"
    assert folder.bezpieczna_kopia(folder.najnowszy_zapis(zrodlo), kopie) == k1
    for i, t in enumerate((2_000, 3_000, 4_000)):
        _plik(sciezka, f"stan{i + 2}".encode(), t)
        ostatnia = folder.bezpieczna_kopia(folder.najnowszy_zapis(zrodlo), kopie)
    assert ostatnia.read_bytes() == b"stan4"
    assert len(list(kopie.glob("*.fm"))) == 2


def test_czy_stabilny(tmp_path):
    sciezka = _plik(tmp_path / "a.fm", b"x", 1_000)
    assert folder.czy_stabilny(sciezka, odstep=0.01)
    assert not folder.czy_stabilny(tmp_path / "brak.fm", odstep=0.01)


def test_kandydaci_folderow():
    win = folder.kandydaci_folderow(home="C:/Users/jan", platforma="win32",
                                    srodowisko={"USERPROFILE": "C:/Users/jan", "OneDrive": "C:/Users/jan/OneDrive"})
    assert win[0] == Path("C:/Users/jan/OneDrive/Documents/Sports Interactive/Football Manager 26/games")
    assert Path("C:/Users/jan/Documents/Sports Interactive/Football Manager 26/games") in win
    mac = folder.kandydaci_folderow(home="/Users/jan", platforma="darwin", srodowisko={})
    assert mac == [Path("/Users/jan/Library/Application Support/Sports Interactive/Football Manager 26/games")]
    linux = folder.kandydaci_folderow(home="/home/deck", platforma="linux", srodowisko={})
    assert any("compatdata/3551340" in str(p) for p in linux)


def test_domyslny_folder_istniejacy(tmp_path):
    gry = tmp_path / "Library" / "Application Support" / folder.PODFOLDER_GRY
    gry.mkdir(parents=True)
    assert folder.domyslny_folder(home=tmp_path, platforma="darwin", srodowisko={}) == gry
