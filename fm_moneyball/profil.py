"""
Profil druzyny na tle ligi (w stylu analiz Gradient Sports): statystyki zespolowe z piłka, bez piłki
i fizyczne, z miejscem w lidze; atletyzm skladu; najwieksze zmiany wzgledem poprzedniego sezonu.

Zrodlo: sumy statystyk sezonu zawodnikow kazdego klubu z zapisu gry (wiersz zawodnika liczy sie dla
klubu, w ktorym gral) i tabela ligi (liczba meczow, punkty, bramki). Bez zapisu (demo, CSV) sumy sa
przyblizane z danych zawodnikow (per 90 x minuty), a wskazniki bez danych sa pomijane.

Atletyzm zawodnika (0-100, 50 = srednia dla pozycji): dystans/90 i sprinty/90 przeliczone na z-score
w obrebie rodziny pozycji wsrod zawodnikow ligi z co najmniej 25% maksymalnej liczby minut, srednia
obu z-score'ow zamieniona na percentyl. Wynik druzyny = srednia wazona minutami.
"""
import numpy as np
import pandas as pd

from fm_moneyball.stale import RODZINA_POZYCJI

MECZ_MINUT = 990            # 11 zawodnikow x 90 minut - przyblizenie liczby meczow bez tabeli
PROG_MINUT_ATLETYZMU = 0.25  # czesc maksymalnej liczby minut w lidze (jak Gradient: 25%)
MALA_PROBA_MECZOW = 10
METRYKI_ATLETYZMU = ('Dystans (km)/90', 'Sprinty/90')

# Kolumna per 90 zawodnika -> licznik druzyny (przyblizenie bez zapisu)
_PER90_LICZNIK = {
    "Liczba goli na 90 min": "goals", "Próby podań/90": "passes_attempted",
    "Podania progresywne/90": "progressive_passes", "Kluczowe podania z gry/90": "key_passes",
    "Stworzone 100% sytuacje/90": "clear_cut_chances_created", "Udane dośrodkowania/90": "crosses_completed",
    "Liczba dryblingów/90": "dribbles", "Przechwyty/90": "interceptions", "Odzyskane piłki/90": "possession_won",
    "Stracone piłki/90": "possession_lost", "Udane próby pressingu/90": "pressures_completed",
    "Sprinty/90": "high_intensity_sprints", "Dystans (km)/90": "distance_km",
}


def _na_mecz(pole):
    return lambda d, m: d.get(pole) / m if d.get(pole) is not None and m else None


def _procent(a, b):
    return lambda d, m: d[a] / d[b] * 100 if d.get(a) is not None and d.get(b) else None


def _iloraz(a, b):
    return lambda d, m: d[a] / d[b] if d.get(a) is not None and d.get(b) else None


