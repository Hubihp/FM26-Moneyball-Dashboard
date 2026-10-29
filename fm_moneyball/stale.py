"""Stale i slowniki wspolne dla wszystkich zrodel danych i modelu."""

def kolumna_oceny(pozycja):
    """Kolumna z ocena zawodnika (1-20) na danej puli pozycji (tylko dane z zapisu)."""
    return f"Ocena|{pozycja}"


# 14 pozycji FM (kazda to osobna pula zawodnikow), od bramkarza do napastnika
POZYCJE = ["Bramkarz", "Środkowy Obrońca", "Lewy Obrońca", "Prawy Obrońca", "Lewy Wahadłowy", "Prawy Wahadłowy",
           "Defensywny Pomocnik", "Środkowy Pomocnik", "Lewy Pomocnik", "Prawy Pomocnik", "Ofensywny Pomocnik",
           "Lewy Skrzydłowy", "Prawy Skrzydłowy", "Napastnik"]
SKROT_POZYCJI_APLIKACJI = {
    "Bramkarz": "BR", "Środkowy Obrońca": "ŚO", "Lewy Obrońca": "LO", "Prawy Obrońca": "PO",
    "Lewy Wahadłowy": "LWAH", "Prawy Wahadłowy": "PWAH", "Defensywny Pomocnik": "DP", "Środkowy Pomocnik": "ŚP",
    "Lewy Pomocnik": "LP", "Prawy Pomocnik": "PP", "Ofensywny Pomocnik": "OP", "Lewy Skrzydłowy": "LS",
    "Prawy Skrzydłowy": "PS", "Napastnik": "N",
}
# Pozycje lewa/prawa dziela wagi i kolumny z "rodzina" (zadania statystyczne sa takie same)
RODZINA_POZYCJI = {
    "Lewy Obrońca": "Boczny Obrońca", "Prawy Obrońca": "Boczny Obrońca",
    "Lewy Wahadłowy": "Wahadłowy", "Prawy Wahadłowy": "Wahadłowy",
    "Lewy Pomocnik": "Boczny Pomocnik", "Prawy Pomocnik": "Boczny Pomocnik",
    "Lewy Skrzydłowy": "Skrzydłowy", "Prawy Skrzydłowy": "Skrzydłowy",
}


def _na_pozycje(wg_rodzin, kopia):
    return {p: kopia(wg_rodzin[RODZINA_POZYCJI.get(p, p)]) for p in POZYCJE}

# Slownik tlumaczen kolumn statystycznych (nazwa w pliku CSV -> nazwa w aplikacji)
TLUMACZENIE_KOLUMN = {
    "xA/90": "Oczekiwane asysty/90",
    "KPzG/90": "Kluczowe podania z gry/90",
    "Liczba goli na 90 min": "Liczba goli na 90 min",
    "xG/strzał": "Oczekiwane gole na strzał",
    "Skut (%)": "Skuteczność strzałów (%)",
    "Ud Pres/90": "Udane próby pressingu/90",
    "Prz/90": "Przechwyty/90",
    "Odz Płk/90": "Odzyskane piłki/90",
    "Str Płk/90": "Stracone piłki/90",
    "Pod/90": "Próby podań/90",
    "% Głw": "% wygranych pojedynków główkowych",
    "Drb/90": "Liczba dryblingów/90",
    "ZxG/90": "Uniknięte oczekiwane gole/90",
    "Szacowana wartość": "Cena"
}

# Mozliwe nazwy kolumny z minutami w eksporcie z FM (zostanie zmieniona na "Minuty")
NAZWY_KOLUMNY_MINUT = ["Min", "Minuty", "Rozegrane minuty", "Min."]

# Statystyki dostepne tylko z pliku zapisu (eksport CSV ich nie ma - wtedy sa pomijane)
KOLUMNY_TYLKO_Z_ZAPISU = [
    "Oczekiwane gole bez karnych/90",
    "Podania progresywne/90",
    "Skuteczność obron (%)",
    "Celność strzałów (%)",
    "Udane dośrodkowania/90",
    "Stworzone 100% sytuacje/90",
    "Sprinty/90",
    "Dystans (km)/90",
    "Udane odbiory/90",
    "Wygrane główki/90",
    "Celność podań (%)",
    "Asysty/90",
    "Kartki/90",
    "Błędy prowadzące do gola/90",
    "Obrony chwytem (%)",
]

# Kolumny liczbowe, ktore konwertujemy raz, przy wczytywaniu
KOLUMNY_STATYSTYK = [v for v in TLUMACZENIE_KOLUMN.values() if v != "Cena"] + KOLUMNY_TYLKO_Z_ZAPISU

