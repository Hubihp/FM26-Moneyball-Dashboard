"""
Nazwy krajow (narodowosci) zawodnikow z zapisu.

Zapis FM26 nie zawiera nazw krajow, tylko ich identyfikatory (nation_id). Nazwy bierzemy:
1. recznie wpisane (dane/nazwy_krajow.csv i ~/.fm_moneyball/nazwy_krajow.csv),
2. automatycznie z nazwanych lig: liga "Ekstraklasa (POL 1)" gra w kraju o id dominujacym
   wsrod jej klubow, wiec ten id to Polska,
3. z klubow-kotwic (kraje bez wczytanej ligi): najczestsza narodowosc w kadrach typowo krajowych
   klubow, np. Hibernian, Aberdeen, Motherwell -> Szkocja,
4. w pozostalych przypadkach "Kraj #id" (do nazwania w zakladce Ligi).
"""
import re
import unicodedata
from collections import Counter

from fm_moneyball.mapy import KATALOG_DANYCH, KATALOG_DOMOWY, wczytaj_mape, zapisz_mape
from fm_moneyball.stale import MAPOWANIE_NAZW_LIG

PLIK_KRAJOW = KATALOG_DANYCH / "nazwy_krajow.csv"
PLIK_KRAJOW_UZYTKOWNIKA = KATALOG_DOMOWY / "nazwy_krajow.csv"

# Kod kraju z etykiety ligi, np. "(POL 1)" -> nazwa kraju
KRAJ_Z_KODU = {
    "ANG": "Anglia", "ARG": "Argentyna", "BEL": "Belgia", "BRA": "Brazylia", "CHO": "Chorwacja",
    "FRA": "Francja", "HIS": "Hiszpania", "HOL": "Holandia", "JAP": "Japonia", "KOL": "Kolumbia",
    "KOR": "Korea Płd.", "MEX": "Meksyk", "NIE": "Niemcy", "POL": "Polska", "POR": "Portugalia",
    "USA": "USA", "WLO": "Włochy",
}
_KOD_LIGI = re.compile(r"\(([A-Z]{3}) \d+\)")


def etykieta_kraju(kraj_id):
    return f"Kraj #{kraj_id}"


def nazwy_auto(ligi):
    """[{nazwa, kraj}] (podsumowanie lig) -> {nation_id: nazwa kraju} z kodow w etykietach lig."""
    glosy = {}
    for liga in ligi:
        if not liga.get("nazwa") or liga.get("kraj") is None:
            continue
        m = _KOD_LIGI.search(MAPOWANIE_NAZW_LIG.get(liga["nazwa"], liga["nazwa"]))
        if m and m.group(1) in KRAJ_Z_KODU:
            glosy.setdefault(liga["kraj"], Counter())[KRAJ_Z_KODU[m.group(1)]] += 1
    return {kraj: licznik.most_common(1)[0][0] for kraj, licznik in glosy.items()}


def wczytaj_nazwy_krajow(plik_uzytkownika=PLIK_KRAJOW_UZYTKOWNIKA, domyslny=PLIK_KRAJOW):
    """Reczne nazwy krajow: domyslne z repozytorium nadpisane edycjami uzytkownika."""
    return {**wczytaj_mape(domyslny), **wczytaj_mape(plik_uzytkownika)}


def zapisz_nazwe_kraju(kraj_id, nazwa, sciezka=PLIK_KRAJOW_UZYTKOWNIKA):
    """Dopisuje lub zmienia nazwe kraju; pusta nazwa usuwa wpis uzytkownika."""
    mapa = wczytaj_mape(sciezka)
    if nazwa:
        mapa[int(kraj_id)] = nazwa
    else:
        mapa.pop(int(kraj_id), None)
    return zapisz_mape(mapa, sciezka, ("nation_id", "nazwa"))


