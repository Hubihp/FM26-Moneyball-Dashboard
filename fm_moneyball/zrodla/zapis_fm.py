"""
Zrodlo: plik zapisu kariery FM26 (.fm), czytany biblioteka `fmsave`.

Plik .fm to kontener z sekcjami skompresowanymi Zstandardem (bez szyfrowania); fmsave
rozpakowuje go i dekoduje rekordy gry. Z jednego zapisu powstaja od razu ramki dla
wszystkich siedmiu pozycji - bez eksportow CSV i recznego przypisywania plikow.

Funkcje budujace ramki przyjmuja zwykle obiekty z atrybutami (rekordy fmsave), wiec mozna je
testowac bez prawdziwego zapisu. Zapis nie zawiera nazw lig (gra bierze je z wlasnej bazy),
dlatego nazwy pochodza z mapy `dane/nazwy_rozgrywek.csv` (id rozgrywek w bazie -> nazwa),
ktora mozna zbudowac automatycznie ze starych eksportow CSV (`zbuduj_mape_nazw_lig`).
"""
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta

import numpy as np
import pandas as pd

from fm_moneyball.kraje import kraj_z_licznika, kraje_z_kotwic, narodowosci_lig
from fm_moneyball.mapy import KATALOG_DANYCH, KATALOG_DOMOWY, wczytaj_mape, zapisz_mape
from fm_moneyball.parsery import fmt_eur
from fm_moneyball.role import ATRYBUTY_PL, KOLUMNA_ATRYBUTU
from fm_moneyball.schemat import dopelnij_schemat
from fm_moneyball.stale import MAPOWANIE_NAZW_LIG, POZYCJE, kolumna_oceny

PLIK_NAZW_ROZGRYWEK = KATALOG_DANYCH / "nazwy_rozgrywek.csv"
PLIK_NAZW_UZYTKOWNIKA = KATALOG_DOMOWY / "nazwy_rozgrywek.csv"

# Waluta bazowa zapisu nie jest waluta wyswietlana w grze. Autor fmsave zmierzyl, ze ekran gry
# pokazuje kwoty ok. 1,157 razy wieksze niz zapisane (to odpowiada kursowi GBP -> EUR).
KURS_DOMYSLNY = 1.157

# Kod pozycji z fmsave -> grupa pozycji w aplikacji
POZYCJA_Z_KODU = {
    "gk": "Bramkarz",
    "dc": "Środkowy Obrońca", "sw": "Środkowy Obrońca",
    "dl": "Boczny Obrońca", "dr": "Boczny Obrońca",
    "wbl": "Wahadłowy", "wbr": "Wahadłowy",
    "dm": "Defensywny Pomocnik",
    "mc": "Środkowy Pomocnik",
    "amc": "Ofensywny Pomocnik",
    "ml": "Skrzydłowy", "mr": "Skrzydłowy", "aml": "Skrzydłowy", "amr": "Skrzydłowy",
    "stc": "Napastnik",
}
# Kod pozycji z fmsave -> polski skrot (jak na boisku w aplikacji)
SKROT_POZYCJI = {"gk": "BR", "dc": "ŚO", "sw": "ŚO", "dl": "LO", "dr": "PO", "wbl": "LWAH", "wbr": "PWAH",
                 "dm": "DP", "mc": "ŚP", "amc": "OP", "ml": "LP", "mr": "PP", "aml": "LS", "amr": "PS",
                 "stc": "N"}
# Kolejnosc rozstrzygania remisow w ocenach pozycji (przy remisie wygrywa pozycja klasyczna:
# DL/DR przed WB, MC przed AMC - do pul Wahadlowy i Ofensywny Pomocnik trafiaja specjalisci)
KOLEJNOSC_KODOW = ("gk", "dc", "sw", "dr", "dl", "wbr", "wbl", "dm", "mc", "amc", "mr", "ml", "amr", "aml", "stc")
OCENA_NATURALNA = 18   # pozycja "naturalna" w FM to ocena 18-20
MAKS_KLUBOW_W_LIDZE = 40   # wieksza "tabela" to nie liga (np. zbiorcza tabela towarzyska)
MIN_KLUBOW_W_LIDZE = 6     # mniejsze tabele to fragmenty (1 klub = "100% z jednego kraju")
MAKS_KLUBOW_W_TERMINARZU = 80
OKNO_SEZONU_WSTECZ = timedelta(days=240)    # od poczatku biezacego sezonu...
OKNO_SEZONU_NAPRZOD = timedelta(days=300)   # ...do jego konca (wlacznie z nierozegranymi kolejkami)

# Liczniki sezonowe potrzebne do statystyk per 90 i odsetkow
POLA_LICZNIKOW = (
    "minutes", "goals", "expected_goals", "non_penalty_expected_goals", "expected_assists", "shots",
    "shots_on_target", "open_play_key_passes", "pressures_completed", "interceptions", "possession_won",
    "possession_lost", "passes_attempted", "progressive_passes", "aerial_challenges_attempted",
    "headers_won", "dribbles", "expected_goals_prevented", "saves_held", "saves_parried", "saves_tipped",
    "shots_on_target_faced", "crosses_completed", "clear_cut_chances_created", "high_intensity_sprints",
)

