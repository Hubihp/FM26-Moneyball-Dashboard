"""
Funkcje "FM-owe" liczone z danych zapisu gry (FM27):

1. Ocena pod role FM: atrybuty zawodnika (1-20) wazone tak, jak gra opisuje role - atrybuty kluczowe (waga 1)
   i zalecane (waga 0,5). Wynik w skali 1-20 jak atrybuty. Role i ich atrybuty na wzor rol z gry.
2. Wagi silnika meczowego: testy spolecznosci FM-Arena (zmiana atrybutu -> punkty druzyny w tysiacach meczow)
   pokazuja, ze szybkosc i przyspieszenie daja najwiecej, potem skocznosc, zwinnosc i drybling. Opcjonalnie
   mnozymy wagi tych atrybutow (zawodnicy z pola; bramkarz bez zmian).
3. Szansa na transfer: czy zawodnik przyjdzie do mojego klubu - z roznicy reputacji mojego klubu i zawodnika.
   Kalibracja na 13 153 transferach miedzy sezonami kariery FM27: do klubu o reputacji nizszej niz wlasna
   o ponad 1000 przechodzi 11% zawodnikow, o ponad 1500 - 4%, o ponad 2000 - 1,4%.
4. Klauzula odstepnego: najnizsza kwota z klauzul kontraktu, ktora obowiazuje wobec mojego klubu (ogolna,
   dla klubow zagranicznych albo krajowych - wg kraju mojego klubu; krajowa tylko do daty wygasniecia).
5. Home-grown: czy zawodnik jest wychowankiem kraju mojego klubu (wymog rejestracji, np. 8 z 25 w Lidze
   Mistrzow) albo samego mojego klubu.
Atrybuty to te z ekranu zawodnika w grze; zapis ma je dla wszystkich zawodnikow (w grze widac je po
skautingu). Dane ukryte (CA/PA, atrybuty ukryte, osobowosc) nie sa uzywane.
"""
import numpy as np
import pandas as pd

PREFIKS_ATRYBUTU = "Atr|"

# atrybut fmsave -> nazwa w grze (polska)
ATRYBUTY = {
    "corners": "Rzuty rożne", "crossing": "Dośrodkowania", "dribbling": "Drybling", "finishing": "Wykończenie",
    "first_touch": "Przyjęcie piłki", "free_kick_taking": "Rzuty wolne", "heading": "Gra głową",
    "long_shots": "Strzały z dystansu", "long_throws": "Długie wyrzuty", "marking": "Krycie", "passing": "Podania",
    "penalty_taking": "Rzuty karne", "tackling": "Odbiór piłki", "technique": "Technika",
    "aggression": "Agresja", "anticipation": "Przewidywanie", "bravery": "Odwaga", "composure": "Opanowanie",
    "concentration": "Koncentracja", "decisions": "Decyzje", "determination": "Determinacja", "flair": "Kreatywność",
    "leadership": "Przywództwo", "off_the_ball": "Gra bez piłki", "positioning": "Ustawianie się",
    "teamwork": "Gra zespołowa", "vision": "Wizja gry", "work_rate": "Pracowitość",
    "acceleration": "Przyspieszenie", "agility": "Zwinność", "balance": "Równowaga", "jumping_reach": "Skoczność",
    "natural_fitness": "Naturalna kondycja", "pace": "Szybkość", "stamina": "Wytrzymałość", "strength": "Siła",
    "aerial_reach": "Zasięg w powietrzu", "command_of_area": "Panowanie w polu karnym", "communication": "Komunikacja",
    "eccentricity": "Ekscentryczność", "handling": "Chwytanie", "kicking": "Wybicia", "one_on_ones": "Sam na sam",
    "punching": "Piąstkowanie", "reflexes": "Refleks", "rushing_out": "Wychodzenie z bramki", "throwing": "Wyrzuty",
}

# 2. Mnozniki wag z testow silnika (FM-Arena, testy atrybutow FM21-FM24): szybkosc i przyspieszenie najwazniejsze,
# potem skocznosc, zwinnosc, drybling. Umiarkowane, bo wyniki zaleza od wersji silnika i taktyki.
WAGI_SILNIKA = {"pace": 1.6, "acceleration": 1.6, "jumping_reach": 1.3, "agility": 1.2, "dribbling": 1.15,
                "stamina": 1.1, "strength": 1.1, "anticipation": 1.1}
