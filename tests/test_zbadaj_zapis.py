"""Funkcje diagnostyczne skryptu narzedzia/zbadaj_zapis.py na sztucznych rekordach."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace as NS

import pytest

pytest.importorskip("fmsave")

_SCIEZKA = Path(__file__).resolve().parents[1] / "narzedzia" / "zbadaj_zapis.py"
_spec = importlib.util.spec_from_file_location("zbadaj_zapis", _SCIEZKA)
zbadaj = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(zbadaj)


def _wiersz(club_uid, team_id, slot=0, pozycja=1):
    return NS(club_uid=club_uid, team_id=team_id, team_slot=slot, position=pozycja, club_name=f"K{club_uid}")


def test_podejrzane_tabele_i_diagnoza_klubu():
    kluby = [NS(uid=i, name=f"Klub {i}", short_name=f"K{i}", nation_id=1 if i <= 10 else i, fa_nation_id=1,
                parent_club_name=None, teams=(NS(team_id=100 + i, slot=0, club_uid=i, is_affiliate=False),))
             for i in range(1, 16)]
    tabele = [NS(competition_id=5, rows=[_wiersz(i, 100 + i) for i in range(1, 11)]),           # liga krajowa
              NS(competition_id=6, rows=[_wiersz(i, 100 + i) for i in (1, 11, 12, 13, 14)])]  # mieszana
    nacja = {k.uid: k.nation_id for k in kluby}
    baza = {5: 50, 6: 60}
    liga_klubu = {1: NS(competition_id=5, database_id=50, nazwa="Liga"), 11: NS(competition_id=6, database_id=60, nazwa=None)}

    podejrzane = zbadaj.podejrzane_tabele(tabele, liga_klubu, nacja, baza, kluby)
    assert [p["competition_id"] for p in podejrzane] == [6]
    assert podejrzane[0]["przyklady"][0] == "Klub 1"

    opis = zbadaj.opisz_klub("Klub 1", kluby, tabele, liga_klubu, nacja, baza)[0]
    assert opis["wybrana_liga"]["database_id"] == 50
    assert {t["competition_id"] for t in opis["tabele"]} == {5, 6}
    assert zbadaj.opisz_klub("Nie ma", kluby, tabele, liga_klubu, nacja, baza)["blad"]


def test_porownanie_lig_terminarz_vs_tabele():
    from fm_moneyball.zrodla.zapis_fm import KandydatLigi
    kluby = [NS(uid=i, name=f"Klub {i}", nation_id=1) for i in (1, 2, 3)]
    z_terminarza = {1: [KandydatLigi(30, 500, 5, 1)], 2: [KandydatLigi(30, 500, 5, 1)]}
    z_tabel = {1: [KandydatLigi(20, 500, 5, 1)], 2: [KandydatLigi(12, 901, 9, 1)], 3: [KandydatLigi(18, 600, 6, 1)]}
    wynik = zbadaj.porownaj_ligi(z_terminarza, z_tabel, kluby, {5: "Serie A"})
    assert wynik["liczniki"] == {"zgodne": 1, "rozne": 1, "tylko_tabele": 1}
    assert wynik["przyklady"] == [{"klub": "Klub 2", "rodzaj": "rozne", "tabele": "Rozgrywki #9",
                                   "terminarz": "Serie A", "mecze": 30}]