# Kolumna w aplikacji -> licznik per 90
PER_90 = {
    "Oczekiwane asysty/90": "expected_assists",
    "Kluczowe podania z gry/90": "open_play_key_passes",
    "Liczba goli na 90 min": "goals",
    "Oczekiwane gole bez karnych/90": "non_penalty_expected_goals",
    "Udane próby pressingu/90": "pressures_completed",
    "Przechwyty/90": "interceptions",
    "Odzyskane piłki/90": "possession_won",
    "Stracone piłki/90": "possession_lost",
    "Próby podań/90": "passes_attempted",
    "Podania progresywne/90": "progressive_passes",
    "Liczba dryblingów/90": "dribbles",
    "Uniknięte oczekiwane gole/90": "expected_goals_prevented",
    "Udane dośrodkowania/90": "crosses_completed",
    "Stworzone 100% sytuacje/90": "clear_cut_chances_created",
    "Sprinty/90": "high_intensity_sprints",
}


@dataclass(frozen=True)
class OpcjeZapisu:
    rodzaj_statystyk: str = "league"      # "league" (liga) albo "overall" (wszystkie rozgrywki)
    min_minut: int = 300
    kurs_waluty: float = KURS_DOMYSLNY
    wszystkie_naturalne_pozycje: bool = True   # zawodnik w kazdej puli, w ktorej jest naturalny (ocena >= 18)
    tylko_kluby_w_lidze: bool = True
    wolni_agenci: bool = True             # zawodnicy bez klubu (z minutami w sezonie) w puli


@dataclass(frozen=True)
class Liga:
    competition_id: int
    database_id: int | None
    nazwa: str | None

    @property
    def etykieta(self):
        if self.nazwa:
            return self.nazwa
        if self.database_id is not None and self.database_id < 0:
            return f"Liga krajowa #{-self.database_id}"
        return f"Rozgrywki #{self.database_id if self.database_id is not None else self.competition_id}"


@dataclass
class WynikZapisu:
    dane: dict
    data_gry: date | None = None
    moj_klub: str | None = None
    moj_klub_uid: int | None = None
    nazwa_zapisu: str = ""
    build: str = ""
    ostrzezenia: list = field(default_factory=list)
    liczniki: dict = field(default_factory=dict)
    moje_kluby: list = field(default_factory=list)     # [{"uid", "nazwa"}] - wszystkie prowadzone druzyny
    ligi: list = field(default_factory=list)           # podsumowanie lig: klucz, domyslna, liczba, kluby, kraj
    kraje_auto: dict = field(default_factory=dict)     # nation_id -> nazwa kraju z klubow-kotwic
    taktyki: list = field(default_factory=list)        # taktyki pierwszej druzyny mojego klubu (odczytaj_taktyki)


# =============================================================================
# CZYSTE FUNKCJE (testowalne bez pliku zapisu)
# =============================================================================
def oceny_pozycji(pozycje):
    """Rekord Positions -> {kod: ocena}."""
    return {kod: int(getattr(pozycje, kod, 0) or 0) for kod in KOLEJNOSC_KODOW}


def glowna_pozycja(pozycje):
    """Kod pozycji z najwyzsza ocena (remis rozstrzyga KOLEJNOSC_KODOW) albo None."""
    oceny = oceny_pozycji(pozycje)
    najlepsza = max(oceny.values(), default=0)
    if najlepsza <= 0:
        return None
    return next(kod for kod in KOLEJNOSC_KODOW if oceny[kod] == najlepsza)


def grupy_pozycji(pozycje, wszystkie_naturalne=False):
    """Lista grup pozycji zawodnika: glowna, a opcjonalnie wszystkie naturalne (ocena >= 18)."""
    glowna = glowna_pozycja(pozycje)
    if glowna is None:
        return []
    grupy = [POZYCJA_Z_KODU[glowna]]
    if wszystkie_naturalne:
        for kod, ocena in oceny_pozycji(pozycje).items():
            grupa = POZYCJA_Z_KODU[kod]
            if ocena >= OCENA_NATURALNA and grupa not in grupy:
                grupy.append(grupa)
    return grupy


def preferowana_noga(lewa, prawa):
    """
    Sila nog (1-20) -> etykieta jak w FM. Progi sa przyblizeniem: slabsza noga >= 15 to
    'Obunożny', <= 5 to 'Wyłącznie ...', pomiedzy - zwykla przewaga jednej nogi.
    """
    if not lewa and not prawa:
        return None
    slabsza, mocniejsza_lewa = min(lewa, prawa), lewa > prawa
    if slabsza >= 15:
        return "Obunożny"
    if slabsza <= 5:
        return "Wyłącznie lewonożny" if mocniejsza_lewa else "Wyłącznie prawonożny"
    return "Lewonożny" if mocniejsza_lewa else "Prawonożny"


def sumuj_statystyki(wiersze, rodzaj):
    """Wiersze PlayerSeasonStats -> {player_uid: {licznik: suma}} dla wybranego rodzaju rozgrywek
    (zawodnik ma osobny wiersz dla kazdej druzyny, w ktorej gral w tym sezonie)."""
    sumy = defaultdict(lambda: defaultdict(float))
    obecne = defaultdict(set)
    for w in wiersze:
        if str(getattr(w, "kind", "")) != rodzaj:
            continue
        uid = w.player_uid
        for pole in POLA_LICZNIKOW:
            wartosc = getattr(w, pole, None)
            if wartosc is not None:
                sumy[uid][pole] += float(wartosc)
                obecne[uid].add(pole)
    # Pola, ktorych zawodnik nie ma wcale (np. obrony u zawodnika z pola), zostaja None
    return {uid: {p: (s[p] if p in obecne[uid] else None) for p in POLA_LICZNIKOW} for uid, s in sumy.items()}


