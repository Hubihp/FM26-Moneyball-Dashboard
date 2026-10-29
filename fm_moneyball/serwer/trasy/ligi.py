"""Trasy: nazwy i mnozniki lig, nazwy krajow (narodowosci), nauka nazw lig z eksportu CSV."""
from fastapi import APIRouter, File, HTTPException, UploadFile

from fm_moneyball.kraje import podsumuj_kraje, zapisz_nazwe_kraju
from fm_moneyball.ligi import wszystkie_mnozniki, zapisz_mnoznik
from fm_moneyball.schemat import REZERWY
from fm_moneyball.serwer.modele import KrajModel, LigaModel
from fm_moneyball.stale import MNOZNIK_NIEZNANEJ_LIGI, MNOZNIKI_LIG
from fm_moneyball.zrodla.csv_fm import wczytaj_csv
from fm_moneyball.zrodla.zapis_fm import zapisz_nazwy_rozgrywek, zbuduj_mape_nazw_lig


def utworz(stan):
    router = APIRouter(prefix="/api")

    @router.get("/ligi")
    def ligi():
        mnozniki = wszystkie_mnozniki(stan.plik_mnoznikow)
        wynik = []
        for liga in stan.ligi:
            nazwa = liga.get("nazwa")
            wynik.append({**liga, "mnoznik": mnozniki.get(nazwa) if nazwa else None})
        return {"ligi": sorted(wynik, key=lambda l: (l["nazwa"] is not None, -l["liczba"])),
                "znane_nazwy": sorted(set(MNOZNIKI_LIG) | set(mnozniki)),
                "mnozniki": mnozniki,
                "mnoznik_nieznanej": MNOZNIK_NIEZNANEJ_LIGI,
                # minuty w rezerwach, druzynach mlodziezowych i ligach niewykrytych (mnoznik wazony minutami)
                "mnoznik_rezerw": mnozniki.get(REZERWY), "nazwa_rezerw": REZERWY}

    @router.put("/ligi/{klucz}")
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

    @router.put("/mnoznik-rezerw")
    def zmien_mnoznik_rezerw(z: LigaModel):
        zapisz_mnoznik(REZERWY, z.mnoznik, stan.plik_mnoznikow)     # None = wartosc domyslna (liga nieznana)
        stan.zastosuj_ligi()
        return ligi()

    @router.get("/kraje")
    def kraje():
        return {"kraje": podsumuj_kraje(stan.wszyscy_zawodnicy(), stan.nazwy_krajow, stan.zrodla_krajow)}

    @router.put("/kraje/{kraj_id}")
    def zmien_kraj(kraj_id: int, z: KrajModel):
        zapisz_nazwe_kraju(kraj_id, (z.nazwa or "").strip(), stan.plik_krajow)
        stan.zastosuj_ligi()
        return kraje()

    @router.post("/nazwy-lig")
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

    return router