WAGA_KLUCZOWEGO, WAGA_ZALECANEGO = 1.0, 0.5

_R = {   # skroty list atrybutow rol
    "bramkarz": ("aerial_reach command_of_area communication handling kicking concentration positioning reflexes agility",
                 "one_on_ones throwing anticipation decisions"),
    "bramkarz_libero": ("command_of_area kicking one_on_ones reflexes anticipation composure concentration positioning "
                        "rushing_out agility", "aerial_reach communication first_touch handling passing throwing "
                        "decisions vision acceleration"),
    "stoper": ("heading marking tackling positioning jumping_reach strength",
               "aggression anticipation bravery composure concentration decisions pace"),
    "stoper_rozgrywajacy": ("heading marking passing tackling composure positioning jumping_reach strength",
                            "first_touch technique vision anticipation bravery concentration decisions pace"),
    "stoper_agresywny": ("heading tackling aggression bravery decisions jumping_reach strength",
                         "marking anticipation composure concentration positioning"),
    "boczny": ("marking tackling anticipation concentration positioning teamwork",
               "crossing dribbling passing technique decisions work_rate pace stamina"),
    "wahadlowy": ("crossing dribbling tackling off_the_ball teamwork work_rate acceleration stamina",
                  "first_touch marking passing technique anticipation decisions positioning agility balance pace"),
    "wahadlowy_pelny": ("crossing dribbling technique flair off_the_ball teamwork work_rate acceleration stamina",
                        "first_touch marking passing tackling anticipation decisions agility balance pace"),
    "dp": ("tackling anticipation concentration positioning teamwork",
           "first_touch marking passing aggression composure decisions work_rate stamina strength"),
    "regista": ("first_touch passing technique composure decisions teamwork vision",
                "anticipation off_the_ball positioning balance"),
    "niszczyciel": ("tackling aggression anticipation teamwork work_rate stamina",
                    "marking bravery concentration positioning agility strength"),
    "box_to_box": ("passing tackling off_the_ball teamwork work_rate stamina",
                   "dribbling finishing first_touch long_shots technique aggression anticipation composure decisions "
                   "positioning acceleration balance pace strength"),
    "rozgrywajacy": ("first_touch passing technique composure decisions off_the_ball teamwork vision",
                     "dribbling flair anticipation agility"),
    "mezzala": ("passing technique decisions off_the_ball work_rate acceleration",
                "dribbling first_touch long_shots vision composure balance stamina"),
    "srodkowy": ("first_touch passing tackling decisions teamwork",
                 "technique anticipation composure concentration off_the_ball vision work_rate stamina"),
    "boczny_pomocnik": ("passing tackling decisions teamwork work_rate",
                        "crossing first_touch technique anticipation composure concentration off_the_ball positioning "
                        "vision stamina"),
    "skrzydlowy": ("crossing dribbling technique acceleration agility",
                   "first_touch passing off_the_ball work_rate balance pace stamina"),
    "odwrocony_skrzydlowy": ("crossing dribbling passing technique acceleration agility",
                             "first_touch long_shots composure decisions off_the_ball vision work_rate balance pace "
                             "stamina"),
    "ofensywny": ("first_touch long_shots passing technique composure decisions flair off_the_ball",
                  "dribbling anticipation vision agility"),
    "cien": ("dribbling finishing first_touch anticipation composure off_the_ball acceleration",
             "passing technique concentration decisions work_rate agility balance pace stamina"),
    "enganche": ("first_touch passing technique composure decisions vision",
                 "dribbling anticipation flair off_the_ball teamwork agility"),
    "odwrocony_napastnik": ("dribbling finishing first_touch technique off_the_ball acceleration agility",
                            "long_shots passing anticipation composure flair balance pace"),
    "snajper": ("finishing anticipation composure off_the_ball", "first_touch heading technique decisions acceleration"),
    "wysuniety": ("dribbling finishing first_touch technique composure off_the_ball acceleration",
                  "passing anticipation decisions work_rate agility balance pace stamina"),
    "target_man": ("heading bravery teamwork balance jumping_reach strength",
                   "finishing first_touch aggression anticipation composure decisions off_the_ball"),
    "falszywa_9": ("dribbling first_touch passing technique composure decisions off_the_ball vision agility",
                   "finishing anticipation flair teamwork balance"),
    "pressujacy": ("aggression anticipation bravery decisions teamwork work_rate acceleration stamina",
                   "first_touch composure concentration agility balance strength"),
}


