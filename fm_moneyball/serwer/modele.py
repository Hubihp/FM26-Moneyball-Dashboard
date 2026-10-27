"""Modele zapytan API (Pydantic)."""
from pydantic import BaseModel, Field

from fm_moneyball.zrodla.zapis_fm import KURS_DOMYSLNY


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
    kandydaci: bool = False
    min_score_kandydata: float = 60
    min_niedowartosciowanie: float | None = None
    tylko_z_okazja: bool = False
    kandydaci_z: list[str] = Field(default_factory=list)


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