def podsumuj_kraje(zawodnicy, nazwy, zrodla=None, przyklady=3):
    """
    Zawodnicy wszystkich pozycji (z 'Kraj_ID') -> [{id, nazwa, zrodlo, reczna, liczba, przyklady}]:
    kraje bez nazwy najpierw, potem wg liczby zawodnikow. Przyklady to najdrozsi zawodnicy -
    po nich najlatwiej rozpoznac kraj w grze.
    """
    if zawodnicy is None or 'Kraj_ID' not in zawodnicy.columns:
        return []
    wynik = []
    for kraj_id, grupa in zawodnicy.dropna(subset=['Kraj_ID']).groupby('Kraj_ID'):
        kraj_id = int(kraj_id)
        najlepsi = grupa.sort_values('Wartość_Numeryczna', ascending=False, na_position='last').head(przyklady)
        wynik.append({
            "id": kraj_id, "nazwa": nazwy.get(kraj_id), "zrodlo": (zrodla or {}).get(kraj_id),
            "reczna": (zrodla or {}).get(kraj_id) == "ręcznie", "liczba": int(len(grupa)),
            "przyklady": [f"{w['Piłkarz']} ({w.get('Klub') or '?'})" for _, w in najlepsi.iterrows()],
        })
    return sorted(wynik, key=lambda k: (k["nazwa"] is not None, -k["liczba"]))