# Kolumny, ktorych NIE traktujemy jako statystyk meczowych
NIE_STATYSTYKI = {
    'SCORE', 'Percentyl', 'Piłkarz', 'ID', 'Wiek', 'Klub', 'Liga', 'Pozycja', 'Cena',
    'Preferowana noga', 'Kraj', 'Wartość_Numeryczna', 'Zarobki_Numeryczne', 'Płaca', 'Wygasa',
    'Wygasa_Data', 'Minuty', 'Mnożnik_Ligi', 'Statystyki_niepełne'
}

# Statystyki, w ktorych MNIEJ znaczy LEPIEJ (uzywane w radarze i wykresach Top 10)
NIZSZE_LEPSZE = {'Stracone piłki/90', 'Strata piłek na podanie', 'Kartki/90', 'Błędy prowadzące do gola/90'}

# Statystyki opisujace styl, a nie jakosc ("wiecej" nie znaczy "lepiej") - pomijane w radarze
NEUTRALNE = {'Próby podań/90'}

# Cechy uzywane w wyniku: nazwa -> (kierunek, wspolczynnik skurczenia)
# kierunek: +1 = wiecej znaczy lepiej, -1 = mniej znaczy lepiej
# skurczenie: 0 = bez skurczenia, 1.0 = standard, 2.0+ = bardziej losowa. Cechy ilorazowe
# (na strzal, %) maja maly mianownik, wiec sa najbardziej losowe - minuty sa tu przyblizeniem
# liczby prob (strzalow, pojedynkow), ktorej eksport z FM nie zawiera.
CECHY = {
    'Oczekiwane asysty/90': (1, 2.0),
    'Kluczowe podania z gry/90': (1, 1.0),
    'Liczba goli na 90 min': (1, 2.0),
    'Oczekiwane gole bez karnych/90': (1, 1.5),
    'Oczekiwane gole na strzał': (1, 3.0),
    'Skuteczność strzałów (%)': (1, 3.0),
    'Udane próby pressingu/90': (1, 1.0),
    'Przechwyty/90': (1, 1.0),
    'Odzyskane piłki/90': (1, 1.0),
    '% wygranych pojedynków główkowych': (1, 2.0),
    'Uniknięte oczekiwane gole/90': (1, 2.0),
    'Skuteczność obron (%)': (1, 3.0),
    'Liczba dryblingów/90': (1, 1.0),
    'Podania progresywne/90': (1, 1.0),
    'Strata piłek na podanie': (-1, 1.0),
    'Udane dośrodkowania/90': (1, 1.5),
    'Stworzone 100% sytuacje/90': (1, 2.0),
    'Sprinty/90': (1, 1.0),
    'Udane odbiory/90': (1, 1.0),
    'Wygrane główki/90': (1, 1.0),
    'Celność podań (%)': (1, 1.0),          # iloraz, ale z duzym mianownikiem (setki podan)
    'Asysty/90': (1, 2.0),
    'Kartki/90': (-1, 2.0),                  # zolta = 1, czerwona = 3
    'Błędy prowadzące do gola/90': (-1, 3.0),   # rzadkie zdarzenie - mocne skurczenie
    'Obrony chwytem (%)': (1, 3.0),
}

