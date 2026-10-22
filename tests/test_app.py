"""Test dymny interfejsu: aplikacja uruchamia sie i rysuje wyniki na danych demo."""
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parents[1] / "app.py")


def _uruchom(zrodlo, pozycja=None):
    at = AppTest.from_file(APP, default_timeout=60)
    at.run()
    at.radio(key="zrodlo").set_value(zrodlo).run()
    if pozycja:
        at.radio(key="pozycja").set_value(pozycja).run()
    return at


def test_bez_danych_pokazuje_instrukcje():
    at = _uruchom("Pliki CSV")
    assert not at.exception
    assert any("Brak danych" in i.value for i in at.info)


@pytest.mark.parametrize("pozycja", ["Bramkarz", "Napastnik"])
def test_demo(pozycja):
    at = _uruchom("Dane demo", pozycja)
    assert not at.exception, at.exception
    assert len(at.dataframe) >= 1
    assert not at.error


def test_wyczysc_filtry_bez_ostrzezen():
    at = _uruchom("Dane demo")
    at.button(key="btn_clear_Bramkarz").click().run()
    assert not at.exception
    assert not any("Session State" in w.value for w in at.warning)


def test_folder_bez_zapisow():
    at = AppTest.from_file(APP, default_timeout=60)
    at.session_state["folder_zapisow"] = "/nie/ma/takiego/folderu"
    at.run()
    assert not at.exception
    assert any("Nie znaleziono plików .fm" in w.value for w in at.warning)


def test_folder_z_uszkodzonym_zapisem(tmp_path):
    (tmp_path / "zepsuty.fm").write_bytes(b"to nie jest zapis FM")
    at = AppTest.from_file(APP, default_timeout=60)
    at.session_state["folder_zapisow"] = str(tmp_path)
    at.run()
    assert not at.exception
    assert any("Nie udało się odczytać zapisu" in e.value for e in at.error)
