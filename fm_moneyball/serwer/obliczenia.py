"""
Liczenie wyniku dla API: pula pozycji, SCORE + wycena + kolumny Moneyball, filtry.
Policzone pule sa trzymane w pamieci, wiec zmiana samych filtrow, sortowania czy karta zawodnika
nie przeliczaja modelu.
"""
import json
import threading
from collections import OrderedDict
from datetime import date

import pandas as pd
from fastapi import HTTPException

from fm_moneyball import analiza, historia
from fm_moneyball.serwer.modele import RankingModel
from fm_moneyball.stale import POZYCJE
from fm_moneyball.wycena import wycen

ILE_POLICZONYCH = 24        # tyle policzonych pul (pozycja x ustawienia) trzymamy w pamieci


class Obliczenia:
    def __init__(self, stan):
        self.stan = stan
        # klucz zawiera wersje danych, wiec po przeladowaniu zrodla stare wpisy nie sa uzywane
        self._policzone = OrderedDict()
        self._blokada = threading.Lock()

    def pula(self, pozycja):
        if pozycja not in POZYCJE:
            raise HTTPException(404, f"Nieznana pozycja: {pozycja}")
        df = self.stan.pula(pozycja)
        if df is None or df.empty:
            raise HTTPException(409, "Brak danych dla tej pozycji - wybierz lub poczekaj na wczytanie źródła.")
        return df

    def data_gry(self):
        tekst = self.stan.migawka()["meta"].get("data_gry")
        return date.fromisoformat(tekst) if tekst else None

    def policz(self, pozycja, wagi, ignoruj_mnoznik, k_baza, kandydaci=False, kandydaci_z=()):
        """-> (policzona pula, pominiete cechy, opis modelu wyceny)"""
        df = self.pula(pozycja)
        wagi = wagi if wagi is not None else analiza.wagi_domyslne(pozycja, df)
        wagi = {k: v for k, v in wagi.items() if k in df.columns}
        kandydaci_z = tuple(sorted(kandydaci_z)) if kandydaci else ()
        klucz = (self.stan.wersja, pozycja, json.dumps(wagi, sort_keys=True), ignoruj_mnoznik, k_baza, kandydaci,
                 kandydaci_z)
        with self._blokada:
            if klucz in self._policzone:
                self._policzone.move_to_end(klucz)
                return self._policzone[klucz]
        odniesienie = None
        if kandydaci:
            df, odniesienie = analiza.dolacz_kandydatow(df, self.stan.wszyscy_zawodnicy(), pozycja, kandydaci_z)
        policzona, pominiete = analiza.policz_wynik(df, wagi, ignoruj_mnoznik, k_baza, odniesienie)
        policzona, model_wyceny = wycen(policzona, odniesienie, self.data_gry())
        porownanie = historia.migawka_porownania(historia.migawki(self.stan.katalog_kariery()), self.data_gry())
        if porownanie is not None:
            wtedy = self.pula_migawki(porownanie[0], pozycja, wagi, ignoruj_mnoznik, k_baza)
            policzona = historia.dolicz_rozwoj(policzona, wtedy)
        wynik = (analiza.wzbogac(policzona, self.data_gry()), pominiete, model_wyceny)
        with self._blokada:
            self._policzone[klucz] = wynik
            while len(self._policzone) > ILE_POLICZONYCH:
                self._policzone.popitem(last=False)
        return wynik

    def pula_migawki(self, sciezka, pozycja, wagi, ignoruj_mnoznik, k_baza):
        """
        Zawodnicy pozycji z migawki historii z SCORE i percentylem liczonymi tymi samymi wagami
        (wagi None = domyslne pozycji, jak w policz).
        """
        if wagi is None:
            wagi = analiza.wagi_domyslne(pozycja, self.pula(pozycja))
        klucz = ("migawka", str(sciezka), sciezka.stat().st_mtime, pozycja, json.dumps(wagi, sort_keys=True),
                 ignoruj_mnoznik, k_baza)
        with self._blokada:
            if klucz in self._policzone:
                self._policzone.move_to_end(klucz)
                return self._policzone[klucz]
        df = historia.pula_migawki(historia.wczytaj(sciezka), pozycja)
        wynik = None
        if not df.empty:
            wynik, _ = analiza.policz_wynik(df, {k: v for k, v in wagi.items() if k in df.columns},
                                            ignoruj_mnoznik, k_baza)
        with self._blokada:
            self._policzone[klucz] = wynik
            while len(self._policzone) > ILE_POLICZONYCH:
                self._policzone.popitem(last=False)
        return wynik

    def historia_zawodnika(self, pozycja, uid, pilkarz, wagi, ignoruj_mnoznik, k_baza):
        """
        Zawodnik w kolejnych migawkach: data, sezon, SCORE i percentyl w pozycji (gdy ja wtedy mial),
        minuty (z oznaczeniem malej proby ponizej MIN_MINUT), wartosc i statystyki /90 pozycji.
        Plus daty migawek bez zawodnika i zmiana SCORE wzgledem ostatniej migawki z wczesniejszego sezonu.
        """
        df = self.pula(pozycja)
        wagi = wagi if wagi is not None else analiza.wagi_domyslne(pozycja, df)
        wagi = {k: v for k, v in wagi.items() if k in df.columns}
        statystyki = analiza.kolumny_statystyk(pozycja, df)
        punkty, brak = [], []
        liczba = lambda x: None if x is None or pd.isna(x) else float(x)  # noqa: E731
        for sciezka, dzien in historia.migawki(self.stan.katalog_kariery()):
            wszyscy = historia.wczytaj(sciezka)
            wiersz = wszyscy[(wszyscy['UID'] == uid) & (wszyscy['Piłkarz'] == pilkarz)]
            if wiersz.empty:
                brak.append(dzien.isoformat())
                continue
            wiersz = wiersz.iloc[0]
            pula = self.pula_migawki(sciezka, pozycja, wagi, ignoruj_mnoznik, k_baza)
            w_puli = pula[pula['UID'] == uid] if pula is not None else None
            jest = w_puli is not None and not w_puli.empty
            minuty = liczba(wiersz.get('Minuty'))
            punkty.append({
                "data": dzien.isoformat(), "sezon": historia.sezon(dzien),
                "SCORE": liczba(w_puli['SCORE'].iloc[0]) if jest else None,
                "Percentyl": liczba(w_puli['Percentyl'].iloc[0]) if jest else None,
                "Minuty": minuty, "mala_proba": minuty is None or minuty < historia.MIN_MINUT,
                "Wartość": liczba(wiersz.get('Wartość_Numeryczna')),
                "statystyki": {k: liczba(wiersz.get(k)) for k in statystyki},
            })
        return {"punkty": punkty, "statystyki": statystyki, "min_minut": historia.MIN_MINUT, "brak": brak,
                "delta": _zmiana_sezonowa(punkty)}

    def wynik_i_filtr(self, z: RankingModel):
        """-> (policzona pula, widoczni po filtrach z Pareto, pominiete, model wyceny, ukryci z mojego klubu)"""
        policzona, pominiete, model_wyceny = self.policz(z.pozycja, z.wagi, z.ignoruj_mnoznik, z.k_baza,
                                                         z.filtry.kandydaci, z.filtry.kandydaci_z)
        filtry = analiza.Filtry(**z.filtry.model_dump())
        moj_klub = self.stan.migawka()["meta"].get("moj_klub_uid")
        widoczni = analiza.filtruj(policzona, filtry, self.data_gry(), moj_klub)
        ukryci_moi = 0
        if filtry.bez_mojego_klubu and moj_klub is not None:
            # ilu zawodnikow mojego klubu spelnia pozostale filtry - interfejs mowi o nich wprost
            filtry.bez_mojego_klubu = False
            ukryci_moi = len(analiza.filtruj(policzona, filtry, self.data_gry(), moj_klub)) - len(widoczni)
        return policzona, analiza.oznacz_pareto(widoczni), pominiete, model_wyceny, ukryci_moi


def kandydat(ramka):
    """Maska kandydatow do przekwalifikowania (zawodnicy z innych pozycji)."""
    if 'Kandydat' not in ramka.columns:
        return pd.Series(False, index=ramka.index)
    return ramka['Kandydat'].fillna(False).astype(bool)


def _zmiana_sezonowa(punkty):
    """
    SCORE ostatniej migawki minus SCORE ostatniej migawki z wczesniejszego sezonu (z SCORE).
    Liczona takze przy malej probie - wtedy z flaga `mala_proba` (kolumna rankingu wymaga progu minut).
    """
    if not punkty or punkty[-1]["SCORE"] is None:
        return None
    teraz = punkty[-1]
    wczesniej = [p for p in punkty if p["sezon"] < teraz["sezon"] and p["SCORE"] is not None]
    if not wczesniej:
        return None
    wtedy = wczesniej[-1]
    return {"wartosc": teraz["SCORE"] - wtedy["SCORE"], "wzgledem": wtedy["data"],
            "minuty_wtedy": wtedy["Minuty"], "minuty_teraz": teraz["Minuty"],
            "mala_proba": teraz["mala_proba"] or wtedy["mala_proba"]}
