"""
API (FastAPI) dla interfejsu React. Serwuje tez zbudowany frontend z katalogu `static/`.

Uruchomienie: `python -m fm_moneyball` (patrz fm_moneyball/__main__.py).
Trasy sa w module `trasy/`, modele zapytan w `modele.py`, liczenie wyniku w `obliczenia.py`.
"""
from pathlib import Path

from fastapi import FastAPI

from fm_moneyball.serwer.obliczenia import Obliczenia
from fm_moneyball.serwer.trasy import analiza, frontend, ligi, zrodlo

KATALOG_STATIC = Path(__file__).resolve().parent / "static"


def utworz_aplikacje(stan):
    app = FastAPI(title="FM26 Moneyball", docs_url="/api/docs", openapi_url="/api/openapi.json")
    app.state.stan = stan
    obl = Obliczenia(stan)
    app.include_router(zrodlo.utworz(stan))
    app.include_router(ligi.utworz(stan))
    app.include_router(analiza.utworz(stan, obl))
    # na koncu: trasa interfejsu przechwytuje kazda inna sciezke
    frontend.podlacz(app, KATALOG_STATIC)
    return app
