"""
Diagnostyka pliku zapisu FM26 - uruchom lokalnie na swoim zapisie i odeslij wynik.

    python narzedzia/zbadaj_zapis.py "C:/.../Football Manager 26/games/Kariera.fm" [eksport1.csv ...] [--zapisz-nazwy]

Wypisuje i zapisuje do pliku `raport_zapisu.json` (obok zapisu albo w biezacym folderze):
  - wersje gry, date w grze, czas odczytu kazdej czesci zapisu,
  - ile zawodnikow, klubow i lig udalo sie odczytac i przypisac,
  - pokrycie kolumn aplikacji (procent zawodnikow z wartoscia) dla kazdej pozycji,
  - probke Twojej kadry (do porownania z tym, co pokazuje gra),
  - liste lig z liczba klubow i przykladowymi klubami (do sprawdzenia przypisania),
  - tabele ligowe wygladajace podejrzanie (mieszane kraje, bardzo duze),
  - z --klub NAZWA: wszystkie tabele, w ktorych wystepuje dany klub (do diagnozy przypisania ligi),
  - (opcjonalnie) nazwy lig rozpoznane ze starych eksportow CSV; z --zapisz-nazwy zapisuje je
    do dane/nazwy_rozgrywek.csv, z ktorego korzysta aplikacja.
Raport jest maly (kilkadziesiat KB), wiec mozna go wkleic lub wyslac zamiast calego zapisu.
Skrypt niczego nie zmienia w zapisie.
"""
import argparse
import json
from collections import Counter
import sys
import time
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def _sprawdz_srodowisko():
    """Czytelny komunikat zamiast tracebacku, gdy brakuje Pythona 3.12+ albo bibliotek."""
    import importlib.util
    wymagania = Path(__file__).resolve().parents[1] / "requirements.txt"
    instalacja = f'py -m pip install -r "{wymagania}"' if sys.platform.startswith("win") \
        else f'python3 -m pip install -r "{wymagania}"'
    if sys.version_info < (3, 12):
        sys.exit(f"Potrzebny jest Python 3.12 lub nowszy (masz {sys.version.split()[0]}).\n"
                 "Windows: winget install -e --id Python.Python.3.12, potem otwórz terminal na nowo\n"
                 f"i zainstaluj biblioteki: {instalacja}")
    brakujace = [m for m in ("pandas", "numpy", "fmsave") if importlib.util.find_spec(m) is None]
    if brakujace:
        sys.exit(f"Brakuje bibliotek: {', '.join(brakujace)}.\nZainstaluj je poleceniem:\n    {instalacja}")


_sprawdz_srodowisko()

import pandas as pd  # noqa: E402

from fm_moneyball.kraje import (kraje_z_kotwic, narodowosci_lig, nazwy_auto, podsumuj_kraje,  # noqa: E402
                                wczytaj_nazwy_krajow)
