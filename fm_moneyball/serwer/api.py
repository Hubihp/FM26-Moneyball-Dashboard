"""
API (FastAPI) dla interfejsu React. Serwuje tez zbudowany frontend z katalogu `static/`.

Uruchomienie: `python -m fm_moneyball` (patrz fm_moneyball/__main__.py).
"""
import asyncio
import json
import threading
from collections import OrderedDict
from datetime import date
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

import pandas as pd

from fm_moneyball import analiza
from fm_moneyball.kraje import podsumuj_kraje, zapisz_nazwe_kraju
from fm_moneyball.ligi import wszystkie_mnozniki, zapisz_mnoznik
from fm_moneyball.wycena import wycen
from fm_moneyball.stale import MNOZNIK_NIEZNANEJ_LIGI, MNOZNIKI_LIG, POZYCJE
from fm_moneyball.zrodla import folder as folder_zapisow
from fm_moneyball.zrodla.csv_fm import wczytaj_csv
from fm_moneyball.zrodla.zapis_fm import KURS_DOMYSLNY, zapisz_nazwy_rozgrywek, zbuduj_mape_nazw_lig

KATALOG_STATIC = Path(__file__).resolve().parent / "static"
ILE_POLICZONYCH = 24        # tyle policzonych pul (pozycja x ustawienia) trzymamy w pamieci


class ZasobyZCache(StaticFiles):
    """Pliki zbudowanego frontendu (nazwy z hashem) - przegladarka moze je trzymac na stale."""

    async def get_response(self, path, scope):
        odpowiedz = await super().get_response(path, scope)
        if odpowiedz.status_code == 200:
            odpowiedz.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        return odpowiedz


# --- modele zapytan -----------------------------------------------------------------------------
class OpcjeZapisuModel(BaseModel):
    rodzaj_statystyk: str = "league"
    min_minut: int = 300
    kurs_waluty: float = KURS_DOMYSLNY
    wszystkie_naturalne_pozycje: bool = False
    tylko_kluby_w_lidze: bool = True
    wolni_agenci: bool = True


class ZrodloModel(BaseModel):
    typ: str                                  # folder | plik | demo
    folder: str | None = None
    plik: str | None = None
    sledz: bool | None = None
    wczytaj_przy_starcie: bool | None = None
    opcje: OpcjeZapisuModel | None = None


class LigaModel(BaseModel):
    nazwa: str | None = None
    mnoznik: float | None = None


class KrajModel(BaseModel):
    nazwa: str | None = None


class WpisListyModel(BaseModel):
    klucz: str                  # UID z zapisu albo ID (CSV, demo)
    pozycja: str
    pilkarz: str = ""


class ListaZyczenModel(BaseModel):
    wpisy: list[WpisListyModel] = Field(default_factory=list)
    wagi: dict[str, dict[str, float]] = Field(default_factory=dict)   # pozycja -> wagi (brak = domyslne)
    ignoruj_mnoznik: bool = False
    k_baza: float = 5


class MojKlubModel(BaseModel):
    uid: int


class KadraModel(BaseModel):
    wagi: dict[str, dict[str, float]] = Field(default_factory=dict)   # pozycja -> wagi (brak = domyslne)
    ignoruj_mnoznik: bool = False
    k_baza: float = 5


class FiltryModel(BaseModel):
    ligi: list[str] = Field(default_factory=list)
    nogi: list[str] = Field(default_factory=list)
    kraje: list[str] = Field(default_factory=list)
    wiek: tuple[int, int] | None = None
    cena: tuple[float | None, float | None] | None = None
    bez_ceny: bool = True
    szukaj: str = ""
    kontrakt_mies: int | None = None
    min_minut: int = 0
    bez_mojego_klubu: bool = False
    okazje: list[str] = Field(default_factory=list)
    max_ryzyko: int | None = None
    min_oplacalnosc: float | None = None
    kandydaci: bool = False
    min_score_kandydata: float = 60
    min_niedowartosciowanie: float | None = None
    tylko_z_okazja: bool = False


class RankingModel(BaseModel):
    pozycja: str
    wagi: dict[str, float] | None = None
    ignoruj_mnoznik: bool = False
    k_baza: float = 5
    filtry: FiltryModel = Field(default_factory=FiltryModel)
    pokaz_ukryte: bool = False


class RadarModel(BaseModel):
    pozycja: str
    ids: list[str]
    kandydaci: bool = False     # szukaj zawodnikow takze poza pula (kandydaci do przekwalifikowania)


class PodobniModel(RankingModel):
    id: str
    n: int = 10


