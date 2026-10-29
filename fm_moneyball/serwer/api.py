"""
API (FastAPI) dla interfejsu React. Serwuje tez zbudowany frontend z katalogu `static/`.

Uruchomienie: `python -m fm_moneyball` (patrz fm_moneyball/__main__.py).
Trasy sa w module `trasy/`, modele zapytan w `modele.py`, liczenie wyniku w `obliczenia.py`.
"""
from pathlib import Path

from fastapi import FastAPI

from fm_moneyball.serwer.obliczenia import Obliczenia
from fm_moneyball.aktualizacje import Aktualizacje
from fm_moneyball.pamiec import Pamiec
from fm_moneyball.serwer.trasy import analiza, frontend, ligi, system, zrodlo

KATALOG_STATIC = Path(__file__).resolve().parent / "static"


def utworz_aplikacje(stan, pamiec=None, aktualizacje=None, okno=None):
    """okno: {"okno": bool, "port": int}; aktualizacje: obiekt Aktualizacje (domyslnie bez sprawdzania)."""
    app = FastAPI(title="FM27 Dashboard", docs_url="/api/docs", openapi_url="/api/openapi.json")
    app.state.stan = stan
    obl = Obliczenia(stan)
    app.include_router(zrodlo.utworz(stan))
    app.include_router(ligi.utworz(stan))
    app.include_router(analiza.utworz(stan, obl))
    app.state.aktualizacje = aktualizacje or Aktualizacje()
    app.include_router(system.utworz(pamiec or Pamiec(), app.state.aktualizacje, okno))
    # na koncu: trasa interfejsu przechwytuje kazda inna sciezke
    frontend.podlacz(app, KATALOG_STATIC)
    return app
