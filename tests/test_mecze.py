from datetime import date
from types import SimpleNamespace

from fm_moneyball import mecze


def _mecz(dzien, dom, wyjazd, gole_d, gole_w, comp=1, rozegrany=True):
    return SimpleNamespace(date=dzien, competition_id=comp, home_club_uid=dom, away_club_uid=wyjazd,
                           home_club_name=f"K{dom}", away_club_name=f"K{wyjazd}", home_team_id=dom * 10,
                           away_team_id=wyjazd * 10, home_team_slot=0, away_team_slot=0,
                           home_goals=gole_d if rozegrany else None, away_goals=gole_w if rozegrany else None,
                           played=rozegrany)


def _stat(m, team, xg):
    return SimpleNamespace(date=m.date, home_team_id=m.home_team_id, away_team_id=m.away_team_id, team_id=team,
                           expected_goals=xg, shots=10, shots_on_target=4, possession_percent=50)


def test_punkty_oczekiwane_i_ocena():
    assert mecze.punkty_oczekiwane(1.0, 1.0) < mecze.punkty_oczekiwane(2.5, 0.5) <= 3
    assert abs(sum(mecze.prawdopodobienstwa(1.3, 0.9)) - 1) < 1e-6
    assert mecze.ocena_meczu(1, 0, 0.4, 1.5) == "szczęśliwa wygrana"
    assert mecze.ocena_meczu(0, 1, 2.0, 0.5) == "pechowa porażka"
    assert mecze.ocena_meczu(2, 1, 1.5, 1.2) is None


def test_zbierz_mecze_moje_i_rywala():
    m1 = _mecz(date(2027, 9, 1), 1, 2, 1, 0)
    m2 = _mecz(date(2027, 9, 8), 3, 1, 2, 2)
    m3 = _mecz(date(2027, 9, 15), 2, 3, 0, 1)            # mecz rywala bez nas
    m4 = _mecz(date(2027, 10, 1), 1, 3, None, None, rozegrany=False)
    stat = [_stat(m1, 10, 0.5), _stat(m1, 20, 1.8), _stat(m3, 20, 1.0), _stat(m3, 30, 0.7)]
    kraje = {1: 5, 2: 5, 3: 5}
    wynik = mecze.zbierz_mecze([m1, m2, m3, m4], stat, {1}, date(2027, 9, 20), kraje, {1: "Liga"})
    moje = wynik["1"]
    assert [m["rywal_uid"] for m in moje] == ["2", "3", "3"]
    assert moje[0]["xg"] == 0.5 and moje[0]["xg_rywala"] == 1.8 and moje[0]["ocena"] == "szczęśliwa wygrana"
    assert moje[0]["rozgrywki"] == "Liga" and moje[1]["xg"] is None      # mecz bez statystyk
    assert not moje[2]["rozegrany"]
    assert [m["data"] for m in wynik["2"]] == ["2027-09-01", "2027-09-15"]  # rywal: tylko rozegrane do dzis
    p = mecze.podsumowanie([m for m in moje if m["rozegrany"]])
    assert (p["wygrane"], p["remisy"], p["porazki"], p["mecze_z_xg"], p["forma"]) == (1, 1, 0, 1, "WR")


def test_nazwy_rozgrywek():
    terminarz = [_mecz(date(2027, 9, 1), 1, 2, 0, 0, comp=7), _mecz(date(2027, 9, 1), 1, 4, 0, 0, comp=8)]
    nazwy = mecze.nazwy_rozgrywek(terminarz, {1: 5, 2: 5, 4: 9}, {})
    assert nazwy == {7: "Puchar krajowy", 8: "Rozgrywki międzynarodowe"}
