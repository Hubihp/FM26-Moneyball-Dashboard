"""
Funkcje "FM-owe" liczone z danych zapisu gry (FM27):

1. Ocena pod role FM: atrybuty zawodnika (1-20) wazone tak, jak gra opisuje role - atrybuty kluczowe (waga 1)
   i zalecane (waga 0,5). Wynik w skali 1-20 jak atrybuty. Role i ich atrybuty na wzor rol z gry.
2. Wagi silnika meczowego: testy spolecznosci FM-Arena (zmiana atrybutu -> punkty druzyny w tysiacach meczow)
   pokazuja, ze szybkosc i przyspieszenie daja najwiecej, potem skocznosc, zwinnosc i drybling. Opcjonalnie
   mnozymy wagi tych atrybutow (zawodnicy z pola; bramkarz bez zmian).
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

# Role FM27 (system rol z FM26: osobne role z pilka i bez pilki), nazwy polskie (oryginal angielski w komentarzu).
# Gra nie zapisuje atrybutow kluczowych rol w pliku - ponizsze listy to nasze przypisanie wg opisow rol w grze:
# kluczowe (waga 1) - to, co rola robi przede wszystkim; zalecane (waga 0,5) - to, co pomaga.
# klucz: (nazwa, faza "z" / "bez", kluczowe, zalecane)
_ROLE = {
    # --- bramkarze
    "bramkarz": ("Bramkarz", "z",  # Goalkeeper
                 "aerial_reach command_of_area communication handling reflexes positioning concentration agility",
                 "one_on_ones kicking throwing anticipation decisions"),
    "bramkarz_nogami": ("Bramkarz grający nogami", "z",  # Ball-Playing Goalkeeper
                        "kicking throwing first_touch passing composure decisions vision reflexes",
                        "handling one_on_ones anticipation concentration positioning technique"),
    "bramkarz_bez_ryzyka": ("Bramkarz bez ryzyka", "z",  # No-Nonsense Goalkeeper
                            "handling reflexes kicking aerial_reach positioning concentration",
                            "command_of_area communication bravery decisions"),
    "bramkarz_na_linii": ("Bramkarz na linii", "bez",  # Line-Holding Keeper
                          "reflexes handling positioning concentration one_on_ones agility",
                          "aerial_reach anticipation decisions"),
    "bramkarz_libero": ("Bramkarz-libero", "bez",  # Sweeper Keeper
                        "rushing_out one_on_ones anticipation composure decisions acceleration agility reflexes",
                        "command_of_area communication kicking first_touch passing pace"),
    # --- srodkowi obroncy
    "stoper": ("Środkowy obrońca", "z",  # Centre-Back
               "heading marking tackling positioning jumping_reach strength",
               "anticipation bravery composure concentration decisions pace passing"),
    "stoper_rozgrywajacy": ("Stoper rozgrywający", "z",  # Ball-Playing Centre-Back
                            "passing composure vision first_touch technique decisions heading marking tackling",
                            "anticipation positioning concentration strength jumping_reach"),
    "stoper_bez_ryzyka": ("Stoper bez ryzyka", "z",  # No-Nonsense Centre-Back
                          "heading marking tackling strength jumping_reach positioning",
                          "aggression bravery anticipation concentration"),
    "szeroki_stoper": ("Szeroki stoper", "z",  # Wide Centre-Back
                       "dribbling passing tackling marking positioning pace stamina",
                       "crossing first_touch technique decisions work_rate acceleration strength"),
    "stoper_wychodzacy": ("Stoper wychodzący z piłką", "z",  # Advanced Centre-Back
                          "dribbling passing first_touch composure decisions vision tackling",
                          "technique anticipation acceleration pace strength marking"),
    "stoper_podlaczajacy": ("Stoper podłączający się", "z",  # Overlapping Centre-Back
                            "crossing dribbling stamina work_rate pace off_the_ball tackling",
                            "passing acceleration teamwork marking positioning"),
    "stoper_doskakujacy": ("Stoper doskakujący", "bez",  # Stopping Centre-Back
                           "tackling aggression bravery anticipation decisions strength",
                           "marking heading jumping_reach acceleration concentration"),
    "stoper_asekurujacy": ("Stoper asekurujący", "bez",  # Covering Centre-Back
                           "marking anticipation concentration positioning pace acceleration",
                           "tackling decisions composure heading jumping_reach"),
    # --- boczni obroncy i wahadlowi
    "boczny": ("Boczny obrońca", "z",  # Full-Back
               "marking tackling anticipation concentration positioning teamwork",
               "crossing dribbling passing technique decisions work_rate pace stamina"),
    "boczny_do_srodka": ("Boczny obrońca do środka", "z",  # Inside Full-Back
                         "marking tackling positioning composure decisions strength",
                         "passing first_touch heading jumping_reach concentration anticipation"),
    "odwrocony_boczny": ("Odwrócony boczny obrońca", "z",  # Inverted Full-Back
                         "first_touch passing technique composure decisions positioning tackling",
                         "vision anticipation teamwork work_rate concentration"),
    "wahadlowy": ("Wahadłowy", "z",  # Wing-Back
                  "crossing dribbling tackling off_the_ball teamwork work_rate acceleration stamina",
                  "first_touch marking passing technique anticipation decisions positioning agility balance pace"),
    "wahadlowy_rozgrywajacy": ("Wahadłowy rozgrywający", "z",  # Playmaking Wing-Back
                               "first_touch passing technique vision decisions teamwork composure",
                               "dribbling crossing work_rate stamina tackling anticipation"),
    "wahadlowy_ofensywny": ("Wahadłowy ofensywny", "z",  # Advanced Wing-Back
                            "crossing dribbling technique flair off_the_ball work_rate acceleration stamina",
                            "first_touch passing pace agility balance teamwork decisions"),
    "wahadlowy_do_srodka": ("Wahadłowy do środka", "z",  # Inside Wing-Back
                            "first_touch passing technique decisions off_the_ball work_rate stamina",
                            "dribbling composure vision tackling anticipation teamwork"),
    "boczny_pressujacy": ("Pressujący boczny obrońca", "bez",  # Pressing Full-Back
                          "tackling aggression anticipation work_rate acceleration stamina",
                          "marking bravery decisions pace teamwork"),
    "boczny_defensywny": ("Defensywny boczny obrońca", "bez",  # Holding Full-Back
                          "marking tackling positioning concentration anticipation",
                          "heading strength jumping_reach decisions teamwork"),
    # --- defensywni pomocnicy
    "dp": ("Defensywny pomocnik", "z",  # Defensive Midfielder
           "tackling anticipation concentration positioning teamwork",
           "first_touch marking passing aggression composure decisions work_rate stamina"),
    "rozgrywajacy_z_glebi": ("Rozgrywający z głębi", "z",  # Deep-Lying Playmaker
                             "first_touch passing technique composure decisions teamwork vision",
                             "anticipation positioning balance"),
    "polobronca": ("Półobrońca", "z",  # Half-Back
                   "marking tackling anticipation composure concentration decisions positioning teamwork",
                   "first_touch passing heading jumping_reach strength"),
    "dp_pressujacy": ("Pressujący defensywny pomocnik", "bez",  # Pressing Defensive Midfielder
                      "tackling aggression anticipation work_rate teamwork stamina",
                      "bravery decisions acceleration strength"),
    "dp_oslaniajacy": ("Osłaniający defensywny pomocnik", "bez",  # Screening Defensive Midfielder
                       "marking anticipation concentration positioning teamwork",
                       "tackling decisions composure strength"),
    "dp_asekurujacy_boki": ("Asekurujący boki defensywny pomocnik", "bez",  # Wide Covering Defensive Midfielder
                            "anticipation positioning work_rate stamina pace tackling",
                            "marking decisions teamwork acceleration"),
    # --- srodkowi pomocnicy
    "srodkowy": ("Środkowy pomocnik", "z",  # Central Midfielder
                 "first_touch passing tackling decisions teamwork",
                 "technique anticipation composure concentration off_the_ball vision work_rate stamina"),
    "box_to_box": ("Box-to-box", "z",  # Box-to-Box Midfielder
                   "passing tackling off_the_ball teamwork work_rate stamina",
                   "dribbling finishing first_touch long_shots technique anticipation decisions positioning pace strength"),
    "box_to_box_rozgrywajacy": ("Rozgrywający box-to-box", "z",  # Box-to-Box Playmaker
                                "first_touch passing technique decisions vision off_the_ball work_rate stamina",
                                "dribbling composure anticipation acceleration"),
    "rozgrywajacy": ("Rozgrywający", "z",  # Midfield Playmaker
                     "first_touch passing technique composure decisions teamwork vision",
                     "dribbling flair anticipation off_the_ball agility"),
    "pomocnik_kanalowy": ("Pomocnik wbiegający w kanały", "z",  # Channel Midfielder
                          "off_the_ball work_rate acceleration stamina passing dribbling",
                          "first_touch technique crossing decisions pace finishing"),
    "sp_pressujacy": ("Pressujący środkowy pomocnik", "bez",  # Pressing Central Midfielder
                      "tackling aggression anticipation work_rate stamina acceleration",
                      "bravery decisions teamwork"),
    "sp_oslaniajacy": ("Osłaniający środkowy pomocnik", "bez",  # Screening Central Midfielder
                       "marking positioning concentration anticipation teamwork",
                       "tackling decisions strength"),
    "sp_szeroki": ("Szeroki środkowy pomocnik", "bez",  # Wide Central Midfielder
                   "work_rate stamina positioning teamwork tackling",
                   "anticipation pace acceleration decisions"),
    # --- boczni pomocnicy i skrzydlowi
    "boczny_pomocnik": ("Boczny pomocnik", "z",  # Wide Midfielder
                        "passing tackling decisions teamwork work_rate",
                        "crossing first_touch technique anticipation composure concentration off_the_ball positioning vision stamina"),
    "skrzydlowy": ("Skrzydłowy", "z",  # Winger
                   "crossing dribbling technique acceleration agility",
                   "first_touch passing off_the_ball work_rate balance pace stamina"),
    "skrzydlowy_rozgrywajacy": ("Rozgrywający skrzydłowy", "z",  # Playmaking Winger
                                "first_touch passing technique vision decisions composure",
                                "dribbling crossing flair off_the_ball agility"),
    "odwrocony_skrzydlowy": ("Odwrócony skrzydłowy", "z",  # Inverted Winger
                             "crossing dribbling passing technique acceleration agility",
                             "first_touch long_shots composure decisions off_the_ball vision work_rate balance pace stamina"),
    "odwrocony_napastnik": ("Odwrócony napastnik", "z",  # Inside Forward
                            "dribbling finishing first_touch technique off_the_ball acceleration agility",
                            "long_shots passing anticipation composure flair balance pace"),
    "szeroki_napastnik": ("Szeroki napastnik", "z",  # Wide Forward
                          "finishing off_the_ball dribbling acceleration pace",
                          "heading first_touch anticipation composure strength"),
    "skrzydlowy_cofajacy": ("Skrzydłowy wracający do obrony", "bez",  # Tracking Winger
                            "work_rate stamina tackling teamwork positioning",
                            "marking anticipation acceleration pace"),
    "skrzydlowy_wyjscie_szerokie": ("Skrzydłowy na wyjście (szeroko)", "bez",  # Wide Outlet Winger
                                    "acceleration pace off_the_ball anticipation",
                                    "dribbling first_touch work_rate"),
    "skrzydlowy_wyjscie_wewnatrz": ("Skrzydłowy na wyjście (do środka)", "bez",  # Inside Outlet Winger
                                    "off_the_ball anticipation acceleration composure",
                                    "first_touch dribbling pace decisions"),
    # --- ofensywni pomocnicy
    "ofensywny": ("Ofensywny pomocnik", "z",  # Attacking Midfielder
                  "first_touch long_shots passing technique composure decisions flair off_the_ball",
                  "dribbling anticipation vision agility"),
    "rozgrywajacy_wysuniety": ("Wysunięty rozgrywający", "z",  # Advanced Playmaker
                               "first_touch passing technique composure decisions vision off_the_ball",
                               "dribbling flair anticipation agility teamwork"),
    "wolna_rola": ("Wolna rola", "z",  # Free Role
                   "first_touch passing technique dribbling flair vision decisions off_the_ball",
                   "composure anticipation agility balance"),
    "cien": ("Cień napastnika", "z",  # Shadow Striker / Second Striker
             "dribbling finishing first_touch anticipation composure off_the_ball acceleration",
             "passing technique concentration decisions work_rate agility balance pace stamina"),
    "op_cofajacy": ("Ofensywny pomocnik wracający", "bez",  # Tracking Attacking Midfielder
                    "work_rate stamina teamwork tackling anticipation",
                    "positioning decisions aggression"),
    "op_wyjscie_srodek": ("Ofensywny pomocnik na wyjście", "bez",  # Central Outlet Attacking Midfielder
                          "off_the_ball anticipation first_touch composure",
                          "acceleration decisions technique"),
    "op_wyjscie_rozdzielajace": ("Ofensywny pomocnik rozdzielający", "bez",  # Splitting Outlet Attacking Midfielder
                                 "off_the_ball acceleration pace anticipation",
                                 "dribbling first_touch decisions"),
    # --- napastnicy
    "napastnik": ("Środkowy napastnik", "z",  # Centre Forward
                  "finishing first_touch heading off_the_ball composure strength",
                  "dribbling passing technique anticipation decisions acceleration jumping_reach"),
    "snajper": ("Snajper", "z",  # Poacher
                "finishing anticipation composure off_the_ball", "first_touch heading technique decisions acceleration"),
    "target_man": ("Target man", "z",  # Target Forward
                   "heading bravery teamwork balance jumping_reach strength",
                   "finishing first_touch aggression anticipation composure decisions off_the_ball"),
    "cofniety_napastnik": ("Cofnięty napastnik", "z",  # Deep-Lying Forward
                           "first_touch passing technique composure decisions off_the_ball teamwork",
                           "finishing vision anticipation balance strength"),
    "napastnik_kanalowy": ("Napastnik wbiegający w kanały", "z",  # Channel Forward
                           "off_the_ball acceleration pace dribbling finishing work_rate",
                           "first_touch anticipation composure crossing stamina"),
    "falszywa_9": ("Fałszywa 9", "z",  # False Nine
                   "dribbling first_touch passing technique composure decisions off_the_ball vision agility",
                   "finishing anticipation flair teamwork balance"),
    "n_cofajacy": ("Napastnik wracający do obrony", "bez",  # Tracking Centre Forward
                   "aggression anticipation bravery decisions teamwork work_rate acceleration stamina",
                   "first_touch composure concentration agility balance strength"),
    "n_wyjscie_srodek": ("Napastnik na wyjście", "bez",  # Central Outlet Centre Forward
                         "off_the_ball anticipation strength first_touch",
                         "heading composure balance"),
    "n_wyjscie_rozdzielajace": ("Napastnik rozdzielający", "bez",  # Splitting Outlet Centre Forward
                                "off_the_ball acceleration pace anticipation",
                                "dribbling finishing decisions"),
}


def _rola(klucz):
    nazwa, faza, kluczowe, zalecane = _ROLE[klucz]
    return {"nazwa": nazwa, "faza": faza, "kluczowe": kluczowe.split(), "zalecane": zalecane.split()}


def _lista(klucze):
    return [_rola(k) for k in klucze.split()]


_BOCZNI = "boczny boczny_do_srodka odwrocony_boczny wahadlowy wahadlowy_rozgrywajacy wahadlowy_ofensywny " \
          "wahadlowy_do_srodka boczny_pressujacy boczny_defensywny"
_WAHADLOWI = "wahadlowy wahadlowy_rozgrywajacy wahadlowy_ofensywny wahadlowy_do_srodka boczny boczny_do_srodka " \
             "odwrocony_boczny boczny_pressujacy boczny_defensywny"
_BOCZNI_POMOCNICY = "boczny_pomocnik skrzydlowy skrzydlowy_rozgrywajacy odwrocony_skrzydlowy skrzydlowy_cofajacy " \
                    "skrzydlowy_wyjscie_szerokie skrzydlowy_wyjscie_wewnatrz"
_SKRZYDLOWI = "skrzydlowy odwrocony_napastnik odwrocony_skrzydlowy skrzydlowy_rozgrywajacy szeroki_napastnik " \
              "skrzydlowy_cofajacy skrzydlowy_wyjscie_szerokie skrzydlowy_wyjscie_wewnatrz"

# Role FM dla kazdej puli pozycji aplikacji (z pilka i bez pilki)
ROLE_FM = {
    "Bramkarz": _lista("bramkarz bramkarz_nogami bramkarz_bez_ryzyka bramkarz_na_linii bramkarz_libero"),
    "Środkowy Obrońca": _lista("stoper stoper_rozgrywajacy stoper_bez_ryzyka szeroki_stoper stoper_wychodzacy "
                                "stoper_podlaczajacy stoper_doskakujacy stoper_asekurujacy"),
    "Lewy Obrońca": _lista(_BOCZNI), "Prawy Obrońca": _lista(_BOCZNI),
    "Lewy Wahadłowy": _lista(_WAHADLOWI), "Prawy Wahadłowy": _lista(_WAHADLOWI),
    "Defensywny Pomocnik": _lista("dp rozgrywajacy_z_glebi polobronca dp_pressujacy dp_oslaniajacy dp_asekurujacy_boki"),
    "Środkowy Pomocnik": _lista("srodkowy box_to_box box_to_box_rozgrywajacy rozgrywajacy pomocnik_kanalowy "
                                 "sp_pressujacy sp_oslaniajacy sp_szeroki"),
    "Lewy Pomocnik": _lista(_BOCZNI_POMOCNICY), "Prawy Pomocnik": _lista(_BOCZNI_POMOCNICY),
    "Ofensywny Pomocnik": _lista("ofensywny rozgrywajacy_wysuniety wolna_rola cien op_cofajacy op_wyjscie_srodek "
                                  "op_wyjscie_rozdzielajace"),
    "Lewy Skrzydłowy": _lista(_SKRZYDLOWI), "Prawy Skrzydłowy": _lista(_SKRZYDLOWI),
    "Napastnik": _lista("napastnik snajper target_man cofniety_napastnik napastnik_kanalowy falszywa_9 n_cofajacy "
                        "n_wyjscie_srodek n_wyjscie_rozdzielajace"),
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
    Kolumny 'Rola FM' i 'Ocena roli' (najlepsza rola z pilka albo wybrana `rola`), 'Rola bez piłki' i 'Ocena roli bez
    piłki' (najlepsza rola bez pilki) oraz 'Rola|<nazwa>' dla kazdej roli pozycji (karta zawodnika).
    Bez atrybutow w danych (CSV, demo) - bez zmian.
    """
    role = ROLE_FM.get(pozycja) or []
    if not role or not ma_atrybuty(df):
        return df
    df = df.copy()
    bramkarz = pozycja == "Bramkarz"
    oceny = pd.DataFrame({r["nazwa"]: ocena_roli(df, r, silnik, bramkarz) for r in role}, index=df.index)
    for r in role:      # karta zawodnika: 'Rola|' - role z pilka, 'RolaBez|' - role bez pilki
        df[("RolaBez|" if r.get("faza") == "bez" else "Rola|") + r["nazwa"]] = oceny[r["nazwa"]]

    def najlepsza(nazwy):
        czesc = oceny[nazwy]
        pelne = czesc.notna().any(axis=1)
        return czesc.fillna(-1).idxmax(axis=1).where(pelne), czesc.max(axis=1)
    z_pilka = [r["nazwa"] for r in role if r.get("faza", "z") == "z"]
    bez_pilki = [r["nazwa"] for r in role if r.get("faza") == "bez"]
    if rola and rola in oceny.columns:
        df["Ocena roli"] = oceny[rola]
        df["Rola FM"] = rola
    else:
        df["Rola FM"], df["Ocena roli"] = najlepsza(z_pilka or list(oceny.columns))
    if bez_pilki:
        df["Rola bez piłki"], df["Ocena roli bez piłki"] = najlepsza(bez_pilki)
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


