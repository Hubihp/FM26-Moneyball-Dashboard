"""Trasy: stan aplikacji, zrodlo danych (folder, plik, demo), moj klub i zdarzenia (SSE)."""
import asyncio
import json
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from fm_moneyball.serwer.modele import MojKlubModel, ZrodloModel
from fm_moneyball.zrodla import folder as folder_zapisow


def utworz(stan):
    router = APIRouter(prefix="/api")

    @router.get("/stan")
    def pobierz_stan():
        return stan.migawka()

    @router.get("/zapisy")
    def lista_zapisow(folder: str | None = None):
        domyslny = folder_zapisow.domyslny_folder()
        folder = folder or stan.konfig.folder or (str(domyslny) if domyslny else None)
        pliki = folder_zapisow.lista_zapisow(folder) if folder else []
        return {"folder": folder, "domyslny": str(domyslny) if domyslny else None,
                "kandydaci": [str(k) for k in folder_zapisow.kandydaci_folderow()],
                "pliki": [{"nazwa": p.nazwa, "sciezka": str(p.sciezka), "rozmiar_mb": round(p.rozmiar / 2**20, 1),
                           "zmieniony": p.mtime} for p in pliki]}

    @router.post("/zrodlo")
    def ustaw_zrodlo(z: ZrodloModel):
        if z.typ not in ("folder", "plik", "demo"):
            raise HTTPException(400, "Nieznany typ źródła.")
        stan.ustaw_zrodlo(z.typ, folder=z.folder, plik=z.plik, sledz=z.sledz,
                          wczytaj_przy_starcie=z.wczytaj_przy_starcie,
                          opcje=z.opcje.model_dump() if z.opcje else None)
        return stan.migawka()

    @router.post("/przeladuj")
    def przeladuj():
        stan.przeladuj(wymus=True)
        return stan.migawka()

    @router.post("/wgraj")
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

    @router.post("/moj-klub")
    def ustaw_moj_klub(z: MojKlubModel):
        stan.ustaw_moj_klub(z.uid)
        return stan.migawka()

    @router.get("/zdarzenia")
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

    return router