# Domyslne WAZNOSCI cech per pozycja (procenty, kazda rodzina sumuje sie do 100). W obliczeniach sa
# normalizowane do sumy 1, wiec liczy sie tylko ich proporcja; cechy, ktorych nie ma w danych (np. eksport
# CSV), sa pomijane. Kierunek cechy (np. strata pilek, kartki: mniej = lepiej) jest w CECHY, wiec waga
# jest zawsze dodatnia. Cechy silnie skorelowane (r > 0,6 na zapisie) tworza bloki o wspolnej wadze:
# udane odbiory + udany pressing, % wygranych glowek + wygrane glowki, gole + npxG + skutecznosc,
# xA + asysty. Faule same w sobie nie obnizaja wyniku (rosna razem z odbiorami - to skutek aktywnej
# obrony), karane sa kartki. Wybicia i bloki pominiete: zaleza od tego, jak czesto druzyna sie broni.
_WAGI_RODZIN = {
    # Bramkarz: obrona strzalow ponad oczekiwania (uniknięte xG izoluja bramkarza od obrony druzyny),
    # bledy, gra nogami (straty), wyjscia (odzyskane pilki), chwytanie zamiast odbijania. Celnosc podan
    # pominieta: u bramkarza zalezy od stylu wznawiania (dlugie wybicia), a nie od jakosci.
    "Bramkarz": {
        'Uniknięte oczekiwane gole/90': 50, 'Skuteczność obron (%)': 15, 'Błędy prowadzące do gola/90': 10,
        'Strata piłek na podanie': 15, 'Odzyskane piłki/90': 5, 'Obrony chwytem (%)': 5},
    # Stoper: odbior pilki (47%), gra w powietrzu (15%), wyprowadzenie (20%), bledy i kartki (8%).
    "Środkowy Obrońca": {
        'Odzyskane piłki/90': 18, 'Przechwyty/90': 14, 'Udane odbiory/90': 10, 'Udane próby pressingu/90': 5,
        '% wygranych pojedynków główkowych': 8, 'Wygrane główki/90': 7, 'Podania progresywne/90': 10,
        'Celność podań (%)': 7, 'Kluczowe podania z gry/90': 3, 'Strata piłek na podanie': 10,
        'Błędy prowadzące do gola/90': 5, 'Kartki/90': 3},
    # Boczny obronca: kreowanie z boku (42%), progresja, obrona flanki (35%), bezpieczenstwo pilki.
    "Boczny Obrońca": {
        'Oczekiwane asysty/90': 20, 'Asysty/90': 5, 'Kluczowe podania z gry/90': 12, 'Udane dośrodkowania/90': 5,
        'Podania progresywne/90': 10, 'Przechwyty/90': 12, 'Odzyskane piłki/90': 10, 'Udane odbiory/90': 8,
        'Udane próby pressingu/90': 5, 'Celność podań (%)': 3, 'Strata piłek na podanie': 7, 'Kartki/90': 3},
    # Wahadlowy: sam daje szerokosc w ustawieniu z trojka obroncow - glowny kreator z boku (45%), przenosi
    # pilke (drybling, progresja) i biega cala flanke (sprinty). Obrone asekuruje trzech stoperow (20%).
    "Wahadłowy": {
        'Oczekiwane asysty/90': 20, 'Asysty/90': 5, 'Kluczowe podania z gry/90': 12, 'Udane dośrodkowania/90': 8,
        'Liczba dryblingów/90': 10, 'Podania progresywne/90': 10, 'Sprinty/90': 5, 'Przechwyty/90': 8,
        'Odzyskane piłki/90': 7, 'Udane odbiory/90': 5, 'Strata piłek na podanie': 7, 'Kartki/90': 3},
    # Defensywny pomocnik: odbior przed linia obrony (53%), rozegranie (32%), bezpieczenstwo i dyscyplina.
    "Defensywny Pomocnik": {
        'Przechwyty/90': 15, 'Odzyskane piłki/90': 15, 'Udane odbiory/90': 10, 'Udane próby pressingu/90': 8,
        'Wygrane główki/90': 5, 'Podania progresywne/90': 12, 'Celność podań (%)': 8, 'Kluczowe podania z gry/90': 7,
        'Oczekiwane asysty/90': 5, 'Strata piłek na podanie': 10, 'Kartki/90': 3, 'Błędy prowadzące do gola/90': 2},
    # Srodkowy pomocnik (box-to-box): kreowanie (36%), zagrozenie (10%), przenoszenie pilki (25%),
    # odbior (17%), bezpieczenstwo pilki - najsilniej zwiazane ze srednia ocena na tej pozycji.
    "Środkowy Pomocnik": {
        'Oczekiwane asysty/90': 17, 'Asysty/90': 4, 'Kluczowe podania z gry/90': 15, 'Liczba goli na 90 min': 5,
        'Oczekiwane gole bez karnych/90': 5, 'Liczba dryblingów/90': 8, 'Podania progresywne/90': 12,
        'Celność podań (%)': 5, 'Odzyskane piłki/90': 5, 'Przechwyty/90': 5, 'Udane odbiory/90': 5,
        'Udane próby pressingu/90': 2, 'Strata piłek na podanie': 10, 'Kartki/90': 2},
    # Ofensywny pomocnik ("dziesiatka"): tworzenie sytuacji (50%) i zagrozenie z wejsc w pole karne
    # (npxG zamiast losowych goli). Drybling = wyjscie spod presji miedzy liniami.
    "Ofensywny Pomocnik": {
        'Oczekiwane asysty/90': 20, 'Asysty/90': 5, 'Kluczowe podania z gry/90': 15, 'Stworzone 100% sytuacje/90': 10,
        'Oczekiwane gole bez karnych/90': 15, 'Liczba goli na 90 min': 5, 'Liczba dryblingów/90': 10,
        'Podania progresywne/90': 5, 'Udane odbiory/90': 3, 'Udane próby pressingu/90': 2,
        'Strata piłek na podanie': 8, 'Kartki/90': 2},
    # Boczny pomocnik (4-4-2): szerokosc i dosrodkowania (45% kreowania), mniej strzalow niz skrzydlowy,
    # wiecej pracy w obronie (15%).
    "Boczny Pomocnik": {
        'Oczekiwane asysty/90': 18, 'Asysty/90': 5, 'Kluczowe podania z gry/90': 12, 'Udane dośrodkowania/90': 10,
        'Liczba goli na 90 min': 7, 'Oczekiwane gole bez karnych/90': 8, 'Liczba dryblingów/90': 10,
        'Podania progresywne/90': 5, 'Odzyskane piłki/90': 7, 'Udane odbiory/90': 5, 'Udane próby pressingu/90': 3,
        'Strata piłek na podanie': 8, 'Kartki/90': 2},
    # Skrzydlowy (czesto odwrocony): gole i zagrozenie (29%), kreowanie (38%), drybling 1 na 1 (15%).
    "Skrzydłowy": {
        'Oczekiwane asysty/90': 18, 'Asysty/90': 5, 'Kluczowe podania z gry/90': 12, 'Liczba goli na 90 min': 12,
        'Oczekiwane gole bez karnych/90': 12, 'Oczekiwane gole na strzał': 5, 'Liczba dryblingów/90': 15,
        'Udane dośrodkowania/90': 3, 'Odzyskane piłki/90': 5, 'Udane próby pressingu/90': 3,
        'Strata piłek na podanie': 8, 'Kartki/90': 2},
    # Napastnik: gole i jakosc sytuacji (52%), udzial w akcjach (30%), praca bez pilki i w powietrzu.
    "Napastnik": {
        'Liczba goli na 90 min': 18, 'Oczekiwane gole bez karnych/90': 20, 'Oczekiwane gole na strzał': 7,
        'Skuteczność strzałów (%)': 7, 'Oczekiwane asysty/90': 10, 'Asysty/90': 5, 'Kluczowe podania z gry/90': 8,
        'Liczba dryblingów/90': 7, 'Odzyskane piłki/90': 5, 'Udane próby pressingu/90': 3,
        '% wygranych pojedynków główkowych': 3, 'Wygrane główki/90': 2, 'Strata piłek na podanie': 5},
}
MERYTORYKA_WAG = _na_pozycje(_WAGI_RODZIN, dict)

