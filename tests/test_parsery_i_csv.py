import numpy as np
import pandas as pd
import pytest

from fm_moneyball.parsery import do_liczb, parse_market_value, parse_wages
from fm_moneyball.stale import POZYCJE
from fm_moneyball.zrodla.csv_fm import generuj_demo_csv, wczytaj_csv, wykryj_pozycje


@pytest.mark.parametrize("tekst", ["1 mln € - 4 mln €", "1 mln €\xa0-\xa04 mln €", "1 mln € – 4 mln €", "1 mln €–4 mln €"])
def test_widelki_ceny_z_roznymi_myslnikami(tekst):
    assert parse_market_value(tekst) == pytest.approx(2_000_000)


def test_cena_nie_na_sprzedaz_to_brak_ceny():
    assert np.isnan(parse_market_value("Nie na sprzedaż"))


@pytest.mark.parametrize("tekst, roczna", [
    ("10 tys. € tyg.", 520_000),
    ("10 tys. €/w", 520_000),
    ("50 tys. € mies.", 600_000),
    ("600 tys. € /rok", 600_000),
])
def test_place(tekst, roczna):
    assert parse_wages(tekst) == pytest.approx(roczna)


def test_do_liczb_tysiace_z_kropka_tylko_na_zadanie():
    seria = pd.Series(["1.234", "2 345", "0,35", "45 %", "-"])
    assert do_liczb(seria, tysiace_z_kropka=True).tolist()[:4] == [1234, 2345, 0.35, 45]
    assert do_liczb(seria).iloc[0] == pytest.approx(1.234)


@pytest.mark.parametrize("pozycja", POZYCJE)
def test_demo_przechodzi_przez_parser(pozycja):
    df, odrzucone = wczytaj_csv(generuj_demo_csv(pozycja))
    assert odrzucone == 0 and len(df) == 150
    assert df['ID'].is_unique
    for kol in ('Wartość_Numeryczna', 'Zarobki_Numeryczne', 'Wygasa_Data', 'Mnożnik_Ligi', 'Minuty'):
        assert kol in df.columns


def test_nieczytelny_wiek_jest_liczony():
    csv = "Piłkarz;Wiek\nA;23\nB;?\n".encode("utf-8")
    df, odrzucone = wczytaj_csv(csv)
    assert len(df) == 1 and odrzucone == 1


def test_brak_kolumny_pilkarz():
    with pytest.raises(ValueError):
        wczytaj_csv("Imię;Wiek\nA;23\n".encode("utf-8"))


def test_wykryj_pozycje_po_nazwie_pliku():
    pusty = pd.DataFrame()
    assert wykryj_pozycje("BR (1).csv", pusty) == "Bramkarz"
    assert wykryj_pozycje("napastnik.csv", pusty) == "Napastnik"
    assert wykryj_pozycje("cokolwiek.csv", pusty) is None
