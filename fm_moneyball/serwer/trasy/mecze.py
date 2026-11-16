"""Trasy analizy meczow mojego klubu i raportu o rywalu (dane z zapisu gry, fm_moneyball/mecze.py)."""
import pandas as pd
from fastapi import APIRouter, HTTPException

from fm_moneyball import mecze as m
from fm_moneyball.serwer.modele import RywalModel
from fm_moneyball.stale import POZYCJE

KLUCZOWYCH_ZAWODNIKOW = 8
MIN_MINUT_KLUCZOWEGO = 900


def utworz(stan, obl):
    router = APIRouter(prefix="/api")

    def _moj_klub():
        uid = stan.migawka()["meta"].get("moj_klub_uid")
        if uid is None:
            raise HTTPException(409, "Nie wiem, którym klubem grasz - wczytaj zapis kariery.")
        return uid

    def _tabela(uid_klubu):
        """Wiersze tabeli ligi mojego klubu: {club_uid tekst: wiersz}."""
        tabela = stan.tabele.get(_moj_klub()) or stan.tabele.get(str(_moj_klub())) or {}
        return {str(w["club_uid"]): w for w in tabela.get("wiersze", [])}

    @router.get("/mecze")
    def mecze_mojego_klubu():
        """Mecze mojego klubu (rozegrane z xG i najblizsze) z podsumowaniem."""
        uid = _moj_klub()
        lista = stan.mecze.get(str(uid)) or []
        rozegrane = [x for x in lista if x["rozegrany"]]
        najblizsze = [x for x in lista if not x["rozegrany"]]
        return {"mecze": rozegrane, "najblizsze": najblizsze, "podsumowanie": m.podsumowanie(rozegrane),
                "ma_dane": bool(lista), "prog_szczescia": m.PROG_SZCZESCIA}

    @router.post("/rywal")
    def rywal(z: RywalModel):
        """Raport o rywalu: forma i xG z ostatnich meczow, miejsce w tabeli, mecze z nami, kluczowi zawodnicy."""
        moj = _moj_klub()
        jego = stan.mecze.get(z.uid) or []
        tabela = _tabela(moj)
        nasze = [x for x in (stan.mecze.get(str(moj)) or []) if x["rywal_uid"] == z.uid and x["rozegrany"]]
        try:
            uid_rywala = int(z.uid)
        except ValueError:
            raise HTTPException(400, "Nieprawidłowy klub.")
        # kluczowi zawodnicy: najwyzszy SCORE wsrod pozycji, na ktorych zawodnik jest w puli (pierwsza druzyna)
        najlepsi = {}
        for pozycja in POZYCJE:
            df = stan.pula(pozycja)
            if df is None or df.empty or 'Klub_UID' not in df.columns or not (df['Klub_UID'] == uid_rywala).any():
                continue
            policzona, _, _ = obl.policz(pozycja, None, z.ignoruj_mnoznik, z.k_baza)
            jego_zaw = policzona[(policzona['Klub_UID'] == uid_rywala)]
            if 'Drużyna_slot' in jego_zaw.columns:
                jego_zaw = jego_zaw[jego_zaw['Drużyna_slot'].fillna(0) == 0]
            for _, w in jego_zaw.iterrows():
                if pd.isna(w.get('SCORE')):
                    continue
                klucz = str(w['UID'])
                if klucz not in najlepsi or w['SCORE'] > najlepsi[klucz]["SCORE"]:
                    najlepsi[klucz] = {
                        "ID": w['ID'], "pozycja_puli": pozycja, "Piłkarz": w['Piłkarz'], "Klub_UID": int(uid_rywala),
                        "Wiek": None if pd.isna(w.get('Wiek')) else int(w['Wiek']),
                        "Pozycja": w.get('Pozycja'), "SCORE": float(w['SCORE']),
                        "Minuty": None if pd.isna(w.get('Minuty')) else int(w['Minuty']),
                        "Rola FM": None if pd.isna(w.get('Rola FM', None)) else w.get('Rola FM'),
                        "Ocena roli": None if pd.isna(w.get('Ocena roli', None)) else float(w['Ocena roli']),
                        "Wartość_Numeryczna": None if pd.isna(w.get('Wartość_Numeryczna')) else
                        float(w['Wartość_Numeryczna']),
                    }
        # najwyzszy SCORE wsrod grajacych (co najmniej 900 minut); gdy takich nie ma - wszyscy
        wszyscy = sorted(najlepsi.values(), key=lambda x: -x["SCORE"])
        kluczowi = [x for x in wszyscy if (x["Minuty"] or 0) >= MIN_MINUT_KLUCZOWEGO] or wszyscy
        return {
            "uid": z.uid, "nazwa": next((x["rywal"] for x in (stan.mecze.get(str(moj)) or []) if x["rywal_uid"] == z.uid),
                                        None),
            "mecze": jego, "podsumowanie": m.podsumowanie(jego),
            "tabela": tabela.get(z.uid), "moja_tabela": tabela.get(str(moj)), "liczba_w_tabeli": len(tabela),
            "z_nami": nasze, "kluczowi": kluczowi[:KLUCZOWYCH_ZAWODNIKOW],
            "moje_podsumowanie": m.podsumowanie([x for x in (stan.mecze.get(str(moj)) or []) if x["rozegrany"]][-m.MECZE_RYWALA:]),
        }

    return router
