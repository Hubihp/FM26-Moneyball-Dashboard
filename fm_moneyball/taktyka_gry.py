"""
Taktyka z zapisu gry (FM27): formacja z pilka i bez pilki, mentalnosc, wybrana XI i rezerwowi.

fmsave czyta `tactics()` (sloty z pozycjami zapisanymi jako bity) i `selections()` (wybor zawodnikow do
slotow). Potwierdzone sa pozycje i mentalnosc; role i instrukcje zapis trzyma jako surowe liczby bez
potwierdzonego znaczenia, wiec ich nie tlumaczymy (lepiej nic niz zgadywanie).
Bity pozycji (fmsave.TacticPosition): 0 BR, 2 D(P), 3 D(L), 4 D(Ś), 7 DP, 8 P(P), 9 P(L), 11 OP(P), 12 OP(L),
13 OP(Ś), 14 N. Bity 1, 5, 6 i 10 fmsave oznacza jako nieznane; z ukladu (miedzy sasiednimi pozycjami)
przyjmujemy: 1 = libero, 5/6 = wahadlowy prawy/lewy, 10 = srodkowy pomocnik.
"""

# bit pozycji -> (pozycja aplikacji, linia formacji, y w % boiska, x dla pozycji bocznych)
POZYCJE_BITOW = {
    0: ("Bramkarz", None, 91, 50),
    1: ("Środkowy Obrońca", "obrona", 82, None),
    2: ("Prawy Obrońca", "obrona", 72, 86),
    3: ("Lewy Obrońca", "obrona", 72, 14),
    4: ("Środkowy Obrońca", "obrona", 76, None),
    5: ("Prawy Wahadłowy", "obrona", 62, 90),
    6: ("Lewy Wahadłowy", "obrona", 62, 10),
    7: ("Defensywny Pomocnik", "dp", 61, None),
    8: ("Prawy Pomocnik", "pomoc", 46, 87),
    9: ("Lewy Pomocnik", "pomoc", 46, 13),
    10: ("Środkowy Pomocnik", "pomoc", 50, None),
    11: ("Prawy Skrzydłowy", "atak", 28, 84),
    12: ("Lewy Skrzydłowy", "atak", 28, 16),
    13: ("Ofensywny Pomocnik", "atak", 36, None),
    14: ("Napastnik", "napad", 15, None),
}
LINIE = ("obrona", "dp", "pomoc", "atak", "napad")
MENTALNOSCI = {1: "bardzo defensywna", 2: "defensywna", 3: "ostrożna", 4: "zrównoważona", 5: "pozytywna",
               6: "ofensywna", 7: "bardzo ofensywna"}
SZEROKOSC_SRODKA = {1: [50], 2: [63, 37], 3: [73, 50, 27], 4: [80, 60, 40, 20], 5: [84, 67, 50, 33, 16]}


def _bit(pozycje):
    """Pierwsza pozycja slotu -> numer bitu (surowa wartosc fmsave) albo None."""
    for p in pozycje or ():
        raw = p.get("raw") if isinstance(p, dict) else getattr(p, "raw", None)
        if raw is not None and raw in POZYCJE_BITOW:
            return raw
    return None


def formacja(bity):
    """
    Bity pozycji 11 slotow -> zapis formacji, np. '4-2-3-1' (linie od obrony do napadu, bez bramkarza).
    Skrzydlowi bez ofensywnego pomocnika naleza do linii ataku z napastnikami (jak w grze: 4-3-3, nie 4-3-2-1).
    """
    liczby = {linia: 0 for linia in LINIE}
    bity = [b for b in bity if b is not None]
    for b in bity:
        if POZYCJE_BITOW[b][1]:
            liczby[POZYCJE_BITOW[b][1]] += 1
    if 13 not in bity and liczby["napad"]:
        liczby["napad"] += liczby["atak"]
        liczby["atak"] = 0
    return "-".join(str(liczby[linia]) for linia in LINIE if liczby[linia])


FLAGA_PRAWA, FLAGA_LEWA = 1 << 21, 1 << 20