def utworz_aplikacje(stan):
    app = FastAPI(title="FM26 Moneyball", docs_url="/api/docs", openapi_url="/api/openapi.json")
    app.state.stan = stan

    def pula(pozycja):
        if pozycja not in POZYCJE:
            raise HTTPException(404, f"Nieznana pozycja: {pozycja}")
        df = stan.pula(pozycja)
        if df is None or df.empty:
            raise HTTPException(409, "Brak danych dla tej pozycji - wybierz lub poczekaj na wczytanie źródła.")
        return df

    def data_gry():
        tekst = stan.migawka()["meta"].get("data_gry")
        return date.fromisoformat(tekst) if tekst else None

    # Policzone pule (SCORE + kolumny Moneyball) dla ostatnich ustawien: zmiana samych filtrow,
    # sortowania czy karta zawodnika nie przeliczaja modelu. Klucz zawiera wersje danych.
    policzone = OrderedDict()
    blokada_policzonych = threading.Lock()

    def policz(pozycja, wagi, ignoruj_mnoznik, k_baza, kandydaci=False):
        df = pula(pozycja)
        wagi = wagi if wagi is not None else analiza.wagi_domyslne(pozycja, df)
        wagi = {k: v for k, v in wagi.items() if k in df.columns}
        klucz = (stan.wersja, pozycja, json.dumps(wagi, sort_keys=True), ignoruj_mnoznik, k_baza, kandydaci)
        with blokada_policzonych:
            if klucz in policzone:
                policzone.move_to_end(klucz)
                return policzone[klucz]
        odniesienie = None
        if kandydaci:
            df, odniesienie = analiza.dolacz_kandydatow(df, stan.wszyscy_zawodnicy(), pozycja)
        policzona, pominiete = analiza.policz_wynik(df, wagi, ignoruj_mnoznik, k_baza, odniesienie)
        policzona, model_wyceny = wycen(policzona, odniesienie, data_gry())
        wynik = (analiza.wzbogac(policzona, data_gry()), pominiete, model_wyceny)
        with blokada_policzonych:
            policzone[klucz] = wynik
            while len(policzone) > ILE_POLICZONYCH:
                policzone.popitem(last=False)
        return wynik

    def wynik_i_filtr(z: RankingModel):
        policzona, pominiete, model_wyceny = policz(z.pozycja, z.wagi, z.ignoruj_mnoznik, z.k_baza, z.filtry.kandydaci)
        filtry = analiza.Filtry(**z.filtry.model_dump())
        moj_klub = stan.migawka()["meta"].get("moj_klub_uid")
        widoczni = analiza.filtruj(policzona, filtry, data_gry(), moj_klub)
        ukryci_moi = 0
        if filtry.bez_mojego_klubu and moj_klub is not None:
            # ilu zawodnikow mojego klubu spelnia pozostale filtry - interfejs mowi o nich wprost
            filtry.bez_mojego_klubu = False
            ukryci_moi = len(analiza.filtruj(policzona, filtry, data_gry(), moj_klub)) - len(widoczni)
        return policzona, analiza.oznacz_pareto(widoczni), pominiete, model_wyceny, ukryci_moi

    def kandydat(ramka):
        if 'Kandydat' not in ramka.columns:
            return pd.Series(False, index=ramka.index)
        return ramka['Kandydat'].fillna(False).astype(bool)

    # --- stan i zrodlo -------------------------------------------------------------------------
    @app.get("/api/stan")
    def pobierz_stan():
        return stan.migawka()

    @app.get("/api/zapisy")
    def lista_zapisow(folder: str | None = None):
        domyslny = folder_zapisow.domyslny_folder()
        folder = folder or stan.konfig.folder or (str(domyslny) if domyslny else None)
        pliki = folder_zapisow.lista_zapisow(folder) if folder else []
        return {"folder": folder, "domyslny": str(domyslny) if domyslny else None,
                "kandydaci": [str(k) for k in folder_zapisow.kandydaci_folderow()],
                "pliki": [{"nazwa": p.nazwa, "sciezka": str(p.sciezka), "rozmiar_mb": round(p.rozmiar / 2**20, 1),
                           "zmieniony": p.mtime} for p in pliki]}

    @app.post("/api/zrodlo")
    def ustaw_zrodlo(z: ZrodloModel):
        if z.typ not in ("folder", "plik", "demo"):
            raise HTTPException(400, "Nieznany typ źródła.")
        stan.ustaw_zrodlo(z.typ, folder=z.folder, plik=z.plik, sledz=z.sledz,
                          wczytaj_przy_starcie=z.wczytaj_przy_starcie,
                          opcje=z.opcje.model_dump() if z.opcje else None)
        return stan.migawka()

    @app.post("/api/przeladuj")
    def przeladuj():
        stan.przeladuj(wymus=True)
        return stan.migawka()

    @app.post("/api/wgraj")
    async def wgraj_zapis(request: Request, nazwa: str):
        """Surowa zawartosc pliku w ciele zapytania (bez multipart) - zapisywana raz, strumieniowo."""
        if not nazwa.lower().endswith(".fm"):
            raise HTTPException(400, "To nie jest plik zapisu FM (.fm).")
        katalog = folder_zapisow.folder_kopii() / "wgrane"
        katalog.mkdir(parents=True, exist_ok=True)
        for stary in katalog.glob("*.fm"):
            stary.unlink(missing_ok=True)
        cel = katalog / Path(nazwa).name
        with open(cel, "wb") as f:
            async for kawalek in request.stream():
                f.write(kawalek)
        if cel.stat().st_size == 0:
            raise HTTPException(400, "Pusty plik.")
        stan.ustaw_zrodlo("plik", plik=str(cel))
        return stan.migawka()

    # --- moj klub i ligi -----------------------------------------------------------------------
    @app.post("/api/moj-klub")
    def ustaw_moj_klub(z: MojKlubModel):
        stan.ustaw_moj_klub(z.uid)
        return stan.migawka()

    @app.get("/api/ligi")
    def ligi():
        mnozniki = wszystkie_mnozniki(stan.plik_mnoznikow)
        wynik = []
        for liga in stan.ligi:
            nazwa = liga.get("nazwa")
            wynik.append({**liga, "mnoznik": mnozniki.get(nazwa) if nazwa else None})
        return {"ligi": sorted(wynik, key=lambda l: (l["nazwa"] is not None, -l["liczba"])),
                "znane_nazwy": sorted(set(MNOZNIKI_LIG) | set(mnozniki)),
                "mnozniki": mnozniki,
                "mnoznik_nieznanej": MNOZNIK_NIEZNANEJ_LIGI}

    @app.put("/api/ligi/{klucz}")
    def zmien_lige(klucz: int, z: LigaModel):
        if not any(l["klucz"] == klucz for l in stan.ligi):
            raise HTTPException(404, "Nieznana liga.")
        nazwa = (z.nazwa or "").strip()
        if nazwa:
            zapisz_nazwy_rozgrywek({klucz: nazwa}, stan.plik_nazw)
            if z.mnoznik is not None and wszystkie_mnozniki(stan.plik_mnoznikow).get(nazwa) != z.mnoznik:
                zapisz_mnoznik(nazwa, z.mnoznik, stan.plik_mnoznikow)
        stan.zastosuj_ligi()
        return ligi()

    @app.post("/api/moja-kadra")
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
            policzona, _, _ = policz(pozycja, z.wagi.get(pozycja), z.ignoruj_mnoznik, z.k_baza)
            wynik.append(analiza.moja_kadra(pozycja, policzona, uid, data_gry()))
        # w kolejnosci POZYCJE: od bramkarza do napastnika (sortowanie po luce robi interfejs)
        return {"klub": meta.get("moj_klub"), "pozycje": wynik}

    @app.get("/api/kraje")
    def kraje():
        return {"kraje": podsumuj_kraje(stan.wszyscy_zawodnicy(), stan.nazwy_krajow, stan.zrodla_krajow)}

    @app.put("/api/kraje/{kraj_id}")
    def zmien_kraj(kraj_id: int, z: KrajModel):
        zapisz_nazwe_kraju(kraj_id, (z.nazwa or "").strip(), stan.plik_krajow)
        stan.zastosuj_ligi()
        return kraje()

    @app.post("/api/lista-zyczen")
    def lista_zyczen(z: ListaZyczenModel):
        znalezieni, brak = [], []
        for pozycja in dict.fromkeys(w.pozycja for w in z.wpisy):
            wpisy = [w for w in z.wpisy if w.pozycja == pozycja]
            df = stan.pula(pozycja) if pozycja in POZYCJE else None
            if df is None or df.empty:
                brak += [w.klucz for w in wpisy]
                continue
            policzona, _, _ = policz(pozycja, z.wagi.get(pozycja), z.ignoruj_mnoznik, z.k_baza)
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

    @app.post("/api/nazwy-lig")
    def naucz_nazw_lig(pliki: list[UploadFile] = File(...)):
        meta = stan.migawka()
        if stan.konfig.typ not in ("folder", "plik") or meta["status"] != "gotowe":
            raise HTTPException(409, "Najpierw wczytaj zapis kariery.")
        ramki = []
        for p in pliki:
            try:
                ramki.append(wczytaj_csv(p.file.read())[0])
            except Exception as e:
                raise HTTPException(400, f"Nie udało się wczytać {p.filename}: {e}")
        sciezka = stan._sciezka_odczytu
        if not sciezka:
            raise HTTPException(409, "Brak wczytanego zapisu.")
        mapa = zbuduj_mape_nazw_lig(sciezka, ramki)
        if mapa:
            zapisz_nazwy_rozgrywek(mapa, stan.plik_nazw)
            stan.przeladuj(wymus=True)
        return {"rozpoznane": {str(k): v for k, v in sorted(mapa.items())}}

    @app.get("/api/zdarzenia")
    async def zdarzenia():
        async def strumien():
            ostatni = None
            licznik = 0
            while True:
                m = stan.migawka()
                biezacy = (m["wersja"], m["status"], m["komunikat"])
                if biezacy != ostatni:
                    ostatni = biezacy
                    yield f"data: {json.dumps({'wersja': m['wersja'], 'status': m['status'], 'komunikat': m['komunikat']}, ensure_ascii=False)}\n\n"
                licznik += 1
                if licznik % 15 == 0:
                    yield ": ping\n\n"
                await asyncio.sleep(1)
        return StreamingResponse(strumien(), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    # --- analiza -------------------------------------------------------------------------------
    @app.get("/api/pozycja/{pozycja}")
    def meta_pozycji(pozycja: str, pokaz_ukryte: bool = False):
        df = pula(pozycja)
        ceny = df['Wartość_Numeryczna'].dropna()
        return {
            "pozycja": pozycja, "liczba": len(df),
            # ligi i kraje wg liczby zawodnikow (najliczniejsze pierwsze)
            "ligi": [{"nazwa": k, "liczba": int(n)} for k, n in df['Liga'].dropna().value_counts().items()]
                     if 'Liga' in df.columns else [],
            "nogi": sorted(df['Preferowana noga'].dropna().unique().tolist()) if 'Preferowana noga' in df.columns else [],
            "kraje": [{"nazwa": k, "liczba": int(n)} for k, n in df['Kraj'].dropna().value_counts().items()]
                      if 'Kraj' in df.columns else [],
            "wiek": [int(df['Wiek'].min()), int(df['Wiek'].max())] if 'Wiek' in df.columns else None,
            "cena_max": float(ceny.max()) if not ceny.empty else None,
            "minuty_max": int(df['Minuty'].max()) if 'Minuty' in df.columns and df['Minuty'].notna().any() else None,
            "wagi_domyslne": analiza.wagi_domyslne(pozycja, df),
            "ma_kontrakty": bool(df['Wygasa_Data'].notna().any()),
            "ma_ukryte": 'CA' in df.columns and bool(df['CA'].notna().any()),
            "ma_ryzyko": 'Podatność na kontuzje' in df.columns and bool(df['Podatność na kontuzje'].notna().any()),
            "okazje": list(analiza.OKAZJE),
        }

    @app.post("/api/ranking")
    def ranking(z: RankingModel):
        policzona, widoczni, pominiete, model_wyceny, ukryci_moi = wynik_i_filtr(z)
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

    @app.post("/api/radar")
    def radar(z: RadarModel):
        return analiza.radar(z.pozycja, pula(z.pozycja), z.ids, stan.wszyscy_zawodnicy() if z.kandydaci else None)

    @app.post("/api/podobni")
    def podobni(z: PodobniModel):
        policzona, widoczni, *_ = wynik_i_filtr(z)
        wynik = analiza.podobni(z.pozycja, policzona, widoczni.index, z.id, z.k_baza, z.n)
        pola = analiza.pola_wiersza(z.pozycja, policzona, z.pokaz_ukryte) + ['Podobieństwo']
        return {"wiersze": analiza.do_json(wynik, pola)}

    # --- frontend ------------------------------------------------------------------------------
    if (KATALOG_STATIC / "index.html").is_file():
        app.mount("/assets", ZasobyZCache(directory=KATALOG_STATIC / "assets"), name="assets")

        @app.get("/{sciezka:path}", include_in_schema=False)
        def frontend(sciezka: str):
            plik = KATALOG_STATIC / sciezka
            if sciezka and plik.is_file() and KATALOG_STATIC in plik.resolve().parents:
                return FileResponse(plik)
            # bez cache: po aktualizacji aplikacji przegladarka musi pobrac nowy interfejs
            # (pliki w assets/ maja hash w nazwie, wiec moga byc trzymane dlugo)
            return FileResponse(KATALOG_STATIC / "index.html", headers={"Cache-Control": "no-cache"})

    return app