def _rola(nazwa, klucz):
    kluczowe, zalecane = _R[klucz]
    return {"nazwa": nazwa, "kluczowe": kluczowe.split(), "zalecane": zalecane.split()}


_OBRONCY_BOCZNI = [_rola("Boczny obrońca", "boczny"), _rola("Wahadłowy", "wahadlowy"),
                   _rola("Pełny wahadłowy", "wahadlowy_pelny")]
_WAHADLOWI = [_rola("Wahadłowy", "wahadlowy"), _rola("Pełny wahadłowy", "wahadlowy_pelny"),
              _rola("Boczny obrońca", "boczny")]
_BOCZNI_POMOCNICY = [_rola("Boczny pomocnik", "boczny_pomocnik"), _rola("Skrzydłowy", "skrzydlowy"),
                     _rola("Odwrócony skrzydłowy", "odwrocony_skrzydlowy")]
_SKRZYDLOWI = [_rola("Skrzydłowy", "skrzydlowy"), _rola("Odwrócony napastnik", "odwrocony_napastnik"),
               _rola("Odwrócony skrzydłowy", "odwrocony_skrzydlowy")]

# 1. Role FM dla kazdej puli pozycji aplikacji (na wzor rol z gry; nazwy polskie)
ROLE_FM = {
    "Bramkarz": [_rola("Bramkarz", "bramkarz"), _rola("Bramkarz-libero", "bramkarz_libero")],
    "Środkowy Obrońca": [_rola("Środkowy obrońca", "stoper"), _rola("Stoper rozgrywający", "stoper_rozgrywajacy"),
                         _rola("Stoper agresywny", "stoper_agresywny")],
    "Lewy Obrońca": _OBRONCY_BOCZNI, "Prawy Obrońca": _OBRONCY_BOCZNI,
    "Lewy Wahadłowy": _WAHADLOWI, "Prawy Wahadłowy": _WAHADLOWI,
    "Defensywny Pomocnik": [_rola("Defensywny pomocnik", "dp"), _rola("Regista", "regista"),
                            _rola("Niszczyciel", "niszczyciel")],
    "Środkowy Pomocnik": [_rola("Środkowy pomocnik", "srodkowy"), _rola("Box-to-box", "box_to_box"),
                          _rola("Rozgrywający", "rozgrywajacy"), _rola("Mezzala", "mezzala")],
    "Lewy Pomocnik": _BOCZNI_POMOCNICY, "Prawy Pomocnik": _BOCZNI_POMOCNICY,
    "Ofensywny Pomocnik": [_rola("Ofensywny pomocnik", "ofensywny"), _rola("Cień napastnika", "cien"),
                           _rola("Enganche", "enganche")],
    "Lewy Skrzydłowy": _SKRZYDLOWI, "Prawy Skrzydłowy": _SKRZYDLOWI,
    "Napastnik": [_rola("Wysunięty napastnik", "wysuniety"), _rola("Snajper", "snajper"),
                  _rola("Target man", "target_man"), _rola("Fałszywa 9", "falszywa_9"),
                  _rola("Napastnik pressujący", "pressujacy")],
}


def wagi_roli(rola, silnik=True, bramkarz=False):
    """{atrybut: waga} roli: kluczowe 1, zalecane 0,5; z wagami silnika (poza bramkarzem)."""
    wagi = {a: WAGA_KLUCZOWEGO for a in rola["kluczowe"]}
    for a in rola["zalecane"]:
        wagi.setdefault(a, WAGA_ZALECANEGO)
    if silnik and not bramkarz:
        wagi = {a: w * WAGI_SILNIKA.get(a, 1.0) for a, w in wagi.items()}
    return wagi


def ma_atrybuty(df):
    return any(str(k).startswith(PREFIKS_ATRYBUTU) for k in df.columns)


