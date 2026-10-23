"""
API (FastAPI) dla interfejsu React. Serwuje tez zbudowany frontend z katalogu `static/`.

Uruchomienie: `python -m fm_moneyball` (patrz fm_moneyball/__main__.py).
"""
import asyncio
import json
import shutil
from datetime import date
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from fm_moneyball import analiza
from fm_moneyball.stale import POZYCJE
from fm_moneyball.zrodla import folder as folder_zapisow
from fm_moneyball.zrodla.csv_fm import wczytaj_csv
from fm_moneyball.zrodla.zapis_fm import KURS_DOMYSLNY, zapisz_nazwy_rozgrywek, zbuduj_mape_nazw_lig

KATALOG_STATIC = Path(__file__).resolve().parent / "static"


# --- modele zapytan -----------------------------------------------------------------------------
class OpcjeZapisuModel(BaseModel):
    rodzaj_statystyk: str = "league"
    min_minut: int = 300
    kurs_waluty: float = KURS_DOMYSLNY
    wszystkie_naturalne_pozycje: bool = False
    tylko_kluby_w_lidze: bool = True


class ZrodloModel(BaseModel):
    typ: str                                  # folder | plik | demo
    folder: str | None = None
    plik: str | None = None
    sledz: bool | None = None
    opcje: OpcjeZapisuModel | None = None


class FiltryModel(BaseModel):
    ligi: list[str] = Field(default_factory=list)
    nogi: list[str] = Field(default_factory=list)
    wiek: tuple[int, int] | None = None
    cena: tuple[float | None, float | None] | None = None
    bez_ceny: bool = True
    szukaj: str = ""
    kontrakt_mies: int | None = None
    min_minut: int = 0
    bez_mojego_klubu: bool = False


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

    def wynik_i_filtr(z: RankingModel):
        df = pula(z.pozycja)
        wagi = z.wagi if z.wagi is not None else analiza.wagi_domyslne(z.pozycja, df)
        wagi = {k: v for k, v in wagi.items() if k in df.columns}
        policzona, pominiete = analiza.policz_wynik(df, wagi, z.ignoruj_mnoznik, z.k_baza)
        filtry = analiza.Filtry(**z.filtry.model_dump())
        widoczni = analiza.filtruj(policzona, filtry, data_gry(), stan.migawka()["meta"].get("moj_klub_uid"))
        return policzona, widoczni, pominiete

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
                          opcje=z.opcje.model_dump() if z.opcje else None)
        return stan.migawka()

    @app.post("/api/przeladuj")
    def przeladuj():
        stan.przeladuj(wymus=True)
        return stan.migawka()

    @app.post("/api/wgraj")
    def wgraj_zapis(plik: UploadFile = File(...)):
        if not (plik.filename or "").lower().endswith(".fm"):
            raise HTTPException(400, "To nie jest plik zapisu FM (.fm).")
        katalog = folder_zapisow.folder_kopii() / "wgrane"
        katalog.mkdir(parents=True, exist_ok=True)
        for stary in katalog.glob("*.fm"):
            stary.unlink(missing_ok=True)
        cel = katalog / Path(plik.filename).name
        with open(cel, "wb") as f:
            shutil.copyfileobj(plik.file, f, length=4 * 2**20)
        stan.ustaw_zrodlo("plik", plik=str(cel))
        return stan.migawka()

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
        sciezka = stan._klucz[0] if stan._klucz else None
        if not sciezka:
            raise HTTPException(409, "Brak wczytanego zapisu.")
        mapa = zbuduj_mape_nazw_lig(sciezka, ramki)
        if mapa:
            zapisz_nazwy_rozgrywek(mapa)
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
            "ligi": analiza.kolejnosc_lig(df['Liga'].dropna().unique().tolist()) if 'Liga' in df.columns else [],
            "nogi": sorted(df['Preferowana noga'].dropna().unique().tolist()) if 'Preferowana noga' in df.columns else [],
            "wiek": [int(df['Wiek'].min()), int(df['Wiek'].max())] if 'Wiek' in df.columns else None,
            "cena_max": float(ceny.max()) if not ceny.empty else None,
            "minuty_max": int(df['Minuty'].max()) if 'Minuty' in df.columns and df['Minuty'].notna().any() else None,
            "wagi_domyslne": analiza.wagi_domyslne(pozycja, df),
            "ma_kontrakty": bool(df['Wygasa_Data'].notna().any()),
            "ma_ukryte": 'CA' in df.columns and bool(df['CA'].notna().any()),
        }

    @app.post("/api/ranking")
    def ranking(z: RankingModel):
        policzona, widoczni, pominiete = wynik_i_filtr(z)
        kolumny = analiza.kolumny_tabeli(z.pozycja, policzona, z.pokaz_ukryte)
        return {
            "kolumny": kolumny,
            "wiersze": analiza.do_json(widoczni, analiza.pola_wiersza(z.pozycja, policzona, z.pokaz_ukryte)),
            "liczba": len(widoczni), "liczba_wszystkich": len(policzona),
            "pominiete": pominiete,
            "statystyki": analiza.kolumny_statystyk(z.pozycja, policzona),
        }

    @app.post("/api/radar")
    def radar(z: RadarModel):
        return analiza.radar(z.pozycja, pula(z.pozycja), z.ids)

    @app.post("/api/podobni")
    def podobni(z: PodobniModel):
        policzona, widoczni, _ = wynik_i_filtr(z)
        wynik = analiza.podobni(z.pozycja, policzona, widoczni.index, z.id, z.k_baza, z.n)
        pola = analiza.pola_wiersza(z.pozycja, policzona, z.pokaz_ukryte) + ['Podobieństwo']
        return {"wiersze": analiza.do_json(wynik, pola)}

    # --- frontend ------------------------------------------------------------------------------
    if (KATALOG_STATIC / "index.html").is_file():
        app.mount("/assets", StaticFiles(directory=KATALOG_STATIC / "assets"), name="assets")

        @app.get("/{sciezka:path}", include_in_schema=False)
        def frontend(sciezka: str):
            plik = KATALOG_STATIC / sciezka
            if sciezka and plik.is_file() and KATALOG_STATIC in plik.resolve().parents:
                return FileResponse(plik)
            return FileResponse(KATALOG_STATIC / "index.html")

    return app