def _iloraz(licznik, mianownik, mnoznik=1.0):
    if licznik is None or not mianownik:
        return np.nan
    return licznik / mianownik * mnoznik


def statystyki_kanoniczne(liczniki):
    """Sumy licznikow -> kolumny aplikacji (per 90 i odsetki)."""
    liczniki = liczniki or {}
    minuty = liczniki.get("minutes") or 0
    wynik = {"Minuty": minuty}
    for kolumna, pole in PER_90.items():
        wynik[kolumna] = _iloraz(liczniki.get(pole), minuty, 90.0)
    strzaly = liczniki.get("shots")
    wynik["Oczekiwane gole na strzał"] = _iloraz(liczniki.get("expected_goals"), strzaly)
    # "Skut (%)" w FM to skutecznosc (gole / strzaly) - potwierdzone na zapisie; celnosc osobno
    wynik["Skuteczność strzałów (%)"] = _iloraz(liczniki.get("goals"), strzaly, 100.0)
    wynik["Celność strzałów (%)"] = _iloraz(liczniki.get("shots_on_target"), strzaly, 100.0)
    wynik["% wygranych pojedynków główkowych"] = _iloraz(
        liczniki.get("headers_won"), liczniki.get("aerial_challenges_attempted"), 100.0)
    # Pola bramkarskie sa tylko u bramkarzy (u reszty None); bez nich xG zapobiegniete nie ma sensu
    obrony = [liczniki.get(p) for p in ("saves_held", "saves_parried", "saves_tipped")]
    bramkarz = all(o is not None for o in obrony)
    wynik["Skuteczność obron (%)"] = (
        _iloraz(sum(obrony), liczniki.get("shots_on_target_faced"), 100.0) if bramkarz else np.nan)
    if not bramkarz:
        wynik["Uniknięte oczekiwane gole/90"] = np.nan
    return wynik


WOLNY_AGENT = "Wolny agent"


# Dane ukryte (skala 1-20): atrybut/cecha rekordu fmsave -> kolumna aplikacji
ATRYBUTY_UKRYTE = {"consistency": "Regularność", "important_matches": "Ważne mecze",
                   "injury_proneness": "Podatność na kontuzje", "determination": "Determinacja"}
OSOBOWOSC = {"professionalism": "Profesjonalizm", "ambition": "Ambicja", "adaptability": "Adaptacja"}


def wiersz_zawodnika(zawodnik, liczniki, liga, opcje, kontuzje=0):
    """Rekord Player (+ jego liczniki sezonowe, liga klubu, liczba kontuzji) -> slownik kolumn aplikacji."""
    kurs = opcje.kurs_waluty
    wolny = zawodnik.club_uid is None
    wartosc = None
    if wolny:
        wartosc = 0.0       # wolny agent: bez kwoty odstepnego
    elif str(getattr(zawodnik, "transfer_value_state", "ok")) == "ok" and zawodnik.transfer_value is not None:
        wartosc = zawodnik.transfer_value * kurs
    kontrakt = getattr(zawodnik, "contract", None)
    tygodniowka = kontrakt.wage * kurs if kontrakt is not None and kontrakt.wage is not None else None
    koniec = kontrakt.end if kontrakt is not None else None
    ability = getattr(zawodnik, "ability", None)
    atrybuty = getattr(zawodnik, "attributes", None)
    osobowosc = getattr(zawodnik, "personality", None)
    koniec_wyp = getattr(zawodnik, "loan_end", None) if getattr(zawodnik, "on_loan", False) else None
    domyslna = WOLNY_AGENT if wolny else (Liga(liga.competition_id, liga.database_id, None).etykieta if liga else None)

    wiersz = {
        "Piłkarz": zawodnik.name,
        "Wiek": zawodnik.age,
        "Klub": WOLNY_AGENT if wolny else zawodnik.club_name,
        "Liga": WOLNY_AGENT if wolny else (liga.etykieta if liga else None),
        "Liga_klucz": liga.database_id if liga and not wolny else None,
        "Liga_domyslna": domyslna,
        "Wolny_agent": wolny,
        "Reputacja_klubu": getattr(zawodnik, "club_reputation", None),
        "Wypożyczenie_do": pd.Timestamp(koniec_wyp) if koniec_wyp else pd.NaT,
        "Kontuzje_2_lata": kontuzje,
        # fmsave podaje kody wielkimi literami ("DC", "WBL") - stad .lower()
        "Pozycja": ", ".join(dict.fromkeys(SKROT_POZYCJI.get(k.lower(), k.upper())
                                           for k in (zawodnik.natural_positions or ()))) or None,
        "Kraj_ID": getattr(zawodnik, "nation_id", None),
        "Preferowana noga": preferowana_noga(zawodnik.left_foot, zawodnik.right_foot),
        "Cena": fmt_eur(wartosc),
        "Wartość_Numeryczna": np.nan if wartosc is None else float(wartosc),
        "Płaca": None if tygodniowka is None else f"{fmt_eur(tygodniowka)} tyg.",
        "Zarobki_Numeryczne": np.nan if tygodniowka is None else float(tygodniowka) * 52,
        "Wygasa": f"{koniec.day}.{koniec.month}.{koniec.year}" if koniec else None,
        "Wygasa_Data": pd.Timestamp(koniec) if koniec else pd.NaT,
        "CA": getattr(ability, "current", None),
        "PA": getattr(ability, "potential", None),
        "Wypożyczony": bool(getattr(zawodnik, "on_loan", False)),
        "UID": zawodnik.uid,
        "Klub_UID": zawodnik.club_uid,
    }
    # Ocena (1-20) na kazdej puli pozycji = najlepsza z jej kodow; pokazuje latwosc przekwalifikowania
    oceny = oceny_pozycji(zawodnik.positions) if getattr(zawodnik, "positions", None) is not None else {}
    for grupa in POZYCJE:
        kody = [k for k, g in POZYCJA_Z_KODU.items() if g == grupa]
        wiersz[kolumna_oceny(grupa)] = max((oceny.get(k, 0) for k in kody), default=None) if oceny else None
    for pole, kolumna in ATRYBUTY_UKRYTE.items():
        wiersz[kolumna] = getattr(atrybuty, pole, None) if atrybuty is not None else None
    for pole, kolumna in OSOBOWOSC.items():
        wiersz[kolumna] = getattr(osobowosc, pole, None) if osobowosc is not None else None
    # atrybuty (1-20) do dopasowania rol
    for pole in ATRYBUTY_PL:
        wiersz[KOLUMNA_ATRYBUTU.format(pole)] = getattr(atrybuty, pole, None) if atrybuty is not None else None
    wiersz.update(statystyki_kanoniczne(liczniki))
    return wiersz