def strona(maska):
    """Flagi maski slotu: 0 = prawa strona pary srodkowej, 1 = lewa, 0.5 = brak flagi (srodek albo nieznane)."""
    if maska & FLAGA_PRAWA:
        return 0
    if maska & FLAGA_LEWA:
        return 1
    return 0.5


def sloty_na_boisku(sloty):
    """
    [(numer slotu, bit z pilka, bit bez pilki[, maska])] -> [{numer, pozycja, x, y, pozycja_bez}] we wspolrzednych
    tablicy (x od lewej, y od bramki rywala). Pozycje srodkowe tego samego rzedu rozstawione od prawej do lewej:
    wg flag strony w masce slotu (na zapisie FM27 srodkowy obronca obok prawego obroncy ma flage 0x200000),
    a przy ich braku w kolejnosci numerow slotow (gra numeruje od prawej).
    """
    wynik, srodek = [], {}
    for numer, bit, bit_bez, *maska in sorted(sloty, key=lambda s: s[0]):
        if bit is None:
            continue
        pozycja, _, y, x = POZYCJE_BITOW[bit]
        wpis = {"numer": numer, "_strona": strona(maska[0]) if maska else 0.5, "pozycja": pozycja, "x": x, "y": y,
                "pozycja_bez": POZYCJE_BITOW[bit_bez][0] if bit_bez is not None else None}
        if x is None:
            srodek.setdefault((pozycja, y), []).append(wpis)
        wynik.append(wpis)
    for wpisy in srodek.values():
        wpisy.sort(key=lambda w: (w["_strona"], w["numer"]))
        for wpis, x in zip(wpisy, SZEROKOSC_SRODKA.get(len(wpisy), [50] * len(wpisy))):
            wpis["x"] = x
    for wpis in wynik:
        del wpis["_strona"]
    return wynik


def taktyki_klubu(zapis, club_uid):
    """
    Taktyki pierwszej druzyny prowadzonego klubu: [{nazwa, mentalnosc, formacja, formacja_bez, sloty, rezerwowi}].
    Pierwsza na liscie to taktyka o najnizszym indeksie (glowna). Sloty maja uid (tekst) i nazwisko wybranego
    zawodnika. Zapis nie mowi, ktorej z kilku taktyk dotyczy wybor XI - fmsave potwierdza go dla wybranej taktyki,
    wiec przy kilku taktykach przypisanie zawodnikow jest pewne tylko dla tej, ktora gra wybrala.
    Rezerwowi to zapisana lista gry (moze byc dluzsza niz lawka w meczu).
    """
    wybor, rezerwowi = {}, []
    for s in zapis.selections():
        if s.club_uid != club_uid or (s.team_slot or 0) != 0 or s.player_uid is None:
            continue
        zawodnik = {"uid": str(s.player_uid), "nazwa": s.player_name}
        if s.substitute:
            rezerwowi.append((s.slot, zawodnik))
        else:
            wybor[s.slot] = zawodnik
    wynik = []
    for t in sorted((t for t in zapis.tactics() if t.club_uid == club_uid and (t.team_slot or 0) == 0),
                    key=lambda t: t.index):
        sloty = [(s.number, _bit(s.in_possession_positions), _bit(s.out_of_possession_positions),
                  s.in_possession_mask or 0) for s in t.slots]
        na_boisku = sloty_na_boisku(sloty)
        for wpis in na_boisku:
            zawodnik = wybor.get(wpis["numer"]) or {}
            wpis["uid"], wpis["nazwa"] = zawodnik.get("uid"), zawodnik.get("nazwa")
        mentalnosc = getattr(t.mentality, "raw", None) if t.mentality is not None else None
        wynik.append({
            "nazwa": t.name, "styl": t.style_name, "mentalnosc": MENTALNOSCI.get(mentalnosc),
            "formacja": formacja(s[1] for s in sloty), "formacja_bez": formacja(s[2] for s in sloty),
            "sloty": na_boisku, "rezerwowi": [z for _, z in sorted(rezerwowi, key=lambda r: r[0])],
        })
    return wynik
