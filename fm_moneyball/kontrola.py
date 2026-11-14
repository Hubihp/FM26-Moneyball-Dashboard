"""
Kontrola jakosci odczytu zapisu: czy statystyki odczytane przez fmsave zgadzaja sie z tym, co gra pokazuje gdzie
indziej. Biblioteka czyta wersje gry, ktorych jej autorzy jeszcze nie zweryfikowali - ta kontrola pokazuje, czy
w tym konkretnym zapisie dane wygladaja wiarygodnie, i wskazuje ligi, w ktorych cos sie nie zgadza.

Sprawdzenia:
- gole zawodnikow klubu (suma statystyk ligowych) a gole klubu w tabelach lig; roznica to glownie gole samobojcze
  rywali, wiec suma zawodnikow moze byc nieco nizsza; porownywane tylko kluby, ktorych minuty zawodnikow pasuja
  do liczby meczow w tabelach (11 x 90 na mecz; czerwone kartki daja mniej),
- celne podania <= podania, strzaly celne <= strzaly (dla kazdego zawodnika),
- gole a xG w calej lidze (w kazdej lidze gra strzela mniej wiecej tyle, ile wynika z xG),
- pola puste w calym zapisie (gra ich nie zapisuje - np. pressing w FM27).
"""
from collections import defaultdict

MIN_GOLI_TABELI = 8            # klub z mniejsza liczba goli w tabeli nie jest porownywany (za malo, by ocenic)
MIN_MECZOW_TABELI = 3
MIN_KLUBOW_OCENY = 6           # mniej porownywalnych klubow w lidze - "mało danych" zamiast oceny
GOLE_ZAKRES = (0.85, 1.03)     # suma goli zawodnikow / gole w tabeli (samobojcze rywali obnizaja)
MINUTY_ZAKRES = (0.86, 1.03)   # minuty / (mecze x 990)
GOLE_XG_ZAKRES = (0.7, 1.4)    # gole / xG w calej lidze
PROG_UWAGI = 0.2               # udzial klubow niezgodnych: powyzej - "uwaga"
PROG_BLEDU = 0.5               # powyzej - "błąd" (ostrzezenie na gorze aplikacji)
MIN_KLUBOW_OSTRZEZENIA = 8


def _tabele_rozgrywek(tabele):
    """Najwieksza tabela kazdych rozgrywek (inne etapy i fragmenty tych samych rozgrywek pomijane)."""
    wynik = {}
    for t in tabele or ():
        comp = getattr(t, "competition_id", None)
        if comp is not None and len(t.rows) > len(getattr(wynik.get(comp), "rows", ())):
            wynik[comp] = t
    return wynik