def ocena_roli(df, rola, silnik=True, bramkarz=False):
    """Ocena zawodnikow w roli (1-20): srednia wazona atrybutow roli; NaN gdy brak atrybutow."""
    wagi = wagi_roli(rola, silnik, bramkarz)
    licznik = pd.Series(0.0, index=df.index)
    mianownik = 0.0
    for atrybut, waga in wagi.items():
        kol = PREFIKS_ATRYBUTU + atrybut
        if kol not in df.columns:
            continue
        licznik = licznik + pd.to_numeric(df[kol], errors="coerce") * waga
        mianownik += waga
    if not mianownik:
        return pd.Series(np.nan, index=df.index)
    return (licznik / mianownik).round(1)


def dolicz_role(df, pozycja, rola=None, silnik=True):
    """
    Kolumny 'Ocena roli' i 'Rola FM' (najlepsza rola pozycji albo wybrana `rola`) oraz 'Rola|<nazwa>' dla kazdej
    roli pozycji (karta zawodnika). Bez atrybutow w danych (CSV, demo) - bez zmian.
    """
    role = ROLE_FM.get(pozycja) or []
    if not role or not ma_atrybuty(df):
        return df
    df = df.copy()
    bramkarz = pozycja == "Bramkarz"
    oceny = pd.DataFrame({r["nazwa"]: ocena_roli(df, r, silnik, bramkarz) for r in role}, index=df.index)
    for r in role:
        df["Rola|" + r["nazwa"]] = oceny[r["nazwa"]]
    if rola and rola in oceny.columns:
        df["Ocena roli"] = oceny[rola]
        df["Rola FM"] = rola
    else:
        pelne = oceny.notna().any(axis=1)
        df["Ocena roli"] = oceny.max(axis=1)
        df["Rola FM"] = oceny.fillna(-1).idxmax(axis=1).where(pelne)
    return df


# --- 3. Szansa na transfer ---------------------------------------------------------------------
# Udzial transferow (kariera FM27, 2 sezony), w ktorych nowy klub mial reputacje nizsza od reputacji zawodnika
# co najmniej o tyle: roznica -> udzial. Interpolacja liniowa miedzy punktami.
UDZIAL_TRANSFEROW = ((-3000, 0.006), (-2000, 0.014), (-1500, 0.04), (-1000, 0.114), (-500, 0.255), (0, 0.50),
                     (600, 0.75))
# starsi schodza nizej chetniej, mlodzi rzadziej (10. percentyl roznicy: 15-23 lat -850, 31+ -1355)
KOREKTA_WIEKU = ((23, -250), (30, 0), (99, 300))
PROGI_SZANSY = ((0.40, "wysoka"), (0.15, "średnia"), (0.04, "niska"), (0.0, "bardzo niska"))
KOLEJNOSC_SZANSY = {"bardzo niska": 0, "niska": 1, "średnia": 2, "wysoka": 3}


def udzial_transferow(roznica):
    """Roznica reputacji (moj klub - zawodnik) -> udzial prawdziwych transferow z taka lub wieksza roznica."""
    x = [p[0] for p in UDZIAL_TRANSFEROW]
    y = [p[1] for p in UDZIAL_TRANSFEROW]
    return np.interp(roznica, x, y)


def szansa_transferu(reputacja, wiek, reputacja_mojego_klubu):
    """Serie: (kategoria szansy, udzial transferow w %) dla kazdego zawodnika."""
    roznica = reputacja_mojego_klubu - pd.to_numeric(reputacja, errors="coerce")
    wiek = pd.to_numeric(wiek, errors="coerce")
    korekta = pd.Series(0.0, index=roznica.index)
    for do_wieku, k in reversed(KOREKTA_WIEKU):
        korekta = korekta.where(~(wiek <= do_wieku), k)
    udzial = pd.Series(udzial_transferow((roznica + korekta).fillna(-10_000).to_numpy()), index=roznica.index)
    udzial = udzial.where(roznica.notna())
    kategoria = pd.Series(None, index=roznica.index, dtype=object)
    for prog, nazwa in reversed(PROGI_SZANSY):
        kategoria = kategoria.where(~(udzial >= prog), nazwa)
    return kategoria.where(udzial.notna()), (udzial * 100).round(1)


