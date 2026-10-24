"""Trasy: analiza pozycji - meta pozycji, ranking, radar, podobni, moja kadra, lista zyczen."""
import pandas as pd
from fastapi import APIRouter, HTTPException

from fm_moneyball import analiza
from fm_moneyball.serwer.modele import KadraModel, ListaZyczenModel, PodobniModel, RadarModel, RankingModel
from fm_moneyball.serwer.obliczenia import kandydat
from fm_moneyball.stale import POZYCJE


def utworz(stan, obl):
    router = APIRouter(prefix="/api")

    @router.get("/pozycja/{pozycja}")
    def meta_pozycji(pozycja: str, pokaz_ukryte: bool = False):
        df = obl.pula(pozycja)
        ceny = df['Wartość_Numeryczna'].dropna()
        return {
            "pozycja": pozycja, "liczba": len(df),
            "nogi": sorted(df['Preferowana noga'].dropna().unique().tolist()) if 'Preferowana noga' in df.columns else [],
            "wiek": [int(df['Wiek'].min()), int(df['Wiek'].max())] if 'Wiek' in df.columns else None,
            "cena_max": float(ceny.max()) if not ceny.empty else None,
            "minuty_max": int(df['Minuty'].max()) if 'Minuty' in df.columns and df['Minuty'].notna().any() else None,
            "wagi_domyslne": analiza.wagi_domyslne(pozycja, df),
            "ma_kontrakty": bool(df['Wygasa_Data'].notna().any()),
            "ma_ukryte": 'CA' in df.columns and bool(df['CA'].notna().any()),
            "ma_ryzyko": 'Podatność na kontuzje' in df.columns and bool(df['Podatność na kontuzje'].notna().any()),
            "okazje": list(analiza.OKAZJE),
        }

    @router.post("/ranking")
    def ranking(z: RankingModel):
        policzona, widoczni, pominiete, model_wyceny, ukryci_moi = obl.wynik_i_filtr(z)
        kolumny = analiza.kolumny_tabeli(z.pozycja, policzona, z.pokaz_ukryte)
        return {
            "pozycja": z.pozycja,
            "kolumny": kolumny,
            "wiersze": analiza.do_json(widoczni, analiza.pola_wiersza(z.pozycja, policzona, z.pokaz_ukryte)),
            # liczby zawodnikow pozycji; kandydaci z innych pozycji osobno
            "liczba": int((~kandydat(widoczni)).sum()), "liczba_wszystkich": int((~kandydat(policzona)).sum()),
            "liczba_kandydatow": int(kandydat(widoczni).sum()),
            "pominiete": pominiete,
            "statystyki": analiza.kolumny_statystyk(z.pozycja, policzona),
            "model_wyceny": model_wyceny,
            "liczba_ukrytych_mojego_klubu": int(ukryci_moi),
        }

    @router.post("/radar")
    def radar(z: RadarModel):
        return analiza.radar(z.pozycja, obl.pula(z.pozycja), z.ids, stan.wszyscy_zawodnicy() if z.kandydaci else None)

    @router.post("/podobni")
    def podobni(z: PodobniModel):
        policzona, widoczni, *_ = obl.wynik_i_filtr(z)
        wynik = analiza.podobni(z.pozycja, policzona, widoczni.index, z.id, z.k_baza, z.n)
        pola = analiza.pola_wiersza(z.pozycja, policzona, z.pokaz_ukryte) + ['Podobieństwo']
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
        znalezieni, brak = [], []
        for pozycja in dict.fromkeys(w.pozycja for w in z.wpisy):
            wpisy = [w for w in z.wpisy if w.pozycja == pozycja]
            df = stan.pula(pozycja) if pozycja in POZYCJE else None
            if df is None or df.empty:
                brak += [w.klucz for w in wpisy]
                continue
            policzona, _, _ = obl.policz(pozycja, z.wagi.get(pozycja), z.ignoruj_mnoznik, z.k_baza)
            for w in wpisy:
                wiersz = analiza.znajdz_zawodnika(policzona, w.klucz, w.pilkarz)
                if wiersz.empty:
                    brak.append(w.klucz)
                else:
                    znalezieni.append(wiersz.assign(**{'Pozycja na liście': pozycja}))
        ramka = pd.concat(znalezieni, ignore_index=True) if znalezieni else pd.DataFrame()
        return {"kolumny": analiza.kolumny_listy(ramka),
                "wiersze": analiza.do_json(ramka, analiza.POLA_WIERSZA + ['Pozycja na liście']),
                "nieznalezieni": brak}

    return router