# --- kraje bez wczytanej ligi: kluby-kotwice -------------------------------------------------------
# Typowo krajowe kluby (wiekszosc kadry to zawodnicy z tego kraju). Najczestsza narodowosc w kadrze
# takiego klubu wskazuje id kraju. Kilka klubow na kraj, bo pojedynczy klub moze miec inna nazwe
# w bazie gry albo kadre pelna obcokrajowcow - decyduje glosowanie.
KOTWICE_KRAJOW = {
    "Szkocja": ["Hibernian", "Heart of Midlothian", "Hearts", "Aberdeen", "Motherwell", "Kilmarnock", "St. Mirren",
                "Dundee United", "Ross County", "St. Johnstone"],
    "Walia": ["Connah's Quay Nomads", "Bala Town", "Penybont", "Caernarfon Town", "Cardiff Metropolitan University",
              "Haverfordwest County"],
    "Irlandia Płn.": ["Linfield", "Glentoran", "Larne", "Cliftonville", "Crusaders", "Coleraine"],
    "Irlandia": ["Shamrock Rovers", "Bohemians", "St. Patrick's Athletic", "Shelbourne", "Dundalk", "Sligo Rovers"],
    "Czechy": ["Sparta Praha", "Slavia Praha", "Viktoria Plzeň", "Baník Ostrava", "Sigma Olomouc", "Slovan Liberec"],
    "Słowacja": ["Slovan Bratislava", "Spartak Trnava", "Žilina", "Ružomberok", "Podbrezová"],
    "Austria": ["Red Bull Salzburg", "Rapid Wien", "Sturm Graz", "Austria Wien", "LASK", "Wolfsberger AC"],
    "Szwajcaria": ["Young Boys", "Basel", "Zürich", "Servette", "St. Gallen", "Luzern", "Lugano"],
    "Dania": ["København", "Brøndby", "Midtjylland", "AGF", "Nordsjælland", "Randers", "Silkeborg"],
    "Szwecja": ["Malmö FF", "AIK", "Djurgården", "Hammarby", "IFK Göteborg", "Häcken", "Elfsborg"],
    "Norwegia": ["Rosenborg", "Bodø/Glimt", "Molde", "Brann", "Viking", "Vålerenga"],
    "Finlandia": ["HJK", "KuPS", "SJK", "Ilves", "Inter Turku"],
    "Islandia": ["Breiðablik", "Víkingur Reykjavík", "KR Reykjavík", "Valur", "FH Hafnarfjörður"],
    "Turcja": ["Galatasaray", "Fenerbahçe", "Beşiktaş", "Trabzonspor", "Konyaspor", "Kayserispor", "Sivasspor"],
    "Grecja": ["Olympiacos", "Panathinaikos", "PAOK", "AEK Athens", "Aris", "OFI"],
    "Cypr": ["APOEL", "Omonia", "AEL Limassol", "Apollon Limassol", "Anorthosis"],
    "Ukraina": ["Shakhtar Donetsk", "Dynamo Kyiv", "Zorya Luhansk", "Vorskla Poltava", "Kolos Kovalivka", "Oleksandriya"],
    "Rosja": ["Zenit", "Spartak Moskva", "CSKA Moskva", "Lokomotiv Moskva", "Dinamo Moskva", "Rubin Kazan", "Rostov"],
    "Białoruś": ["BATE Borisov", "Dinamo Minsk", "Shakhtyor Soligorsk"],
    "Serbia": ["Crvena Zvezda", "Partizan", "Vojvodina", "Čukarički", "TSC"],
    "Bośnia i Hercegowina": ["Sarajevo", "Željezničar", "Borac Banja Luka", "Zrinjski"],
    "Czarnogóra": ["Budućnost Podgorica", "Sutjeska Nikšić"],
    "Słowenia": ["Maribor", "Olimpija Ljubljana", "Celje", "Mura", "Koper"],
    "Macedonia Płn.": ["Vardar", "Shkëndija", "Struga"],
    "Albania": ["Partizani", "Tirana", "Vllaznia", "Skënderbeu"],
    "Kosowo": ["Ballkani", "Drita", "Prishtina"],
    "Rumunia": ["FCSB", "CFR Cluj", "Rapid București", "Universitatea Craiova", "Dinamo București", "Farul Constanța"],
    "Bułgaria": ["Ludogorets", "CSKA Sofia", "Levski Sofia", "Lokomotiv Plovdiv", "Botev Plovdiv"],
    "Węgry": ["Ferencváros", "Puskás Akadémia", "Fehérvár", "Debrecen", "Paks", "Újpest"],
    "Izrael": ["Maccabi Tel-Aviv", "Maccabi Haifa", "Hapoel Be'er Sheva", "Hapoel Tel-Aviv", "Beitar Jerusalem"],
    "Gruzja": ["Dinamo Tbilisi", "Dinamo Batumi", "Torpedo Kutaisi"],
    "Armenia": ["Pyunik", "Ararat-Armenia", "Noah"],
    "Azerbejdżan": ["Qarabağ", "Neftçi", "Sabah"],
    "Kazachstan": ["Astana", "Kairat", "Tobol"],
    "Litwa": ["Žalgiris", "Kauno Žalgiris", "Sūduva"],
    "Łotwa": ["RFS", "Riga", "Valmiera"],
    "Estonia": ["Flora", "Levadia", "Paide"],
    "Maroko": ["Wydad", "Raja Casablanca", "AS FAR", "RS Berkane", "FUS Rabat"],
    "Algieria": ["MC Alger", "CR Belouizdad", "JS Kabylie", "USM Alger", "ES Sétif"],
    "Tunezja": ["Espérance", "Club Africain", "Étoile du Sahel", "CS Sfaxien"],
    "Egipt": ["Al Ahly", "Zamalek", "Pyramids", "Ismaily", "Al Masry"],
    "RPA": ["Kaizer Chiefs", "Orlando Pirates", "Mamelodi Sundowns", "SuperSport United", "Stellenbosch"],
    "Nigeria": ["Enyimba", "Kano Pillars", "Rivers United", "Shooting Stars", "Remo Stars"],
    "Ghana": ["Asante Kotoko", "Hearts of Oak", "Medeama", "Dreams", "Aduana Stars"],
    "Senegal": ["Jaraaf", "Génération Foot", "Teungueth", "Casa Sports", "Diambars"],
    "Mali": ["Stade Malien", "Djoliba", "Real Bamako"],
    "Wybrzeże Kości Słoniowej": ["ASEC Mimosas", "Africa Sports", "Stade d'Abidjan", "SOA", "Sporting Gagnoa"],
    "Kamerun": ["Coton Sport", "Canon Yaoundé", "Union Douala"],
    "DR Konga": ["TP Mazembe", "Vita Club", "DCMP"],
    "Gwinea": ["Horoya", "Hafia"],
    "Zambia": ["ZESCO United", "Zanaco", "Power Dynamos"],
    "Zimbabwe": ["Dynamos", "CAPS United", "FC Platinum"],
    "Angola": ["Petro de Luanda", "Primeiro de Agosto", "Sagrada Esperança"],
    "Tanzania": ["Simba", "Young Africans", "Azam"],
    "Kenia": ["Gor Mahia", "AFC Leopards", "Tusker"],
    "Kanada": ["Forge", "Cavalry", "Pacific", "York United"],
    "Urugwaj": ["Peñarol", "Defensor Sporting", "Danubio", "Cerro Largo", "Montevideo Wanderers"],
    "Chile": ["Colo-Colo", "Universidad de Chile", "Universidad Católica", "Cobresal", "Huachipato", "Palestino"],
    "Paragwaj": ["Olimpia", "Cerro Porteño", "Libertad", "Guaraní", "Sportivo Luqueño"],
    "Peru": ["Alianza Lima", "Universitario", "Sporting Cristal", "Melgar", "Cienciano"],
    "Ekwador": ["LDU Quito", "Independiente del Valle", "Emelec", "Aucas", "Barcelona SC"],
    "Boliwia": ["Bolívar", "The Strongest", "Always Ready", "Jorge Wilstermann"],
    "Wenezuela": ["Caracas", "Deportivo Táchira", "Monagas", "Carabobo"],
    "Kostaryka": ["Saprissa", "Alajuelense", "Herediano"],
    "Honduras": ["Motagua", "Real España", "Marathón"],
    "Arabia Saudyjska": ["Al-Hilal", "Al-Nassr", "Al-Ittihad", "Al-Shabab", "Al-Ettifaq", "Al-Fateh"],
    "Katar": ["Al-Sadd", "Al-Duhail", "Al-Rayyan", "Al-Gharafa"],
    "ZEA": ["Al-Ain", "Al-Wahda", "Shabab Al-Ahli", "Al-Jazira"],
    "Iran": ["Persepolis", "Esteghlal", "Sepahan", "Tractor"],
    "Chiny": ["Shanghai Port", "Shanghai Shenhua", "Beijing Guoan", "Shandong Taishan", "Chengdu Rongcheng"],
    "Australia": ["Melbourne Victory", "Sydney", "Melbourne City", "Central Coast Mariners", "Adelaide United",
                  "Western Sydney Wanderers"],
    "Tajlandia": ["Buriram United", "Muangthong United", "Bangkok United"],
    "Indie": ["Mohun Bagan", "East Bengal", "Bengaluru", "Mumbai City"],
}
MIN_ZAWODNIKOW_KOTWICY = 8
MIN_UDZIAL_KOTWICY = 0.5        # najczestsza narodowosc w kadrze klubu-kotwicy
MIN_UDZIAL_JEDNEGO_GLOSU = 0.7  # gdy kraj ma tylko jeden glos, musi byc wyrazny
MIN_UDZIAL_LIGI = 0.35          # najczestsza narodowosc wsrod zawodnikow nazwanej ligi

