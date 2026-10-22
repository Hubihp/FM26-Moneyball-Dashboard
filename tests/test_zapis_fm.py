"""Adapter zapisu .fm testowany na sztucznych rekordach o polach jak w fmsave (bez prawdziwego zapisu)."""
from datetime import date
from types import SimpleNamespace as NS

import numpy as np
import pandas as pd
import pytest

fmsave = pytest.importorskip("fmsave")

from fm_moneyball.zrodla.zapis_fm import (OpcjeZapisu, glowna_pozycja, grupy_pozycji, ligi_klubow,  # noqa: E402
                                          mapa_nazw_z_csv, preferowana_noga, statystyki_kanoniczne,
                                          sumuj_statystyki, zbuduj_ramki, zapisz_nazwy_rozgrywek,
                                          wczytaj_nazwy_rozgrywek)

KODY = ("gk", "sw", "dl", "dc", "dr", "dm", "ml", "mc", "mr", "aml", "amc", "amr", "stc", "wbl", "wbr")


def pozycje(**oceny):
    return NS(**{k: oceny.get(k, 1) for k in KODY})


def zawodnik(uid, poz, klub=10, wiek=24, wartosc=1_000_000, placa=10_000, **kw):
    dane = dict(
        uid=uid, name=f"Gracz {uid}", age=wiek, club_uid=klub, club_name=f"Klub {klub}",
        natural_positions=tuple(k for k in KODY if getattr(poz, k) >= 18), positions=poz,
        left_foot=8, right_foot=20, transfer_value=wartosc,
        transfer_value_state=fmsave.TransferValueState.OK,
        contract=NS(wage=placa, end=date(2027, 6, 30)), ability=NS(current=120, potential=150), on_loan=False,
    )
    dane.update(kw)
    return NS(**dane)


def wiersz_statystyk(uid, kind=fmsave.SeasonStatsKind.LEAGUE, **liczniki):
    baza = dict(minutes=900, goals=3, expected_goals=2.5, non_penalty_expected_goals=2.0, expected_assists=1.0,
                shots=20, shots_on_target=8, open_play_key_passes=10, pressures_completed=50, interceptions=9,
                possession_won=40, possession_lost=60, passes_attempted=400, progressive_passes=30,
                aerial_challenges_attempted=20, headers_won=12, dribbles=15, expected_goals_prevented=None,
                saves_held=None, saves_parried=None, saves_tipped=None, shots_on_target_faced=None)
    baza.update(liczniki)
    return NS(player_uid=uid, kind=kind, **baza)


def test_rodzaj_statystyk_jako_tekst():
    assert str(fmsave.SeasonStatsKind.LEAGUE) == "league"
    assert str(fmsave.TransferValueState.OK) == "ok"


def test_pozycje():
    assert glowna_pozycja(pozycje(dc=20, dm=18)) == "dc"
    assert grupy_pozycji(pozycje(dc=20, dm=18)) == ["Środkowy Obrońca"]
    assert grupy_pozycji(pozycje(dc=20, dm=18), wszystkie_naturalne=True) == ["Środkowy Obrońca", "Defensywny Pomocnik"]
    assert grupy_pozycji(pozycje(amr=20, stc=20)) == ["Skrzydłowy"]     # remis -> kolejnosc kodow
    assert glowna_pozycja(NS(**{k: 0 for k in KODY})) is None


@pytest.mark.parametrize("lewa, prawa, etykieta", [
    (20, 3, "Wyłącznie lewonożny"), (8, 20, "Prawonożny"), (16, 20, "Obunożny"), (20, 12, "Lewonożny")])
def test_noga(lewa, prawa, etykieta):
    assert preferowana_noga(lewa, prawa) == etykieta


def test_sumowanie_po_druzynach_i_rodzaju():
    wiersze = [wiersz_statystyk(1, minutes=600, goals=2), wiersz_statystyk(1, minutes=300, goals=1),
               wiersz_statystyk(1, kind=fmsave.SeasonStatsKind.CUP, minutes=90, goals=5)]
    sumy = sumuj_statystyki(wiersze, "league")
    assert sumy[1]["minutes"] == 900 and sumy[1]["goals"] == 3
    assert sumy[1]["saves_held"] is None


def test_statystyki_per_90_i_odsetki():
    s = statystyki_kanoniczne(sumuj_statystyki([wiersz_statystyk(1)], "league")[1])
    assert s["Minuty"] == 900
    assert s["Liczba goli na 90 min"] == pytest.approx(0.3)
    assert s["Oczekiwane gole na strzał"] == pytest.approx(0.125)
    assert s["Skuteczność strzałów (%)"] == pytest.approx(40)
    assert s["% wygranych pojedynków główkowych"] == pytest.approx(60)
    assert np.isnan(s["Skuteczność obron (%)"]) and np.isnan(s["Uniknięte oczekiwane gole/90"])


def test_bramkarz_ma_obrony():
    s = statystyki_kanoniczne(sumuj_statystyki([wiersz_statystyk(
        1, saves_held=10, saves_parried=5, saves_tipped=5, shots_on_target_faced=25,
        expected_goals_prevented=1.0)], "league")[1])
    assert s["Skuteczność obron (%)"] == pytest.approx(80)
    assert s["Uniknięte oczekiwane gole/90"] == pytest.approx(0.1)


def test_dzielenie_przez_zero():
    s = statystyki_kanoniczne({"minutes": 0, "shots": 0, "goals": 0})
    assert all(np.isnan(v) for k, v in s.items() if k != "Minuty")


