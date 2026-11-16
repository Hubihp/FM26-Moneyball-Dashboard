"""
Personel klubu z zapisu gry (FM27): ranking trenerow, skautow, fizjoterapeutow i analitykow wedlug atrybutow
oraz luki w sztabie na tle ligi.

fmsave czyta atrybuty personelu w skali 1-100 (poza autorytetem i praca z mlodzieza, 1-20) i oznacza je jako
niepotwierdzone; gra pokazuje je w skali 1-20, wiec dzielimy przez 5. Odczyt calego personelu trwa ok. 20 s,
dlatego program robi go na zadanie (karta Personel), a nie przy kazdym wczytaniu zapisu.

Obszary pracy na wzor ocen trenerow w grze (gwiazdki za trening w danym obszarze): ocena = srednia atrybutow
obszaru w skali 1-20.
"""
from statistics import median

OBSZARY = {
    "Bramkarze": ("goalkeeping",),
    "Kondycja": ("fitness",),
    "Obrona": ("defending", "tactical"),
    "Atak": ("attacking", "tactical"),
    "Strzały": ("attacking", "technical"),
    "Technika": ("technical",),
    "Taktyka": ("tactical", "tactical_knowledge"),
    "Skauting": ("judging_player_ability", "judging_player_potential"),
    "Fizjoterapia": ("physiotherapy", "sports_science"),
    "Analiza danych": ("analysing_data",),
    "Praca z młodzieżą": ("working_with_youngsters",),
}
# atrybuty w skali 1-20 (reszta 1-100)
SKALA_20 = {"working_with_youngsters", "authority", "adaptability"}
STANOWISKA = {
    "COACH": "trener", "CHAIRPERSON": "prezes", "DIRECTOR": "członek zarządu", "MANAGING_DIRECTOR": "dyrektor zarządzający",
    "DIRECTOR_OF_FOOTBALL": "dyrektor sportowy", "PHYSIO": "fizjoterapeuta", "SCOUT": "skaut", "MANAGER": "menedżer",
    "ASSISTANT_MANAGER": "asystent menedżera", "GOALKEEPING_COACH": "trener bramkarzy", "CHIEF_DOCTOR": "lekarz",
    "HEAD_OF_SPORTS_SCIENCE": "szef nauki o sporcie", "SPORTS_SCIENTIST": "naukowiec sportowy",
    "HEAD_PHYSIO": "główny fizjoterapeuta", "PERFORMANCE_ANALYST": "analityk", "HEAD_OF_YOUTH_DEVELOPMENT":
    "szef szkolenia młodzieży", "TECHNICAL_DIRECTOR": "dyrektor techniczny",
}
# stanowiska bez pracy w obszarach (zarzad, lekarz) - pomijane w rankingu sztabu
POZA_SZTABEM = {"CHAIRPERSON", "DIRECTOR", "MANAGING_DIRECTOR", "CHIEF_DOCTOR"}
TRENERSKIE = ("Kondycja", "Obrona", "Atak", "Strzały", "Technika", "Taktyka", "Praca z młodzieżą")
# obszary, w ktorych pracuje dane stanowisko (nieznane stanowisko - wszystkie)
OBSZARY_STANOWISK = {
    "COACH": TRENERSKIE, "ASSISTANT_MANAGER": TRENERSKIE, "MANAGER": TRENERSKIE,
    "GOALKEEPING_COACH": ("Bramkarze", "Praca z młodzieżą"),
    "SCOUT": ("Skauting",), "DIRECTOR_OF_FOOTBALL": ("Skauting",), "TECHNICAL_DIRECTOR": ("Skauting",),
    "PHYSIO": ("Fizjoterapia",), "HEAD_PHYSIO": ("Fizjoterapia",),
    "SPORTS_SCIENTIST": ("Fizjoterapia", "Kondycja"), "HEAD_OF_SPORTS_SCIENCE": ("Fizjoterapia", "Kondycja"),
    "PERFORMANCE_ANALYST": ("Analiza danych",), "HEAD_OF_YOUTH_DEVELOPMENT": ("Praca z młodzieżą",),
}
KANDYDATOW = 5
MAKS_WIEKU_KANDYDATA = 66


def _skala(nazwa, wartosc):
    if wartosc is None:
        return None
    return float(wartosc) if nazwa in SKALA_20 else float(wartosc) / 5.0


def oceny(atrybuty):
    """StaffAttributes -> {obszar: ocena 1-20 albo None}."""
    if atrybuty is None:
        return {}
    wynik = {}
    for obszar, pola in OBSZARY.items():
        wartosci = [_skala(p, getattr(atrybuty, p, None)) for p in pola]
        wartosci = [w for w in wartosci if w is not None]
        wynik[obszar] = round(sum(wartosci) / len(wartosci), 1) if wartosci else None
    return wynik


