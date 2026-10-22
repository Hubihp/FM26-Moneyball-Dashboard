"""
Diagnostyka pliku zapisu FM26 - uruchom lokalnie na swoim zapisie i odeslij wynik.

    python narzedzia/zbadaj_zapis.py "C:/.../Football Manager 26/games/Kariera.fm" [eksport1.csv ...] [--zapisz-nazwy]

Wypisuje i zapisuje do pliku `raport_zapisu.json` (obok zapisu albo w biezacym folderze):
  - wersje gry, date w grze, czas odczytu kazdej czesci zapisu,
  - ile zawodnikow, klubow i lig udalo sie odczytac i przypisac,
  - pokrycie kolumn aplikacji (procent zawodnikow z wartoscia) dla kazdej pozycji,
  - probke Twojej kadry (do porownania z tym, co pokazuje gra),
  - liste lig z liczba klubow i przykladowymi klubami (do sprawdzenia przypisania),
  - (opcjonalnie) nazwy lig rozpoznane ze starych eksportow CSV; z --zapisz-nazwy zapisuje je
    do dane/nazwy_rozgrywek.csv, z ktorego korzysta aplikacja.
Raport jest maly (kilkadziesiat KB), wiec mozna go wkleic lub wyslac zamiast calego zapisu.
Skrypt niczego nie zmienia w zapisie.
"""
import argparse
import json
import sys
import time
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd  # noqa: E402

from fm_moneyball.stale import KOLUMNY_PER_POZYCJA  # noqa: E402
from fm_moneyball.zrodla.csv_fm import wczytaj_csv  # noqa: E402
from fm_moneyball.zrodla.zapis_fm import (PLIK_NAZW_ROZGRYWEK, OpcjeZapisu, kandydaci_lig,  # noqa: E402
                                          ligi_klubow, mapa_nazw_z_csv, sumuj_statystyki,
                                          wczytaj_nazwy_rozgrywek, zapisz_nazwy_rozgrywek, zbuduj_ramki)

KOLUMNY_PROBKI = ['Piłkarz', 'Wiek', 'Pozycja', 'Liga', 'Minuty', 'Cena', 'Płaca', 'Wygasa', 'CA', 'PA',
                  'Liczba goli na 90 min', 'Oczekiwane asysty/90', 'Kluczowe podania z gry/90',
                  'Stracone piłki/90', 'Skuteczność strzałów (%)', 'Uniknięte oczekiwane gole/90',
                  'Skuteczność obron (%)']


def _czas(etykieta, funkcja, czasy):
    start = time.perf_counter()
    wynik = funkcja()
    czasy[etykieta] = round(time.perf_counter() - start, 2)
    print(f"  {etykieta}: {czasy[etykieta]} s")
    return wynik