# --- Status w kadrze (kontrakt) ------------------------------------------------------------
STATUSY_KADRY = {1: "gwiazda zespołu", 2: "ważny zawodnik", 3: "podstawowy zawodnik", 4: "zawodnik kadry",
                 5: "rezerwowy wchodzący z ławki", 7: "zawodnik z marginesu", 9: "awaryjny rezerwowy",
                 10: "wschodzący talent", 11: "perspektywiczny talent", 13: "młodzieżowiec",
                 14: "podstawowy w drużynie B", 15: "pierwszy bramkarz", 16: "bramkarz pucharowy",
                 17: "bramkarz krajowych pucharów", 18: "bramkarz pucharów międzynarodowych", 20: "rezerwowy",
                 21: "awaryjny bramkarz", 22: "zbędny"}

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


def kraj_mojego_klubu(df, moj_klub_uid):
    """Kraj mojego klubu - z wierszy jego zawodnikow (najczestszy kraj klubu)."""
    if df is None or moj_klub_uid is None or "Klub_UID" not in df.columns or "Klub_kraj_ID" not in df.columns:
        return None
    kraj = pd.to_numeric(df.loc[df["Klub_UID"] == moj_klub_uid, "Klub_kraj_ID"], errors="coerce").dropna()
    return int(kraj.mode().iloc[0]) if len(kraj) else None


def dolicz_fm(df, moj_klub_uid, data_gry=None, kraj=None):
    """
    Kolumny niezalezne od wybranej roli: 'Klauzula', 'HG', 'Status w kadrze'.
    kraj: kraj mojego klubu z calych danych (pula pozycji moze nie miec moich zawodnikow).
    """
    if "Klub_kraj_ID" not in df.columns:
        return df
    df = df.copy()
    kraj = kraj if kraj is not None else kraj_mojego_klubu(df, moj_klub_uid)
    df["Klauzula"] = klauzula_dla_klubu(df, kraj, data_gry)
    df["HG"] = home_grown(df, kraj, moj_klub_uid)
    if "Status_kadry" in df.columns:
        df["Status w kadrze"] = pd.to_numeric(df["Status_kadry"], errors="coerce").map(STATUSY_KADRY)
    return df
