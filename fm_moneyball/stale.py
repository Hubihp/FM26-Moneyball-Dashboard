"""Stale i slowniki wspolne dla wszystkich zrodel danych i modelu."""

def kolumna_oceny(pozycja):
    """Kolumna z ocena zawodnika (1-20) na danej puli pozycji (tylko dane z zapisu)."""
    return f"Ocena|{pozycja}"


POZYCJE = ["Bramkarz", "Środkowy Obrońca", "Boczny Obrońca", "Wahadłowy", "Defensywny Pomocnik",
           "Środkowy Pomocnik", "Ofensywny Pomocnik", "Skrzydłowy", "Napastnik"]

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
]

# Kolumny liczbowe, ktore konwertujemy raz, przy wczytywaniu
KOLUMNY_STATYSTYK = [v for v in TLUMACZENIE_KOLUMN.values() if v != "Cena"] + KOLUMNY_TYLKO_Z_ZAPISU

# Dane, ktorych gracz nie widzi wprost w grze (dostepne tylko z pliku zapisu)
KOLUMNY_UKRYTE = ['CA', 'PA']

# Kolumny, ktorych NIE traktujemy jako statystyk meczowych
NIE_STATYSTYKI = {
    'SCORE', 'Percentyl', 'Wiarygodność', 'Piłkarz', 'ID', 'Wiek', 'Klub', 'Liga', 'Pozycja', 'Cena',
    'Preferowana noga', 'Kraj', 'Wartość_Numeryczna', 'Zarobki_Numeryczne', 'Płaca', 'Wygasa',
    'Wygasa_Data', 'Minuty', 'Mnożnik_Ligi', 'CA', 'PA'
}

# Statystyki, w ktorych MNIEJ znaczy LEPIEJ (uzywane w radarze i wykresach Top 10)
NIZSZE_LEPSZE = {'Stracone piłki/90', 'Strata piłek na podanie'}

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
}

# Domyslne WAZNOSCI cech per pozycja (0-100). W obliczeniach sa normalizowane do sumy 1,
# wiec liczy sie tylko ich wzajemna proporcja. Cechy, ktorych nie ma w danych, sa pomijane.
MERYTORYKA_WAG = {
    "Bramkarz": {
        'Uniknięte oczekiwane gole/90': 50, 'Skuteczność obron (%)': 20, 'Odzyskane piłki/90': 10,
        'Strata piłek na podanie': 20},
    "Środkowy Obrońca": {
        '% wygranych pojedynków główkowych': 15, 'Przechwyty/90': 20, 'Udane próby pressingu/90': 10,
        'Kluczowe podania z gry/90': 10, 'Odzyskane piłki/90': 25, 'Strata piłek na podanie': 20,
        'Podania progresywne/90': 10},
    "Boczny Obrońca": {
        'Oczekiwane asysty/90': 30, 'Kluczowe podania z gry/90': 20, 'Przechwyty/90': 15,
        'Odzyskane piłki/90': 10, 'Udane próby pressingu/90': 10, 'Strata piłek na podanie': 15,
        'Podania progresywne/90': 10},
    # Wahadlowy: sam daje szerokosc w ustawieniu z trojka obroncow - glowny kreator z boku (xA,
    # dosrodkowania), przenosi pilke (drybling, podania progresywne) i biega cala flanke (sprinty).
    # Obrone asekuruje trzech stoperow, wiec czesc defensywna to 25% (u bocznego obroncy 50%).
    "Wahadłowy": {
        'Oczekiwane asysty/90': 25, 'Kluczowe podania z gry/90': 15, 'Udane dośrodkowania/90': 10,
        'Liczba dryblingów/90': 10, 'Podania progresywne/90': 10, 'Sprinty/90': 5, 'Przechwyty/90': 10,
        'Odzyskane piłki/90': 5, 'Udane próby pressingu/90': 5, 'Strata piłek na podanie': 5},
    "Defensywny Pomocnik": {
        'Oczekiwane asysty/90': 10, 'Kluczowe podania z gry/90': 15, 'Przechwyty/90': 20,
        'Odzyskane piłki/90': 25, 'Udane próby pressingu/90': 15,
        '% wygranych pojedynków główkowych': 5, 'Strata piłek na podanie': 10,
        'Podania progresywne/90': 10},
    "Środkowy Pomocnik": {
        'Oczekiwane asysty/90': 25, 'Liczba goli na 90 min': 10, 'Kluczowe podania z gry/90': 20,
        'Liczba dryblingów/90': 10, 'Odzyskane piłki/90': 10, 'Udane próby pressingu/90': 10,
        'Strata piłek na podanie': 15, 'Podania progresywne/90': 10},
    # Ofensywny pomocnik ("dziesiatka"): tworzenie sytuacji (xA, kluczowe podania, 100% sytuacje = 55%)
    # i zagrozenie z wejsc w pole karne (npxG zamiast losowych goli). Drybling = wyjscie spod presji
    # miedzy liniami; strata pilek ma mala wage, bo ryzykowne podania naleza do tej roli.
    "Ofensywny Pomocnik": {
        'Oczekiwane asysty/90': 25, 'Kluczowe podania z gry/90': 20, 'Stworzone 100% sytuacje/90': 10,
        'Oczekiwane gole bez karnych/90': 15, 'Liczba goli na 90 min': 5, 'Liczba dryblingów/90': 10,
        'Podania progresywne/90': 5, 'Udane próby pressingu/90': 5, 'Strata piłek na podanie': 5},
    "Skrzydłowy": {
        'Oczekiwane asysty/90': 25, 'Liczba goli na 90 min': 15, 'Oczekiwane gole bez karnych/90': 10,
        'Oczekiwane gole na strzał': 10, 'Kluczowe podania z gry/90': 15, 'Liczba dryblingów/90': 15,
        'Udane próby pressingu/90': 5, 'Odzyskane piłki/90': 5, 'Strata piłek na podanie': 5},
    "Napastnik": {
        'Liczba goli na 90 min': 20, 'Oczekiwane gole bez karnych/90': 20, 'Oczekiwane gole na strzał': 10,
        'Oczekiwane asysty/90': 15, 'Kluczowe podania z gry/90': 10, 'Liczba dryblingów/90': 10,
        'Udane próby pressingu/90': 5, 'Odzyskane piłki/90': 5, 'Skuteczność strzałów (%)': 10},
}

