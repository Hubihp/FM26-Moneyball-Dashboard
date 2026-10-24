"""
Trasy: zakladka "Moja taktyka" - 11 miejsc taktyki z zapisu, role IP/OOP i ranking zawodnikow.

Zapis przechowuje pozycje i role jako nienazwane numery bitow, wiec nazwy nadaje uzytkownik
(kalibracja, plik ~/.fm_moneyball/role_taktyki.json):
  pozycje: "3,17" (numery bitow maski miejsca) -> grupa z poradnika (np. "DC")
  role:    "IP|DC|5" (faza, grupa, numer bitu roli) -> nazwa roli
"""
import json

import pandas as pd
from fastapi import APIRouter, HTTPException

from fm_moneyball import role
from fm_moneyball.serwer.modele import KalibracjaModel

ILE_W_RANKINGU = 8
ILE_MOICH = 3          # tylu najlepszych moich zawodnikow zawsze widac pod miejscem


def wczytaj_kalibracje(plik):
    try:
        dane = json.loads(plik.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        dane = {}
    return {"pozycje": dict(dane.get("pozycje") or {}), "role": dict(dane.get("role") or {})}


def zapisz_kalibracje(plik, kalibracja):
    plik.parent.mkdir(parents=True, exist_ok=True)
    plik.write_text(json.dumps(kalibracja, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")


def klucz_pozycji(bity):
    return ",".join(str(b) for b in sorted(bity))


def klucz_roli(faza, grupa, bit):
    return f"{faza}|{grupa}|{bit}"


def opisz_faze(miejsce, faza, kalibracja):
    """Surowe numery fazy miejsca -> {klucz_pozycji, grupa, bit_roli, klucz_roli, rola}."""
    bity = miejsce[f"{faza.lower()}_pozycje"]
    k_poz = klucz_pozycji(bity)
    grupa = kalibracja["pozycje"].get(k_poz)
    bit = miejsce[f"{faza.lower()}_rola"]
    k_roli = klucz_roli(faza, grupa, bit) if grupa and bit is not None else None
    nazwa = kalibracja["role"].get(k_roli) if k_roli else None
    if nazwa and role.znajdz_role(grupa, faza, nazwa) is None:
        nazwa = None
    return {"klucz_pozycji": k_poz, "grupa": grupa, "bit_roli": bit, "klucz_roli": k_roli, "rola": nazwa}


def ranking_miejsca(stan, fazy, moj_klub_uid):
    """Zawodnicy pul pozycji miejsca, uszeregowani wg sredniej dopasowania do rol IP i OOP."""
    grupy = [f["grupa"] for f in fazy.values() if f["grupa"]]
    pule = list(dict.fromkeys(p for g in grupy for p in role.GRUPY[g][1]))
    ramki = [df for df in (stan.pula(p) for p in pule) if df is not None and not df.empty]
    if not ramki:
        return []
    zawodnicy = pd.concat(ramki, ignore_index=True)
    zawodnicy = zawodnicy.drop_duplicates('UID' if 'UID' in zawodnicy.columns else 'ID').reset_index(drop=True)
    if not role.ma_atrybuty(zawodnicy):
        return []
    wyniki = {}
    for faza, f in fazy.items():
        r = role.znajdz_role(f["grupa"], faza, f["rola"]) if f["grupa"] and f["rola"] else None
        if r is not None:
            wyniki[faza] = role.dopasuj(zawodnicy, r)
    if not wyniki:
        return []
    razem = pd.DataFrame(wyniki).mean(axis=1)
    zawodnicy = zawodnicy.assign(_ip=wyniki.get("IP"), _oop=wyniki.get("OOP"), _razem=razem)
    zawodnicy = zawodnicy[zawodnicy['_razem'].notna()].sort_values('_razem', ascending=False)
    moi = zawodnicy['Klub_UID'] == moj_klub_uid if moj_klub_uid is not None else pd.Series(False, index=zawodnicy.index)
    wybrani = pd.concat([zawodnicy.head(ILE_W_RANKINGU), zawodnicy[moi].head(ILE_MOICH)])
    wybrani = wybrani[~wybrani.index.duplicated()].sort_values('_razem', ascending=False)
    return [{
        "id": str(w['ID']), "pilkarz": w['Piłkarz'], "klub": w.get('Klub'), "wiek": _liczba(w.get('Wiek')),
        "pozycja": w.get('Pozycja'), "cena": _liczba(w.get('Wartość_Numeryczna')),
        "ip": _liczba(w['_ip']), "oop": _liczba(w['_oop']), "razem": round(float(w['_razem']), 1),
        "moj": bool(moj_klub_uid is not None and w.get('Klub_UID') == moj_klub_uid),
    } for _, w in wybrani.iterrows()]


def _liczba(x):
    return None if x is None or pd.isna(x) else float(x)


def utworz(stan):
    router = APIRouter(prefix="/api")

    @router.get("/taktyka")
    def taktyka(indeks: int | None = None):
        moj = stan.migawka()["meta"].get("moj_klub_uid")
        taktyki = [t for t in stan.taktyki if t.get("klub_uid") == moj]
        kalibracja = wczytaj_kalibracje(stan.plik_kalibracji)
        wynik = {"taktyki": [{"indeks": t["indeks"], "nazwa": t["nazwa"], "mentalnosc": t.get("mentalnosc")}
                             for t in taktyki],
                 "grupy": role.katalog_grup(), "wybrana": None, "miejsca": []}
        if not taktyki:
            return wynik
        t = next((t for t in taktyki if t["indeks"] == indeks), taktyki[0])
        wynik["wybrana"] = t["indeks"]
        for m in sorted(t["miejsca"], key=lambda m: m["nr"]):
            fazy = {faza: opisz_faze(m, faza, kalibracja) for faza in role.FAZY}
            wynik["miejsca"].append({"nr": m["nr"], **fazy, "zawodnicy": ranking_miejsca(stan, fazy, moj)})
        return wynik

    @router.put("/taktyka/kalibracja")
    def kalibruj(z: KalibracjaModel):
        kalibracja = wczytaj_kalibracje(stan.plik_kalibracji)
        if z.rodzaj == "pozycja":
            if z.wartosc is not None and z.wartosc not in role.GRUPY:
                raise HTTPException(400, "Nieznana grupa pozycji.")
            slownik = kalibracja["pozycje"]
        elif z.rodzaj == "rola":
            faza, grupa, _ = (z.klucz.split("|") + ["", "", ""])[:3]
            if z.wartosc is not None and role.znajdz_role(grupa, faza, z.wartosc) is None:
                raise HTTPException(400, "Nieznana rola dla tej pozycji.")
            slownik = kalibracja["role"]
        else:
            raise HTTPException(400, "Nieznany rodzaj kalibracji.")
        if z.wartosc:
            slownik[z.klucz] = z.wartosc
        else:
            slownik.pop(z.klucz, None)
        zapisz_kalibracje(stan.plik_kalibracji, kalibracja)
        return kalibracja

    return router