# Slowa ogolne w nazwach klubow pomijane przy porownaniu ("FC Basel" = "Basel")
_OGOLNE = {"fc", "sc", "cf", "ac", "afc", "sk", "fk", "nk", "cd", "ca", "sv", "bk", "club", "de", "the", "cs",
           "as", "ks", "jk", "kv", "krc", "rc", "sd", "ud", "if", "ff", "fbc", "cfc", "sfc", "football", "futbol"}


def klucz_nazwy_klubu(nazwa):
    """Nazwa klubu -> zbior znaczacych slow (bez akcentow, wielkosci liter i skrotow typu FC/SK)."""
    tekst = str(nazwa or "").lower()
    for znak, zamiana in (("ø", "o"), ("æ", "ae"), ("ð", "d"), ("þ", "th"), ("ß", "ss"), ("ł", "l"), ("ı", "i")):
        tekst = tekst.replace(znak, zamiana)
    tekst = unicodedata.normalize("NFKD", tekst).encode("ascii", "ignore").decode()
    slowa = re.split(r"[^a-z0-9]+", tekst)
    return frozenset(s for s in slowa if s and s not in _OGOLNE)


def _narodowosci_klubow(zawodnicy):
    """{club_uid: Counter(nation_id)} ze wszystkich zawodnikow zapisu."""
    wynik = {}
    for z in zawodnicy:
        klub, kraj = getattr(z, "club_uid", None), getattr(z, "nation_id", None)
        if klub is not None and kraj is not None:
            wynik.setdefault(klub, Counter())[kraj] += 1
    return wynik


