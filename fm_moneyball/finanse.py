"""
Finanse klubu z zapisu gry (FM27): miesieczne saldo, przychody i wydatki bez transferow, place, transfery
oraz prosta prognoza salda na 12 miesiecy.

fmsave podaje dla kazdego klubu kilkanascie-kilkadziesiat miesiecy (FinanceMonth). Znaczenie czesci pol
jest niepotwierdzone (przychody, wydatki, place, transfery netto); saldo i budzety placowe sa potwierdzone.
Kwoty w walucie bazowej zapisu - przeliczane kursem jak wartosci zawodnikow.
"""
MIESIECY_SREDNIEJ = 12          # srednia miesieczna z ostatnich tylu miesiecy
PROG_PLAC = 0.70                # place / przychody powyzej - ostrzezenie (UEFA: koszty kadry do 70% przychodow)
PROG_PLAC_BLAD = 0.90


def miesiace_klubu(miesiace, club_uid, kurs):
    """Rekordy FinanceMonth -> [{miesiac, saldo, przychody, wydatki, place, transfery, wynik, przychody_razem,
    wydatki_razem, place_tydzien, budzet_plac_tydzien, budzet_transferowy}] od najstarszego (kwoty w EUR)."""
    eur = lambda x: None if x is None else round(float(x) * kurs)   # noqa: E731
    wynik = []
    for m in sorted((m for m in miesiace if m.club_uid == club_uid and m.month is not None), key=lambda m: m.month):
        wynik.append({
            "miesiac": m.month.isoformat(), "saldo": eur(m.balance),
            "przychody": eur(m.income_excluding_transfers), "wydatki": eur(m.expenditure_excluding_transfers),
            "place": eur(m.wage_bill),
            # fmsave: dodatnie = wydatek netto na transfery; tutaj dodatnie = zarobek (sprzedaz), jak w saldzie
            "transfery": None if m.net_transfers is None else -eur(m.net_transfers),
            "wynik": eur(m.net), "przychody_razem": eur(m.total_income), "wydatki_razem": eur(m.total_expenditure),
            "place_tydzien": eur(m.wage_payroll_weekly), "budzet_plac_tydzien": eur(m.wage_budget_weekly),
            "budzet_transferowy": eur(m.transfer_budget_remaining),
        })
    return wynik


def _suma(lista, klucz):
    wartosci = [m[klucz] for m in lista if m.get(klucz) is not None]
    return sum(wartosci) if wartosci else None


def podsumowanie(miesiace):
    """Wskazniki z ostatnich MIESIECY_SREDNIEJ miesiecy i prognoza salda za 12 miesiecy (bez transferow)."""
    if not miesiace:
        return None
    ostatnie = miesiace[-MIESIECY_SREDNIEJ:]
    przychody, wydatki, place = _suma(ostatnie, "przychody"), _suma(ostatnie, "wydatki"), _suma(ostatnie, "place")
    transfery = _suma(ostatnie, "transfery")
    n = len(ostatnie)
    operacyjny = (przychody - wydatki) / n if przychody is not None and wydatki is not None else None
    saldo = miesiace[-1]["saldo"]
    ostatni = miesiace[-1]
    # place zawodnikow rocznie z tygodniowej listy plac (pole potwierdzone; "place" miesieczne nie jest) wobec
    # przychodow bez transferow w przeliczeniu na rok
    place_rocznie = ostatni["place_tydzien"] * 52 if ostatni.get("place_tydzien") is not None else None
    przychody_rocznie = przychody * 12 / n if przychody else None
    udzial_plac = place_rocznie / przychody_rocznie if place_rocznie is not None and przychody_rocznie else None
    return {
        "miesiecy": n, "saldo": saldo, "przychody": przychody, "wydatki": wydatki, "place": place,
        "transfery": transfery, "wynik_operacyjny_miesiac": round(operacyjny) if operacyjny is not None else None,
        "prognoza_salda_12": round(saldo + 12 * operacyjny) if saldo is not None and operacyjny is not None else None,
        "udzial_plac": round(udzial_plac, 3) if udzial_plac is not None else None,
        "status_plac": None if udzial_plac is None else
        "błąd" if udzial_plac > PROG_PLAC_BLAD else "uwaga" if udzial_plac > PROG_PLAC else "ok",
        "place_rocznie": place_rocznie, "przychody_rocznie": round(przychody_rocznie) if przychody_rocznie else None,
        "place_tydzien": ostatni["place_tydzien"], "budzet_plac_tydzien": ostatni["budzet_plac_tydzien"],
        "budzet_transferowy": ostatni["budzet_transferowy"],
        "prog_plac": PROG_PLAC,
    }


def wygasajace_kontrakty(kadra, data_gry, miesiecy=12):
    """
    Zawodnicy pierwszej druzyny mojego klubu, ktorym kontrakt wygasa w ciagu `miesiecy` - place, ktore zwolnia sie z budzetu
    (albo trzeba je przedluzyc). kadra: DataFrame z 'Piłkarz', 'Zarobki_Numeryczne' (rocznie), 'Wygasa_Data'.
    """
    import pandas as pd
    if kadra is None or kadra.empty or 'Wygasa_Data' not in kadra.columns or data_gry is None:
        return []
    dzis = pd.Timestamp(data_gry)
    koniec = dzis + pd.DateOffset(months=miesiecy)
    wygasa = kadra[kadra['Wygasa_Data'].between(dzis, koniec)].sort_values('Wygasa_Data')
    return [{"Piłkarz": w['Piłkarz'], "Wygasa": w['Wygasa_Data'].date().isoformat(),
             "Płaca_tydzien": None if pd.isna(w.get('Zarobki_Numeryczne')) else round(float(w['Zarobki_Numeryczne']) / 52),
             "Wiek": None if pd.isna(w.get('Wiek')) else int(w['Wiek'])}
            for _, w in wygasa.iterrows()]