def zbuduj_ramki(zawodnicy, liczniki_po_uid, liga_klubu, opcje, moje_kluby=(), kontuzje=None):
    """
    Zawodnicy + liczniki + liga kazdego klubu -> {pozycja: kanoniczny DataFrame}.
    Pomija zawodnikow bez wieku, ponizej progu minut i (opcjonalnie) z klubow, ktorych nie udalo
    sie przypisac do ligi krajowej. Wolni agenci trafiaja do puli, gdy opcje.wolni_agenci.
    Zawodnicy moich klubow (`moje_kluby`) trafiaja zawsze - potrzebni do analizy kadry.
    """
    moje_kluby = set(moje_kluby)
    kontuzje = kontuzje or {}
    wiersze = {p: [] for p in POZYCJE}
    for zawodnik in zawodnicy:
        if not zawodnik.age:
            continue
        moj = zawodnik.club_uid in moje_kluby
        if zawodnik.club_uid is None:
            if not opcje.wolni_agenci:
                continue
            liga = None
        else:
            liga = liga_klubu.get(zawodnik.club_uid)
            if liga is None and opcje.tylko_kluby_w_lidze and not moj:
                continue
        liczniki = liczniki_po_uid.get(zawodnik.uid)
        minuty = (liczniki or {}).get("minutes") or 0
        if minuty < opcje.min_minut and not moj:
            continue
        grupy = grupy_pozycji(zawodnik.positions, opcje.wszystkie_naturalne_pozycje)
        if not grupy:
            continue
        wiersz = wiersz_zawodnika(zawodnik, liczniki, liga, opcje, kontuzje.get(zawodnik.uid, 0))
        wiersz["Pula_główna"] = grupy[0]
        for grupa in grupy:
            wiersze[grupa].append(wiersz)
    return {p: dopelnij_schemat(pd.DataFrame(w)) for p, w in wiersze.items() if w}


@dataclass(frozen=True)
class KandydatLigi:
    rozmiar: int
    competition_id: int
    database_id: int | None
    kraj: int | None = None      # dominujacy kraj klubow w tabeli


def opis_tabeli(tabela, nacja):
    """(wiersze pierwszych druzyn, dominujacy kraj, jego udzial) - kluby bez kraju liczone jako obce."""
    wiersze = [w for w in tabela.rows
               if w.club_uid is not None and getattr(w, "team_slot", None) in (0, None)]
    znane = [nacja.get(w.club_uid) for w in wiersze if nacja.get(w.club_uid) is not None]
    if not znane:
        return wiersze, None, 0.0
    kraj, ile = Counter(znane).most_common(1)[0]
    return wiersze, kraj, ile / len(wiersze)


def klucz_rozgrywek(baza, competition_id, kraj):
    """
    Klucz rozgrywek w mapie nazw: id z bazy gry, a gdy go brak (np. liga belgijska w FM26 ma
    database_id = None) - zastepczy klucz -kraj. Jest staly miedzy zapisami tej samej bazy, wiec
    taka lige tez mozna nazwac w dane/nazwy_rozgrywek.csv (np. "-131,Jupiler Pro League").
    """
    db_id = baza.get(competition_id)
    if db_id is None and kraj is not None:
        return -kraj
    return db_id


def kluby_drugorzedne(kluby):
    """
    Kluby, dla ktorych istnieje inny klub o tej samej nazwie i kraju z nizszym uid. W FM26 to
    przede wszystkim druzyny kobiece (np. A.S. Roma 1100 i 2000209836, FC Twente 1009 i 37087234).
    """
    najstarszy = {}
    for klub in kluby:
        nazwa = (getattr(klub, "name", None) or "").strip().lower()
        if nazwa:
            klucz = (nazwa, getattr(klub, "nation_id", None))
            najstarszy[klucz] = min(najstarszy.get(klucz, klub.uid), klub.uid)
    return {k.uid for k in kluby
            if (getattr(k, "name", None) or "").strip()
            and najstarszy[((k.name or "").strip().lower(), getattr(k, "nation_id", None))] != k.uid}