from fm_moneyball.stale import KOLUMNY_PER_POZYCJA  # noqa: E402
from fm_moneyball.zrodla.csv_fm import wczytaj_csv  # noqa: E402
from fm_moneyball.zrodla.zapis_fm import (PLIK_NAZW_UZYTKOWNIKA, OpcjeZapisu, kandydaci_lig,  # noqa: E402
                                          kandydaci_lig_z_terminarza, kluby_drugorzedne,
                                          ligi_klubow, opis_tabeli, podsumuj_ligi, polacz_kandydatow, mapa_nazw_z_csv,
                                          sumuj_statystyki,
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


def _kraje(wiersze, nacja):
    licznik = Counter(nacja.get(w.club_uid) for w in wiersze)
    return {"top": [[k, n] for k, n in licznik.most_common(3) if k is not None],
            "bez_kraju": licznik.get(None, 0)}


def _opis(tabela, nacja, baza, nazwa_klubu=None):
    wiersze, kraj, udzial = opis_tabeli(tabela, nacja)
    opis = {"competition_id": tabela.competition_id, "database_id": baza.get(tabela.competition_id),
            "wiersze": len(tabela.rows), "pierwsze_druzyny": len(wiersze), "kraj": kraj,
            "udzial_kraju": round(udzial, 2), "kraje": _kraje(tabela.rows, nacja)}
    if nazwa_klubu is not None:
        opis["przyklady"] = [nazwa_klubu.get(w.club_uid, w.club_name) for w in tabela.rows[:6]]
    return opis


def podejrzane_tabele(tabele, liga_klubu, nacja, baza, kluby):
    """Tabele uzyte jako liga, ktore maja mieszane kraje albo bardzo duzo klubow."""
    nazwa_klubu = {k.uid: k.name for k in kluby}
    uzyte = {l.competition_id for l in liga_klubu.values()}
    wynik = []
    for tabela in tabele:
        if tabela.competition_id not in uzyte:
            continue
        opis = _opis(tabela, nacja, baza, nazwa_klubu)
        if opis["udzial_kraju"] < 0.9 or opis["pierwsze_druzyny"] > 30:
            wynik.append(opis)
    return wynik[:40]


def porownaj_ligi(z_terminarza, z_tabel, kluby, nazwy, limit=15):
    """Kluby, dla ktorych liga z terminarza i liga z tabel sie roznia (do recznej kontroli)."""
    liga_t = ligi_klubow([], [], kluby, nazwy, kandydaci=z_terminarza)
    liga_tab = ligi_klubow([], [], kluby, nazwy, kandydaci=z_tabel)
    nazwa_klubu = {k.uid: k.name for k in kluby}
    licznik = Counter()
    przyklady = []
    for uid in set(liga_t) | set(liga_tab):
        a, b = liga_tab.get(uid), liga_t.get(uid)
        if a is None:
            licznik["tylko_terminarz"] += 1
            klucz = "tylko_terminarz"
        elif b is None:
            licznik["tylko_tabele"] += 1
            continue
        elif a.competition_id != b.competition_id:
            licznik["rozne"] += 1
            klucz = "rozne"
        else:
            licznik["zgodne"] += 1
            continue
        if len(przyklady) < limit:
            mecze = z_terminarza[uid][0].rozmiar
            przyklady.append({"klub": nazwa_klubu.get(uid), "rodzaj": klucz,
                              "tabele": None if a is None else a.etykieta, "terminarz": b.etykieta,
                              "mecze": mecze})
    return {"liczniki": dict(licznik), "przyklady": przyklady}


def opisz_klub(nazwa, kluby, tabele, liga_klubu, nacja, baza, mecze=(), data_gry=None):
    """Wszystko, co wplywa na przypisanie ligi klubowi: jego druzyny i tabele, w ktorych wystepuja."""
    szukana = nazwa.strip().lower()
    pasujace = [k for k in kluby if szukana in {(k.name or "").lower(), (k.short_name or "").lower()}]
    pasujace = pasujace or [k for k in kluby if szukana in (k.name or "").lower()][:3]
    if not pasujace:
        return {"szukano": nazwa, "blad": "nie znaleziono klubu"}
    wynik = []
    for klub in pasujace:
        druzyny = {t.team_id: t for t in klub.teams}
        tabele_klubu = []
        for tabela in tabele:
            for w in tabela.rows:
                if w.club_uid == klub.uid or w.team_id in druzyny:
                    opis = _opis(tabela, nacja, baza)
                    opis.update(team_id=w.team_id, team_slot=w.team_slot, wiersz_club_uid=w.club_uid,
                                pozycja=w.position)
                    tabele_klubu.append(opis)
        terminarz = Counter()
        for m in mecze:
            if m.round is None and m.competition_id is not None and klub.uid in (m.home_club_uid, m.away_club_uid):
                if data_gry is None or m.date is None or abs((m.date - data_gry).days) <= 300:
                    terminarz[m.competition_id] += 1
        liga = liga_klubu.get(klub.uid)
        wynik.append({
            "szukano": nazwa, "klub": klub.name, "uid": klub.uid, "nation_id": klub.nation_id,
            "fa_nation_id": klub.fa_nation_id, "parent_club": klub.parent_club_name,
            "druzyny": [[t.team_id, t.slot, t.club_uid, t.is_affiliate] for t in klub.teams],
            "wybrana_liga": None if liga is None else {"competition_id": liga.competition_id,
                                                       "database_id": liga.database_id, "nazwa": liga.nazwa},
            "tabele": tabele_klubu,
            "terminarz_mecze_bez_rundy": [[comp, baza.get(comp), ile] for comp, ile in terminarz.most_common(8)],
        })
    return wynik


def _znany(zawodnik):
    """Klucz sortowania 'najbardziej znanych': reputacja biezaca, potem wartosc transferowa."""
    reputacja = getattr(getattr(zawodnik, "reputation", None), "current", None) or 0
    return (reputacja, getattr(zawodnik, "transfer_value", None) or 0)


def lista_krajow(zawodnicy, nazwy, zrodla=None, przyklady=5, kontrolne=2):
    """
    Zawodnicy zapisu -> linie tekstu: najpierw kraje bez nazwy (wszystkie, wg liczby zawodnikow),
    kazdy z kilkoma najbardziej znanymi zawodnikami do sprawdzenia narodowosci w internecie;
    potem kontrolnie kraje z nazwa (zrodlo nazwy + 2 zawodnikow).
    """
    zrodla = zrodla or {}
    po_kraju = {}
    for z in zawodnicy:
        if getattr(z, "nation_id", None) is not None:
            po_kraju.setdefault(z.nation_id, []).append(z)

    def opis(z):
        return f"{z.name} ({getattr(z, 'club_name', None) or 'bez klubu'}, {getattr(z, 'age', None) or '?'})"

    kolejnosc = sorted(po_kraju, key=lambda k: -len(po_kraju[k]))
    linie = ["# KRAJE BEZ NAZWY: id | zawodnikow | najbardziej znani zawodnicy (klub, wiek)"]
    for kraj in kolejnosc:
        if nazwy.get(kraj):
            continue
        znani = sorted(po_kraju[kraj], key=_znany, reverse=True)[:przyklady]
        linie.append(f"{kraj} | {len(po_kraju[kraj])} | " + "; ".join(opis(z) for z in znani))
    linie.append("")
    linie.append("# KRAJE Z NAZWA (kontrolnie): id | nazwa | zrodlo | zawodnicy")
    for kraj in kolejnosc:
        if not nazwy.get(kraj):
            continue
        znani = sorted(po_kraju[kraj], key=_znany, reverse=True)[:kontrolne]
        linie.append(f"{kraj} | {nazwy[kraj]} | {zrodla.get(kraj, '?')} | " + "; ".join(opis(z) for z in znani))
    return linie


def tryb_kraje(sciezka, wyjscie=Path("kraje_bez_nazwy.txt")):
    """Szybki tryb --kraje: tylko to, co potrzebne do nazw krajow (bez statystyk i kontuzji)."""
    import fmsave
    from fm_moneyball.zrodla.zapis_fm import kandydaci_lig_lacznie

    print(f"Odczyt zapisu {sciezka.name} (tylko kraje)...")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        with fmsave.open(sciezka) as zapis:
            kluby = list(zapis.clubs())
            kandydaci = kandydaci_lig_lacznie(zapis, kluby, zapis.info.game_date)
            liga_klubu = ligi_klubow([], [], kluby, wczytaj_nazwy_rozgrywek(), kandydaci=kandydaci)
            zawodnicy = list(zapis.players())
    zrodla = {}
    nazwy = {}
    for zrodlo, mapa in (("kluby", kraje_z_kotwic(kluby, zawodnicy)),
                         ("liga", nazwy_auto(podsumuj_ligi(liga_klubu, kluby,
                                                           narodowosci=narodowosci_lig(zawodnicy, liga_klubu)))),
                         ("ręcznie", wczytaj_nazwy_krajow())):
        nazwy.update(mapa)
        zrodla.update(dict.fromkeys(mapa, zrodlo))
    linie = lista_krajow(zawodnicy, nazwy, zrodla)
    wyjscie.write_text("\n".join(linie) + "\n", encoding="utf-8")
    print("\n".join(linie[:15]))
    print(f"...\nZapisano: {wyjscie.resolve()}  (wklej jego zawartosc do czatu)")
    return linie


def main():
    import fmsave

    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("zapis", type=Path)
    parser.add_argument("csv", nargs="*", type=Path, help="stare eksporty CSV z gry (do rozpoznania nazw lig)")
    parser.add_argument("--wyjscie", type=Path, default=Path("raport_zapisu.json"))
    parser.add_argument("--klub", action="append", default=[],
                        help="nazwa klubu do szczegolowej diagnozy przypisania ligi (mozna podac wiele razy)")
    parser.add_argument("--kraje", action="store_true",
                        help="tylko lista krajow bez nazwy z najbardziej znanymi zawodnikami (kraje_bez_nazwy.txt)")
    parser.add_argument("--zapisz-nazwy", action="store_true",
                        help=f"zapisz nazwy lig rozpoznane z CSV do {PLIK_NAZW_UZYTKOWNIKA}")
    args = parser.parse_args()
    if args.kraje:
        tryb_kraje(args.zapis)
        return

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
            rozgrywki = list(zapis.competitions())
            try:
                mecze = _czas("terminarz", lambda: list(zapis.fixtures()), czasy)
            except Exception as e:
                print(f"  terminarz: BLAD {e}")
                raport["blad_terminarza"] = str(e)
                mecze = []
            try:
                tabele = _czas("tabele ligowe", lambda: list(zapis.league_tables()), czasy)
            except Exception as e:
                print(f"  tabele ligowe: BLAD {e}")
                raport["blad_tabel_ligowych"] = str(e)
                tabele = []
            zarzadzane = list(zapis.managed_clubs())
    raport["ostrzezenia_fmsave"] = sorted({f"{w.category.__name__}: {w.message}"[:300] for w in zlapane})[:20]

    drugorzedne = kluby_drugorzedne(kluby)
    odrzucone = Counter()
    z_terminarza = kandydaci_lig_z_terminarza(mecze, rozgrywki, kluby, info.game_date,
                                              drugorzedne=drugorzedne, statystyki=odrzucone)
    z_tabel = kandydaci_lig(tabele, rozgrywki, kluby, drugorzedne=drugorzedne)
    kandydaci = polacz_kandydatow(z_terminarza, z_tabel)
    raport["terminarz"] = {"mecze": len(mecze), "kluby_z_liga_z_terminarza": len(z_terminarza),
                           "kluby_z_liga_z_tabel": len(z_tabel), "kluby_drugorzedne": len(drugorzedne),
                           "odrzucone_rozgrywki": dict(odrzucone)}
    print("Terminarz:", json.dumps(raport["terminarz"], ensure_ascii=False))
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
            zapisz_nazwy_rozgrywek(mapa)
            nazwy = wczytaj_nazwy_rozgrywek()
            print(f"Zapisano nazwy lig: {PLIK_NAZW_UZYTKOWNIKA}")
        else:
            nowe = set(mapa.values())
            nazwy = {**{k: v for k, v in nazwy.items() if k not in mapa and v not in nowe}, **mapa}
    liga_klubu = ligi_klubow(tabele, rozgrywki, kluby, nazwy, kandydaci=kandydaci)
    raport["porownanie_lig"] = porownaj_ligi(z_terminarza, z_tabel, kluby, nazwy)
    print("Terminarz vs tabele:", json.dumps(raport["porownanie_lig"]["liczniki"], ensure_ascii=False))
    rodzaje = pd.Series([str(s.kind) for s in statystyki]).value_counts().to_dict()
    raport["liczniki"] = {
        "kluby": len(kluby), "zawodnicy": len(zawodnicy), "wiersze_statystyk": len(statystyki),
        "wiersze_wg_rodzaju": rodzaje, "tabele_ligowe": len(tabele), "rozgrywki": len(rozgrywki),
        "kluby_z_liga": len(liga_klubu), "ligi": len({l.competition_id for l in liga_klubu.values()}),
        "ligi_z_nazwa": len({l.competition_id for l in liga_klubu.values() if l.nazwa}),
    }
    print("Liczniki:", json.dumps(raport["liczniki"], ensure_ascii=False))

    nacja = {k.uid: k.nation_id for k in kluby}
    baza = {r.id: r.database_id for r in rozgrywki}
    raport["tabele_podejrzane"] = podejrzane_tabele(tabele, liga_klubu, nacja, baza, kluby)
    if raport["tabele_podejrzane"]:
        print(f"Podejrzane tabele ligowe: {len(raport['tabele_podejrzane'])} (szczegóły w raporcie)")
    if args.klub:
        raport["kluby_diagnoza"] = [opisz_klub(n, kluby, tabele, liga_klubu, nacja, baza, mecze, info.game_date)
                                    for n in args.klub]
        for opis in raport["kluby_diagnoza"]:
            print(f"\n--klub {json.dumps(opis, ensure_ascii=False, default=str)[:2000]}")

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
    naturalne = zbuduj_ramki(zawodnicy, sumuj_statystyki(statystyki, opcje.rodzaj_statystyk), liga_klubu,
                             OpcjeZapisu(wszystkie_naturalne_pozycje=True))
    raport["zawodnicy_na_pozycji_wszystkie_naturalne"] = {p: len(d) for p, d in naturalne.items()}
    print("Ze wszystkimi naturalnymi pozycjami:", raport["zawodnicy_na_pozycji_wszystkie_naturalne"])

    # Narodowosci: nazwy wyprowadzone z nazwanych lig i kraje, ktore trzeba nazwac recznie
    z_kotwic = kraje_z_kotwic(kluby, zawodnicy)
    z_lig = nazwy_auto(podsumuj_ligi(liga_klubu, kluby, narodowosci=narodowosci_lig(zawodnicy, liga_klubu)))
    nazwy_krajow = {**z_kotwic, **z_lig, **wczytaj_nazwy_krajow()}
    raport["kraje_zrodla"] = {"z_lig": len(z_lig), "z_klubow_kotwic": len(z_kotwic)}
    wszyscy_w_analizie = pd.concat(list(ramki.values())).drop_duplicates('UID') if ramki else None
    kraje = podsumuj_kraje(wszyscy_w_analizie, nazwy_krajow)
    raport["kraje_z_nazwa"] = {str(k["id"]): k["nazwa"] for k in kraje if k["nazwa"]}
    raport["kraje_bez_nazwy"] = [k for k in kraje if not k["nazwa"]][:25]
    print(f"Kraje z nazwą: {len(raport['kraje_z_nazwa'])} (z lig: {len(z_lig)}, z klubów: {len(z_kotwic)}), "
          f"bez nazwy: {sum(1 for k in kraje if not k['nazwa'])}")

    if zarzadzane:
        moj, moj_uid = zarzadzane[0].club_name, zarzadzane[0].club_uid
        raport["moj_klub"] = moj
        wszyscy = zbuduj_ramki(zawodnicy, sumuj_statystyki(statystyki, opcje.rodzaj_statystyk), liga_klubu,
                               OpcjeZapisu(min_minut=0, tylko_kluby_w_lidze=False))
        kadra = pd.concat([d.assign(Grupa=p) for p, d in wszyscy.items()])
        kadra = kadra[kadra['Klub_UID'] == moj_uid].sort_values('Minuty', ascending=False).head(20)
        kolumny = ['Grupa'] + [k for k in KOLUMNY_PROBKI if k in kadra.columns]
        raport["probka_kadry"] = json.loads(kadra[kolumny].round(2).to_json(orient="records", force_ascii=False))
        print(f"\nTwoja kadra ({moj}) - porównaj z ekranem w grze:")
        with pd.option_context("display.width", 250, "display.max_columns", 30):
            print(kadra[kolumny[:10]].to_string(index=False))

    args.wyjscie.write_text(json.dumps(raport, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print(f"\nRaport zapisany: {args.wyjscie.resolve()}")


if __name__ == "__main__":
    main()
