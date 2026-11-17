"""
Mecze z zapisu gry (FM27): analiza meczow mojego klubu (xG za i przeciw, punkty oczekiwane, szczesliwe wygrane
i pechowe porazki) oraz raport o rywalu (forma, xG, miejsce w tabeli, kluczowi zawodnicy).

Terminarz (fixtures) daje wyniki i daty, statystyki druzyn (team_match_stats) - xG, strzaly i posiadanie pilki.
Gra zachowuje statystyki tylko czesci meczow (szczegolowe raporty), wiec mecz moze miec wynik bez xG.
"""
import math
from collections import Counter, defaultdict
from datetime import timedelta

MECZE_WSTECZ_DNI = 400            # mecze mojego klubu: ostatnie ~13 miesiecy...
MECZE_NAPRZOD_DNI = 200           # ...i najblizsze ~6 miesiecy terminarza
MECZE_RYWALA = 10                 # tyle ostatnich meczow kazdego rywala
PROG_SZCZESCIA = 0.6              # wygrana mimo xG nizszego o tyle - "szczesliwa"; porazka mimo wyzszego - "pechowa"
MAKS_GOLI_POISSONA = 10


def _poisson(lam, k):
    return math.exp(-lam) * lam ** k / math.factorial(k)


def prawdopodobienstwa(xg, xg_rywala):
    """(P wygranej, P remisu, P porazki) z xG obu druzyn (niezalezne rozklady Poissona)."""
    if xg is None or xg_rywala is None:
        return None
    a = [_poisson(max(xg, 0.0), k) for k in range(MAKS_GOLI_POISSONA + 1)]
    b = [_poisson(max(xg_rywala, 0.0), k) for k in range(MAKS_GOLI_POISSONA + 1)]
    wygrana = sum(a[i] * b[j] for i in range(len(a)) for j in range(len(b)) if i > j)
    remis = sum(a[i] * b[i] for i in range(len(a)))
    return wygrana, remis, max(0.0, 1.0 - wygrana - remis)


def punkty_oczekiwane(xg, xg_rywala):
    p = prawdopodobienstwa(xg, xg_rywala)
    return None if p is None else round(3 * p[0] + p[1], 2)


def ocena_meczu(gole, gole_rywala, xg, xg_rywala):
    """'szczęśliwa wygrana', 'pechowa porażka' (wynik wbrew xG), None w pozostalych przypadkach."""
    if None in (gole, gole_rywala, xg, xg_rywala):
        return None
    if gole > gole_rywala and xg_rywala - xg >= PROG_SZCZESCIA:
        return "szczęśliwa wygrana"
    if gole < gole_rywala and xg - xg_rywala >= PROG_SZCZESCIA:
        return "pechowa porażka"
    if gole == gole_rywala and abs(xg - xg_rywala) >= 2 * PROG_SZCZESCIA:
        return "szczęśliwy remis" if xg < xg_rywala else "pechowy remis"
    return None


def nazwy_rozgrywek(terminarz, kraj_klubu, ligi):
    """
    {competition_id: nazwa}: liga z mapy lig aplikacji; inne rozgrywki - "Puchar krajowy" (kluby jednego kraju)
    albo "Rozgrywki międzynarodowe". Zapis FM27 nie ma nazw rozgrywek.
    ligi: {competition_id: etykieta ligi}.
    """
    kraje = defaultdict(set)
    for m in terminarz:
        for uid in (m.home_club_uid, m.away_club_uid):
            if uid is not None and kraj_klubu.get(uid) is not None:
                kraje[m.competition_id].add(kraj_klubu[uid])
    wynik = {}
    for comp, zbior in kraje.items():
        wynik[comp] = ligi.get(comp) or ("Puchar krajowy" if len(zbior) <= 1 else "Rozgrywki międzynarodowe")
    return wynik


def _pierwsza(slot):
    return (slot or 0) == 0