# Presety rol: gotowe zestawy wag (kazda rola sumuje sie do 100) jako punkt startu w panelu wag.
# Pierwsza rola kazdej rodziny to wagi domyslne. Kierunek cech (mniej = lepiej) jest w CECHY.
_xA, _A, _KP, _CCC, _DOS = ('Oczekiwane asysty/90', 'Asysty/90', 'Kluczowe podania z gry/90',
                            'Stworzone 100% sytuacje/90', 'Udane dośrodkowania/90')
_G, _NPXG, _XGS, _SKUT = ('Liczba goli na 90 min', 'Oczekiwane gole bez karnych/90', 'Oczekiwane gole na strzał',
                          'Skuteczność strzałów (%)')
_DRB, _PROG, _CEL, _STR = ('Liczba dryblingów/90', 'Podania progresywne/90', 'Celność podań (%)', 'Strata piłek na podanie')
_PRZ, _ODZ, _ODB, _PRS = ('Przechwyty/90', 'Odzyskane piłki/90', 'Udane odbiory/90', 'Udane próby pressingu/90')
_GLP, _GLW, _SPR, _KAR, _BL = ('% wygranych pojedynków główkowych', 'Wygrane główki/90', 'Sprinty/90', 'Kartki/90',
                               'Błędy prowadzące do gola/90')