_PODSTAWA = ['SCORE', 'Percentyl', 'Piłkarz', 'Wiek', 'Kraj', 'Pozycja', 'Preferowana noga', 'Liga', 'Klub', 'Cena']
KOLUMNY_PER_POZYCJA = {
    "Bramkarz": _PODSTAWA + ['Uniknięte oczekiwane gole/90', 'Skuteczność obron (%)', 'Odzyskane piłki/90', 'Stracone piłki/90', 'Strata piłek na podanie', 'Próby podań/90'],
    "Środkowy Obrońca": _PODSTAWA + ['Kluczowe podania z gry/90', 'Podania progresywne/90', 'Udane próby pressingu/90', 'Przechwyty/90', 'Odzyskane piłki/90', 'Stracone piłki/90', 'Strata piłek na podanie', 'Próby podań/90', '% wygranych pojedynków główkowych'],
    "Boczny Obrońca": _PODSTAWA + ['Oczekiwane asysty/90', 'Kluczowe podania z gry/90', 'Udane dośrodkowania/90', 'Podania progresywne/90', 'Udane próby pressingu/90', 'Przechwyty/90', 'Odzyskane piłki/90', 'Stracone piłki/90', 'Strata piłek na podanie', 'Próby podań/90'],
    "Wahadłowy": _PODSTAWA + ['Oczekiwane asysty/90', 'Kluczowe podania z gry/90', 'Udane dośrodkowania/90', 'Podania progresywne/90', 'Liczba dryblingów/90', 'Sprinty/90', 'Udane próby pressingu/90', 'Przechwyty/90', 'Odzyskane piłki/90', 'Stracone piłki/90', 'Strata piłek na podanie', 'Próby podań/90'],
    "Defensywny Pomocnik": _PODSTAWA + ['Oczekiwane asysty/90', 'Kluczowe podania z gry/90', 'Podania progresywne/90', 'Udane próby pressingu/90', 'Przechwyty/90', 'Odzyskane piłki/90', 'Stracone piłki/90', 'Strata piłek na podanie', 'Próby podań/90', '% wygranych pojedynków główkowych'],
    "Środkowy Pomocnik": _PODSTAWA + ['Oczekiwane asysty/90', 'Kluczowe podania z gry/90', 'Podania progresywne/90', 'Liczba goli na 90 min', 'Udane próby pressingu/90', 'Odzyskane piłki/90', 'Stracone piłki/90', 'Strata piłek na podanie', 'Próby podań/90', 'Liczba dryblingów/90'],
    "Ofensywny Pomocnik": _PODSTAWA + ['Oczekiwane asysty/90', 'Kluczowe podania z gry/90', 'Stworzone 100% sytuacje/90', 'Podania progresywne/90', 'Liczba goli na 90 min', 'Oczekiwane gole bez karnych/90', 'Oczekiwane gole na strzał', 'Celność strzałów (%)', 'Liczba dryblingów/90', 'Udane próby pressingu/90', 'Odzyskane piłki/90', 'Stracone piłki/90', 'Strata piłek na podanie', 'Próby podań/90'],
    "Skrzydłowy": _PODSTAWA + ['Oczekiwane asysty/90', 'Kluczowe podania z gry/90', 'Udane dośrodkowania/90', 'Liczba goli na 90 min', 'Oczekiwane gole bez karnych/90', 'Oczekiwane gole na strzał', 'Celność strzałów (%)', 'Udane próby pressingu/90', 'Odzyskane piłki/90', 'Stracone piłki/90', 'Strata piłek na podanie', 'Próby podań/90', 'Liczba dryblingów/90'],
    "Napastnik": _PODSTAWA + ['Oczekiwane asysty/90', 'Kluczowe podania z gry/90', 'Liczba goli na 90 min', 'Oczekiwane gole bez karnych/90', 'Oczekiwane gole na strzał', 'Skuteczność strzałów (%)', 'Celność strzałów (%)', 'Udane próby pressingu/90', 'Odzyskane piłki/90', 'Stracone piłki/90', 'Strata piłek na podanie', 'Próby podań/90', 'Liczba dryblingów/90'],
}

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
