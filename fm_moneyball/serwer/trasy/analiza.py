"""Trasy: analiza pozycji - meta pozycji, ranking, radar, podobni, moja kadra, lista zyczen."""
import pandas as pd
from fastapi import APIRouter, HTTPException

from fm_moneyball import analiza, historia
from fm_moneyball.serwer.modele import HistoriaModel, HistoriaWieluModel, PorownanieZMoimModel, KadraModel, ListaZyczenModel, PodobniModel, RadarModel, RankingModel
from fm_moneyball.serwer.obliczenia import kandydat
from fm_moneyball.stale import POZYCJE


def utworz(stan, obl):
    router = APIRouter(prefix="/api")

    @router.get("/pozycja/{pozycja}")
    def meta_pozycji(pozycja: str):
        df = obl.pula(pozycja)
        ceny = df['Wartość_Numeryczna'].dropna()
        porownanie = historia.migawka_porownania(historia.migawki(stan.katalog_kariery()), obl.data_gry())
        return {
            "pozycja": pozycja, "liczba": len(df),
            "nogi": sorted(df['Preferowana noga'].dropna().unique().tolist()) if 'Preferowana noga' in df.columns else [],
            "wiek": [int(df['Wiek'].min()), int(df['Wiek'].max())] if 'Wiek' in df.columns else None,
            "cena_max": float(ceny.max()) if not ceny.empty else None,
            "minuty_max": int(df['Minuty'].max()) if 'Minuty' in df.columns and df['Minuty'].notna().any() else None,
            "wagi_domyslne": analiza.wagi_domyslne(pozycja, df),
            "ma_kontrakty": bool(df['Wygasa_Data'].notna().any()),
            "okazje": list(analiza.OKAZJE),
            # historia rozwoju: migawki poprzednich wczytan tej kariery
            "ma_historie": porownanie is not None,
            "data_porownania": porownanie[1].isoformat() if porownanie is not None else None,
            "min_minut_rozwoju": historia.MIN_MINUT,
        }

    @router.post("/ranking")
    def ranking(z: RankingModel):
        policzona, widoczni, pominiete, model_wyceny, ukryci_moi = obl.wynik_i_filtr(z)
        kolumny = analiza.kolumny_tabeli(z.pozycja, policzona)
        return {
            "pozycja": z.pozycja,
            "kolumny": kolumny,
            "wiersze": analiza.do_json(widoczni, analiza.pola_wiersza(z.pozycja, policzona)),
            # liczby zawodnikow pozycji; kandydaci z innych pozycji osobno
            "liczba": int((~kandydat(widoczni)).sum()), "liczba_wszystkich": int((~kandydat(policzona)).sum()),
            "liczba_kandydatow": int(kandydat(widoczni).sum()),
            "pominiete": pominiete,
            "statystyki": analiza.kolumny_statystyk(z.pozycja, policzona),
            "model_wyceny": model_wyceny,
            "liczba_ukrytych_mojego_klubu": int(ukryci_moi),
        }

    @router.post("/historia")
    def historia_zawodnika(z: HistoriaModel):
        wszyscy = stan.wszyscy_zawodnicy()
        wiersz = wszyscy[wszyscy['ID'] == z.id] if wszyscy is not None else None
        if wiersz is None or wiersz.empty or 'UID' not in wiersz.columns:
            return {"punkty": [], "statystyki": [], "min_minut": historia.MIN_MINUT}
        w = wiersz.iloc[0]
        if pd.isna(w['UID']):
            return {"punkty": [], "statystyki": [], "min_minut": historia.MIN_MINUT}
        return obl.historia_zawodnika(z.pozycja, int(w['UID']), w['Piłkarz'], z.wagi, z.ignoruj_mnoznik, z.k_baza)

    @router.post("/historia-wielu")
    def historia_wielu(z: HistoriaWieluModel):
        """Historia kilku zawodnikow (zakladka Porownanie) w skali jednej pozycji."""
        wszyscy = stan.wszyscy_zawodnicy()
        wynik = []
        for id_ in z.ids:
            wiersz = wszyscy[wszyscy['ID'] == id_] if wszyscy is not None and 'UID' in wszyscy.columns else None
            if wiersz is None or wiersz.empty or pd.isna(wiersz.iloc[0]['UID']):
                wynik.append({"id": id_, "pilkarz": None, "punkty": [], "brak": [], "delta": None})
                continue
            w = wiersz.iloc[0]
            h = obl.historia_zawodnika(z.pozycja, int(w['UID']), w['Piłkarz'], z.wagi, z.ignoruj_mnoznik, z.k_baza)
            wynik.append({"id": id_, "pilkarz": w['Piłkarz'], **h})
        return {"zawodnicy": wynik, "min_minut": historia.MIN_MINUT}

    @router.post("/porownanie-z-moim")
    def porownanie_z_moim(z: PorownanieZMoimModel):
        """Kandydat na tle najlepszego zawodnika mojego klubu (z biezacego zapisu) na tej pozycji."""
        # pula z kandydatami: zawodnik spoza pozycji tez ma SCORE w jej skali
        policzona, _, _ = obl.policz(z.pozycja, z.wagi, z.ignoruj_mnoznik, z.k_baza, kandydaci=True)
        wiersz = policzona[policzona['ID'] == z.id]
        if wiersz.empty:
            raise HTTPException(404, "Nie znaleziono zawodnika.")
        nominalni = policzona[~policzona['Kandydat'].fillna(False).astype(bool)] \
            if 'Kandydat' in policzona.columns else policzona
        return analiza.porownaj_z_moim(z.pozycja, nominalni, wiersz.iloc[0], stan.migawka()["meta"].get("moj_klub_uid"))

    @router.post("/radar")
    def radar(z: RadarModel):
        return analiza.radar(z.pozycja, obl.pula(z.pozycja), z.ids, stan.wszyscy_zawodnicy() if z.kandydaci else None)

    @router.post("/podobni")
    def podobni(z: PodobniModel):
        policzona, widoczni, *_ = obl.wynik_i_filtr(z)
        wynik = analiza.podobni(z.pozycja, policzona, widoczni.index, z.id, z.k_baza, z.n)
        pola = analiza.pola_wiersza(z.pozycja, policzona) + ['Podobieństwo']
        return {"wiersze": analiza.do_json(wynik, pola)}

    @router.post("/moja-kadra")
    def kadra(z: KadraModel):
        meta = stan.migawka()["meta"]
        uid = meta.get("moj_klub_uid")
        if uid is None:
            raise HTTPException(409, "Nie wiem, którym klubem grasz - wczytaj zapis kariery.")
        wynik = []
        for pozycja in POZYCJE:
            df = stan.pula(pozycja)
            if df is None or df.empty:
                continue
            policzona, _, _ = obl.policz(pozycja, z.wagi.get(pozycja), z.ignoruj_mnoznik, z.k_baza)
            wynik.append(analiza.moja_kadra(pozycja, policzona, uid, obl.data_gry()))
        # w kolejnosci POZYCJE: od bramkarza do napastnika (sortowanie po luce robi interfejs)
        return {"klub": meta.get("moj_klub"), "pozycje": wynik}

    @router.post("/lista-zyczen")
    def lista_zyczen(z: ListaZyczenModel):
        """
        Zawodnik jest szukany niezaleznie od pozycji, z ktorej go dodano: najpierw w puli tej pozycji,
        potem w tej samej puli z kandydatami z innych pozycji (tak byl widoczny przy dodawaniu),
        a na koncu w swojej glownej pozycji (np. wpis z nazwa pozycji sprzed zmiany ich podzialu).
        """
        policzone = {}

        def pula_policzona(pozycja, kandydaci):
            if (pozycja, kandydaci) not in policzone:
                df = stan.pula(pozycja) if pozycja in POZYCJE else None
                policzone[(pozycja, kandydaci)] = None if df is None or df.empty else obl.policz(
                    pozycja, z.wagi.get(pozycja), z.ignoruj_mnoznik, z.k_baza, kandydaci)[0]
            return policzone[(pozycja, kandydaci)]

        wszyscy = None
        znalezieni, brak = [], []
        for w in z.wpisy:
            proby = [(w.pozycja, False), (w.pozycja, True)]
            if wszyscy is None:
                wszyscy = stan.wszyscy_zawodnicy()
            if wszyscy is not None:
                gdzie = analiza.znajdz_zawodnika(wszyscy, w.klucz, w.pilkarz)
                if not gdzie.empty:
                    glowna = gdzie.iloc[0].get('Pula_główna')
                    glowna = glowna if isinstance(glowna, str) else gdzie.iloc[0].get('Pula')
                    proby.append((glowna, False))
            for pozycja, kandydaci in proby:
                policzona = pula_policzona(pozycja, kandydaci)
                wiersz = analiza.znajdz_zawodnika(policzona, w.klucz, w.pilkarz) if policzona is not None else None
                if wiersz is not None and not wiersz.empty:
                    znalezieni.append(wiersz.assign(**{'Pozycja na liście': pozycja}))
                    break
            else:
                brak.append(w.klucz)
        ramka = pd.concat(znalezieni, ignore_index=True) if znalezieni else pd.DataFrame()
        return {"kolumny": analiza.kolumny_listy(ramka),
                "wiersze": analiza.do_json(ramka, analiza.POLA_WIERSZA + ['Pozycja na liście']),
                "nieznalezieni": brak}

    return router
