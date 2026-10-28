"""Profil druzyny na tle ligi: metryki, miejsca, atletyzm, zmiany; sumy druzyn z zapisu."""
from types import SimpleNamespace as NS

import numpy as np
import pandas as pd
import pytest

from fm_moneyball import profil
from fm_moneyball.zrodla.zapis_fm import sumuj_druzyny, tabela_ligi


def _druzyny():
    baza = dict(minutes=9900, goals=20, expected_goals=15, shots=150, passes_attempted=5000, passes_completed=4500,
                tackles_attempted=200, tackles_completed=140, fouls_made=100, yellow_cards=20, red_cards=0,
                distance_km=1200, high_intensity_sprints=1300, mistakes_leading_to_goal=3, ocena=6.8)
    return {
        1: {**baza, "nazwa": "Moj FC", "goals": 30, "fouls_made": 150, "distance_km": 1100},
        2: {**baza, "nazwa": "Drugi"},
        3: {**baza, "nazwa": "Trzeci", "goals": 10, "fouls_made": 80, "distance_km": 1300},
    }


def test_miejsca_i_kierunek_metryk():
    tabela = {"wiersze": [{"club_uid": u, "klub": f"K{u}", "mecze": 10, "punkty": p, "gole": g, "stracone": s}
                          for u, p, g, s in ((1, 25, 30, 5), (2, 15, 20, 10), (3, 5, 10, 20))]}
    t = profil.tabela_profilu(_druzyny(), [1, 2, 3], tabela)
    assert t.at[1, 'Mecze'] == 10 and t.at[1, 'Gole na mecz'] == pytest.approx(3.0)
    sekcje = profil.porownanie(t, 1)
    po_nazwie = {m["nazwa"]: m for lista in sekcje.values() for m in lista}
    assert po_nazwie["Punkty na mecz"]["miejsce"] == 1 and po_nazwie["Stracone gole na mecz"]["miejsce"] == 1
    assert po_nazwie["Faule na mecz"]["miejsce"] == 3            # najwiecej fauli = ostatnie miejsce
    assert po_nazwie["Dystans na mecz (km)"]["miejsce"] == 3
    assert po_nazwie["Celność podań (%)"]["wartosc"] == pytest.approx(90.0)
    assert po_nazwie["Dystans na mecz (km)"]["rozklad"][-1]["moj"]
    pods = profil.podsumowanie(sekcje, 10)
    assert po_nazwie["Gole − xG na mecz"]["miejsce"] == 1
    assert pods["mocne"] and all(m["miejsce"] == 1 for m in pods["mocne"])
    assert all(m["miejsce"] == 3 for m in pods["slabe"])
    assert any(m["nazwa"] == "Faule na mecz" for m in pods["slabe"]) and not pods["mala_proba"]


def test_przyblizenie_bez_zapisu():
    zawodnicy = pd.DataFrame({'Klub_UID': [1, 1, 2], 'Klub': ['A', 'A', 'B'], 'Minuty': [990.0, 990.0, 1980.0],
                              'Liczba goli na 90 min': [0.5, 0.0, 0.25], 'Próby podań/90': [50.0, 40.0, 30.0]})
    d = profil.druzyny_z_zawodnikow(zawodnicy)
    assert d[1]["goals"] == pytest.approx(5.5) and d[2]["passes_attempted"] == pytest.approx(660)
    t = profil.tabela_profilu(d, [1, 2])
    assert t.at[1, 'Mecze'] == 2 and np.isnan(t.at[1, 'Celność podań (%)'])


def _zawodnicy(n=40, seed=3):
    rng = np.random.default_rng(seed)
    return pd.DataFrame({
        'UID': np.arange(n), 'ID': [f"Z{i}" for i in range(n)], 'Piłkarz': [f"Z{i}" for i in range(n)],
        'Klub_UID': np.arange(n) % 4, 'Klub': [f"K{i % 4}" for i in range(n)], 'Minuty': rng.uniform(500, 2700, n),
        'Pula_główna': np.where(np.arange(n) % 2, 'Prawy Obrońca', 'Środkowy Obrońca'),
        'Dystans (km)/90': rng.normal(11, 0.8, n), 'Sprinty/90': rng.normal(12, 4, n)})


def test_atletyzm_wzgledem_pozycji_i_skladow():
    z = _zawodnicy()
    z.loc[0, ['Dystans (km)/90', 'Sprinty/90']] = [20.0, 60.0]           # najbardziej atletyczny stoper
    a = profil.atletyzm(z, [0, 1, 2, 3], 0, mecze=30)
    assert a["prog_minut"] == pytest.approx(675) and set(a["metryki"]) == set(profil.METRYKI_ATLETYZMU)
    wyniki = {w["Piłkarz"]: w["Atletyzm"] for w in a["zawodnicy"]}
    if "Z0" in wyniki:
        assert wyniki["Z0"] > 90
    assert all(0 <= w["Atletyzm"] <= 100 for w in a["zawodnicy"])
    assert len(a["kluby"]) == 4 and a["moj"]["klub"] == "K0"
    # sklady z zapisu: zawodnik Z5 gral dla klubu 3 (np. przed transferem) - liczy sie dla 3, z tymi minutami
    sklady = {0: {0: 2000.0}, 3: {5: 1500.0, 7: 100.0}}
    b = profil.atletyzm(z, [0, 3], 0, {0: "Moj", 3: "Inny"}, mecze=30, sklady=sklady)
    assert [k["klub"] for k in b["kluby"]] and {k["klub"] for k in b["kluby"]} <= {"Moj", "Inny"}
    assert [w["Piłkarz"] for w in b["zawodnicy"]] == ["Z0"]            # Z7: 100 minut < prog
    assert profil.atletyzm(z.drop(columns=['Dystans (km)/90', 'Sprinty/90']), [0], 0) is None