def zbierz_mecze(terminarz, statystyki_druzyn, moje_kluby, data_gry, kraj_klubu=None, ligi=None):
    """
    Mecze pierwszych druzyn: moich klubow (ostatnie MECZE_WSTECZ_DNI i najblizsze MECZE_NAPRZOD_DNI) oraz rywali
    z tego okresu (ich ostatnie MECZE_RYWALA rozegranych meczow) -> {club_uid: [mecz]}, mecz: {data, rozgrywki,
    u_siebie, rywal_uid, rywal, gole, gole_rywala, xg, xg_rywala, strzaly, strzaly_rywala, celne, celne_rywala,
    posiadanie, rozegrany}. statystyki_druzyn: rekordy TeamMatchStats.
    """
    if data_gry is None:
        return {}
    od, do = data_gry - timedelta(days=MECZE_WSTECZ_DNI), data_gry + timedelta(days=MECZE_NAPRZOD_DNI)
    moje_kluby = set(moje_kluby)
    nazwy = nazwy_rozgrywek(terminarz, kraj_klubu or {}, ligi or {})
    pierwsze = [m for m in terminarz if m.date is not None and _pierwsza(m.home_team_slot)
                and _pierwsza(m.away_team_slot) and m.home_club_uid is not None and m.away_club_uid is not None]
    moje = [m for m in pierwsze if od <= m.date <= do and (m.home_club_uid in moje_kluby or m.away_club_uid in moje_kluby)]
    rywale = {m.away_club_uid if m.home_club_uid in moje_kluby else m.home_club_uid for m in moje}
    statystyki = {(s.date, s.home_team_id, s.away_team_id, s.team_id): s for s in statystyki_druzyn}

    def wpis(m, klub):
        dom = m.home_club_uid == klub
        ja, on = (m.home_team_id, m.away_team_id) if dom else (m.away_team_id, m.home_team_id)
        s_ja = statystyki.get((m.date, m.home_team_id, m.away_team_id, ja))
        s_on = statystyki.get((m.date, m.home_team_id, m.away_team_id, on))
        gole = m.home_goals if dom else m.away_goals
        gole_r = m.away_goals if dom else m.home_goals
        rozegrany = bool(m.played) and gole is not None and gole_r is not None
        xg = round(s_ja.expected_goals, 2) if s_ja is not None and s_ja.expected_goals is not None else None
        xg_r = round(s_on.expected_goals, 2) if s_on is not None and s_on.expected_goals is not None else None
        return {
            "data": m.date.isoformat(), "sezon": m.date.year if m.date.month >= 7 else m.date.year - 1,
            "rozgrywki_id": m.competition_id,
            "rozgrywki": nazwy.get(m.competition_id, "Inne rozgrywki"),
            "u_siebie": dom,
            # gospodarz i gosc z terminarza; boisko neutralne wg flagi meczu (finaly, mecze na wybranym stadionie)
            "strona": "Neutralne" if getattr(m, "is_neutral_venue", None) else ("Dom" if dom else "Wyjazd"),
            "rywal_uid": str(m.away_club_uid if dom else m.home_club_uid),
            "rywal": (m.away_club_name if dom else m.home_club_name) or "?",
            "rozegrany": rozegrany,
            "gole": gole if rozegrany else None, "gole_rywala": gole_r if rozegrany else None,
            "xg": xg if rozegrany else None, "xg_rywala": xg_r if rozegrany else None,
            "strzaly": getattr(s_ja, "shots", None), "strzaly_rywala": getattr(s_on, "shots", None),
            "celne": getattr(s_ja, "shots_on_target", None), "celne_rywala": getattr(s_on, "shots_on_target", None),
            "posiadanie": getattr(s_ja, "possession_percent", None),
            "xpkt": punkty_oczekiwane(xg, xg_r) if rozegrany else None,
            "ocena": ocena_meczu(gole, gole_r, xg, xg_r) if rozegrany else None,
        }
    wynik = defaultdict(list)
    for m in sorted(moje, key=lambda m: m.date):
        for klub in (m.home_club_uid, m.away_club_uid):
            if klub in moje_kluby:
                wynik[klub].append(wpis(m, klub))
    for klub in rywale - moje_kluby:
        jego = sorted((m for m in pierwsze if m.date <= data_gry and m.played
                       and klub in (m.home_club_uid, m.away_club_uid)), key=lambda m: m.date)
        wynik[klub] = [wpis(m, klub) for m in jego[-MECZE_RYWALA:]]
    return {str(k): v for k, v in wynik.items()}


def _srednia(wartosci):
    wartosci = [w for w in wartosci if w is not None]
    return round(sum(wartosci) / len(wartosci), 2) if wartosci else None


def wynik_litera(m):
    if not m.get("rozegrany"):
        return None
    return "W" if m["gole"] > m["gole_rywala"] else "R" if m["gole"] == m["gole_rywala"] else "P"


def podsumowanie(mecze):
    """Podsumowanie rozegranych meczow: bilans, gole, xG, punkty i punkty oczekiwane (z meczow z xG)."""
    rozegrane = [m for m in mecze if m.get("rozegrany")]
    z_xg = [m for m in rozegrane if m.get("xpkt") is not None]
    litery = Counter(wynik_litera(m) for m in rozegrane)
    punkty_xg = sum(3 if wynik_litera(m) == "W" else 1 if wynik_litera(m) == "R" else 0 for m in z_xg)
    return {
        "mecze": len(rozegrane), "wygrane": litery["W"], "remisy": litery["R"], "porazki": litery["P"],
        "gole": sum(m["gole"] for m in rozegrane), "stracone": sum(m["gole_rywala"] for m in rozegrane),
        "mecze_z_xg": len(z_xg),
        "xg": round(sum(m["xg"] for m in z_xg), 1) if z_xg else None,
        "xg_rywala": round(sum(m["xg_rywala"] for m in z_xg), 1) if z_xg else None,
        "gole_z_xg": sum(m["gole"] for m in z_xg), "stracone_z_xg": sum(m["gole_rywala"] for m in z_xg),
        "punkty_z_xg": punkty_xg, "xpkt": round(sum(m["xpkt"] for m in z_xg), 1) if z_xg else None,
        "xg_mecz": _srednia(m["xg"] for m in z_xg), "xg_rywala_mecz": _srednia(m["xg_rywala"] for m in z_xg),
        "forma": "".join(wynik_litera(m) for m in rozegrane[-5:]),
        "szczesliwe": sum(1 for m in rozegrane if (m.get("ocena") or "").startswith("szczęśliw")),
        "pechowe": sum(1 for m in rozegrane if (m.get("ocena") or "").startswith("pechow")),
    }