_ROLE = {
    "Bramkarz": [
        ("Bramkarz klasyczny", "Przede wszystkim obrona strzałów; gra nogami ma małe znaczenie.",
         {'Uniknięte oczekiwane gole/90': 60, 'Skuteczność obron (%)': 20, _BL: 10, 'Obrony chwytem (%)': 5, _STR: 5}),
        ("Bramkarz-libero", "Wysoko ustawiony: wyjścia poza pole karne i rozpoczynanie akcji krótkim podaniem.",
         {'Uniknięte oczekiwane gole/90': 35, 'Skuteczność obron (%)': 10, _BL: 10, _ODZ: 15, _STR: 15, _CEL: 15}),
    ],
    "Środkowy Obrońca": [
        ("Stoper grający piłką", "Wyprowadza piłkę: podania progresywne, celność, mało strat; odbiór nadal ważny.",
         {_PROG: 20, _CEL: 12, _KP: 5, _STR: 13, _ODZ: 14, _PRZ: 12, _ODB: 6, _GLP: 5, _GLW: 5, _BL: 5, _KAR: 3}),
        ("Zabijaka", "Klasyczny stoper: wygrywa główki i pojedynki, przecina podania; rozegranie drugorzędne.",
         {_GLP: 12, _GLW: 13, _ODB: 15, _ODZ: 20, _PRZ: 15, _PRS: 5, _STR: 7, _BL: 7, _KAR: 3, _PROG: 3}),
    ],
    "Boczny Obrońca": [
        ("Ofensywny boczny obrońca", "Daje szerokość i kreuje: xA, dośrodkowania, podłączanie się do ataku.",
         {_xA: 25, _A: 5, _KP: 15, _DOS: 12, _PROG: 10, _DRB: 5, _PRZ: 8, _ODZ: 7, _ODB: 5, _STR: 5, _KAR: 3}),
        ("Defensywny boczny obrońca", "Przede wszystkim broni flanki: odbiory, przechwyty, główki.",
         {_PRZ: 18, _ODZ: 15, _ODB: 15, _PRS: 7, _GLW: 5, _xA: 10, _KP: 7, _PROG: 8, _STR: 10, _KAR: 5}),
        ("Odwrócony boczny obrońca", "Schodzi do środka pola: celność, progresja i bezpieczeństwo piłki.",
         {_PROG: 18, _CEL: 15, _STR: 15, _KP: 10, _xA: 10, _PRZ: 12, _ODZ: 10, _ODB: 7, _KAR: 3}),
    ],
    "Wahadłowy": [
        ("Ofensywny wahadłowy", "Główny kreator z boku: xA, dośrodkowania, drybling, sprinty.",
         {_xA: 25, _A: 5, _KP: 15, _DOS: 12, _DRB: 12, _PROG: 8, _SPR: 8, _PRZ: 5, _STR: 7, _KAR: 3}),
        ("Defensywny wahadłowy", "Piąty obrońca: odbiór i asekuracja, mniej kreowania.",
         {_PRZ: 15, _ODZ: 15, _ODB: 12, _PRS: 8, _SPR: 5, _xA: 15, _KP: 8, _PROG: 7, _STR: 10, _KAR: 5}),
    ],
    "Defensywny Pomocnik": [
        ("Regista", "Rozgrywający sprzed obrony: progresja, celność, kluczowe podania, mało strat.",
         {_PROG: 22, _CEL: 13, _KP: 12, _xA: 8, _STR: 15, _PRZ: 12, _ODZ: 10, _ODB: 5, _KAR: 3}),
        ("Niszczyciel", "Odbiera piłkę: odbiory, przechwyty, pressing, główki; rozegranie proste.",
         {_ODB: 18, _PRZ: 18, _ODZ: 18, _PRS: 12, _GLW: 8, _STR: 10, _CEL: 5, _BL: 5, _KAR: 6}),
    ],
    "Środkowy Pomocnik": [
        ("Box-to-box", "Wszędzie po trochu: bieganie, odbiór, wejścia w pole karne.",
         {_xA: 12, _KP: 10, _G: 8, _NPXG: 10, _DRB: 8, _PROG: 10, _ODZ: 8, _PRZ: 8, _ODB: 8, _PRS: 6, _STR: 10, _KAR: 2}),
        ("Rozgrywający", "Kreator z głębi: kluczowe podania, xA, progresja i celność.",
         {_xA: 22, _A: 5, _KP: 20, _PROG: 18, _CEL: 10, _DRB: 5, _STR: 15, _ODZ: 5}),
        ("Pomocnik pressujący", "Odzyskuje piłkę wysoko: pressing, odbiory, przechwyty.",
         {_PRS: 18, _ODB: 15, _PRZ: 15, _ODZ: 12, _xA: 10, _KP: 8, _PROG: 7, _STR: 10, _KAR: 5}),
    ],
    "Boczny Pomocnik": [
        ("Klasyczny dośrodkowujący", "Gra przy linii i dośrodkowuje: dośrodkowania, xA, drybling.",
         {_DOS: 20, _xA: 22, _A: 5, _KP: 13, _DRB: 12, _G: 5, _NPXG: 5, _ODZ: 5, _STR: 10, _KAR: 3}),
        ("Pracowity boczny pomocnik", "Pomaga w obronie: odbiory, pressing, odzyskane piłki.",
         {_ODZ: 15, _ODB: 12, _PRS: 10, _PRZ: 8, _xA: 15, _KP: 10, _DOS: 10, _DRB: 5, _STR: 10, _KAR: 5}),
    ],
    "Ofensywny Pomocnik": [
        ("Kreator", "Ostatnie podanie: xA, kluczowe podania, 100% sytuacje.",
         {_xA: 28, _A: 5, _KP: 22, _CCC: 15, _DRB: 10, _PROG: 5, _NPXG: 5, _STR: 10}),
        ("Cień napastnika", "Wbiega w pole karne i strzela: npxG, gole, xG na strzał.",
         {_NPXG: 25, _G: 18, _XGS: 7, _xA: 12, _KP: 10, _DRB: 10, _PRS: 5, _ODZ: 3, _STR: 10}),
    ],
    "Skrzydłowy": [
        ("Odwrócony skrzydłowy", "Schodzi do środka i strzela: gole, npxG, drybling.",
         {_G: 18, _NPXG: 18, _XGS: 7, _DRB: 17, _xA: 12, _KP: 10, _PRS: 3, _ODZ: 5, _STR: 10}),
        ("Klasyczny skrzydłowy", "Gra przy linii: dośrodkowania, xA, drybling 1 na 1.",
         {_DOS: 15, _xA: 22, _A: 5, _KP: 15, _DRB: 18, _G: 5, _NPXG: 5, _ODZ: 5, _STR: 10}),
    ],
    "Napastnik": [
        ("Snajper", "Kończy akcje: gole, npxG, jakość i skuteczność strzałów.",
         {_G: 25, _NPXG: 25, _XGS: 12, _SKUT: 13, _xA: 8, _KP: 5, _GLP: 4, _STR: 8}),
        ("Target man", "Gra tyłem i w powietrzu: wygrane główki, gole, zgrywanie piłek.",
         {_GLW: 18, _GLP: 12, _G: 15, _NPXG: 15, _xA: 8, _KP: 8, _ODZ: 8, _STR: 10, _XGS: 6}),
        ("Fałszywa 9", "Schodzi do rozegrania: xA, kluczowe podania, drybling, progresja.",
         {_xA: 20, _A: 5, _KP: 18, _DRB: 12, _PROG: 10, _NPXG: 12, _G: 8, _STR: 10, _ODZ: 5}),
        ("Napastnik pressujący", "Pierwszy obrońca: pressing, odzyskane piłki, odbiory, do tego gole.",
         {_PRS: 15, _ODZ: 12, _ODB: 8, _G: 15, _NPXG: 18, _xA: 10, _KP: 7, _STR: 10, _SPR: 5}),
    ],
}
ROLE_RODZIN = {r: [("Domyślna (uniwersalna)", "Wagi domyślne pozycji - uniwersalny zawodnik.", dict(_WAGI_RODZIN[r]))]
               + [(n, o, dict(w)) for n, o, w in _ROLE[r]] for r in _WAGI_RODZIN}