# --- 4. Klauzula odstepnego ----------------------------------------------------------------------
def klauzula_dla_klubu(df, kraj_mojego_klubu, data_gry=None):
    """Najnizsza klauzula odstepnego obowiazujaca wobec mojego klubu (kwota) albo NaN."""
    dzis = pd.Timestamp(data_gry) if data_gry is not None else pd.Timestamp.today()
    kraj_klubu = pd.to_numeric(df.get("Klub_kraj_ID"), errors="coerce") if "Klub_kraj_ID" in df.columns else None
    kandydaci = []
    if "Klauzula_ogolna" in df.columns:
        kandydaci.append(df["Klauzula_ogolna"])
    if kraj_klubu is not None and kraj_mojego_klubu is not None:
        zagranica = kraj_klubu.notna() & (kraj_klubu != kraj_mojego_klubu)
        kraj = kraj_klubu == kraj_mojego_klubu
        if "Klauzula_zagraniczna" in df.columns:
            kandydaci.append(df["Klauzula_zagraniczna"].where(zagranica))
        if "Klauzula_krajowa" in df.columns:
            wazna = df["Klauzula_krajowa_do"].isna() | (df["Klauzula_krajowa_do"] >= dzis) \
                if "Klauzula_krajowa_do" in df.columns else True
            kandydaci.append(df["Klauzula_krajowa"].where(kraj & wazna))
    if not kandydaci:
        return pd.Series(np.nan, index=df.index)
    return pd.concat(kandydaci, axis=1).min(axis=1)


# --- 5. Home-grown ---------------------------------------------------------------------------------
def home_grown(df, kraj_mojego_klubu, moj_klub_uid):
    """'HG' : 'klub' (wychowanek mojego klubu), 'kraj' (wychowanek kraju mojego klubu) albo None."""
    def zawiera(kolumna, wartosc):
        if kolumna not in df.columns or wartosc is None:
            return pd.Series(False, index=df.index)
        szukane = str(int(wartosc))
        return df[kolumna].fillna("").astype(str).map(lambda t: szukane in t.split(";"))
    klub = zawiera("HG_kluby", moj_klub_uid)
    kraj = zawiera("HG_kraje", kraj_mojego_klubu)
    wynik = pd.Series(None, index=df.index, dtype=object)
    wynik = wynik.where(~kraj, "kraj")
    return wynik.where(~klub, "klub")


def kraj_i_reputacja_klubu(df, moj_klub_uid):
    """(kraj, reputacja) mojego klubu - z wierszy jego zawodnikow."""
    if moj_klub_uid is None or "Klub_UID" not in df.columns:
        return None, None
    moi = df[df["Klub_UID"] == moj_klub_uid]
    kraj = pd.to_numeric(moi.get("Klub_kraj_ID"), errors="coerce").dropna() if "Klub_kraj_ID" in moi.columns else []
    rep = pd.to_numeric(moi.get("Klub_reputacja"), errors="coerce").dropna() if "Klub_reputacja" in moi.columns else []
    return (int(kraj.mode().iloc[0]) if len(kraj) else None), (float(rep.median()) if len(rep) else None)


def dolicz_fm(df, moj_klub_uid, data_gry=None, kontekst=None):
    """
    Kolumny niezalezne od wybranej roli: 'Szansa transferu' (+ 'Szansa_udział'), 'Klauzula', 'HG'.
    kontekst: (kraj, reputacja) mojego klubu z calych danych (pula pozycji moze nie miec moich zawodnikow).
    """
    if "Reputacja" not in df.columns:
        return df
    df = df.copy()
    kraj, rep = kontekst if kontekst is not None else kraj_i_reputacja_klubu(df, moj_klub_uid)
    if rep is not None:
        szansa, udzial = szansa_transferu(df["Reputacja"], df.get("Wiek"), rep)
        moi = df["Klub_UID"] == moj_klub_uid if "Klub_UID" in df.columns else False
        df["Szansa transferu"] = szansa.where(~moi)
        df["Szansa_udział"] = udzial.where(~moi)
    df["Klauzula"] = klauzula_dla_klubu(df, kraj, data_gry)
    df["HG"] = home_grown(df, kraj, moj_klub_uid)
    return df
