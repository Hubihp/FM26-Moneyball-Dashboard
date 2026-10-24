"""
Dopasowanie zawodnikow do rol FM26: osobno w posiadaniu pilki (IP) i bez pilki (OOP).

Role i ich opisy pochodza z poradnika (Steam, "FM26 roles"); zestawy atrybutow kluczowych (waga 2)
i dodatkowych (waga 1) oraz statystyki meczowe przypisane do roli to propozycja zatwierdzona przez
uzytkownika - wszystko jest w tym pliku, zeby latwo bylo je poprawic.

Metoda (0-100):
  atrybuty    = suma w_i * (a_i - 1) / 19 / suma w_i * 100      (atrybuty 1-20 z zapisu gry)
  statystyki  = srednia percentyli wymienionych statystyk w puli pozycji ("mniej = lepiej" odwrocone)
  dopasowanie = (1 - s) * atrybuty + s * statystyki,  s = 0.25 * min(1, minuty / 900)
Bez atrybutow (dane demo, CSV) dopasowania nie ma.
"""
import numpy as np
import pandas as pd

from fm_moneyball.stale import NIZSZE_LEPSZE

WAGA_KLUCZOWYCH = 2.0
WAGA_DODATKOWYCH = 1.0
UDZIAL_STATYSTYK = 0.25
MINUTY_PELNEJ_PROBY = 900
KOLUMNA_ATRYBUTU = "Atr|{}"
FAZY = ("IP", "OOP")
NAZWA_FAZY = {"IP": "przy piłce", "OOP": "bez piłki"}

# Atrybut rekordu fmsave -> nazwa polska (jak w grze)
ATRYBUTY_PL = {
    "crossing": "Dośrodkowania", "dribbling": "Drybling", "finishing": "Wykończenie", "heading": "Gra głową",
    "long_shots": "Strzały z dystansu", "marking": "Krycie", "off_the_ball": "Gra bez piłki", "passing": "Podania",
    "tackling": "Odbiór", "vision": "Wizja gry", "handling": "Chwytanie", "aerial_reach": "Zasięg w powietrzu",
    "command_of_area": "Panowanie w polu karnym", "communication": "Komunikacja", "kicking": "Wykopy",
    "throwing": "Wyrzuty", "anticipation": "Przewidywanie", "decisions": "Decyzje", "one_on_ones": "Sam na sam",
    "positioning": "Ustawianie się", "reflexes": "Refleks", "first_touch": "Przyjęcie", "technique": "Technika",
    "flair": "Polot", "teamwork": "Praca zespołowa", "work_rate": "Pracowitość",
    "rushing_out": "Wychodzenie z bramki", "acceleration": "Przyspieszenie", "strength": "Siła",
    "stamina": "Wytrzymałość", "pace": "Szybkość", "jumping_reach": "Skok", "balance": "Równowaga",
    "bravery": "Odwaga", "aggression": "Agresja", "agility": "Zwinność", "composure": "Opanowanie",
    "concentration": "Koncentracja",
}
_Z_POLSKIEJ = {v: k for k, v in ATRYBUTY_PL.items()}

# Skroty statystyk meczowych -> kolumny aplikacji
STATYSTYKI = {
    "xA": "Oczekiwane asysty/90", "KP": "Kluczowe podania z gry/90", "PP": "Podania progresywne/90",
    "PRS": "Udane próby pressingu/90", "PRZ": "Przechwyty/90", "ODZ": "Odzyskane piłki/90",
    "GŁ": "% wygranych pojedynków główkowych", "DŚ": "Udane dośrodkowania/90", "DRY": "Liczba dryblingów/90",
    "xG": "Oczekiwane gole bez karnych/90", "G": "Liczba goli na 90 min", "STR": "Strata piłek na podanie",
    "PRÓB": "Próby podań/90", "xGA": "Uniknięte oczekiwane gole/90", "OBR": "Skuteczność obron (%)",
    "SPR": "Sprinty/90", "100": "Stworzone 100% sytuacje/90", "xG/S": "Oczekiwane gole na strzał",
    "SKU": "Skuteczność strzałów (%)",
}