ROLE_POZYCJI = {p: ROLE_RODZIN[RODZINA_POZYCJI.get(p, p)] for p in POZYCJE}

_PODSTAWA = ['SCORE', 'Percentyl', 'Piłkarz', 'Wiek', 'Kraj', 'Pozycja', 'Preferowana noga', 'Liga', 'Klub', 'Cena']
_KOLUMNY_RODZIN = {
    "Bramkarz": _PODSTAWA + ['Uniknięte oczekiwane gole/90', 'Skuteczność obron (%)', 'Odzyskane piłki/90', 'Stracone piłki/90', 'Strata piłek na podanie', 'Błędy prowadzące do gola/90', 'Celność podań (%)', 'Obrony chwytem (%)', 'Próby podań/90'],
    "Środkowy Obrońca": _PODSTAWA + ['Kluczowe podania z gry/90', 'Podania progresywne/90', 'Udane próby pressingu/90', 'Przechwyty/90', 'Odzyskane piłki/90', 'Stracone piłki/90', 'Strata piłek na podanie', 'Udane odbiory/90', 'Wygrane główki/90', 'Celność podań (%)', 'Błędy prowadzące do gola/90', 'Kartki/90', 'Próby podań/90', '% wygranych pojedynków główkowych'],
    "Boczny Obrońca": _PODSTAWA + ['Oczekiwane asysty/90', 'Kluczowe podania z gry/90', 'Udane dośrodkowania/90', 'Podania progresywne/90', 'Udane próby pressingu/90', 'Przechwyty/90', 'Odzyskane piłki/90', 'Stracone piłki/90', 'Strata piłek na podanie', 'Asysty/90', 'Udane odbiory/90', 'Celność podań (%)', 'Kartki/90', 'Próby podań/90'],
    "Wahadłowy": _PODSTAWA + ['Oczekiwane asysty/90', 'Kluczowe podania z gry/90', 'Udane dośrodkowania/90', 'Podania progresywne/90', 'Liczba dryblingów/90', 'Sprinty/90', 'Udane próby pressingu/90', 'Przechwyty/90', 'Odzyskane piłki/90', 'Stracone piłki/90', 'Strata piłek na podanie', 'Asysty/90', 'Udane odbiory/90', 'Kartki/90', 'Próby podań/90'],
    "Defensywny Pomocnik": _PODSTAWA + ['Oczekiwane asysty/90', 'Kluczowe podania z gry/90', 'Podania progresywne/90', 'Udane próby pressingu/90', 'Przechwyty/90', 'Odzyskane piłki/90', 'Stracone piłki/90', 'Strata piłek na podanie', 'Udane odbiory/90', 'Wygrane główki/90', 'Celność podań (%)', 'Kartki/90', 'Błędy prowadzące do gola/90', 'Próby podań/90', '% wygranych pojedynków główkowych'],
    "Środkowy Pomocnik": _PODSTAWA + ['Oczekiwane asysty/90', 'Kluczowe podania z gry/90', 'Podania progresywne/90', 'Liczba goli na 90 min', 'Udane próby pressingu/90', 'Odzyskane piłki/90', 'Stracone piłki/90', 'Strata piłek na podanie', 'Asysty/90', 'Oczekiwane gole bez karnych/90', 'Celność podań (%)', 'Przechwyty/90', 'Udane odbiory/90', 'Kartki/90', 'Próby podań/90', 'Liczba dryblingów/90'],
    "Ofensywny Pomocnik": _PODSTAWA + ['Oczekiwane asysty/90', 'Kluczowe podania z gry/90', 'Stworzone 100% sytuacje/90', 'Podania progresywne/90', 'Liczba goli na 90 min', 'Oczekiwane gole bez karnych/90', 'Oczekiwane gole na strzał', 'Celność strzałów (%)', 'Liczba dryblingów/90', 'Udane próby pressingu/90', 'Odzyskane piłki/90', 'Stracone piłki/90', 'Strata piłek na podanie', 'Asysty/90', 'Udane odbiory/90', 'Kartki/90', 'Próby podań/90'],
    "Boczny Pomocnik": _PODSTAWA + ['Oczekiwane asysty/90', 'Kluczowe podania z gry/90', 'Udane dośrodkowania/90', 'Liczba goli na 90 min', 'Oczekiwane gole bez karnych/90', 'Oczekiwane gole na strzał', 'Celność strzałów (%)', 'Udane próby pressingu/90', 'Odzyskane piłki/90', 'Stracone piłki/90', 'Strata piłek na podanie', 'Asysty/90', 'Podania progresywne/90', 'Udane odbiory/90', 'Kartki/90', 'Próby podań/90', 'Liczba dryblingów/90'],
    "Skrzydłowy": _PODSTAWA + ['Oczekiwane asysty/90', 'Kluczowe podania z gry/90', 'Udane dośrodkowania/90', 'Liczba goli na 90 min', 'Oczekiwane gole bez karnych/90', 'Oczekiwane gole na strzał', 'Celność strzałów (%)', 'Udane próby pressingu/90', 'Odzyskane piłki/90', 'Stracone piłki/90', 'Strata piłek na podanie', 'Asysty/90', 'Kartki/90', 'Próby podań/90', 'Liczba dryblingów/90'],
    "Napastnik": _PODSTAWA + ['Oczekiwane asysty/90', 'Kluczowe podania z gry/90', 'Liczba goli na 90 min', 'Oczekiwane gole bez karnych/90', 'Oczekiwane gole na strzał', 'Skuteczność strzałów (%)', 'Celność strzałów (%)', 'Udane próby pressingu/90', 'Odzyskane piłki/90', 'Stracone piłki/90', 'Strata piłek na podanie', 'Asysty/90', '% wygranych pojedynków główkowych', 'Wygrane główki/90', 'Próby podań/90', 'Liczba dryblingów/90'],
}
KOLUMNY_PER_POZYCJA = _na_pozycje(_KOLUMNY_RODZIN, list)