def _czy_krajowe(uidy, nacja, drugorzedne, prog_krajowy, min_klubow, maks_klubow, statystyki=None):
    """Kraj rozgrywek albo None, gdy to nie liga krajowa (miedzynarodowe, za male/duze, kobiece)."""
    def odrzuc(powod):
        if statystyki is not None:
            statystyki[powod] += 1
        return None
    n = len(uidy)
    if not min_klubow <= n <= maks_klubow:
        return odrzuc("rozmiar")
    znane = [nacja.get(u) for u in uidy if nacja.get(u) is not None]
    if not znane:
        return odrzuc("bez_kraju")
    kraj, ile = Counter(znane).most_common(1)[0]
    if ile / n < prog_krajowy:
        return odrzuc("miedzynarodowe")
    if sum(u in drugorzedne for u in uidy) / n >= 0.5:
        return odrzuc("kobiece_lub_drugorzedne")
    return kraj


def kandydaci_lig_z_terminarza(mecze, rozgrywki, kluby, data_gry=None, prog_krajowy=0.8,
                               drugorzedne=None, statystyki=None):
    """
    Liga klubu z terminarza: rozgrywki, w ktorych pierwsza druzyna gra kolejki ligowe (mecz bez
    rundy) w biezacym sezonie - lacznie z kolejkami jeszcze nierozegranymi. Dziala takze, gdy tabela
    ligi nie istnieje (Belgia w play-offach, Serie A przed startem sezonu) i nie daje fragmentow.
    Rozgrywki sa krajowe, gdy >= `prog_krajowy` uczestnikow jest z jednego znanego kraju, maja
    MIN_KLUBOW_W_LIDZE..MAKS_KLUBOW_W_TERMINARZU klubow i nie sa rozgrywkami kobiecymi.
    Zwraca {club_uid: [KandydatLigi(rozmiar=liczba meczow, ...), ...]} od najwiekszej liczby meczow.
    """
    nacja = {k.uid: getattr(k, "nation_id", None) for k in kluby}
    baza = {r.id: r.database_id for r in rozgrywki}
    drugorzedne = kluby_drugorzedne(kluby) if drugorzedne is None else drugorzedne
    uczestnicy = defaultdict(set)
    mecze_klubu = defaultdict(Counter)
    for m in mecze:
        if m.round is not None or m.competition_id is None:
            continue
        if data_gry is not None:
            if m.date is None or not (data_gry - OKNO_SEZONU_WSTECZ <= m.date <= data_gry + OKNO_SEZONU_NAPRZOD):
                continue
        strony = ((m.home_club_uid, m.home_team_slot), (m.away_club_uid, m.away_team_slot))
        if any(uid is None or slot not in (0, None) for uid, slot in strony):
            continue
        for uid, _ in strony:
            uczestnicy[m.competition_id].add(uid)
            mecze_klubu[uid][m.competition_id] += 1
    krajowe = {}
    for comp, uidy in uczestnicy.items():
        kraj = _czy_krajowe(uidy, nacja, drugorzedne, prog_krajowy, MIN_KLUBOW_W_LIDZE,
                            MAKS_KLUBOW_W_TERMINARZU, statystyki)
        if kraj is not None:
            krajowe[comp] = kraj
    wynik = {}
    for uid, licznik in mecze_klubu.items():
        lista = [KandydatLigi(ile, comp, klucz_rozgrywek(baza, comp, krajowe[comp]), krajowe[comp])
                 for comp, ile in licznik.items() if comp in krajowe]
        if lista:
            wynik[uid] = sorted(lista, key=lambda k: (-k.rozmiar, k.competition_id))
    return wynik


def kandydaci_lig(tabele, rozgrywki, kluby, prog_krajowy=0.8, drugorzedne=None):
    """
    Wszystkie krajowe tabele ligowe, w ktorych wystepuje pierwsza druzyna klubu.
    Zapasowe zrodlo (gdy klub nie ma kandydata z terminarza). Tabela jest krajowa, gdy co
    najmniej `prog_krajowy` jej klubow pochodzi z jednego, znanego kraju (kluby bez kraju sie do
    niego nie licza), ma MIN_KLUBOW_W_LIDZE..MAKS_KLUBOW_W_LIDZE klubow i nie jest kobieca.
    Pomijane sa wiec rozgrywki miedzynarodowe, fragmenty tabel i zbiorcze tabele.
    Klub moze miec kilku kandydatow: np. w marcu kluby brazylijskie sa w tabeli ligi stanowej,
    a gdy rusza sezon - takze w tabeli Serie A.
    Zwraca {club_uid: [KandydatLigi, ...]} od najwiekszej tabeli.
    """
    nacja = {k.uid: getattr(k, "nation_id", None) for k in kluby}
    baza = {r.id: r.database_id for r in rozgrywki}
    drugorzedne = kluby_drugorzedne(kluby) if drugorzedne is None else drugorzedne
    rozmiary = defaultdict(dict)   # club_uid -> competition_id -> (rozmiar, kraj)
    for tabela in tabele:
        if tabela.competition_id is None:
            continue
        wiersze, _, _ = opis_tabeli(tabela, nacja)
        kraj = _czy_krajowe({w.club_uid for w in wiersze}, nacja, drugorzedne, prog_krajowy,
                            MIN_KLUBOW_W_LIDZE, MAKS_KLUBOW_W_LIDZE)
        if kraj is None:
            continue
        for w in wiersze:
            obecny = rozmiary[w.club_uid].get(tabela.competition_id, (0, kraj))
            rozmiary[w.club_uid][tabela.competition_id] = (max(obecny[0], len(wiersze)), kraj)
    return {
        uid: sorted((KandydatLigi(r, comp, klucz_rozgrywek(baza, comp, kraj), kraj)
                     for comp, (r, kraj) in per_comp.items()),
                    key=lambda k: (-k.rozmiar, k.competition_id))
        for uid, per_comp in rozmiary.items()
    }