def test_zmiany_spadki_i_wzrosty():
    rozwoj = [{"Piłkarz": "A", "ID": "a", "pozycja": "N", "SCORE": 60.0, "Δ SCORE": -8.0},
              {"Piłkarz": "B", "ID": "b", "pozycja": "N", "SCORE": 70.0, "Δ SCORE": 5.0},
              {"Piłkarz": "C", "ID": "c", "pozycja": "N", "SCORE": 50.0, "Δ SCORE": None}]
    z = profil.zmiany_zawodnikow(rozwoj, {1: (7.0, 1500), 2: (6.5, 500)}, {1: (7.4, 2000), 2: (6.0, 2000)}, 1000)
    assert [m["Piłkarz"] for m in z["spadki"]] == ["A"] and z["spadki"][0]["SCORE wtedy"] == pytest.approx(68)
    assert [m["Piłkarz"] for m in z["wzrosty"]] == ["B"]
    assert len(z["oceny_spadki"]) == 1 and z["oceny_spadki"][0]["zmiana"] == pytest.approx(-0.4)
    assert z["oceny_wzrosty"] == []                                    # zawodnik 2: za malo minut teraz


def test_sumy_druzyn_z_wierszy_zapisu():
    def w(gracz, klub, slot, minuty, gole, ocena=7.0, mecze=10):
        return NS(kind="league", player_uid=gracz, club_uid=klub, club_name=f"K{klub}", team_slot=slot,
                  minutes=minuty, goals=gole, average_rating=ocena, rated_appearances=mecze)
    wiersze = [w(1, 10, 0, 900, 2), w(2, 10, 0, 450, 1, 6.0, 5), w(1, 20, 0, 300, 1),   # gracz 1 po transferze
               w(3, 10, 1, 900, 9), NS(kind="cup", player_uid=4, club_uid=10, team_slot=0, minutes=90, goals=5)]
    d = sumuj_druzyny(wiersze, "league")
    assert d[10]["goals"] == 3 and d[10]["minutes"] == 1350          # bez rezerw (slot 1) i pucharu
    assert d[10]["sklad"] == {1: 900.0, 2: 450.0} and d[20]["sklad"] == {1: 300.0}
    assert d[10]["ocena"] == pytest.approx((7.0 * 10 + 6.0 * 5) / 15)

    def tab(comp, kluby):
        return NS(competition_id=comp, rows=[NS(club_uid=k, club_name=f"K{k}", position=i + 1, played=30, won=1,
                                                drawn=1, lost=1, goals_for=1, goals_against=1, points=3)
                                             for i, k in enumerate(kluby)])
    t = tabela_ligi([tab(5, [99]), tab(5, [10, 20, 30]), tab(6, [10])], 5, 10)
    assert t["competition_id"] == 5 and [r["club_uid"] for r in t["wiersze"]] == [10, 20, 30]
    assert tabela_ligi([tab(5, [99])], 5, 10) is None


def test_druzyny_w_klubie_i_pierwsza_druzyna():
    from fm_moneyball import analiza
    from fm_moneyball.zrodla.zapis_fm import INNA_DRUZYNA, PIERWSZA_DRUZYNA, dopisz_druzyny, etykiety_druzyn
    mecze = [NS(home_club_uid=1, home_team_slot=1, away_club_uid=2, away_team_slot=1, competition_id=50),
             NS(home_club_uid=3, home_team_slot=0, away_club_uid=1, away_team_slot=1, competition_id=50),
             NS(home_club_uid=1, home_team_slot=0, away_club_uid=2, away_team_slot=0, competition_id=7)]
    rozgrywki = [NS(id=50, database_id=500, name="Liga juniorow"), NS(id=7, database_id=70, name="Liga")]
    et = etykiety_druzyn(mecze, rozgrywki, {1})
    assert et == {1: {1: "Liga juniorow"}}
    assert etykiety_druzyn(mecze, rozgrywki, {1}, {500: "U19 Elite"}) == {1: {1: "U19 Elite"}}
    df = pd.DataFrame({'Klub_UID': [1, 1, 1, 2], 'Drużyna_slot': [0, 1, 3, 1], 'SCORE': [60.0, 70.0, 50.0, 40.0]})
    dane = dopisz_druzyny({"N": df}, et)
    assert list(dane["N"]['Drużyna']) == [PIERWSZA_DRUZYNA, f"{INNA_DRUZYNA} (Liga juniorow)", INNA_DRUZYNA, INNA_DRUZYNA]
    assert list(analiza.moi_zawodnicy(df, 1).index) == [0]
    assert list(analiza.moi_zawodnicy(df, 1, tylko_pierwsza=False).index) == [0, 1, 2]
    assert len(analiza.moi_zawodnicy(df.drop(columns='Drużyna_slot'), 1)) == 3      # CSV/demo: wszyscy
