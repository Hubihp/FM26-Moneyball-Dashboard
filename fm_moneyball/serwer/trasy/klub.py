"""Trasy klubu: finanse (z odczytu zapisu) i personel (odczyt na zadanie w osobnym procesie)."""
import logging
import threading

from fastapi import APIRouter, HTTPException

from fm_moneyball import finanse as fin
from fm_moneyball import historia_proces
from fm_moneyball.analiza import moi_zawodnicy
from fm_moneyball.personel import personel_z_zapisu

log = logging.getLogger("fm_moneyball")


def utworz(stan, obl):
    router = APIRouter(prefix="/api")
    pamiec = {}                       # (wersja, klub) -> wynik analizy personelu
    blokada = threading.Lock()        # jeden odczyt personelu naraz

    def _moj_klub():
        uid = stan.migawka()["meta"].get("moj_klub_uid")
        if uid is None:
            raise HTTPException(409, "Nie wiem, którym klubem grasz - wczytaj zapis kariery.")
        return uid

    def _kluby_ligi(uid):
        """Kluby ligi mojego klubu: z tabeli ligi, a gdy jej nie ma (poczatek sezonu) - kluby z ta sama liga
        w danych zawodnikow."""
        tabela = stan.tabele.get(uid) or stan.tabele.get(str(uid)) or {}
        kluby = [w["club_uid"] for w in tabela.get("wiersze", []) if w.get("club_uid") is not None]
        if len(kluby) > 1:
            return kluby
        wszyscy = stan.wszyscy_zawodnicy()
        if wszyscy is None or 'Liga' not in wszyscy.columns:
            return kluby
        liga = wszyscy.loc[wszyscy['Klub_UID'] == uid, 'Liga'].dropna()
        if liga.empty:
            return kluby
        return [int(k) for k in wszyscy.loc[wszyscy['Liga'] == liga.mode().iloc[0], 'Klub_UID'].dropna().unique()]

    def _nazwy_druzyn(uid):
        """{slot: nazwa druzyny} z danych zawodnikow klubu (np. 'Rezerwy / juniorzy (Primavera)')."""
        wszyscy = stan.wszyscy_zawodnicy()
        nazwy = {"0": "Pierwsza drużyna"}
        if wszyscy is None or 'Drużyna_slot' not in wszyscy.columns or 'Drużyna' not in wszyscy.columns:
            return nazwy
        klubu = wszyscy[(wszyscy['Klub_UID'] == uid) & wszyscy['Drużyna_slot'].notna()]
        for slot, grupa in klubu.groupby('Drużyna_slot'):
            if int(slot) != 0:
                nazwa = str(grupa['Drużyna'].mode().iloc[0])
                nazwy[str(int(slot))] = nazwa.replace("Rezerwy / juniorzy (", "").rstrip(")") \
                    if "(" in nazwa else f"Drużyna {int(slot) + 1}"
        return nazwy

    @router.get("/finanse")
    def finanse():
        """Miesieczne finanse mojego klubu, wskazniki z ostatnich 12 miesiecy i wygasajace kontrakty."""
        uid = _moj_klub()
        miesiace = stan.finanse.get(str(uid)) or []
        wszyscy = stan.wszyscy_zawodnicy()
        kadra = moi_zawodnicy(wszyscy, uid, tylko_pierwsza=True) if wszyscy is not None else None
        return {"miesiace": miesiace, "podsumowanie": fin.podsumowanie(miesiace),
                "wygasajace": fin.wygasajace_kontrakty(kadra, obl.data_gry()), "ma_dane": bool(miesiace)}

    @router.get("/personel")
    def personel():
        """Sztab mojego klubu z ocenami obszarow, luki na tle ligi i kandydaci (odczyt ok. 20 s, potem z pamieci)."""
        uid = _moj_klub()
        sciezka = getattr(stan, "_sciezka_odczytu", None)
        if not sciezka or stan.meta.get("demo"):
            raise HTTPException(409, "Personel wymaga wczytanego zapisu gry (przy CSV i danych demo go nie ma).")
        klucz = (stan.wersja, uid)
        with blokada:
            if klucz in pamiec:
                return pamiec[klucz]
            kluby_ligi = _kluby_ligi(uid)
            kurs = stan.konfig.opcje_zapisu().kurs_waluty
            argumenty = (sciezka, uid, kluby_ligi, kurs)
            pula = historia_proces.pula_procesow()
            try:
                wynik = pula.submit(personel_z_zapisu, *argumenty).result() if pula is not None else None
            except Exception as e:      # proces zawiodl - odczyt w watku
                log.warning("Personel: proces pomocniczy zawiódł (%s) - odczyt w wątku", e)
                wynik = None
            finally:
                if pula is not None:
                    pula.shutdown()
            if wynik is None:
                try:
                    wynik = personel_z_zapisu(*argumenty)
                except Exception as e:
                    raise HTTPException(500, f"Nie udało się odczytać personelu z zapisu ({type(e).__name__}).")
            wynik["liga_klubow"] = len(kluby_ligi)
            wynik["nazwy_druzyn"] = _nazwy_druzyn(uid)
            pamiec.clear()
            pamiec[klucz] = wynik
            return wynik

    return router