def kraje_z_kotwic(kluby, zawodnicy, kotwice=None):
    """
    Kluby i zawodnicy zapisu -> {nation_id: nazwa kraju} z klubow-kotwic. Kazdy znaleziony klub
    glosuje na najczestsza narodowosc swojej kadry (>= 50%, >= 8 zawodnikow). Kraj dostaje id
    z najwieksza liczba glosow, gdy ma >= 2 glosy albo jeden wyrazny (>= 70%). Id wskazane przez
    dwa rozne kraje jest odrzucane (niejednoznaczne).
    """
    kotwice = KOTWICE_KRAJOW if kotwice is None else kotwice
    po_nazwie = {}
    for klub in kluby:
        po_nazwie.setdefault(klucz_nazwy_klubu(klub.name), []).append(klub.uid)
    narodowosci = _narodowosci_klubow(zawodnicy)

    wybrane = {}
    for kraj, nazwy_klubow in kotwice.items():
        glosy, udzialy = Counter(), {}
        for nazwa in nazwy_klubow:
            for uid in po_nazwie.get(klucz_nazwy_klubu(nazwa), []):
                licznik = narodowosci.get(uid)
                if not licznik or sum(licznik.values()) < MIN_ZAWODNIKOW_KOTWICY:
                    continue
                kraj_id, ile = licznik.most_common(1)[0]
                udzial = ile / sum(licznik.values())
                if udzial >= MIN_UDZIAL_KOTWICY:
                    glosy[kraj_id] += 1
                    udzialy[kraj_id] = max(udzialy.get(kraj_id, 0), udzial)
        if not glosy:
            continue
        kraj_id, ile = glosy.most_common(1)[0]
        if ile >= 2 or udzialy[kraj_id] >= MIN_UDZIAL_JEDNEGO_GLOSU:
            wybrane.setdefault(kraj_id, []).append(kraj)
    return {kraj_id: kraje[0] for kraj_id, kraje in wybrane.items() if len(kraje) == 1}


def narodowosci_lig(zawodnicy, liga_klubu):
    """{competition_id ligi: Counter(nation_id zawodnikow jej klubow)} - do nazwania krajow po lidze."""
    wynik = {}
    for z in zawodnicy:
        liga = liga_klubu.get(getattr(z, "club_uid", None))
        kraj = getattr(z, "nation_id", None)
        if liga is not None and kraj is not None:
            wynik.setdefault(liga.competition_id, Counter())[kraj] += 1
    return wynik


def kraj_z_licznika(licznik, min_udzial=MIN_UDZIAL_LIGI):
    """Najczestsza narodowosc, gdy ma wyrazny udzial; inaczej None."""
    if not licznik:
        return None
    kraj_id, ile = licznik.most_common(1)[0]
    return kraj_id if ile / sum(licznik.values()) >= min_udzial else None