# Grupy pozycji z poradnika -> (nazwa polska, pule aplikacji)
GRUPY = {
    "GK": ("Bramkarz", ["Bramkarz"]),
    "DC": ("Środkowy obrońca", ["Środkowy Obrońca"]),
    "DLR": ("Boczny obrońca", ["Boczny Obrońca"]),
    "WB": ("Wahadłowy", ["Wahadłowy"]),
    "DM": ("Defensywny pomocnik", ["Defensywny Pomocnik"]),
    "CM": ("Środkowy pomocnik", ["Środkowy Pomocnik"]),
    "MLR": ("Boczny pomocnik", ["Skrzydłowy"]),
    "AMLR": ("Skrzydłowy", ["Skrzydłowy"]),
    "AMC": ("Ofensywny pomocnik", ["Ofensywny Pomocnik"]),
    "ST": ("Napastnik", ["Napastnik"]),
}


def _r(nazwa, kluczowe, dodatkowe, statystyki=""):
    return {"nazwa": nazwa, "kluczowe": [s.strip() for s in kluczowe.split(",")],
            "dodatkowe": [s.strip() for s in dodatkowe.split(",") if s.strip()],
            "statystyki": [s.strip() for s in statystyki.split(",") if s.strip()]}


# Zestawy wspolne dla kilku grup
_FB_IP = [
    _r("Full-Back", "Dośrodkowania, Podania, Pracowitość", "Wytrzymałość, Decyzje, Przyjęcie"),
    _r("Wing-Back", "Dośrodkowania, Wytrzymałość, Pracowitość, Gra bez piłki, Przyspieszenie",
       "Drybling, Technika, Szybkość", "DŚ, xA"),
    _r("Inside Wing-Back", "Podania, Przyjęcie, Opanowanie, Decyzje", "Wizja gry, Technika, Pracowitość", "PRÓB, PP"),
    _r("Inside Full-Back", "Podania, Ustawianie się, Opanowanie, Decyzje", "Przyjęcie, Siła", "STR"),
    _r("Playmaking Wing-Back", "Podania, Wizja gry, Dośrodkowania, Technika",
       "Decyzje, Przyjęcie, Opanowanie, Wytrzymałość", "KP, xA, PP"),
]
_PRESSING_FB = ("Pracowitość, Agresja, Odbiór, Przyspieszenie, Wytrzymałość", "Przewidywanie, Szybkość, Odwaga",
                "PRS, ODZ")
_HOLDING_FB = ("Ustawianie się, Krycie, Koncentracja, Decyzje", "Gra głową, Siła, Odbiór", "PRZ")
_ADV_PLAYMAKER = _r("Advanced Playmaker", "Podania, Wizja gry, Technika, Przyjęcie, Decyzje",
                    "Opanowanie, Polot, Gra bez piłki", "KP, xA")
_CHANNEL_MID = _r("Channel Midfielder", "Gra bez piłki, Przyspieszenie, Wytrzymałość, Pracowitość",
                  "Wykończenie, Przyjęcie, Szybkość, Drybling", "xG")
_WINGER_IP = _r("Winger", "Dośrodkowania, Drybling, Przyspieszenie, Szybkość",
                "Technika, Przyjęcie, Gra bez piłki, Zwinność", "DŚ, DRY, xA")
_PLAYMAKING_WINGER = _r("Playmaking Winger", "Podania, Wizja gry, Technika, Przyjęcie, Decyzje",
                        "Dośrodkowania, Drybling, Polot", "KP, xA")
_INSIDE_WINGER = _r("Inside Winger", "Drybling, Podania, Przyjęcie, Technika, Gra bez piłki",
                    "Wizja gry, Decyzje, Zwinność", "KP, DRY")
_SZEROKI_OOP = ("Pracowitość, Wytrzymałość, Praca zespołowa", "Ustawianie się, Odbiór", "")
_TRACKING_SZEROKI = ("Pracowitość, Wytrzymałość, Krycie, Odbiór, Ustawianie się", "Koncentracja, Praca zespołowa",
                     "ODZ, PRS")
_WIDE_OUTLET = ("Przyspieszenie, Szybkość, Gra bez piłki", "Przyjęcie, Drybling", "")