# (sekcja, nazwa, funkcja(sumy, mecze), wyzej = lepiej, format, opis)
METRYKI = [
    ("Wyniki", "Punkty na mecz", _na_mecz("_punkty"), True, "dec2", "z tabeli ligi"),
    ("Wyniki", "Gole na mecz", _na_mecz("_gole"), True, "dec2", "z tabeli ligi"),
    ("Wyniki", "Stracone gole na mecz", _na_mecz("_stracone"), False, "dec2", "z tabeli ligi"),
    ("Wyniki", "Średnia ocena zawodników", lambda d, m: d.get("ocena"), True, "dec2", "ważona liczbą meczów"),
    ("Z piłką", "Próby podań na mecz", _na_mecz("passes_attempted"), True, "dec1", "odpowiednik posiadania piłki"),
    ("Z piłką", "Celność podań (%)", _procent("passes_completed", "passes_attempted"), True, "dec1", ""),
    ("Z piłką", "Podania progresywne na mecz", _na_mecz("progressive_passes"), True, "dec1",
     "odpowiednik podań przerywających linie"),
    ("Z piłką", "Kluczowe podania na mecz", _na_mecz("key_passes"), True, "dec1", "podania do groźnej strefy"),
    ("Z piłką", "100% sytuacje na mecz", _na_mecz("clear_cut_chances_created"), True, "dec2", "stworzone"),
    ("Z piłką", "Strzały na mecz", _na_mecz("shots"), True, "dec1", ""),
    ("Z piłką", "xG na mecz", _na_mecz("expected_goals"), True, "dec2", ""),
    ("Z piłką", "xG na strzał", _iloraz("expected_goals", "shots"), True, "dec3", "jakość sytuacji"),
    ("Z piłką", "Gole − xG na mecz", lambda d, m: (d["goals"] - d["expected_goals"]) / m
     if d.get("goals") is not None and d.get("expected_goals") is not None and m else None, True, "zmiana2",
     "skuteczność wykończenia (gole zawodników)"),
    ("Z piłką", "Celne dośrodkowania (%)", _procent("crosses_completed", "crosses_attempted"), True, "dec1", ""),
    ("Z piłką", "Dryblingi na mecz", _na_mecz("dribbles"), True, "dec1", ""),
    ("Z piłką", "Straty piłki na mecz", _na_mecz("possession_lost"), False, "dec1", "mniej = lepiej"),
    ("Bez piłki", "Skuteczność odbiorów (%)", _procent("tackles_completed", "tackles_attempted"), True, "dec1",
     "odpowiednik wygranych starć"),
    ("Bez piłki", "Wygrane główki (%)", _procent("headers_won", "aerial_challenges_attempted"), True, "dec1", ""),
    ("Bez piłki", "Przechwyty na mecz", _na_mecz("interceptions"), True, "dec1", ""),
    ("Bez piłki", "Odzyskane piłki na mecz", _na_mecz("possession_won"), True, "dec1", ""),
    ("Bez piłki", "Skuteczność pressingu (%)", _procent("pressures_completed", "pressures_attempted"), True,
     "dec1", ""),
    ("Bez piłki", "Udany pressing na mecz", _na_mecz("pressures_completed"), True, "dec1", ""),
    ("Bez piłki", "Bloki na mecz", _na_mecz("blocks"), True, "dec1", ""),
    ("Bez piłki", "Wybicia na mecz", _na_mecz("clearances"), True, "dec1", ""),
    ("Bez piłki", "Faule na mecz", _na_mecz("fouls_made"), False, "dec1", "mniej = lepiej"),
    ("Bez piłki", "Kartki na mecz", lambda d, m: (d["yellow_cards"] + 2 * d["red_cards"]) / m
     if d.get("yellow_cards") is not None and d.get("red_cards") is not None and m else None, False, "dec2",
     "czerwona = 2; mniej = lepiej"),
    ("Bez piłki", "Błędy prowadzące do gola", lambda d, m: d.get("mistakes_leading_to_goal"), False, "int",
     "w sezonie; mniej = lepiej"),
    ("Fizycznie", "Dystans na mecz (km)", _na_mecz("distance_km"), True, "dec1", "cała drużyna, ze zmiennikami"),
    ("Fizycznie", "Sprinty na mecz", _na_mecz("high_intensity_sprints"), True, "dec1", ""),
]


def druzyny_z_zawodnikow(zawodnicy):
    """Przyblizone sumy druzyn z danych zawodnikow (demo, CSV): per 90 x minuty / 90."""
    if zawodnicy is None or zawodnicy.empty or 'Klub_UID' not in zawodnicy.columns:
        return {}
    wynik = {}
    for uid, grupa in zawodnicy[zawodnicy['Klub_UID'].notna()].groupby('Klub_UID'):
        minuty = grupa['Minuty'].fillna(0)
        d = {"nazwa": str(grupa['Klub'].iloc[0]), "minutes": float(minuty.sum()), "_mecze": minuty.sum() / MECZ_MINUT}
        for kolumna, licznik in _PER90_LICZNIK.items():
            if kolumna in grupa.columns and grupa[kolumna].notna().any():
                d[licznik] = float((grupa[kolumna].fillna(0) * minuty / 90).sum())
        wynik[uid] = d
    return wynik


def tabela_profilu(druzyny, kluby, tabela=None):
    """
    Sumy druzyn (tylko kluby ligi) + tabela -> DataFrame: wiersz = klub, kolumny = metryki,
    'Klub', 'Mecze'. Liczba meczow z tabeli, a bez niej - z minut.
    """
    wiersze_tabeli = {w["club_uid"]: w for w in (tabela or {}).get("wiersze", [])}
    wiersze = {}
    for uid in kluby:
        d = dict(druzyny.get(uid) or {})
        if not d:
            continue
        t = wiersze_tabeli.get(uid)
        if t:
            d.update(_punkty=t["punkty"], _gole=t["gole"], _stracone=t["stracone"])
            mecze = t["mecze"]
        else:
            mecze = round(d.get("_mecze") or (d.get("minutes", 0) / MECZ_MINUT))
        wiersz = {"Klub": (t or {}).get("klub") or d.get("nazwa"), "Mecze": mecze}
        for _, nazwa, funkcja, *_ in METRYKI:
            try:
                wartosc = funkcja(d, mecze)
            except (KeyError, TypeError, ZeroDivisionError):
                wartosc = None
            wiersz[nazwa] = np.nan if wartosc is None else float(wartosc)
        wiersze[uid] = wiersz
    return pd.DataFrame.from_dict(wiersze, orient='index')