def ligi_klubow(tabele, rozgrywki, kluby, nazwy=None, prog_krajowy=0.8, kandydaci=None):
    """
    Liga krajowa kazdego klubu. Sposrod kandydatow (`kandydaci_lig`) wygrywaja kolejno:
    tabele z krajem klubu (Club.nation_id), rozgrywki, ktorych nazwe znamy z mapy (liga stanowa
    przegrywa wtedy z Serie A), najwieksza tabela (grupa pucharu krajowego przegrywa z liga).
    Zwraca {club_uid: Liga}.
    """
    nazwy = nazwy or {}
    nacja = {k.uid: getattr(k, "nation_id", None) for k in kluby}
    if kandydaci is None:
        kandydaci = kandydaci_lig(tabele, rozgrywki, kluby, prog_krajowy)
    wynik = {}
    for uid, lista in kandydaci.items():
        swoje = [k for k in lista if k.kraj is not None and k.kraj == nacja.get(uid)]
        lista = swoje or lista
        nazwane = [k for k in lista if k.database_id in nazwy]
        wybrany = (nazwane or lista)[0]
        db_id = wybrany.database_id
        wynik[uid] = Liga(wybrany.competition_id, db_id, nazwy.get(db_id) if db_id is not None else None)
    return wynik


def surowa_nazwa_ligi(wyswietlana):
    """'Premier League (ANG 1)' -> 'Premier League' (klucz MNOZNIKI_LIG); nieznana - bez zmian."""
    for surowa, nazwa in MAPOWANIE_NAZW_LIG.items():
        if nazwa == wyswietlana:
            return surowa
    return wyswietlana


def mapa_nazw_z_csv(kandydaci, kluby, ramki_csv, min_glosow=2, min_udzial=0.6, min_pokrycie=0.5):
    """
    Uczy sie nazw lig ze starych eksportow CSV: klub z CSV -> klub w zapisie (po nazwie) ->
    rozgrywki, w ktorych klub teraz gra; nazwa ligi z CSV oddaje "glos" na kazde z nich.

    Przypisanie jest jeden do jednego (kazda nazwa -> jedno id, kazde id -> jedna nazwa),
    zachlannie od najwiekszej liczby glosow. Dzieki temu kilka klubow, ktore od czasu eksportu
    awansowaly lub spadly (albo graja tez w lidze stanowej), nie nada swojej starej nazwy
    innym rozgrywkom - te przegrywaja z rozgrywkami, w ktorych gra wiekszosc ligi.
    Warunki dla pary (id, nazwa): co najmniej `min_glosow` glosow, `min_udzial` glosow oddanych
    na to id oraz `min_pokrycie` klubow z CSV o tej nazwie ligi. Ostatni warunek odrzuca np. lige
    stanowa, w ktorej gra tylko czesc klubow Serie A (gdy sama Serie A jeszcze nie ruszyla).
    Zwraca {database_id: nazwa}.
    """
    po_nazwie = defaultdict(set)
    for klub in kluby:
        for nazwa in {klub.name, klub.short_name}:
            if nazwa:
                po_nazwie[nazwa.strip().lower()].add(klub.uid)

    pary = set()   # (club_uid, nazwa ligi) - klub glosuje raz, nawet gdy jest w kilku plikach CSV
    for ramka in ramki_csv:
        if 'Klub' not in ramka.columns or 'Liga' not in ramka.columns:
            continue
        for klub, liga in ramka[['Klub', 'Liga']].dropna().drop_duplicates().itertuples(index=False):
            uidy = po_nazwie.get(str(klub).strip().lower(), set())
            if len(uidy) == 1:   # brak lub niejednoznaczna nazwa klubu - pomijamy
                pary.add((next(iter(uidy)), surowa_nazwa_ligi(str(liga))))

    glosy = defaultdict(Counter)
    kluby_z_nazwa = Counter()   # ile klubow z CSV o danej nazwie ligi ma jakichkolwiek kandydatow
    for uid, nazwa in pary:
        lista = [k for k in kandydaci.get(uid, ()) if k.database_id is not None]
        if lista:
            kluby_z_nazwa[nazwa] += 1
        for kandydat in lista:
            glosy[kandydat.database_id][nazwa] += 1

    propozycje = sorted(
        ((ile, ile / sum(licznik.values()), db_id, nazwa)
         for db_id, licznik in glosy.items() for nazwa, ile in licznik.items()),
        key=lambda p: (-p[0], -p[1], p[2], p[3]))
    mapa, zajete_nazwy = {}, set()
    for ile, udzial, db_id, nazwa in propozycje:
        if (ile < min_glosow or udzial < min_udzial or ile / kluby_z_nazwa[nazwa] < min_pokrycie
                or db_id in mapa or nazwa in zajete_nazwy):
            continue
        mapa[db_id] = nazwa
        zajete_nazwy.add(nazwa)
    return mapa


def wczytaj_nazwy_rozgrywek(sciezka=PLIK_NAZW_UZYTKOWNIKA, domyslny=PLIK_NAZW_ROZGRYWEK):
    """
    Mapa {klucz rozgrywek: nazwa}: domyslna z repozytorium (dane/) nadpisana edycjami uzytkownika
    (~/.fm_moneyball). Pliki CSV `id,nazwa`; klucze ujemne (-kraj) sa dozwolone.
    """
    return {**wczytaj_mape(domyslny), **wczytaj_mape(sciezka)}