ROLE_GRUP = {
    "GK": {
        "IP": [
            _r("Goalkeeper", "Wykopy, Wyrzuty, Decyzje", "Podania, Opanowanie"),
            _r("Ball-Playing Goalkeeper", "Podania, Wizja gry, Opanowanie, Przyjęcie",
               "Wykopy, Wyrzuty, Technika, Decyzje", "PRÓB, STR"),
            _r("No-Nonsense Goalkeeper", "Wykopy, Decyzje, Koncentracja", "Opanowanie"),
        ],
        "OOP": [
            _r("Goalkeeper", "Chwytanie, Refleks, Ustawianie się, Sam na sam",
               "Komunikacja, Koncentracja, Zasięg w powietrzu", "xGA, OBR"),
            _r("Sweeper Keeper", "Wychodzenie z bramki, Przewidywanie, Przyspieszenie, Sam na sam, "
               "Panowanie w polu karnym", "Szybkość, Decyzje, Opanowanie, Refleks", "xGA"),
            _r("Line-Holding Goalkeeper", "Refleks, Ustawianie się, Chwytanie, Koncentracja", "Zwinność, Sam na sam",
               "OBR"),
        ],
    },
    "DC": {
        "IP": [
            _r("Centre-Back", "Podania, Opanowanie, Decyzje", "Przyjęcie, Koncentracja", "STR"),
            _r("Advanced Centre-Back", "Podania, Przyjęcie, Opanowanie, Decyzje", "Technika, Wizja gry, Wytrzymałość",
               "PP"),
            _r("Ball-Playing Centre-Back", "Podania, Wizja gry, Opanowanie, Technika", "Przyjęcie, Decyzje", "PP, KP"),
            _r("No-Nonsense Centre-Back", "Gra głową, Siła, Odwaga, Decyzje", "Skok, Koncentracja", "GŁ"),
        ],
        "OOP": [
            _r("Centre-Back", "Krycie, Odbiór, Ustawianie się, Gra głową", "Przewidywanie, Koncentracja, Skok, Siła",
               "PRZ, GŁ"),
            _r("Stopping Centre-Back", "Odbiór, Agresja, Odwaga, Przewidywanie, Siła", "Krycie, Skok, Decyzje",
               "PRS, ODZ"),
            _r("Covering Centre-Back", "Ustawianie się, Przewidywanie, Szybkość, Koncentracja",
               "Przyspieszenie, Krycie, Decyzje", "PRZ"),
        ],
    },
    "DLR": {
        "IP": _FB_IP,
        "OOP": [
            _r("Full-Back", "Krycie, Odbiór, Ustawianie się, Koncentracja", "Przewidywanie, Pracowitość, Szybkość",
               "PRZ"),
            _r("Pressing Full-Back", *_PRESSING_FB),
            _r("Holding Full-Back", *_HOLDING_FB),
        ],
    },
    "WB": {
        "IP": [
            _FB_IP[1],
            _r("Advanced Wing-Back", "Dośrodkowania, Drybling, Gra bez piłki, Przyspieszenie, Wytrzymałość",
               "Technika, Szybkość, Polot, Pracowitość", "DŚ, DRY, xA, SPR"),
            _FB_IP[2],
            _FB_IP[4],
        ],
        "OOP": [
            _r("Wing-Back", "Pracowitość, Wytrzymałość, Odbiór, Ustawianie się", "Krycie, Przewidywanie, Szybkość",
               "ODZ"),
            _r("Pressing Wing-Back", *_PRESSING_FB),
            _r("Holding Wing-Back", *_HOLDING_FB),
        ],
    },
    "DM": {
        "IP": [
            _r("Defensive Midfielder", "Podania, Decyzje, Opanowanie", "Przyjęcie, Praca zespołowa", "STR, PRÓB"),
            _r("Deep-Lying Playmaker", "Podania, Wizja gry, Opanowanie, Decyzje, Technika",
               "Przyjęcie, Przewidywanie, Praca zespołowa", "PP, KP, PRÓB"),
            _r("Halfback", "Podania, Ustawianie się, Opanowanie, Decyzje", "Krycie, Odbiór, Przyjęcie, Koncentracja",
               "PRÓB, STR"),
        ],
        "OOP": [
            _r("Defensive Midfielder", "Odbiór, Ustawianie się, Przewidywanie, Pracowitość",
               "Krycie, Koncentracja, Praca zespołowa, Siła", "PRZ, ODZ"),
            _r("Dropping Defensive Midfielder", "Ustawianie się, Krycie, Odbiór, Gra głową", "Siła, Skok, Koncentracja",
               "GŁ, PRZ"),
            _r("Screening Defensive Midfielder", "Przewidywanie, Ustawianie się, Koncentracja, Decyzje",
               "Odbiór, Praca zespołowa", "PRZ"),
        ],
    },
    "CM": {
        "IP": [
            _r("Central Midfielder", "Podania, Decyzje, Praca zespołowa, Przyjęcie",
               "Opanowanie, Wytrzymałość, Pracowitość", "PRÓB, STR"),
            _r("Attacking Midfielder", "Gra bez piłki, Podania, Przyjęcie, Wytrzymałość",
               "Strzały z dystansu, Wykończenie, Technika, Decyzje", "xG, G"),
            _ADV_PLAYMAKER,
            _r("Wide Central Midfielder", "Podania, Dośrodkowania, Wytrzymałość, Pracowitość",
               "Przyjęcie, Gra bez piłki, Decyzje", "DŚ"),
            _CHANNEL_MID,
            _r("Midfield Playmaker", "Podania, Wizja gry, Decyzje, Przyjęcie, Wytrzymałość",
               "Technika, Opanowanie, Praca zespołowa, Gra bez piłki", "PP, PRÓB, KP"),
        ],
        "OOP": [
            _r("Central Midfielder", "Pracowitość, Ustawianie się, Odbiór, Praca zespołowa",
               "Przewidywanie, Wytrzymałość, Koncentracja", "ODZ"),
            _r("Pressing Central Midfielder", "Pracowitość, Agresja, Wytrzymałość, Przyspieszenie, Odbiór",
               "Przewidywanie, Odwaga, Praca zespołowa", "PRS, ODZ"),
            _r("Screening Central Midfielder", "Przewidywanie, Ustawianie się, Koncentracja, Decyzje",
               "Odbiór, Praca zespołowa, Krycie", "PRZ"),
        ],
    },
    "MLR": {
        "IP": [
            _r("Wide Midfielder", "Podania, Dośrodkowania, Pracowitość, Decyzje",
               "Wytrzymałość, Przyjęcie, Praca zespołowa"),
            _WINGER_IP, _PLAYMAKING_WINGER, _INSIDE_WINGER,
        ],
        "OOP": [
            _r("Wide Midfielder", *_SZEROKI_OOP),
            _r("Tracking Wide Midfielder", *_TRACKING_SZEROKI),
            _r("Wide Outlet Wide Midfielder", *_WIDE_OUTLET),
        ],
    },
    "AMLR": {
        "IP": [
            _WINGER_IP,
            _r("Inside Forward", "Wykończenie, Drybling, Gra bez piłki, Przyspieszenie, Opanowanie",
               "Technika, Przyjęcie, Strzały z dystansu, Szybkość", "xG, G"),
            _PLAYMAKING_WINGER,
            _r("Wide Forward", "Gra bez piłki, Wykończenie, Przyspieszenie, Pracowitość",
               "Szybkość, Wytrzymałość, Opanowanie, Drybling", "xG, PRS"),
            _INSIDE_WINGER,
        ],
        "OOP": [
            _r("Winger", *_SZEROKI_OOP),
            _r("Tracking Winger", *_TRACKING_SZEROKI),
            _r("Inside Outlet Winger", "Gra bez piłki, Przyspieszenie, Przewidywanie", "Opanowanie, Przyjęcie, Szybkość"),
            _r("Wide Outlet Winger", *_WIDE_OUTLET),
        ],
    },
    "AMC": {
        "IP": [
            _r("Attacking Midfielder", "Podania, Przyjęcie, Gra bez piłki, Decyzje",
               "Technika, Wizja gry, Strzały z dystansu", "xA, KP"),
            _ADV_PLAYMAKER,
            _r("Free Role", "Wizja gry, Technika, Polot, Drybling, Podania",
               "Przyjęcie, Decyzje, Opanowanie, Gra bez piłki", "KP, DRY, 100"),
            _r("Second Striker", "Gra bez piłki, Wykończenie, Opanowanie, Przewidywanie",
               "Przyjęcie, Strzały z dystansu, Przyspieszenie, Technika", "xG, G"),
            _CHANNEL_MID,
        ],
        "OOP": [
            _r("Advanced Midfielder", "Pracowitość, Praca zespołowa, Decyzje", "Przewidywanie, Wytrzymałość", "PRS"),
            _r("Tracking Attacking Midfielder", "Pracowitość, Wytrzymałość, Odbiór, Ustawianie się",
               "Przewidywanie, Krycie, Praca zespołowa", "ODZ, PRS"),
            _r("Central Outlet Attacking Midfielder", "Gra bez piłki, Przewidywanie, Przyspieszenie",
               "Opanowanie, Przyjęcie"),
        ],
    },
    "ST": {
        "IP": [
            _r("Deep-Lying Forward", "Przyjęcie, Podania, Technika, Opanowanie, Decyzje",
               "Wizja gry, Siła, Praca zespołowa, Gra bez piłki", "KP, xA"),
            _r("Centre Forward", "Wykończenie, Gra bez piłki, Przyjęcie, Opanowanie",
               "Gra głową, Siła, Przyspieszenie, Technika, Podania", "xG, G"),
            _r("Target Forward", "Siła, Gra głową, Skok, Równowaga", "Przyjęcie, Odwaga, Wykończenie, Praca zespołowa",
               "GŁ"),
            _r("Poacher", "Wykończenie, Gra bez piłki, Opanowanie, Przewidywanie", "Przyjęcie, Przyspieszenie",
               "xG, xG/S, SKU"),
            _r("Channel Forward", "Gra bez piłki, Przyspieszenie, Szybkość, Wytrzymałość, Pracowitość",
               "Wykończenie, Drybling, Przyjęcie"),
            _r("False 9", "Przyjęcie, Podania, Wizja gry, Technika, Decyzje", "Drybling, Opanowanie, Polot, Zwinność",
               "KP, xA, DRY"),
        ],
        "OOP": [
            _r("Centre Forward", "Pracowitość, Wytrzymałość, Praca zespołowa", "Agresja, Przewidywanie, Przyspieszenie",
               "PRS"),
            _r("Tracking Centre Forward", "Pracowitość, Wytrzymałość, Ustawianie się, Praca zespołowa",
               "Odbiór, Przewidywanie", "ODZ, PRS"),
            _r("Central Outlet Centre Forward", "Gra bez piłki, Siła, Przewidywanie", "Opanowanie, Przyjęcie, Równowaga"),
            _r("Splitting Outlet Centre Forward", "Gra bez piłki, Przyspieszenie, Szybkość", "Przewidywanie, Drybling"),
        ],
    },
}