def porownanie(profil, moj_uid):
    """Metryki mojej druzyny: wartosc, srednia ligi, miejsce (1 = najlepsze), liczba klubow, rozklad."""
    sekcje = {}
    if moj_uid not in profil.index:
        return sekcje
    for sekcja, nazwa, _, wyzej, fmt, opis in METRYKI:
        wartosci = profil[nazwa].dropna()
        if moj_uid not in wartosci.index or len(wartosci) < 2:
            continue
        miejsca = wartosci.rank(ascending=not wyzej, method='min')
        sekcje.setdefault(sekcja, []).append({
            "nazwa": nazwa, "wartosc": float(wartosci[moj_uid]), "srednia": float(wartosci.mean()),
            "miejsce": int(miejsca[moj_uid]), "n": int(len(wartosci)), "wyzej_lepiej": wyzej, "format": fmt,
            "opis": opis,
            "rozklad": [{"klub": str(profil.at[u, 'Klub']), "wartosc": float(v), "moj": bool(u == moj_uid)}
                        for u, v in wartosci.sort_values(ascending=not wyzej).items()],
        })
    return sekcje


def podsumowanie(sekcje, mecze, ile=3):
    """Najmocniejsze i najslabsze strony (po miejscu w lidze) + ostrzezenie o malej probie."""
    wszystkie = [m for sekcja, lista in sekcje.items() if sekcja != "Wyniki" for m in lista]
    wzgledne = sorted(wszystkie, key=lambda m: (m["miejsce"] - 1) / max(m["n"] - 1, 1))
    mocne = [m for m in wzgledne if m["miejsce"] <= max(1, m["n"] // 4)][:ile]
    slabe = [m for m in reversed(wzgledne) if m["miejsce"] > m["n"] - max(1, m["n"] // 4)][:ile]
    skrot = lambda m: {"nazwa": m["nazwa"], "miejsce": m["miejsce"], "n": m["n"]}   # noqa: E731
    return {"mocne": [skrot(m) for m in mocne], "slabe": [skrot(m) for m in slabe],
            "mala_proba": mecze is not None and mecze < MALA_PROBA_MECZOW}


def _rodzina(zawodnicy):
    pula = zawodnicy['Pula_główna'] if 'Pula_główna' in zawodnicy.columns else zawodnicy.get('Pula')
    if pula is None:
        return pd.Series("wszyscy", index=zawodnicy.index)
    return pula.map(lambda p: RODZINA_POZYCJI.get(p, p) if isinstance(p, str) else "inne")


def atletyzm(zawodnicy, kluby, moj_uid, nazwy_klubow=None, mecze=None, sklady=None):
    """
    -> None (brak danych o dystansie i sprintach) albo slownik: prog minut, metryki, moi zawodnicy
    (wynik 0-100), ranking klubow (srednia wazona minutami), miejsce mojego klubu.
    Prog minut: 25% minut mozliwych w lidze (mecze x 90); bez liczby meczow - 25% maksimum minut
    (maksimum bywa zawyzone u zawodnikow po transferze z ligi o innym kalendarzu).
    sklady ({club_uid: {player_uid: minuty w lidze dla tego klubu}}, z zapisu): zawodnik liczy sie dla klubu,
    w ktorym gral, z tymi minutami (prog i waga); bez nich - obecny klub i minuty sezonu.
    """
    if zawodnicy is None or zawodnicy.empty or 'Klub_UID' not in zawodnicy.columns:
        return None
    if sklady and 'UID' in zawodnicy.columns:
        po_uid = zawodnicy.drop_duplicates('UID').set_index('UID')
        wiersze = []
        for klub in kluby:
            for gracz, minuty in (sklady.get(klub) or {}).items():
                if gracz in po_uid.index:
                    wiersze.append({**po_uid.loc[gracz].to_dict(), "UID": gracz, "Klub_UID": klub, "Minuty": minuty,
                                    "Klub": nazwy_klubow.get(klub) if nazwy_klubow else po_uid.at[gracz, 'Klub']})
        liga = pd.DataFrame(wiersze)
        if liga.empty:
            return None
    else:
        liga = zawodnicy[zawodnicy['Klub_UID'].isin(list(kluby)) & zawodnicy['Minuty'].notna()]
    metryki = [m for m in METRYKI_ATLETYZMU if m in liga.columns and liga[m].notna().any()]
    if liga.empty or not metryki:
        return None
    mozliwe = mecze * 90 if mecze else liga['Minuty'].max()
    prog = float(np.ceil(PROG_MINUT_ATLETYZMU * mozliwe))
    ok = liga[(liga['Minuty'] >= prog) & liga[metryki].notna().all(axis=1)].copy()
    ok['Rodzina'] = _rodzina(ok)
    z = pd.DataFrame(index=ok.index)
    for m in metryki:
        grupy = ok.groupby('Rodzina')[m]
        odch = grupy.transform('std').replace(0, np.nan)
        z[m] = ((ok[m] - grupy.transform('mean')) / odch).fillna(0.0)
    ok['_laczny'] = z.mean(axis=1)
    liczba = ok.groupby('Rodzina')['_laczny'].transform('size')
    miejsce = ok.groupby('Rodzina')['_laczny'].rank(method='average')
    ok['Atletyzm'] = np.where(liczba > 1, (miejsce - 0.5) / liczba * 100, 50.0)

    nazwy_klubow = nazwy_klubow or {}
    kluby_wynik = []
    for uid, grupa in ok.groupby('Klub_UID'):
        wagi = grupa['Minuty']
        kluby_wynik.append({"klub": nazwy_klubow.get(uid) or str(grupa['Klub'].iloc[0]),
                            "wynik": float(np.average(grupa['Atletyzm'], weights=wagi)),
                            "zawodnicy": int(len(grupa)), "moj": bool(uid == moj_uid)})
    kluby_wynik.sort(key=lambda k: -k["wynik"])
    for i, k in enumerate(kluby_wynik, 1):
        k["miejsce"] = i
    moi = ok[ok['Klub_UID'] == moj_uid].sort_values('Atletyzm', ascending=False)
    return {
        "prog_minut": prog, "metryki": metryki,
        "zawodnicy": [{"Piłkarz": r['Piłkarz'], "ID": r.get('ID'), "Pozycja": r.get('Pozycja'),
                       "Pula": r.get('Pula_główna', r.get('Pula')), "Minuty": float(r['Minuty']),
                       "Atletyzm": float(r['Atletyzm']),
                       **{m: float(r[m]) for m in metryki}} for _, r in moi.iterrows()],
        "kluby": kluby_wynik,
        "moj": next((k for k in kluby_wynik if k["moj"]), None),
    }


def zmiany_zawodnikow(moi_z_rozwojem, oceny_teraz, oceny_wtedy, min_minut, ile=5):
    """
    Najwieksze spadki i wzrosty moich zawodnikow wzgledem poprzedniego sezonu:
    Δ SCORE (z historii, juz policzone w pulach) i Δ sredniej oceny (migawka poprzedniego sezonu).
    moi_z_rozwojem: [{Piłkarz, ID, pozycja, SCORE, Δ SCORE}]; oceny_*: {UID: (ocena, minuty)}.
    """
    score = [m for m in moi_z_rozwojem if m.get("Δ SCORE") is not None and not pd.isna(m["Δ SCORE"])]
    for m in score:
        m["SCORE wtedy"] = m["SCORE"] - m["Δ SCORE"]
    oceny = []
    for uid, (teraz, min_teraz) in oceny_teraz.items():
        wtedy = oceny_wtedy.get(uid)
        if wtedy is None or pd.isna(teraz) or pd.isna(wtedy[0]) or min_teraz < min_minut or wtedy[1] < min_minut:
            continue
        oceny.append({"uid": uid, "teraz": float(teraz), "wtedy": float(wtedy[0]), "zmiana": float(teraz - wtedy[0])})
    po_score = sorted(score, key=lambda m: m["Δ SCORE"])
    po_ocenie = sorted(oceny, key=lambda m: m["zmiana"])
    return {
        # zmiany ponizej dokladnosci wyswietlania (0,1 SCORE, 0,01 oceny) to brak zmiany
        "spadki": [m for m in po_score if m["Δ SCORE"] <= -0.05][:ile],
        "wzrosty": [m for m in reversed(po_score) if m["Δ SCORE"] >= 0.05][:ile],
        "oceny_spadki": [m for m in po_ocenie if m["zmiana"] <= -0.005][:ile],
        "oceny_wzrosty": [m for m in reversed(po_ocenie) if m["zmiana"] >= 0.005][:ile],
    }
