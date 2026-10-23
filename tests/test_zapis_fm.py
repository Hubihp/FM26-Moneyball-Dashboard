"""Adapter zapisu .fm testowany na sztucznych rekordach o polach jak w fmsave (bez prawdziwego zapisu)."""
from datetime import date
from types import SimpleNamespace as NS

import numpy as np
import pandas as pd
import pytest

fmsave = pytest.importorskip("fmsave")

from fm_moneyball.zrodla.zapis_fm import (KandydatLigi, OpcjeZapisu, glowna_pozycja, grupy_pozycji,  # noqa: E402
                                          kandydaci_lig, kandydaci_lig_z_terminarza, kluby_drugorzedne,
                                          polacz_kandydatow, ligi_klubow, mapa_nazw_z_csv, preferowana_noga, statystyki_kanoniczne,
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
    assert s["Skuteczność strzałów (%)"] == pytest.approx(15)     # gole / strzaly (jak "Skut (%)" w grze)
    assert s["Celność strzałów (%)"] == pytest.approx(40)         # celne / strzaly
    assert s["% wygranych pojedynków główkowych"] == pytest.approx(60)
    # u zawodnika z pola brak pol bramkarskich -> brak danych (a nie 0)
    assert np.isnan(s["Skuteczność obron (%)"]) and np.isnan(s["Uniknięte oczekiwane gole/90"])
    zero = statystyki_kanoniczne(sumuj_statystyki([wiersz_statystyk(1, expected_goals_prevented=0.0)], "league")[1])
    assert np.isnan(zero["Uniknięte oczekiwane gole/90"])


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
    from fm_moneyball.zrodla.zapis_fm import Liga
    return Liga(competition_id=1, database_id=1, nazwa=nazwa)


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
    assert 19 not in ligi     # tylko we fragmencie tabeli (2 kluby) - to nie liga


def _kluby(nazwy):
    return [NS(uid=i, name=n, short_name=n, nation_id=1) for i, n in enumerate(nazwy, start=1)]


def test_mapa_nazw_jeden_do_jednego_przy_awansach():
    # 6 klubow gra dzis w Championship (id 12), 3 awansowaly do Premier League (id 11).
    # Stare CSV podaje "EFL Championship" dla wszystkich 9, a klubow z Premier League nie zawiera.
    kluby = _kluby([f"Klub {i}" for i in range(1, 10)])
    kandydaci = {k.uid: [KandydatLigi(24, 12 if k.uid <= 6 else 11, 12 if k.uid <= 6 else 11)] for k in kluby}
    csv = pd.DataFrame({"Klub": [k.name for k in kluby], "Liga": ["EFL Championship (ANG 2)"] * 9})
    assert mapa_nazw_z_csv(kandydaci, kluby, [csv]) == {12: "EFL Championship"}


def test_mapa_nazw_liga_stanowa_przegrywa_z_krajowa():
    # 8 klubow Serie A (id 500) gra tez w dwoch ligach stanowych (id 901 i 902)
    kluby = _kluby([f"Clube {i}" for i in range(1, 9)])
    kandydaci = {k.uid: [KandydatLigi(16, 901 if k.uid <= 4 else 902, 901 if k.uid <= 4 else 902),
                         KandydatLigi(20, 500, 500)] for k in kluby}
    csv = pd.DataFrame({"Klub": [k.name for k in kluby], "Liga": ["Série A (BRA 1)"] * 8})
    mapa = mapa_nazw_z_csv(kandydaci, kluby, [csv])
    assert mapa == {500: "Série A"}
    ligi = ligi_klubow([], [], kluby, nazwy=mapa, kandydaci=kandydaci)
    assert all(l.competition_id == 500 and l.etykieta == "Série A" for l in ligi.values())


def test_mapa_nazw_liga_stanowa_bez_krajowej_nie_dostaje_nazwy():
    # Serie A jeszcze nie ruszyla: 8 klubow z CSV "Série A" gra tylko w trzech ligach stanowych
    kluby = _kluby([f"Clube {i}" for i in range(1, 9)])
    stan = {1: 901, 2: 901, 3: 901, 4: 902, 5: 902, 6: 902, 7: 903, 8: 903}
    kandydaci = {k.uid: [KandydatLigi(12, stan[k.uid], stan[k.uid])] for k in kluby}
    csv = pd.DataFrame({"Klub": [k.name for k in kluby], "Liga": ["Série A (BRA 1)"] * 8})
    assert mapa_nazw_z_csv(kandydaci, kluby, [csv]) == {}


def test_kraj_none_i_limit_rozmiaru():
    kluby = [NS(uid=i, nation_id=None if i <= 50 else 1) for i in range(1, 61)]
    tabele = [_tabela(1, list(range(1, 51))),          # kluby bez kraju - nie jest krajowa
              _tabela(2, list(range(51, 61)))]         # 10 klubow z kraju 1
    kandydaci = kandydaci_lig(tabele, [NS(id=1, database_id=1), NS(id=2, database_id=2)], kluby)
    assert 1 not in kandydaci and kandydaci[51][0].competition_id == 2
    duze = [NS(uid=i, nation_id=1) for i in range(1, 51)]
    assert kandydaci_lig([_tabela(3, list(range(1, 51)))], [NS(id=3, database_id=3)], duze) == {}


def test_liga_z_krajem_klubu_wygrywa_z_obca_nazwana():
    kluby = [NS(uid=1, nation_id=1)]
    kandydaci = {1: [KandydatLigi(20, 100, 7, kraj=2), KandydatLigi(18, 200, 8, kraj=1)]}
    liga = ligi_klubow([], [], kluby, nazwy={7: "Obca liga"}, kandydaci=kandydaci)[1]
    assert liga.competition_id == 200


def test_kandydaci_lig_bez_nazw_najwieksza_tabela():
    kluby = [NS(uid=i, nation_id=1) for i in range(1, 21)]
    tabele = [_tabela(901, list(range(1, 17))), _tabela(500, list(range(1, 21)))]
    kandydaci = kandydaci_lig(tabele, [NS(id=901, database_id=9), NS(id=500, database_id=5)], kluby)
    assert [k.competition_id for k in kandydaci[1]] == [500, 901]
    assert ligi_klubow([], [], kluby, kandydaci=kandydaci)[1].etykieta == "Rozgrywki #5"
    # gdy znamy nazwe tylko ligi stanowej, wygrywa ona (nazwana ma pierwszenstwo)
    assert ligi_klubow([], [], kluby, nazwy={9: "Paulista"}, kandydaci=kandydaci)[1].competition_id == 901


def test_mapa_nazw_z_csv_progi_i_dopasowanie_klubow():
    kluby = [NS(uid=1, name="Legia Warszawa", short_name="Legia"), NS(uid=2, name="Lech Poznań", short_name="Lech"),
             NS(uid=3, name="Arsenal", short_name="Arsenal"), NS(uid=4, name="Arsenal", short_name="Arsenal")]
    kandydaci = {1: [KandydatLigi(18, 7, 7)], 2: [KandydatLigi(18, 7, 7)], 3: [KandydatLigi(20, 8, 8)]}
    csv = pd.DataFrame({"Klub": ["Legia", "Lech Poznań", "Arsenal"],
                        "Liga": ["Ekstraklasa (POL 1)", "Ekstraklasa (POL 1)", "Premier League (ANG 1)"]})
    # ten sam klub w dwoch plikach CSV glosuje raz; "Arsenal" jest niejednoznaczny
    assert mapa_nazw_z_csv(kandydaci, kluby, [csv, csv]) == {7: "Ekstraklasa"}
    assert mapa_nazw_z_csv(kandydaci, kluby, [csv], min_glosow=1) == {7: "Ekstraklasa"}


def test_zapis_mapy_nowe_wpisy_wygrywaja(tmp_path):
    plik = tmp_path / "nazwy.csv"
    zapisz_nazwy_rozgrywek({11: "EFL Championship", 16: "Ligue 1"}, plik)    # 11 nauczone blednie
    wynik = zapisz_nazwy_rozgrywek({12: "EFL Championship", 22: "Bundesliga"}, plik)
    assert wynik == {12: "EFL Championship", 16: "Ligue 1", 22: "Bundesliga"}
    assert wczytaj_nazwy_rozgrywek(plik) == wynik


def test_domyslna_mapa_nazw_pasuje_do_mnoznikow():
    from fm_moneyball.stale import MNOZNIKI_LIG
    from fm_moneyball.zrodla.zapis_fm import PLIK_NAZW_ROZGRYWEK
    mapa = wczytaj_nazwy_rozgrywek(PLIK_NAZW_ROZGRYWEK)
    # jedna liga moze miec kilka id (np. dwie fazy ligi argentynskiej), ale kazda nazwa musi miec mnoznik
    assert mapa and all(nazwa in MNOZNIKI_LIG for nazwa in mapa.values())


# --- liga z terminarza ---------------------------------------------------------------------------
DZIS = date(2032, 3, 21)


def _mecz(comp, dom, wyj, dzien=DZIS, runda=None, slot_dom=0, slot_wyj=0):
    return NS(competition_id=comp, round=runda, date=dzien, home_club_uid=dom, away_club_uid=wyj,
              home_team_slot=slot_dom, away_team_slot=slot_wyj)


def _kolejki(comp, uidy, ile_kolejek, dzien=DZIS):
    """Kazdy z kazdym, az kazdy klub zagra `ile_kolejek` meczow (w przyblizeniu)."""
    mecze = []
    for i in range(ile_kolejek):
        for j in range(0, len(uidy) - 1, 2):
            a, b = uidy[(j + i) % len(uidy)], uidy[(j + 1 + i) % len(uidy)]
            mecze.append(_mecz(comp, a, b, dzien))
    return mecze


def test_terminarz_liga_wygrywa_z_liga_stanowa_i_towarzyskimi():
    kluby = [NS(uid=i, name=f"Clube {i}", nation_id=1) for i in range(1, 21)] + \
            [NS(uid=i, name=f"Foreign {i}", nation_id=i) for i in range(50, 56)]
    serie_a = list(range(1, 21))
    mecze = (_kolejki(500, serie_a, 30, date(2032, 6, 1))                # Serie A: zaplanowana na przyszlosc
             + _kolejki(901, list(range(1, 13)), 11)                      # liga stanowa
             + [_mecz(777, 1, u) for u in range(50, 56)])                 # towarzyskie z zagranicznymi
    rozgrywki = [NS(id=500, database_id=5), NS(id=901, database_id=9), NS(id=777, database_id=7)]
    kandydaci = kandydaci_lig_z_terminarza(mecze, rozgrywki, kluby, DZIS)
    assert kandydaci[1][0].competition_id == 500
    assert {k.competition_id for k in kandydaci[1]} == {500, 901}     # towarzyskie odrzucone (mieszane kraje)
    assert ligi_klubow([], [], kluby, kandydaci=kandydaci)[1].etykieta == "Rozgrywki #5"


def test_terminarz_pomija_rundy_pucharowe_druzyny_rezerw_i_mecze_spoza_sezonu():
    kluby = [NS(uid=i, name=f"K{i}", nation_id=1) for i in range(1, 9)]
    uidy = list(range(1, 9))
    mecze = (_kolejki(1, uidy, 10, date(2030, 1, 1))                     # dawny sezon - poza oknem
             + [_mecz(2, a, a + 1, runda=NS(raw=7)) for a in range(1, 8)]   # puchar (runda)
             + [_mecz(3, a, a + 1, slot_dom=1) for a in range(1, 8)])        # druzyny rezerw
    assert kandydaci_lig_z_terminarza(mecze, [], kluby, DZIS) == {}


def test_rozgrywki_kobiece_sa_pomijane():
    meskie = [NS(uid=i, name=f"Klub {i}", nation_id=1) for i in range(1, 9)]
    kobiece = [NS(uid=2_000_000_000 + i, name=f"Klub {i}", nation_id=1) for i in range(1, 9)]
    assert kluby_drugorzedne(meskie + kobiece) == {k.uid for k in kobiece}
    mecze = _kolejki(10, [k.uid for k in meskie], 14) + _kolejki(20, [k.uid for k in kobiece], 14)
    kandydaci = kandydaci_lig_z_terminarza(mecze, [], meskie + kobiece, DZIS)
    assert set(kandydaci) == {k.uid for k in meskie}
    assert all(l[0].competition_id == 10 for l in kandydaci.values())


def test_polacz_kandydatow_terminarz_ma_pierwszenstwo():
    z_terminarza = {1: [KandydatLigi(30, 500, 5)]}
    z_tabel = {1: [KandydatLigi(12, 901, 9)], 2: [KandydatLigi(18, 600, 6)]}
    polaczeni = polacz_kandydatow(z_terminarza, z_tabel)
    assert polaczeni[1][0].competition_id == 500 and polaczeni[2][0].competition_id == 600


def test_klub_uid_w_ramce():
    ramki = zbuduj_ramki([zawodnik(1, pozycje(stc=20))], sumuj_statystyki([wiersz_statystyk(1)], "league"),
                         {10: _liga()}, OpcjeZapisu())
    assert ramki["Napastnik"].iloc[0]["Klub_UID"] == 10


# --- rozgrywki bez database_id (np. liga belgijska) ------------------------------------------------
def test_rozgrywki_bez_database_id_dostaja_klucz_kraju():
    belgia = [NS(uid=i, name=f"Club {i}", short_name=f"C{i}", nation_id=131) for i in range(1, 19)]
    mecze = _kolejki(0, [k.uid for k in belgia], 34)
    tabele = [_tabela(0, [k.uid for k in belgia])]
    rozgrywki = [NS(id=0, database_id=None)]
    z_terminarza = kandydaci_lig_z_terminarza(mecze, rozgrywki, belgia, DZIS)
    z_tabel = kandydaci_lig(tabele, rozgrywki, belgia)
    assert z_terminarza[1][0].database_id == -131 and z_tabel[1][0].database_id == -131
    liga = ligi_klubow([], [], belgia, nazwy={-131: "Jupiler Pro League"}, kandydaci=z_terminarza)[1]
    assert liga.etykieta == "Jupiler Pro League"
    assert ligi_klubow([], [], belgia, kandydaci=z_terminarza)[1].etykieta == "Liga krajowa #131"
    # uczenie z CSV nazywa takze lige bez database_id
    csv = pd.DataFrame({"Klub": [k.name for k in belgia], "Liga": ["Jupiler Pro League (BEL 1)"] * 18})
    assert mapa_nazw_z_csv(z_terminarza, belgia, [csv]) == {-131: "Jupiler Pro League"}


def test_mapa_nazw_z_kluczem_ujemnym(tmp_path):
    plik = tmp_path / "nazwy.csv"
    zapisz_nazwy_rozgrywek({-131: "Jupiler Pro League", 32: "Serie A"}, plik)
    assert wczytaj_nazwy_rozgrywek(plik) == {-131: "Jupiler Pro League", 32: "Serie A"}


# --- wolni agenci, moj klub, dane ukryte, kontuzje, podsumowanie lig -------------------------------
def test_wolni_agenci_i_moj_klub_poza_progiem_minut():
    from fm_moneyball.zrodla.zapis_fm import WOLNY_AGENT
    zawodnicy = [zawodnik(1, pozycje(stc=20), klub=None, club_name=None),
                 zawodnik(2, pozycje(stc=20), klub=55),                     # moj klub, malo minut, bez ligi
                 zawodnik(3, pozycje(stc=20), klub=10)]
    liczniki = sumuj_statystyki([wiersz_statystyk(1), wiersz_statystyk(2, minutes=50),
                                 wiersz_statystyk(3, minutes=50)], "league")
    ramki = zbuduj_ramki(zawodnicy, liczniki, {10: _liga()}, OpcjeZapisu(), moje_kluby=[55])
    nap = ramki["Napastnik"].set_index("UID")
    assert set(nap.index) == {1, 2}
    assert nap.loc[1, "Klub"] == WOLNY_AGENT and nap.loc[1, "Wartość_Numeryczna"] == 0 and bool(nap.loc[1, "Wolny_agent"])
    bez = zbuduj_ramki(zawodnicy, liczniki, {10: _liga()}, OpcjeZapisu(wolni_agenci=False))
    assert "Napastnik" not in bez


def test_dane_ukryte_kontuzje_i_klucz_ligi():
    z = zawodnik(1, pozycje(stc=20),
                 attributes=NS(consistency=14, important_matches=9, injury_proneness=17, determination=12),
                 personality=NS(professionalism=18, ambition=11, adaptability=7),
                 on_loan=True, loan_end=date(2032, 6, 30))
    ramki = zbuduj_ramki([z], sumuj_statystyki([wiersz_statystyk(1)], "league"), {10: _liga()}, OpcjeZapisu(),
                         kontuzje={1: 3})
    w = ramki["Napastnik"].iloc[0]
    assert (w["Regularność"], w["Podatność na kontuzje"], w["Profesjonalizm"]) == (14, 17, 18)
    assert w["Kontuzje_2_lata"] == 3 and w["Wypożyczenie_do"] == pd.Timestamp(2032, 6, 30)
    assert w["Liga_klucz"] == 1 and w["Liga_domyslna"] == "Rozgrywki #1"


def test_policz_kontuzje_i_podsumowanie_lig():
    from fm_moneyball.zrodla.zapis_fm import Liga, podsumuj_ligi, policz_kontuzje
    rekordy = [NS(kind="history", player_uid=1, date=date(2031, 9, 1)),
               NS(kind="history", player_uid=1, date=date(2025, 1, 1)),     # za stara
               NS(kind="typed", player_uid=1, date=date(2031, 9, 1)),       # inny magazyn
               NS(kind="history", player_uid=2, date=date(2032, 1, 1))]
    assert policz_kontuzje(rekordy, DZIS) == {1: 1, 2: 1}
    kluby = [NS(uid=i, name=f"Klub {i}") for i in range(1, 4)]
    ligi = podsumuj_ligi({1: Liga(5, 50, "Liga A"), 2: Liga(5, 50, "Liga A"), 3: Liga(6, None, None)}, kluby)
    assert ligi[0] == {"klucz": 50, "domyslna": "Rozgrywki #50", "nazwa": "Liga A", "liczba": 2,
                       "kluby": ["Klub 1", "Klub 2"]}
