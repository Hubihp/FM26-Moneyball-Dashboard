"""Trasy: wersja programu, aktualizacje i pamiec interfejsu (lista zyczen, filtry, uklad tabel)."""
import logging
import time
import webbrowser

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

ADRES_PRZENIESIENIA = "http://localhost:{port}/?przenies=1"
log = logging.getLogger("fm_moneyball")


class ZmianyPamieci(BaseModel):
    zmiany: dict[str, str | None]


def utworz(pamiec, aktualizacje, okno=None):
    """okno: {"okno": bool, "port": int} - czy program dziala we wlasnym oknie."""
    okno = okno or {"okno": False, "port": 8765}
    router = APIRouter(prefix="/api")

    @router.get("/system")
    def system():
        return {**aktualizacje.stan(), "okno": okno["okno"]}

    @router.post("/aktualizacja/sprawdz")
    def sprawdz():
        aktualizacje.sprawdz()
        return aktualizacje.stan()

    @router.post("/aktualizacja/instaluj")
    def instaluj():
        if not aktualizacje.instaluj():
            raise HTTPException(409, "Aktualizacji nie można zainstalować z programu - pobierz ją ze strony wydania.")
        return aktualizacje.stan()

    @router.get("/pamiec")
    def pobierz_pamiec():
        return pamiec.wszystko()

    @router.put("/pamiec")
    def zapisz_pamiec(z: ZmianyPamieci):
        return {"liczba": pamiec.ustaw(z.zmiany)}

    @router.post("/system/gotowe")
    def gotowe():
        """Interfejs wczytany - zapis czasu startu do dziennika (raz na uruchomienie)."""
        if "start" in okno and not okno.get("zmierzono"):
            okno["zmierzono"] = True
            from fm_moneyball.okno import ETAPY
            etapy = ", ".join(f"{k} {v:.1f} s" for k, v in ETAPY.items())
            log.info("Czas startu: %.1f s do gotowego interfejsu (%s)", time.time() - okno["start"], etapy or "bez okna")
        return {"ok": True}

    @router.post("/przenies-z-przegladarki")
    def przenies():
        # otwiera aplikacje w domyslnej przegladarce, ktora wysle swoje dane (localStorage) na serwer
        webbrowser.open(ADRES_PRZENIESIENIA.format(port=okno["port"]))
        return {"ok": True}

    return router
