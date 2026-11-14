"""Kontrola jakosci odczytu: zgodnosc goli i minut z tabelami lig, testy pol."""
from types import SimpleNamespace as NS

from fm_moneyball.kontrola import kontrola, sprawdz_ligi, sprawdz_pola
from fm_moneyball.zrodla.zapis_fm import Liga


def _tabela(comp, wiersze):
    return NS(competition_id=comp, rows=tuple(NS(club_uid=u, played=m, goals_for=g) for u, m, g in wiersze))


def test_zgodna_liga_i_rozjechana_liga():
    # liga 1: zgodna (samobojcze rywali obnizaja sume zawodnikow o 1-2 gole); liga 2: gole zawodnikow 2x za duze
    druzyny = {u: {"goals": 30 - u % 2, "minutes": 20 * 990 - 300, "expected_goals": 29.0} for u in range(1, 11)}
    druzyny.update({u: {"goals": 60, "minutes": 20 * 990, "expected_goals": 28.0} for u in range(11, 21)})
    liga_klubu = {u: Liga(100 if u <= 10 else 200, 1000 if u <= 10 else 2000, None) for u in range(1, 21)}
    tabele = [_tabela(100, [(u, 20, 30) for u in range(1, 11)]), _tabela(200, [(u, 20, 30) for u in range(11, 21)]),
              _tabela(100, [(1, 2, 3)])]    # fragment (inny etap) - pomijany, wygrywa najwieksza tabela
    ligi = {x["klucz"]: x for x in sprawdz_ligi(tabele, druzyny, liga_klubu)}
    assert ligi[1000]["status"] == "ok" and ligi[1000]["gole_niezgodne"] == 0 and ligi[1000]["kluby"] == 10
    assert ligi[2000]["status"] == "błąd" and ligi[2000]["gole_niezgodne"] == 10
    wynik = kontrola(tabele, druzyny, liga_klubu, {})
    assert wynik["ostrzezenie_ligi"] == [2000]


def test_kilka_lig_klubu_i_brak_odniesienia():
    # Brazylia: klub gra w lidze stanowej i krajowej, statystyki obejmuja obie - porownanie z suma tabel
    druzyny = {u: {"goals": 39, "minutes": 30 * 990, "expected_goals": 40.0} for u in range(1, 9)}
    liga_klubu = {u: Liga(5, 50, None) for u in range(1, 9)}
    liga_klubu[99] = Liga(6, 60, None)        # liga stanowa jest liga innych (mniejszych) klubow
    tabele = [_tabela(5, [(u, 20, 30) for u in range(1, 9)]), _tabela(6, [(u, 10, 10) for u in [*range(1, 9), 99]]),
              _tabela(7, [(u, 6, 12) for u in range(1, 9)])]   # puchar europejski (niczyja liga) - pomijany
    ligi = {x["klucz"]: x for x in sprawdz_ligi(tabele, druzyny, liga_klubu)}
    assert ligi[50]["status"] == "ok" and ligi[50]["kluby"] == 8
    # liga bez tabeli w zapisie (minuty nie pasuja) - brak odniesienia, a nie blad odczytu
    ligi = {x["klucz"]: x for x in sprawdz_ligi(tabele[:1], druzyny, liga_klubu)}
    assert ligi[50]["status"] == "brak odniesienia" and ligi[50]["nieporownywalne"] == 8
    assert kontrola(tabele[:1], druzyny, liga_klubu, {})["ostrzezenie_ligi"] == []
    # klub po 2 meczach nie jest oceniany
    assert sprawdz_ligi([_tabela(5, [(1, 2, 3)])], druzyny, liga_klubu) == []


def test_pola_zawodnikow():
    liczniki = {i: {"passes_completed": 40, "passes_attempted": 50, "shots_on_target": 3, "shots": 5,
                    "pressures_completed": None, "minutes": 900} for i in range(200)}
    liczniki[0]["passes_completed"] = 80          # jeden zawodnik niespojny (0,5% - w normie)
    pola = {p["nazwa"]: p for p in sprawdz_pola(liczniki)}
    assert pola["Celne podania ≤ podania"]["liczba"] == 1 and pola["Celne podania ≤ podania"]["status"] == "ok"
    assert pola["Strzały celne ≤ strzały"]["status"] == "ok"
    assert "pressures_completed" in pola["Pola, których zapis nie podaje"]["opis"]
    for i in range(20):
        liczniki[i]["shots_on_target"] = 9
    assert {p["nazwa"]: p for p in sprawdz_pola(liczniki)}["Strzały celne ≤ strzały"]["status"] == "błąd"
