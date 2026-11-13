"""Taktyka z zapisu FM27: pozycje z bitow, formacja, rozstawienie srodkowych, wybor XI i rezerwowi."""
from types import SimpleNamespace as NS

from fm_moneyball.taktyka_gry import formacja, sloty_na_boisku, taktyki_klubu

# 4-2-3-1 jak w zapisie FM27 (numer slotu, bit z pilka, bit bez pilki, maska z flagami strony)
SLOTY_4231 = [(0, 0, 0, 0x1), (1, 2, 2, 0x4), (2, 4, 4, 0x200010), (3, 4, 4, 0x100010), (4, 3, 3, 0x8),
              (5, 7, 7, 0x100080), (6, 7, 7, 0x200080), (7, 11, 11, 0x800), (8, 13, 12, 0x2000),
              (9, 12, 13, 0x1000), (10, 14, 14, 0x4000)]


def test_formacja_z_bitow():
    assert formacja(s[1] for s in SLOTY_4231) == "4-2-3-1"
    assert formacja([0, 2, 4, 4, 3, 10, 10, 10, 11, 12, 14]) == "4-3-3"
    assert formacja([0, 5, 4, 4, 4, 6, 10, 10, 7, 14, 14]) == "5-1-2-2"


def test_srodkowi_rozstawieni_wg_flag_strony():
    sloty = {s["numer"]: s for s in sloty_na_boisku(SLOTY_4231)}
    assert sloty[0]["pozycja"] == "Bramkarz"
    assert sloty[1]["pozycja"] == "Prawy Obrońca" and sloty[1]["x"] > 80
    assert sloty[4]["pozycja"] == "Lewy Obrońca" and sloty[4]["x"] < 20
    assert sloty[2]["x"] > sloty[3]["x"]          # flaga 0x200000 = prawa strona
    assert sloty[6]["x"] > sloty[5]["x"]
    assert sloty[8]["pozycja"] == "Ofensywny Pomocnik" and sloty[8]["pozycja_bez"] == "Lewy Skrzydłowy"
    # bez flag: kolejnosc numerow od prawej
    bez_flag = {s["numer"]: s for s in sloty_na_boisku([(0, 0, 0), (1, 4, 4), (2, 4, 4), (3, 4, 4)])}
    assert bez_flag[1]["x"] > bez_flag[2]["x"] > bez_flag[3]["x"]


def _slot(numer, bit, bit_bez, maska):
    return NS(number=numer, in_possession_positions=(NS(raw=bit),), out_of_possession_positions=(NS(raw=bit_bez),),
              in_possession_mask=maska)


def test_taktyki_klubu_z_wyborem_xi():
    taktyka = NS(club_uid=7, team_slot=0, index=0, name="Ofensywna 4-2-3-1", style_name="Niestandardowa",
                 mentality=NS(raw=6), slots=tuple(_slot(*s) for s in SLOTY_4231))
    rezerwy = NS(club_uid=7, team_slot=1, index=0, name="Rezerwy", style_name="", mentality=NS(raw=4), slots=())
    obca = NS(club_uid=8, team_slot=0, index=0, name="Obca", style_name="", mentality=NS(raw=4), slots=())
    wybor = [NS(club_uid=7, team_slot=0, substitute=False, slot=i, player_uid=100 + i, player_name=f"Gracz {i}")
             for i in range(11)]
    wybor += [NS(club_uid=7, team_slot=0, substitute=True, slot=1, player_uid=202, player_name="Rez B"),
              NS(club_uid=7, team_slot=0, substitute=True, slot=0, player_uid=201, player_name="Rez A"),
              NS(club_uid=7, team_slot=1, substitute=False, slot=0, player_uid=999, player_name="Z rezerw")]
    zapis = NS(tactics=lambda: [taktyka, rezerwy, obca], selections=lambda: wybor)
    wynik = taktyki_klubu(zapis, 7)
    assert len(wynik) == 1
    t = wynik[0]
    assert t["formacja"] == "4-2-3-1" and t["mentalnosc"] == "ofensywna"
    assert {s["numer"]: s["uid"] for s in t["sloty"]}[10] == "110"
    assert {s["numer"]: s["nazwa"] for s in t["sloty"]}[0] == "Gracz 0"
    assert [r["nazwa"] for r in t["rezerwowi"]] == ["Rez A", "Rez B"]


def test_aktywna_taktyka_wg_dopasowania_xi():
    # dwie taktyki: 4-2-3-1 (indeks 0) i 3-5-2 (indeks 1); wybrani zawodnicy to obroncy z ocena na srodku obrony
    t4231 = NS(club_uid=7, team_slot=0, index=0, name="4-2-3-1", style_name="", mentality=NS(raw=4),
               slots=tuple(_slot(*s) for s in SLOTY_4231))
    sloty_352 = [(0, 0, 0, 0x1), (1, 4, 4, 0x10), (2, 4, 4, 0x10), (3, 4, 4, 0x10), (4, 5, 5, 0x20), (5, 10, 10, 0x400),
                 (6, 7, 7, 0x80), (7, 10, 10, 0x400), (8, 6, 6, 0x40), (9, 14, 14, 0x4000), (10, 14, 14, 0x4000)]
    t352 = NS(club_uid=7, team_slot=0, index=1, name="3-5-2", style_name="", mentality=NS(raw=4),
              slots=tuple(_slot(*s) for s in sloty_352))
    wybor = [NS(club_uid=7, team_slot=0, substitute=False, slot=i, player_uid=100 + i, player_name=f"G{i}")
             for i in range(11)]
    zapis = NS(tactics=lambda: [t4231, t352], selections=lambda: wybor)
    oceny = {101: {"dc": 20, "dr": 5}, 102: {"dc": 20}, 103: {"dc": 20, "dl": 5}}
    wynik = taktyki_klubu(zapis, 7, oceny)
    assert wynik[0]["nazwa"] == "3-5-2" and wynik[0]["aktywna"] and not wynik[1]["aktywna"]
    assert wynik[0]["formacja"] == "5-1-2-2"        # wahadlowi w linii obrony (jak "5-3-2 WB" w grze)
    assert all(s["uid"] is None for s in wynik[1]["sloty"])          # XI tylko w aktywnej taktyce
    # bez ocen: pierwsza wg indeksu
    assert taktyki_klubu(zapis, 7)[0]["nazwa"] == "4-2-3-1"
