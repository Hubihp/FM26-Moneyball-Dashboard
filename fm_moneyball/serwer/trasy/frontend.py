"""Serwowanie zbudowanego frontendu (katalog static/) z odpowiednimi naglowkami cache."""
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles


class ZasobyZCache(StaticFiles):
    """Pliki zbudowanego frontendu (nazwy z hashem) - przegladarka moze je trzymac na stale."""

    async def get_response(self, path, scope):
        odpowiedz = await super().get_response(path, scope)
        if odpowiedz.status_code == 200:
            odpowiedz.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        return odpowiedz


def podlacz(app, katalog):
    """Pliki z katalogu albo index.html (trasy interfejsu). Dolaczane na koncu - lapie kazda sciezke."""
    if not (katalog / "index.html").is_file():
        return
    app.mount("/assets", ZasobyZCache(directory=katalog / "assets"), name="assets")

    @app.get("/{sciezka:path}", include_in_schema=False)
    def frontend(sciezka: str):
        plik = katalog / sciezka
        if sciezka and plik.is_file() and katalog in plik.resolve().parents:
            return FileResponse(plik)
        # bez cache: po aktualizacji aplikacji przegladarka musi pobrac nowy interfejs
        # (pliki w assets/ maja hash w nazwie, wiec moga byc trzymane dlugo)
        return FileResponse(katalog / "index.html", headers={"Cache-Control": "no-cache"})