def role_grupy(grupa, faza):
    return ROLE_GRUP[grupa][faza]


def znajdz_role(grupa, faza, nazwa):
    return next((r for r in ROLE_GRUP.get(grupa, {}).get(faza, []) if r["nazwa"] == nazwa), None)


def role_pozycji(pozycja):
    """Role puli aplikacji: {faza: [rola]} bez powtorzen nazw (np. Winger w ML i AML)."""
    wynik = {}
    for faza in FAZY:
        widziane = {}
        for grupa, (_, pule) in GRUPY.items():
            if pozycja in pule:
                for rola in ROLE_GRUP[grupa][faza]:
                    widziane.setdefault(rola["nazwa"], rola)
        wynik[faza] = list(widziane.values())
    return wynik


def kolumna_roli(faza, nazwa):
    return f"Rola|{faza}|{nazwa}"


def ma_atrybuty(pula):
    kolumny = [KOLUMNA_ATRYBUTU.format(a) for a in ATRYBUTY_PL]
    return all(k in pula.columns for k in kolumny) and bool(pula[kolumny].notna().any().any())


def _percentyle(pula, kolumna):
    seria = pd.to_numeric(pula[kolumna], errors="coerce")
    p = seria.rank(pct=True, method="average") * 100
    if kolumna in NIZSZE_LEPSZE:
        p = 100 - p + 100 / max(seria.notna().sum(), 1)
    return p