def zapisz_nazwy_rozgrywek(mapa, sciezka=PLIK_NAZW_UZYTKOWNIKA):
    """
    Dopisuje nazwy do pliku uzytkownika. Nowe wpisy wygrywaja: stary wpis z tym samym id
    albo z ta sama nazwa pod innym id (np. blednie nauczony wczesniej) jest usuwany.
    Zwraca zawartosc pliku uzytkownika po zapisie.
    """
    nowe_nazwy = set(mapa.values())
    stare = {db_id: nazwa for db_id, nazwa in wczytaj_mape(sciezka).items()
             if db_id not in mapa and nazwa not in nowe_nazwy}
    return zapisz_mape({**stare, **mapa}, sciezka, ("database_id", "nazwa"))


# =============================================================================
# ODCZYT PLIKU (fmsave)
# =============================================================================
def _otworz(sciezka):
    import warnings

    import fmsave
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", fmsave.FmsaveWarning)
        return fmsave.open(sciezka)


def polacz_kandydatow(z_terminarza, z_tabel):
    """Terminarz ma pierwszenstwo; tabele tylko dla klubow, ktorych terminarz nie przypisal."""
    wynik = dict(z_tabel)
    wynik.update({uid: lista for uid, lista in z_terminarza.items() if lista})
    return wynik


def kandydaci_lig_lacznie(zapis, kluby, data_gry, ostrzezenia=None, statystyki=None):
    """Kandydaci lig z terminarza i (zapasowo) z tabel ligowych; bledy odczytu nie blokuja reszty."""
    ostrzezenia = [] if ostrzezenia is None else ostrzezenia
    drugorzedne = kluby_drugorzedne(kluby)
    rozgrywki = list(zapis.competitions())
    z_terminarza, z_tabel = {}, {}
    try:
        z_terminarza = kandydaci_lig_z_terminarza(zapis.fixtures(), rozgrywki, kluby, data_gry,
                                                  drugorzedne=drugorzedne, statystyki=statystyki)
    except Exception as e:
        ostrzezenia.append(f"Nie udało się odczytać terminarza ({e}); liga z tabel ligowych.")
    try:
        z_tabel = kandydaci_lig(zapis.league_tables(), rozgrywki, kluby, drugorzedne=drugorzedne)
    except Exception as e:
        ostrzezenia.append(f"Nie udało się odczytać tabel ligowych ({e}).")
    return polacz_kandydatow(z_terminarza, z_tabel)


def policz_kontuzje(rekordy, data_gry, dni=730):
    """Liczba kontuzji kazdego zawodnika w ostatnich `dni` (z historii kontuzji w zapisie)."""
    od = data_gry - timedelta(days=dni) if data_gry else None
    licznik = Counter()
    for r in rekordy:
        if str(getattr(r, "kind", "")) != "history" or r.player_uid is None:
            continue
        if od is not None and (r.date is None or r.date < od):
            continue
        licznik[r.player_uid] += 1
    return licznik


def podsumuj_ligi(liga_klubu, kluby, limit=5, narodowosci=None):
    """
    [{klucz, domyslna, nazwa, liczba, kluby, kraj}] - do edycji nazw i mnoznikow w aplikacji.
    `kraj` to id kraju ligi, z ktorego aplikacja nazywa narodowosci zawodnikow: najczestsza
    narodowosc zawodnikow ligi (`narodowosci` = narodowosci_lig, ta sama numeracja co
    Player.nation_id), a bez nich dominujacy nation_id klubow.
    """
    nazwa_klubu = {k.uid: k.name for k in kluby}
    kraj_klubu = {k.uid: getattr(k, "nation_id", None) for k in kluby}
    grupy = {}
    for uid, liga in liga_klubu.items():
        g = grupy.setdefault(liga.competition_id, {"klucz": liga.database_id,
                                                   "domyslna": Liga(liga.competition_id, liga.database_id, None).etykieta,
                                                   "nazwa": liga.nazwa, "kluby": [], "kraje": Counter(),
                                                   "competition_id": liga.competition_id})
        g["kluby"].append(nazwa_klubu.get(uid) or "?")
        if kraj_klubu.get(uid) is not None:
            g["kraje"][kraj_klubu[uid]] += 1
    wynik = []
    for g in grupy.values():
        kraje = g.pop("kraje")
        competition_id = g.pop("competition_id")
        if narodowosci is not None:
            kraj = kraj_z_licznika(narodowosci.get(competition_id))
        else:
            kraj = kraje.most_common(1)[0][0] if kraje else None
        wynik.append({**g, "liczba": len(g["kluby"]), "kluby": sorted(g["kluby"])[:limit], "kraj": kraj})
    return sorted(wynik, key=lambda g: -g["liczba"])


ETAPY_WCZYTYWANIA = ("Otwieranie zapisu", "Kluby i terminarz", "Zawodnicy", "Statystyki sezonu",
                     "Kontuzje", "Budowanie tabel")