# Mnozniki lig bazowe (wartosci heurystyczne - nie sa walidowane na danych)
MNOZNIKI_LIG = {
    "Premier League": 0.918,
    "EFL Championship": 0.811,
    "Liga Profesional de Fútbol": 0.809,
    "Liga Profesional": 0.809,
    "Primera Nacional": 0.749,
    "Jupiler Pro League": 0.816,
    "Profvoetbal 1A": 0.816,
    "Challenger Pro League": 0.695,
    "Profvoetbal 1B": 0.695,
    "Série A": 0.826,
    "Brasileirão": 0.826,
    "Série B": 0.721,
    "Brasileirão Série B": 0.721,
    "Hrvatska nogometna liga": 0.792,
    "HNL": 0.792,
    "Prva nogometa liga": 0.673,
    "1. NL": 0.673,
    "Ligue 1": 0.856,
    "Ligue 2": 0.758,
    "LaLiga": 0.866,
    "LaLiga 2": 0.777,
    "Eredivisie": 0.783,
    "Eerste Divisie": 0.66,
    "J1 League": 0.777,
    "J2 League": 0.695,
    "Liga MX": 0.778,
    "Liga Rozwojowa": 0.7,
    "Liga de Expansión MX": 0.7,
    "Bundesliga": 0.867,
    "2. Bundesliga": 0.778,
    "Ekstraklasa": 0.795,
    "I liga": 0.686,
    "1. Liga": 0.686,
    "Liga Portugal": 0.814,
    "Liga Portugal 2": 0.726,
    "MLS": 0.784,
    "Serie A": 0.86,
    "Serie B": 0.759,
    "Brasileirão Série C": 0.67,
    "Primera A": 0.75,
    "Primera B": 0.67,
    "K League 1": 0.76,
    "K League 2": 0.69,
}