def wynik_atrybutow(pula, rola):
    licznik = pd.Series(0.0, index=pula.index)
    suma_wag = pd.Series(0.0, index=pula.index)
    for nazwy, waga in ((rola["kluczowe"], WAGA_KLUCZOWYCH), (rola["dodatkowe"], WAGA_DODATKOWYCH)):
        for nazwa in nazwy:
            kol = KOLUMNA_ATRYBUTU.format(_Z_POLSKIEJ[nazwa])
            if kol not in pula.columns:
                continue
            a = pd.to_numeric(pula[kol], errors="coerce")
            licznik += ((a - 1) / 19).fillna(0) * waga
            suma_wag += a.notna() * waga
    return (licznik / suma_wag.where(suma_wag > 0)) * 100


def wynik_statystyk(pula, rola, percentyle=None):
    kolumny = [STATYSTYKI[s] for s in rola["statystyki"] if STATYSTYKI[s] in pula.columns]
    if not kolumny:
        return None
    percentyle = percentyle if percentyle is not None else {}
    ramka = pd.DataFrame({k: percentyle[k] if k in percentyle else _percentyle(pula, k) for k in kolumny})
    return ramka.mean(axis=1, skipna=True)


def dopasuj(pula, rola, percentyle=None):
    """Dopasowanie (0-100) zawodnikow puli do roli; NaN bez atrybutow."""
    atrybuty = wynik_atrybutow(pula, rola)
    statystyki = wynik_statystyk(pula, rola, percentyle)
    if statystyki is None:
        return atrybuty.round(1)
    minuty = pd.to_numeric(pula['Minuty'], errors="coerce").fillna(0) if 'Minuty' in pula.columns else 0
    udzial = UDZIAL_STATYSTYK * np.minimum(1.0, minuty / MINUTY_PELNEJ_PROBY)
    udzial = pd.Series(udzial, index=pula.index).where(statystyki.notna(), 0.0)
    return ((1 - udzial) * atrybuty + udzial * statystyki.fillna(0)).round(1)


