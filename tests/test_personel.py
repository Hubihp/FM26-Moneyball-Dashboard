from types import SimpleNamespace

from fm_moneyball import finanse, personel


def _osoba(uid, klub, job, **atr):
    pola = {p: None for p in ("goalkeeping", "fitness", "defending", "tactical", "attacking", "technical",
                              "tactical_knowledge", "judging_player_ability", "judging_player_potential",
                              "physiotherapy", "sports_science", "analysing_data", "working_with_youngsters")}
    pola.update(atr)
    return SimpleNamespace(uid=uid, name=f"O{uid}", age=40, club_uid=klub, club_name=f"K{klub}", team_slot=0, wage=100,
                           contract_end=None, has_contract=True, is_human_manager=False,
                           job=SimpleNamespace(label=SimpleNamespace(name=job)), attributes=SimpleNamespace(**pola))


def test_oceny_obszarow_i_luki():
    ludzie = [_osoba(1, 10, "SCOUT", judging_player_ability=60, judging_player_potential=60),       # moj: 12/20
              _osoba(2, 10, "PHYSIO", physiotherapy=90, sports_science=90, working_with_youngsters=20),
              _osoba(3, 20, "SCOUT", judging_player_ability=90, judging_player_potential=90),       # liga: 18
              _osoba(4, 30, "SCOUT", judging_player_ability=80, judging_player_potential=80),       # liga: 16
              _osoba(5, 99, "SCOUT", judging_player_ability=100, judging_player_potential=100),     # spoza ligi
              _osoba(6, 99, "UNKNOWN", judging_player_ability=100, judging_player_potential=100)]   # dzialacz
    wynik = personel.analiza_personelu(ludzie, 10, {20, 30}, kurs=1.0)
    skauting = next(o for o in wynik["obszary"] if o["obszar"] == "Skauting")
    assert skauting["moja"] == 12.0 and skauting["mediana_ligi"] == 17.0 and skauting["luka"] and skauting["miejsce"] == 3
    assert [k["uid"] for k in wynik["kandydaci"]["Skauting"]] == ["5", "3", "4"]   # bez dzialacza o nieznanym stanowisku
    fizjo = next(m for m in wynik["sztab"] if m["uid"] == "2")
    assert fizjo["najlepszy_obszar"] == "Fizjoterapia"          # nie praca z mlodzieza - nie jego obszar


def test_podsumowanie_finansow():
    miesiace = [{"miesiac": f"2027-{m:02d}-01", "saldo": 1000 * m, "przychody": 100, "wydatki": 80, "place": 60,
                 "transfery": 0, "place_tydzien": 10, "budzet_plac_tydzien": 12, "budzet_transferowy": 5}
                for m in range(1, 13)]
    p = finanse.podsumowanie(miesiace)
    assert p["wynik_operacyjny_miesiac"] == 20 and p["prognoza_salda_12"] == 12000 + 240
    assert p["udzial_plac"] == round(520 / 1200, 3) and p["status_plac"] == "ok"


def test_prognoza_wartosci_za_2_lata():
    import numpy as np
    import pandas as pd

    from fm_moneyball.wycena import prognoza_wartosci
    # log(cena) = 10 + 0.05*SCORE - 0.1*wiek (bez kontraktu): +10 SCORE i +2 lata -> exp(0.5 - 0.2)
    model = {"beta": [10.0, 0.05, -0.1, 0.0, 0.0, 0.0, 0.0], "zakres": {"SCORE": (0, 100), "wiek": (15, 40)}}
    df = pd.DataFrame({"SCORE": [60.0, 60.0], "Rozwój_wiek_2": [10.0, 0.0], "Wiek": [20, 30],
                       "Wartość_Numeryczna": [1e6, np.nan]})
    wynik = prognoza_wartosci(df, model)
    assert abs(wynik.loc[0, "Zmiana wartości"] - np.exp(0.3)) < 1e-9
    assert abs(wynik.loc[0, "Wartość za 2 lata"] - 1e6 * np.exp(0.3)) < 1e-3
    assert np.isnan(wynik.loc[1, "Wartość za 2 lata"])        # bez obecnej wartosci - bez prognozy