def main():
    import fmsave

    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("zapis", type=Path)
    parser.add_argument("csv", nargs="*", type=Path, help="stare eksporty CSV z gry (do rozpoznania nazw lig)")
    parser.add_argument("--wyjscie", type=Path, default=Path("raport_zapisu.json"))
    parser.add_argument("--zapisz-nazwy", action="store_true",
                        help=f"zapisz nazwy lig rozpoznane z CSV do {PLIK_NAZW_ROZGRYWEK.name}")
    args = parser.parse_args()

    raport = {"fmsave": fmsave.__version__, "rozmiar_mb": round(args.zapis.stat().st_size / 2**20, 1)}
    czasy = raport["czasy_s"] = {}
    print(f"Zapis: {args.zapis.name} ({raport['rozmiar_mb']} MB), fmsave {fmsave.__version__}")

    with warnings.catch_warnings(record=True) as zlapane:
        warnings.simplefilter("always")
        with fmsave.open(args.zapis) as zapis:
            info = zapis.info
            raport.update(gra=info.game, build=info.build, znany_build=info.known_build,
                          data_w_grze=str(info.game_date), baza=info.db_version)
            print(f"Gra {info.game} build {info.build} (znany: {info.known_build}), data w grze {info.game_date}")
            kluby = _czas("kluby", lambda: list(zapis.clubs()), czasy)
            zawodnicy = _czas("zawodnicy", lambda: list(zapis.players()), czasy)
            statystyki = _czas("statystyki sezonu", lambda: list(zapis.player_season_stats()), czasy)
            try:
                tabele = _czas("tabele ligowe", lambda: list(zapis.league_tables()), czasy)
                rozgrywki = list(zapis.competitions())
            except Exception as e:
                print(f"  tabele ligowe: BLAD {e}")
                raport["blad_tabel_ligowych"] = str(e)
                tabele, rozgrywki = [], []
            zarzadzane = list(zapis.managed_clubs())
    raport["ostrzezenia_fmsave"] = sorted({f"{w.category.__name__}: {w.message}"[:300] for w in zlapane})[:20]

    kandydaci = kandydaci_lig(tabele, rozgrywki, kluby)
    nazwy = wczytaj_nazwy_rozgrywek()
    if args.csv:
        ramki_csv = []
        for plik in args.csv:
            try:
                ramki_csv.append(wczytaj_csv(plik.read_bytes())[0])
            except Exception as e:
                print(f"Pominięto {plik.name}: {e}")
        mapa = mapa_nazw_z_csv(kandydaci, kluby, ramki_csv)
        raport["nazwy_lig_z_csv"] = {str(k): v for k, v in sorted(mapa.items())}
        print(f"Rozpoznane nazwy lig z CSV ({len(mapa)}):", ", ".join(sorted(mapa.values())))
        if args.zapisz_nazwy:
            nazwy = zapisz_nazwy_rozgrywek(mapa)
            print(f"Zapisano nazwy lig: {PLIK_NAZW_ROZGRYWEK}")
        else:
            nowe = set(mapa.values())
            nazwy = {**{k: v for k, v in nazwy.items() if k not in mapa and v not in nowe}, **mapa}
    liga_klubu = ligi_klubow(tabele, rozgrywki, kluby, nazwy, kandydaci=kandydaci)
    rodzaje = pd.Series([str(s.kind) for s in statystyki]).value_counts().to_dict()
    raport["liczniki"] = {
        "kluby": len(kluby), "zawodnicy": len(zawodnicy), "wiersze_statystyk": len(statystyki),
        "wiersze_wg_rodzaju": rodzaje, "tabele_ligowe": len(tabele), "rozgrywki": len(rozgrywki),
        "kluby_z_liga": len(liga_klubu), "ligi": len({l.competition_id for l in liga_klubu.values()}),
        "ligi_z_nazwa": len({l.competition_id for l in liga_klubu.values() if l.nazwa}),
    }
    print("Liczniki:", json.dumps(raport["liczniki"], ensure_ascii=False))

    nazwa_klubu = {k.uid: k.name for k in kluby}
    kluby_ligi = {}
    for uid, liga in liga_klubu.items():
        kluby_ligi.setdefault(liga.etykieta, []).append(nazwa_klubu.get(uid, "?"))
    raport["ligi"] = {
        etykieta: {"kluby": len(lista), "przyklady": sorted(lista)[:3]}
        for etykieta, lista in sorted(kluby_ligi.items(), key=lambda e: -len(e[1]))}
    print("\nLigi (liczba klubów, przykłady):")
    for etykieta, opis in raport["ligi"].items():
        print(f"  {etykieta}: {opis['kluby']} - {', '.join(opis['przyklady'])}")

    opcje = OpcjeZapisu()
    ramki = zbuduj_ramki(zawodnicy, sumuj_statystyki(statystyki, opcje.rodzaj_statystyk), liga_klubu, opcje)
    raport["zawodnicy_na_pozycji"] = {p: len(d) for p, d in ramki.items()}
    raport["pokrycie_kolumn_proc"] = {
        p: {k: round(float(d[k].notna().mean() * 100), 1) for k in KOLUMNY_PER_POZYCJA[p] if k in d.columns}
        for p, d in ramki.items()}
    print("Zawodnicy w analizie:", raport["zawodnicy_na_pozycji"])

    if zarzadzane:
        moj = zarzadzane[0].club_name
        raport["moj_klub"] = moj
        wszyscy = zbuduj_ramki(zawodnicy, sumuj_statystyki(statystyki, opcje.rodzaj_statystyk), liga_klubu,
                               OpcjeZapisu(min_minut=0, tylko_kluby_w_lidze=False))
        kadra = pd.concat([d.assign(Grupa=p) for p, d in wszyscy.items()])
        kadra = kadra[kadra['Klub'] == moj].sort_values('Minuty', ascending=False).head(20)
        kolumny = ['Grupa'] + [k for k in KOLUMNY_PROBKI if k in kadra.columns]
        raport["probka_kadry"] = json.loads(kadra[kolumny].round(2).to_json(orient="records", force_ascii=False))
        print(f"\nTwoja kadra ({moj}) - porównaj z ekranem w grze:")
        with pd.option_context("display.width", 250, "display.max_columns", 30):
            print(kadra[kolumny[:10]].to_string(index=False))

    args.wyjscie.write_text(json.dumps(raport, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print(f"\nRaport zapisany: {args.wyjscie.resolve()}")


if __name__ == "__main__":
    main()