def dopasowania(pula, pozycja):
    """
    Dolicza kolumny dopasowania do kazdej roli pozycji ('Rola|IP|nazwa') oraz najlepsza role
    w kazdej fazie ('Rola IP' + 'Dopasowanie IP'). Pula bez atrybutow wraca bez zmian.
    """
    if pula.empty or not ma_atrybuty(pula):
        return pula
    role = role_pozycji(pozycja)
    percentyle = {}
    for faza in FAZY:
        for rola in role[faza]:
            for s in rola["statystyki"]:
                k = STATYSTYKI[s]
                if k in pula.columns and k not in percentyle:
                    percentyle[k] = _percentyle(pula, k)
    nowe = {}
    for faza in FAZY:
        kolumny = []
        for rola in role[faza]:
            kol = kolumna_roli(faza, rola["nazwa"])
            nowe[kol] = dopasuj(pula, rola, percentyle)
            kolumny.append(kol)
        if kolumny:
            ramka = pd.DataFrame({k: nowe[k] for k in kolumny})
            najlepsza = ramka.fillna(-1).idxmax(axis=1)
            nowe[f"Dopasowanie {faza}"] = ramka.max(axis=1)
            nowe[f"Rola {faza}"] = najlepsza.str.split("|").str[2].where(ramka.notna().any(axis=1))
    return pula.assign(**nowe)


def lista_rol_zawodnika(wiersz, pozycja):
    """Pelne listy rol (IP, OOP) zawodnika posortowane malejaco: {faza: [{nazwa, wynik}]}."""
    wynik = {}
    for faza, role in role_pozycji(pozycja).items():
        pozycje = []
        for rola in role:
            w = wiersz.get(kolumna_roli(faza, rola["nazwa"]))
            if w is not None and not pd.isna(w):
                pozycje.append({"nazwa": rola["nazwa"], "wynik": float(w)})
        wynik[faza] = sorted(pozycje, key=lambda r: -r["wynik"])
    return wynik


def opis_rol(pozycja):
    """Role pozycji dla interfejsu: {faza: [{nazwa, kluczowe, dodatkowe, statystyki}]}."""
    return {faza: [{"nazwa": r["nazwa"], "kluczowe": r["kluczowe"], "dodatkowe": r["dodatkowe"],
                    "statystyki": [STATYSTYKI[s] for s in r["statystyki"]]} for r in role]
            for faza, role in role_pozycji(pozycja).items()}


def katalog_grup():
    """Wszystkie grupy z rolami (do kalibracji taktyki)."""
    return [{"grupa": g, "nazwa": nazwa, "pule": pule,
             "role": {faza: [r["nazwa"] for r in ROLE_GRUP[g][faza]] for faza in FAZY}}
            for g, (nazwa, pule) in GRUPY.items()]