def sprawdz_ligi(tabele, druzyny, liga_klubu):
    """
    Gole i minuty klubow wzgledem tabel lig. Statystyki ligowe zapisu obejmuja wszystkie ligi klubu w sezonie (np.
    w Brazylii stanowa i krajowa), wiec klub porownujemy z suma wszystkich jego tabel. Klub, ktorego minuty nie
    pasuja do tych tabel (liga bez tabeli w zapisie, sezon kalendarzowy z inna data), jest nieporownywalny - to nie
    blad odczytu, tylko brak punktu odniesienia. U klubow porownywalnych sprawdzane sa gole.
    tabele: rekordy fmsave LeagueTable (competition_id, rows z club_uid, played, goals_for); druzyny: {club_uid:
    {"goals", "minutes", "expected_goals"}}; liga_klubu: {club_uid: Liga}. Zwraca liste lig: {competition_id,
    klucz, kluby (porownywalne), nieporownywalne, gole_niezgodne, gole_xg, status}.
    """
    # tylko tabele rozgrywek, ktore sa liga jakiegos klubu (bez fazy ligowej pucharow europejskich)
    ligowe = {liga.competition_id for liga in (liga_klubu or {}).values()}
    tabele_klubu = defaultdict(dict)          # club_uid -> {competition_id: (mecze, gole)}
    for comp, t in _tabele_rozgrywek(tabele).items():
        if comp not in ligowe:
            continue
        for r in t.rows:
            if r.club_uid is not None and getattr(r, "played", None):
                tabele_klubu[r.club_uid][comp] = (r.played, getattr(r, "goals_for", None) or 0)
    grupy = defaultdict(list)
    for uid, liga in (liga_klubu or {}).items():
        grupy[(liga.competition_id, liga.database_id)].append(uid)

    def odniesienie(uid, comp, minuty):
        """(mecze, gole) z tabel, do ktorych pasuja minuty: sama liga klubu albo suma jego lig (np. stanowa
        i krajowa w Brazylii); None - zadna kombinacja nie pasuje."""
        wlasne = tabele_klubu[uid]
        warianty = ([wlasne[comp]] if comp in wlasne else []) + \
            ([tuple(map(sum, zip(*wlasne.values())))] if len(wlasne) > 1 else [])
        for mecze_t, gole_t in warianty:
            if mecze_t >= MIN_MECZOW_TABELI and MINUTY_ZAKRES[0] <= minuty / (mecze_t * 990) <= MINUTY_ZAKRES[1]:
                return mecze_t, gole_t
        return None
    wynik = []
    for (comp, klucz), uidy in grupy.items():
        kluby = nieporownywalne = gole_zle = 0
        gole_suma = xg_suma = 0.0
        for uid in uidy:
            d = (druzyny or {}).get(uid)
            if not d or d.get("minutes") is None or not tabele_klubu.get(uid):
                continue
            if max(m for m, _ in tabele_klubu[uid].values()) < MIN_MECZOW_TABELI:
                continue         # za wczesnie w sezonie, by porownywac
            odn = odniesienie(uid, comp, d["minutes"])
            if odn is None:
                nieporownywalne += 1
                continue
            kluby += 1
            if odn[1] >= MIN_GOLI_TABELI and d.get("goals") is not None:
                gole_zle += not GOLE_ZAKRES[0] <= d["goals"] / odn[1] <= GOLE_ZAKRES[1]
            if d.get("goals") is not None and d.get("expected_goals") is not None:
                gole_suma += d["goals"]
                xg_suma += d["expected_goals"]
        if not kluby and not nieporownywalne:
            continue
        gole_xg = round(gole_suma / xg_suma, 2) if xg_suma > 0 else None
        udzial = gole_zle / kluby if kluby else 0.0
        xg_zle = gole_xg is not None and not GOLE_XG_ZAKRES[0] <= gole_xg <= GOLE_XG_ZAKRES[1]
        if not kluby:
            status = "brak odniesienia"
        elif kluby < MIN_KLUBOW_OCENY:
            status = "mało danych"
        else:
            status = "błąd" if udzial > PROG_BLEDU else "uwaga" if udzial > PROG_UWAGI or xg_zle else "ok"
        wynik.append({"competition_id": comp, "klucz": klucz, "kluby": kluby, "nieporownywalne": nieporownywalne,
                      "gole_niezgodne": gole_zle, "gole_xg": gole_xg, "status": status})
    kolejnosc = {"błąd": 0, "uwaga": 1, "ok": 2, "mało danych": 3, "brak odniesienia": 4}
    return sorted(wynik, key=lambda x: (kolejnosc[x["status"]], -x["kluby"]))


def sprawdz_pola(liczniki):
    """Testy pol statystyk zawodnikow: {nazwa, opis, status, liczba} dla kazdego sprawdzenia."""
    liczniki = liczniki or {}
    pary = (("passes_completed", "passes_attempted", "Celne podania ≤ podania"),
            ("shots_on_target", "shots", "Strzały celne ≤ strzały"))
    wynik = []
    for celne, wszystkie, nazwa in pary:
        sprawdzeni = zle = 0
        for s in liczniki.values():
            a, b = s.get(celne), s.get(wszystkie)
            if a is None or b is None:
                continue
            sprawdzeni += 1
            zle += a > b + 0.5
        if sprawdzeni:
            udzial = zle / sprawdzeni
            wynik.append({"nazwa": nazwa, "liczba": zle, "sprawdzeni": sprawdzeni,
                          "status": "ok" if udzial <= 0.01 else "uwaga" if udzial <= 0.05 else "błąd",
                          "opis": "wszyscy zawodnicy w porządku" if not zle
                          else f"niezgodnych zawodników: {zle} z {sprawdzeni}"})
    obecne = defaultdict(int)
    for s in liczniki.values():
        for pole, w in s.items():
            if w is not None and not isinstance(w, dict):
                obecne[pole] += 1
    from fm_moneyball.zrodla.zapis_fm import POLA_LICZNIKOW
    puste = [p for p in POLA_LICZNIKOW if liczniki and not obecne.get(p)]
    wynik.append({"nazwa": "Pola, których zapis nie podaje", "liczba": len(puste), "sprawdzeni": len(POLA_LICZNIKOW),
                  "status": "ok" if not puste else "info",
                  "opis": "brak" if not puste else ", ".join(puste) + " - pominięte w SCORE"})
    return wynik


def kontrola(tabele, druzyny, liga_klubu, liczniki):
    """Pelna kontrola odczytu: {"ligi": [...], "pola": [...], "ostrzezenie": tekst albo None}."""
    ligi = sprawdz_ligi(tabele, druzyny, liga_klubu)
    pola = sprawdz_pola(liczniki)
    zle = [x for x in ligi if x["status"] == "błąd" and x["kluby"] >= MIN_KLUBOW_OSTRZEZENIA]
    return {"ligi": ligi, "pola": pola, "ostrzezenie_ligi": [x["klucz"] for x in zle],
            "zle_pola": [p["nazwa"] for p in pola if p["status"] == "błąd"]}