# Mnoznik dla lig spoza tabeli: najnizszy znany (a nie 1.0, ktore premiowaloby nieznane,
# zwykle slabsze ligi wyzej niz Premier League).
MNOZNIK_NIEZNANEJ_LIGI = min(MNOZNIKI_LIG.values())

# Slownik mapujacy wyswietlane nazwy lig w aplikacji
MAPOWANIE_NAZW_LIG = {
    "Premier League": "Premier League (ANG 1)",
    "EFL Championship": "EFL Championship (ANG 2)",
    "Liga Profesional de Fútbol": "Liga Profesional de Fútbol (ARG 1)",
    "Liga Profesional": "Liga Profesional de Fútbol (ARG 1)",
    "Primera Nacional": "Primera Nacional (ARG 2)",
    "Jupiler Pro League": "Jupiler Pro League (BEL 1)",
    "Profvoetbal 1A": "Jupiler Pro League (BEL 1)",
    "Challenger Pro League": "Challenger Pro League (BEL 2)",
    "Profvoetbal 1B": "Challenger Pro League (BEL 2)",
    "Série A": "Série A (BRA 1)",
    "Brasileirão": "Série A (BRA 1)",
    "Série B": "Série B (BRA 2)",
    "Brasileirão Série B": "Série B (BRA 2)",
    "Hrvatska nogometna liga": "Hrvatska nogometna liga (CHO 1)",
    "HNL": "Hrvatska nogometna liga (CHO 1)",
    "Prva nogometa liga": "Prva nogometa liga (CHO 2)",
    "1. NL": "Prva nogometa liga (CHO 2)",
    "Ligue 1": "Ligue 1 (FRA 1)",
    "Ligue 2": "Ligue 2 (FRA 2)",
    "LaLiga": "LaLiga (HIS 1)",
    "LaLiga 2": "LaLiga 2 (HIS 2)",
    "Eredivisie": "Eredivisie (HOL 1)",
    "Eerste Divisie": "Eerste Divisie (HOL 2)",
    "J1 League": "J1 League (JAP 1)",
    "J2 League": "J2 League (JAP 2)",
    "Liga MX": "Liga MX (MEX 1)",
    "Liga Rozwojowa": "Liga Rozwojowa (MEX 2)",
    "Liga de Expansión MX": "Liga Rozwojowa (MEX 2)",
    "Bundesliga": "Bundesliga (NIE 1)",
    "2. Bundesliga": "2. Bundesliga (NIE 2)",
    "Ekstraklasa": "Ekstraklasa (POL 1)",
    "I liga": "I liga (POL 2)",
    "1. Liga": "I liga (POL 2)",
    "Liga Portugal": "Liga Portugal (POR 1)",
    "Liga Portugal 2": "Liga Portugal 2 (POR 2)",
    "MLS": "MLS (USA 1)",
    "Serie A": "Serie A (WLO 1)",
    "Serie B": "Serie B (WLO 2)",
    "Brasileirão Série C": "Brasileirão Série C (BRA 3)",
    "Primera A": "Primera A (KOL 1)",
    "Primera B": "Primera B (KOL 2)",
    "K League 1": "K League 1 (KOR 1)",
    "K League 2": "K League 2 (KOR 2)",
}