def wczytaj_zapis(sciezka, opcje=OpcjeZapisu(), nazwy=None, postep=None):
    """
    Plik .fm -> WynikZapisu (ramki dla wszystkich pozycji + metadane).
    `postep(nr, nazwa)` jest wywolywane przed kazdym etapem (ETAPY_WCZYTYWANIA); czasy etapow
    trafiaja do liczniki["czasy_s"].
    """
    import time
    import warnings

    import fmsave
    nazwy = wczytaj_nazwy_rozgrywek() if nazwy is None else nazwy
    ostrzezenia = []
    czasy = {}
    zegar = {"etap": None, "start": time.perf_counter()}

    def etap(nr):
        teraz = time.perf_counter()
        if zegar["etap"] is not None:
            czasy[zegar["etap"]] = round(teraz - zegar["start"], 1)
        zegar.update(etap=ETAPY_WCZYTYWANIA[nr] if nr is not None else None, start=teraz)
        if postep and nr is not None:
            postep(nr, ETAPY_WCZYTYWANIA[nr])

    with warnings.catch_warnings(record=True) as zlapane:
        warnings.simplefilter("always", fmsave.FmsaveWarning)
        etap(0)
        with fmsave.open(sciezka) as zapis:
            info = zapis.info
            etap(1)
            kluby = list(zapis.clubs())
            kandydaci = kandydaci_lig_lacznie(zapis, kluby, info.game_date, ostrzezenia)
            liga_klubu = ligi_klubow([], [], kluby, nazwy, kandydaci=kandydaci)
            zarzadzane = list(zapis.managed_clubs())
            etap(2)
            zawodnicy = list(zapis.players())
            etap(3)
            rodzaj = fmsave.SeasonStatsKind(opcje.rodzaj_statystyk)
            liczniki = sumuj_statystyki(zapis.player_season_stats().where(kind=rodzaj), opcje.rodzaj_statystyk)
            etap(4)
            try:
                taktyki = odczytaj_taktyki(zapis.tactics(), {m.club_uid for m in zarzadzane})
            except Exception as e:   # taktyki sa dodatkiem (zakladka "Moja taktyka")
                ostrzezenia.append(f"Nie udało się odczytać taktyk ({e}).")
                taktyki = []
            try:
                kontuzje = policz_kontuzje(zapis.injuries(), info.game_date)
            except Exception as e:   # historia kontuzji jest dodatkiem - jej brak nie blokuje reszty
                ostrzezenia.append(f"Nie udało się odczytać historii kontuzji ({e}).")
                kontuzje = {}
    for w in zlapane:
        if issubclass(w.category, fmsave.UnknownBuildWarning):
            ostrzezenia.append(f"Nieznana wersja gry - fmsave może czytać dane błędnie: {w.message}")

    etap(5)
    moje = [{"uid": m.club_uid, "nazwa": m.club_name} for m in zarzadzane]
    dane = zbuduj_ramki(zawodnicy, liczniki, liga_klubu, opcje, [m["uid"] for m in moje], kontuzje)
    etap(None)
    return WynikZapisu(
        dane=dane,
        data_gry=info.game_date,
        moj_klub=moje[0]["nazwa"] if moje else None,
        moj_klub_uid=moje[0]["uid"] if moje else None,
        nazwa_zapisu=info.save_name,
        build=info.build,
        ostrzezenia=ostrzezenia,
        liczniki={"zawodnicy_w_zapisie": len(zawodnicy), "z_statystykami": len(liczniki),
                  "kluby_z_liga": len(liga_klubu), "w_aplikacji": sum(len(d) for d in dane.values()),
                  "czasy_s": czasy},
        moje_kluby=moje,
        ligi=podsumuj_ligi(liga_klubu, kluby, narodowosci=narodowosci_lig(zawodnicy, liga_klubu)),
        kraje_auto=kraje_z_kotwic(kluby, zawodnicy),
        taktyki=taktyki,
    )


def _numer_bitu(wartosc):
    return int(wartosc).bit_length() - 1 if wartosc else None


def odczytaj_taktyki(taktyki, moje_kluby):
    """
    Taktyki pierwszych druzyn moich klubow -> [{klub_uid, indeks, nazwa, mentalnosc, miejsca}]. Zapis nie nazywa
    pozycji ani rol (same numery bitow), wiec miejsce niesie surowe numery: pozycje IP/OOP (bity maski)
    i role IP/OOP (numer jedynego ustawionego bitu). Nazwy nadaje kalibracja w aplikacji.
    """
    wynik = []
    for t in taktyki:
        if t.club_uid not in moje_kluby or t.team_slot not in (0, None):
            continue
        miejsca = []
        for m in t.slots:
            nieznane = m.unknown or {}
            miejsca.append({
                "nr": m.number,
                "ip_pozycje": [int(p.raw) for p in m.in_possession_positions],
                "oop_pozycje": [int(p.raw) for p in m.out_of_possession_positions],
                "ip_rola": _numer_bitu(nieznane.get("in_possession_role_bits")),
                "oop_rola": _numer_bitu(nieznane.get("out_of_possession_role_bits")),
            })
        mentalnosc = getattr(getattr(t, "mentality", None), "label", None)
        wynik.append({"klub_uid": t.club_uid, "indeks": t.index, "nazwa": t.name or f"Taktyka {t.index + 1}",
                      "mentalnosc": getattr(mentalnosc, "name", None), "miejsca": miejsca})
    return sorted(wynik, key=lambda t: (t["klub_uid"], t["indeks"]))


def zbuduj_mape_nazw_lig(sciezka, ramki_csv):
    """Plik .fm + ramki ze starych eksportow CSV -> {database_id: nazwa ligi}."""
    with _otworz(sciezka) as zapis:
        kluby = list(zapis.clubs())
        kandydaci = kandydaci_lig_lacznie(zapis, kluby, zapis.info.game_date)
    return mapa_nazw_z_csv(kandydaci, kluby, ramki_csv)