def _liga(nazwa="Ekstraklasa"):
    return NS(etykieta=nazwa, database_id=1, nazwa=nazwa)


def test_zbuduj_ramki_filtry_i_kolumny():
    zawodnicy = [
        zawodnik(1, pozycje(stc=20)),
        zawodnik(2, pozycje(stc=20), klub=None),           # bez klubu
        zawodnik(3, pozycje(stc=20)),                      # za malo minut
        zawodnik(4, pozycje(gk=20), klub=99),              # klub bez ligi
        zawodnik(5, pozycje(dc=20), transfer_value_state=fmsave.TransferValueState.UNSET, contract=None),
    ]
    liczniki = sumuj_statystyki([wiersz_statystyk(1), wiersz_statystyk(2), wiersz_statystyk(3, minutes=100),
                                 wiersz_statystyk(4), wiersz_statystyk(5)], "league")
    ramki = zbuduj_ramki(zawodnicy, liczniki, {10: _liga()}, OpcjeZapisu(kurs_waluty=1.0, min_minut=300))
    assert set(ramki) == {"Napastnik", "Środkowy Obrońca"}
    nap = ramki["Napastnik"].iloc[0]
    assert nap["Piłkarz"] == "Gracz 1" and nap["Liga"] == "Ekstraklasa (POL 1)"
    assert nap["Mnożnik_Ligi"] == pytest.approx(0.795)
    assert nap["Wartość_Numeryczna"] == 1_000_000 and nap["Cena"] == "1 mln €"
    assert nap["Zarobki_Numeryczne"] == 520_000 and nap["Płaca"] == "10 tys. € tyg."
    assert nap["Wygasa_Data"] == pd.Timestamp(2027, 6, 30) and nap["Wygasa"] == "30.6.2027"
    assert nap["Preferowana noga"] == "Prawonożny" and nap["Pozycja"] == "STC"
    obr = ramki["Środkowy Obrońca"].iloc[0]
    assert np.isnan(obr["Wartość_Numeryczna"]) and obr["Płaca"] is None


def test_kurs_waluty():
    ramki = zbuduj_ramki([zawodnik(1, pozycje(stc=20))], sumuj_statystyki([wiersz_statystyk(1)], "league"),
                         {10: _liga()}, OpcjeZapisu(kurs_waluty=1.2))
    assert ramki["Napastnik"].iloc[0]["Wartość_Numeryczna"] == pytest.approx(1_200_000)


def _tabela(comp_id, kluby, sloty=None):
    sloty = sloty or [0] * len(kluby)
    return NS(competition_id=comp_id, rows=[NS(club_uid=k, team_slot=s) for k, s in zip(kluby, sloty)])


def test_ligi_klubow():
    kluby = [NS(uid=i, nation_id=1 if i < 20 else 2, name=f"Klub {i}", short_name=f"K{i}") for i in range(1, 30)]
    tabele = [
        _tabela(100, list(range(1, 19))),                    # liga krajowa (18 klubow z kraju 1)
        _tabela(200, [1, 2, 21, 22, 23, 24, 25, 26]),        # puchar miedzynarodowy - pomijany
        _tabela(300, [1, 2, 3, 4]),                          # grupa pucharu krajowego - mniejsza niz liga
        _tabela(400, [5, 19], sloty=[1, 0]),                 # druzyna rezerw klubu 5 - pomijana
        _tabela(None, [27]),
    ]
    rozgrywki = [NS(id=100, database_id=7), NS(id=200, database_id=8), NS(id=300, database_id=9), NS(id=400, database_id=10)]
    ligi = ligi_klubow(tabele, rozgrywki, kluby, nazwy={7: "Ekstraklasa"})
    assert ligi[1].competition_id == 100 and ligi[1].etykieta == "Ekstraklasa"
    assert ligi[5].competition_id == 100
    assert 21 not in ligi and 27 not in ligi
    assert ligi[19].etykieta == "Rozgrywki #10"


def test_mapa_nazw_z_csv(tmp_path):
    kluby = [NS(uid=1, name="Legia Warszawa", short_name="Legia"), NS(uid=2, name="Lech Poznań", short_name="Lech"),
             NS(uid=3, name="Arsenal", short_name="Arsenal")]
    liga_klubu = {1: NS(database_id=7), 2: NS(database_id=7), 3: NS(database_id=8)}
    csv = pd.DataFrame({"Klub": ["Legia", "Lech Poznań", "Arsenal"],
                        "Liga": ["Ekstraklasa (POL 1)", "Ekstraklasa (POL 1)", "Premier League (ANG 1)"]})
    mapa = mapa_nazw_z_csv(liga_klubu, kluby, [csv])
    assert mapa == {7: "Ekstraklasa"}          # Premier League ma tylko jeden glos
    assert mapa_nazw_z_csv(liga_klubu, kluby, [csv], min_glosow=1) == {7: "Ekstraklasa", 8: "Premier League"}

    plik = tmp_path / "nazwy.csv"
    zapisz_nazwy_rozgrywek({7: "Ekstraklasa"}, plik)
    zapisz_nazwy_rozgrywek({7: "Inna", 8: "Premier League"}, plik)   # istniejace wpisy maja pierwszenstwo
    assert wczytaj_nazwy_rozgrywek(plik) == {7: "Ekstraklasa", 8: "Premier League"}