def _stanowisko(s):
    job = getattr(s, "job", None)
    nazwa = getattr(getattr(job, "label", None), "name", None)
    return nazwa if nazwa and nazwa != "UNKNOWN" else None


def obszary_osoby(s):
    return OBSZARY_STANOWISK.get(_stanowisko(s), tuple(OBSZARY))


def opis_osoby(s, kurs):
    o = oceny(s.attributes)
    swoje = obszary_osoby(s)
    najlepszy = max(((k, v) for k, v in o.items() if v is not None and k in swoje), key=lambda kv: kv[1],
                    default=(None, None))
    stanowisko = _stanowisko(s)
    return {"uid": str(s.uid), "nazwa": s.name, "wiek": s.age, "klub": s.club_name, "klub_uid": s.club_uid,
            "stanowisko": STANOWISKA.get(stanowisko, "inny personel"), "druzyna": s.team_slot or 0,
            "placa_tydzien": None if s.wage is None else round(float(s.wage) * kurs),
            "kontrakt_do": s.contract_end.isoformat() if s.contract_end else None,
            "oceny": o, "obszary": list(swoje), "najlepszy_obszar": najlepszy[0], "najlepsza_ocena": najlepszy[1]}


def analiza_personelu(personel, moj_klub_uid, kluby_ligi, kurs):
    """
    personel: rekordy fmsave Staff (wszystkie kluby). Zwraca {sztab, obszary, kandydaci}:
    sztab - moj personel (bez zarzadu i lekarza) z ocenami obszarow; obszary - najlepsza ocena w sztabie na tle
    najlepszych w klubach ligi (mediana, maksimum, miejsce); kandydaci - dla obszarow ponizej mediany ligi
    najlepsi pracownicy innych klubow.
    """
    moi, najlepsi_ligi = [], {}
    pula = []
    for s in personel:
        if s.attributes is None or _stanowisko(s) in POZA_SZTABEM or getattr(s, "is_human_manager", False) \
                or not getattr(s, "has_contract", True):
            continue
        # tylko obszary, w ktorych osoba pracuje na swoim stanowisku
        swoje = obszary_osoby(s)
        o = {k: v for k, v in oceny(s.attributes).items() if k in swoje}
        if s.club_uid == moj_klub_uid:
            moi.append(opis_osoby(s, kurs))
        elif s.club_uid in kluby_ligi:
            najlepsze = najlepsi_ligi.setdefault(s.club_uid, {})
            for obszar, v in o.items():
                if v is not None and v > najlepsze.get(obszar, 0):
                    najlepsze[obszar] = v
        if s.club_uid != moj_klub_uid and (s.age or 0) <= MAKS_WIEKU_KANDYDATA and _stanowisko(s) in OBSZARY_STANOWISK:
            pula.append((s, o))
    obszary = []
    for obszar in OBSZARY:
        moje = [m["oceny"].get(obszar) for m in moi if m["druzyna"] == 0 and obszar in m["obszary"]
                and m["oceny"].get(obszar) is not None]
        moja = max(moje, default=None)
        ligi = [k.get(obszar) for k in najlepsi_ligi.values() if k.get(obszar) is not None]
        mediana = round(median(ligi), 1) if ligi else None
        miejsce = (1 + sum(1 for v in ligi if moja is not None and v > moja)) if moja is not None and ligi else None
        kto = next((m["nazwa"] for m in moi if m["druzyna"] == 0 and obszar in m["obszary"]
                    and m["oceny"].get(obszar) == moja), None)
        obszary.append({"obszar": obszar, "moja": moja, "kto": kto, "mediana_ligi": mediana,
                        "najlepsza_ligi": max(ligi, default=None), "miejsce": miejsce, "klubow": len(ligi) + 1,
                        "luka": moja is None or (mediana is not None and moja < mediana)})
    kandydaci = {}
    for o in obszary:
        if not o["luka"]:
            continue
        lepsi = sorted(((s, oc) for s, oc in pula if (oc.get(o["obszar"]) or 0) > (o["moja"] or 0)),
                       key=lambda x: -(x[1].get(o["obszar"]) or 0))[:KANDYDATOW]
        kandydaci[o["obszar"]] = [opis_osoby(s, kurs) for s, _ in lepsi]
    moi.sort(key=lambda m: -(m["najlepsza_ocena"] or 0))
    return {"sztab": moi, "obszary": obszary, "kandydaci": kandydaci, "obszary_opis": {k: list(v) for k, v in OBSZARY.items()}}


def personel_z_zapisu(sciezka, moj_klub_uid, kluby_ligi, kurs):
    """Odczyt personelu z pliku zapisu i analiza (wolane w procesie potomnym albo zapasowo w watku)."""
    import warnings

    import fmsave
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        with fmsave.open(sciezka) as zapis:
            return analiza_personelu(zapis.staff(), moj_klub_uid, set(kluby_ligi), kurs)
