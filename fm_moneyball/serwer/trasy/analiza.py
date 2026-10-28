"""Trasy: analiza pozycji - meta pozycji, ranking, radar, podobni, moja kadra, lista zyczen."""
import pandas as pd
from fastapi import APIRouter, HTTPException

import time

from fm_moneyball import analiza, historia, optymalizator, profil
from fm_moneyball.serwer.modele import HistoriaModel, HistoriaWieluModel, NastepcaModel, PorownanieZMoimModel, KadraModel, ListaZyczenModel, OptymalizatorModel, PodobniModel, RadarModel, RankingModel, SprzedajDrogoModel
from fm_moneyball.serwer.obliczenia import kandydat
from fm_moneyball.stale import POZYCJE


def utworz(stan, obl):
    router = APIRouter(prefix="/api")

    @router.get("/pozycja/{pozycja}")
    def meta_pozycji(pozycja: str):
        df = obl.pula(pozycja)
        ceny = df['Wartość_Numeryczna'].dropna()
        porownanie = historia.migawka_porownania(historia.migawki(stan.katalog_kariery()), obl.data_gry())
        return {
            "pozycja": pozycja, "liczba": len(df),
            "nogi": sorted(df['Preferowana noga'].dropna().unique().tolist()) if 'Preferowana noga' in df.columns else [],
            "wiek": [int(df['Wiek'].min()), int(df['Wiek'].max())] if 'Wiek' in df.columns else None,
            "cena_max": float(ceny.max()) if not ceny.empty else None,
            "pensja_max": (float(df['Zarobki_Numeryczne'].max() / analiza.TYGODNI_W_ROKU)
                           if 'Zarobki_Numeryczne' in df.columns and df['Zarobki_Numeryczne'].notna().any() else None),
            "minuty_max": int(df['Minuty'].max()) if 'Minuty' in df.columns and df['Minuty'].notna().any() else None,
            "wagi_domyslne": analiza.wagi_domyslne(pozycja, df),
            "ma_kontrakty": bool(df['Wygasa_Data'].notna().any()),
            "okazje": list(analiza.OKAZJE),
            # historia rozwoju: migawki poprzednich wczytan tej kariery
            "ma_historie": porownanie is not None,
            "data_porownania": porownanie[1].isoformat() if porownanie is not None else None,
            "min_minut_rozwoju": historia.MIN_MINUT,
        }

    @router.post("/ranking")
    def ranking(z: RankingModel):
        policzona, widoczni, pominiete, model_wyceny, ukryci_moi = obl.wynik_i_filtr(z)
        kolumny = analiza.kolumny_tabeli(z.pozycja, policzona)
        return {
            "pozycja": z.pozycja,
            "kolumny": kolumny,
            "wiersze": analiza.do_json(widoczni, analiza.pola_wiersza(z.pozycja, policzona)),
            # liczby zawodnikow pozycji; kandydaci z innych pozycji osobno
            "liczba": int((~kandydat(widoczni)).sum()), "liczba_wszystkich": int((~kandydat(policzona)).sum()),
            "liczba_kandydatow": int(kandydat(widoczni).sum()),
            "pominiete": pominiete,
            "statystyki": analiza.kolumny_statystyk(z.pozycja, policzona),
            "model_wyceny": model_wyceny,
            "liczba_ukrytych_mojego_klubu": int(ukryci_moi),
        }

    @router.post("/historia")
    def historia_zawodnika(z: HistoriaModel):
        wszyscy = stan.wszyscy_zawodnicy()
        wiersz = wszyscy[wszyscy['ID'] == z.id] if wszyscy is not None else None
        if wiersz is None or wiersz.empty or 'UID' not in wiersz.columns:
            return {"punkty": [], "statystyki": [], "min_minut": historia.MIN_MINUT}
        w = wiersz.iloc[0]
        if pd.isna(w['UID']):
            return {"punkty": [], "statystyki": [], "min_minut": historia.MIN_MINUT}
        return obl.historia_zawodnika(z.pozycja, int(w['UID']), w['Piłkarz'], z.wagi, z.ignoruj_mnoznik, z.k_baza)

    @router.post("/historia-wielu")
    def historia_wielu(z: HistoriaWieluModel):
        """Historia kilku zawodnikow (zakladka Porownanie) w skali jednej pozycji."""
        wszyscy = stan.wszyscy_zawodnicy()
        wynik = []
        for id_ in z.ids:
            wiersz = wszyscy[wszyscy['ID'] == id_] if wszyscy is not None and 'UID' in wszyscy.columns else None
            if wiersz is None or wiersz.empty or pd.isna(wiersz.iloc[0]['UID']):
                wynik.append({"id": id_, "pilkarz": None, "punkty": [], "brak": [], "delta": None})
                continue
            w = wiersz.iloc[0]
            h = obl.historia_zawodnika(z.pozycja, int(w['UID']), w['Piłkarz'], z.wagi, z.ignoruj_mnoznik, z.k_baza)
            wynik.append({"id": id_, "pilkarz": w['Piłkarz'], **h})
        return {"zawodnicy": wynik, "min_minut": historia.MIN_MINUT}

    @router.post("/nastepca")
    def nastepca(z: NastepcaModel):
        """
        Zawodnicy o najbardziej podobnym stylu gry (podobienstwo cosinusowe wektorow z-score statystyk
        pozycji, wazonych minutami i skurczonych przy malej probie) - takze z innych pozycji, po filtrach
        pozycji z panelu, zawsze bez mojego klubu.
        """
        policzona, _, _ = obl.policz(z.pozycja, z.wagi, z.ignoruj_mnoznik, z.k_baza, kandydaci=True)
        if not (policzona['ID'] == z.id).any():
            raise HTTPException(404, "Nie znaleziono zawodnika.")
        filtry = analiza.Filtry(**{**z.filtry.model_dump(), "bez_mojego_klubu": True, "min_score_kandydata": 0.0})
        moj_klub = stan.migawka()["meta"].get("moj_klub_uid")
        widoczni = analiza.filtruj(policzona, filtry, obl.data_gry(), moj_klub)
        wynik = analiza.podobni(z.pozycja, policzona, widoczni.index, z.id, z.k_baza, z.n)
        wynik = wynik.assign(Podobieństwo=(wynik['Podobieństwo'].clip(lower=0) * 100).round(1))
        kolumny = analiza.kolumny_tabeli(z.pozycja, policzona)
        kolumny.insert(1, {'naglowek': 'Podobieństwo', 'pole': 'Podobieństwo', 'format': 'pasek',
                           'statystyka': False, 'nizsze_lepsze': False, 'sortuj': True})
        if 'Kandydat z pozycji' not in [k['pole'] for k in kolumny]:
            kolumny.insert(3, analiza._opis_kolumny('Kandydat z pozycji'))
        return {"kolumny": kolumny, "liczba_po_filtrach": int(len(widoczni)),
                "wiersze": analiza.do_json(wynik, analiza.pola_wiersza(z.pozycja, policzona)
                                           + ['Podobieństwo', 'Kandydat z pozycji'])}

    @router.post("/porownanie-z-moim")
    def porownanie_z_moim(z: PorownanieZMoimModel):
        """Kandydat na tle najlepszego zawodnika mojego klubu (z biezacego zapisu) na tej pozycji."""
        # pula z kandydatami: zawodnik spoza pozycji tez ma SCORE w jej skali
        policzona, _, _ = obl.policz(z.pozycja, z.wagi, z.ignoruj_mnoznik, z.k_baza, kandydaci=True)
        wiersz = policzona[policzona['ID'] == z.id]
        if wiersz.empty:
            raise HTTPException(404, "Nie znaleziono zawodnika.")
        nominalni = policzona[~policzona['Kandydat'].fillna(False).astype(bool)] \
            if 'Kandydat' in policzona.columns else policzona
        return analiza.porownaj_z_moim(z.pozycja, nominalni, wiersz.iloc[0], stan.migawka()["meta"].get("moj_klub_uid"))

    @router.post("/radar")
    def radar(z: RadarModel):
        return analiza.radar(z.pozycja, obl.pula(z.pozycja), z.ids, stan.wszyscy_zawodnicy() if z.kandydaci else None)

    @router.post("/podobni")
    def podobni(z: PodobniModel):
        policzona, widoczni, *_ = obl.wynik_i_filtr(z)
        wynik = analiza.podobni(z.pozycja, policzona, widoczni.index, z.id, z.k_baza, z.n)
        pola = analiza.pola_wiersza(z.pozycja, policzona) + ['Podobieństwo']
        return {"wiersze": analiza.do_json(wynik, pola)}

    @router.post("/moja-kadra")
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
            policzona, _, _ = obl.policz(pozycja, z.wagi.get(pozycja), z.ignoruj_mnoznik, z.k_baza)
            wynik.append(analiza.moja_kadra(pozycja, policzona, uid, obl.data_gry()))
        # w kolejnosci POZYCJE: od bramkarza do napastnika (sortowanie po luce robi interfejs)
        return {"klub": meta.get("moj_klub"), "pozycje": wynik}

    def _moj_klub():
        uid = stan.migawka()["meta"].get("moj_klub_uid")
        if uid is None:
            raise HTTPException(409, "Nie wiem, którym klubem grasz - wczytaj zapis kariery.")
        return uid

    def _pula_z_filtrami(pozycja, z, uid):
        policzona, _, _ = obl.policz(pozycja, z.wagi.get(pozycja), z.ignoruj_mnoznik, z.k_baza)
        filtry = analiza.Filtry(**{**z.filtry.model_dump(), "bez_mojego_klubu": True, "kandydaci": False})
        return policzona, analiza.filtruj(policzona, filtry, obl.data_gry(), uid).index

    @router.post("/sprzedaj-drogo")
    def sprzedaj_drogo(z: SprzedajDrogoModel):
        uid = _moj_klub()
        wynik = []
        for pozycja in POZYCJE:
            df = stan.pula(pozycja)
            if df is None or df.empty:
                continue
            policzona, widoczni = _pula_z_filtrami(pozycja, z, uid)
            wynik += analiza.sprzedaj_drogo(pozycja, policzona, widoczni, uid, z.k_baza)
        return {"wymiany": sorted(wynik, key=lambda w: -w["zysk"]), "prog": analiza.PROG_PRZEPLACENIA,
                "tolerancja": analiza.PROG_WZMOCNIENIA}

    @router.post("/optymalizator")
    def optymalizuj(z: OptymalizatorModel):
        uid = _moj_klub()
        start = time.perf_counter()
        kandydaci, pule, bazy = {}, {}, {}
        for pozycja in z.pozycje:
            if pozycja not in POZYCJE or stan.pula(pozycja) is None:
                continue
            policzona, widoczni = _pula_z_filtrami(pozycja, z, uid)
            baza, zastepczy, lista = analiza.kandydaci_optymalizatora(policzona, widoczni, uid)
            kandydaci[pozycja], pule[pozycja], bazy[pozycja] = lista, policzona, (baza, zastepczy)
        wybor, zysk, pewne = optymalizator.optymalizuj(kandydaci, z.budzet, z.budzet_plac)
        gwiazda = optymalizator.jedna_gwiazda(kandydaci, z.budzet, z.budzet_plac)
        pola = ['ID', 'Piłkarz', 'Klub', 'Klub_UID', 'Liga', 'Wiek', 'SCORE', 'Minuty', 'Wartość_Numeryczna',
                'Zarobki_Numeryczne', 'Wygasa_Data', 'Lata_kontraktu', 'Wolny_agent', 'U21', 'UID', 'Pozycja']

        def opis(pozycja, k):
            pula = pule[pozycja]
            wiersz = analiza.do_json(pula.loc[[k.dane["idx"]]], [p for p in pola if p in pula.columns])[0]
            return {"pozycja": pozycja, "zawodnik": wiersz, "zysk": k.zysk, "cena": k.cena, "pensja": k.pensja,
                    "moj_score": bazy[pozycja][0], "poziom_zastepczy": bazy[pozycja][1]}

        zestaw = [opis(p, wybor[p]) for p in z.pozycje if p in wybor]
        wydane, pensje = sum(k.cena for k in wybor.values()), sum(k.pensja for k in wybor.values())
        return {
            "zestaw": zestaw, "zysk": zysk, "wydane": wydane, "pensje": pensje,
            "zostalo": z.budzet - wydane, "zostalo_plac": z.budzet_plac - pensje,
            "pozycje_bez_wzmocnienia": [p for p in z.pozycje if p in kandydaci and p not in wybor],
            "jedna_gwiazda": opis(*gwiazda) if gwiazda else None,
            "liczba_kandydatow": sum(len(v) for v in kandydaci.values()),
            "optimum_pewne": pewne, "czas_ms": round((time.perf_counter() - start) * 1000),
            "bazy": {p: {"score": b[0], "poziom_zastepczy": b[1]} for p, b in bazy.items()},
        }

    @router.post("/profil-druzyny")
    def profil_druzyny(z: KadraModel):
        """Moja druzyna na tle ligi: statystyki zespolowe, atletyzm skladu, zmiany wzgledem poprzedniego sezonu."""
        uid = _moj_klub()
        wszyscy = stan.wszyscy_zawodnicy()
        if wszyscy is None or 'Klub_UID' not in wszyscy.columns:
            raise HTTPException(409, "Brak danych zawodników.")
        tabela = stan.tabele.get(uid)
        moi = wszyscy[wszyscy['Klub_UID'] == uid]
        liga = moi['Liga'].mode().iloc[0] if not moi.empty and moi['Liga'].notna().any() else None
        if tabela:
            kluby = [w["club_uid"] for w in tabela["wiersze"]]
        else:
            kluby = wszyscy.loc[wszyscy['Liga'] == liga, 'Klub_UID'].dropna().unique().tolist()
        z_zapisu = bool(stan.druzyny)
        druzyny = stan.druzyny if z_zapisu else profil.druzyny_z_zawodnikow(wszyscy[wszyscy['Klub_UID'].isin(kluby)])
        tabela_profilu = profil.tabela_profilu(druzyny, kluby, tabela)
        sekcje = profil.porownanie(tabela_profilu, uid)
        mecze = int(tabela_profilu.at[uid, 'Mecze']) if uid in tabela_profilu.index else None
        nazwy = {w["club_uid"]: w["klub"] for w in tabela["wiersze"]} if tabela else None
        mecze_ligi = int(tabela_profilu['Mecze'].max()) if not tabela_profilu.empty else None
        sklady = {k: d.get("sklad") for k, d in druzyny.items() if d.get("sklad")} if z_zapisu else None
        atletyzm = profil.atletyzm(wszyscy, kluby, uid, nazwy, mecze_ligi, sklady)

        # zmiany wzgledem poprzedniego sezonu: Δ SCORE z historii (w pulach) i Δ sredniej oceny z migawki
        rozwoj = []
        for pozycja in POZYCJE:
            if stan.pula(pozycja) is None:
                continue
            policzona, _, _ = obl.policz(pozycja, z.wagi.get(pozycja), z.ignoruj_mnoznik, z.k_baza)
            if 'Δ SCORE' not in policzona.columns:
                continue
            glowna = policzona['Pula_główna'] == pozycja if 'Pula_główna' in policzona.columns else True
            for _, r in policzona[(policzona['Klub_UID'] == uid) & glowna].iterrows():
                rozwoj.append({"Piłkarz": r['Piłkarz'], "ID": r['ID'], "pozycja": pozycja, "SCORE": float(r['SCORE']),
                               "Δ SCORE": None if pd.isna(r['Δ SCORE']) else float(r['Δ SCORE'])})
        porownanie = historia.migawka_porownania(historia.migawki(stan.katalog_kariery()), obl.data_gry())
        oceny_teraz, oceny_wtedy = {}, {}
        if porownanie is not None and 'UID' in moi.columns and 'Średnia ocena' in moi.columns:
            oceny_teraz = {r['UID']: (r['Średnia ocena'], r['Minuty']) for _, r in moi.iterrows()}
            wtedy = historia.wczytaj(porownanie[0])
            if 'Średnia ocena' in wtedy.columns:
                oceny_wtedy = {r['UID']: (r['Średnia ocena'], r['Minuty'])
                               for _, r in wtedy[wtedy['UID'].isin(list(oceny_teraz))].iterrows()}
        zmiany = profil.zmiany_zawodnikow(rozwoj, oceny_teraz, oceny_wtedy, historia.MIN_MINUT)
        imiona = dict(zip(moi['UID'], moi['Piłkarz'])) if 'UID' in moi.columns else {}
        for m in zmiany["oceny_spadki"] + zmiany["oceny_wzrosty"]:
            m["Piłkarz"] = imiona.get(m.pop("uid"))

        wiersz_tabeli = next((w for w in tabela["wiersze"] if w["club_uid"] == uid), None) if tabela else None
        return {
            "klub": stan.migawka()["meta"].get("moj_klub"), "liga": liga, "kluby": len(tabela_profilu),
            "mecze": mecze, "tabela": wiersz_tabeli, "z_zapisu": z_zapisu,
            "sekcje": [{"nazwa": n, "metryki": sekcje[n]} for n in ("Wyniki", "Z piłką", "Bez piłki", "Fizycznie")
                       if n in sekcje],
            "podsumowanie": profil.podsumowanie(sekcje, mecze),
            "atletyzm": atletyzm,
            "zmiany": {**zmiany, "historia": porownanie is not None,
                       "data_porownania": porownanie[1].isoformat() if porownanie is not None else None,
                       "min_minut": historia.MIN_MINUT},
        }

    @router.post("/lista-zyczen")
    def lista_zyczen(z: ListaZyczenModel):
        """
        Zawodnik jest szukany niezaleznie od pozycji, z ktorej go dodano: najpierw w puli tej pozycji,
        potem w tej samej puli z kandydatami z innych pozycji (tak byl widoczny przy dodawaniu),
        a na koncu w swojej glownej pozycji (np. wpis z nazwa pozycji sprzed zmiany ich podzialu).
        """
        policzone = {}

        def pula_policzona(pozycja, kandydaci):
            if (pozycja, kandydaci) not in policzone:
                df = stan.pula(pozycja) if pozycja in POZYCJE else None
                policzone[(pozycja, kandydaci)] = None if df is None or df.empty else obl.policz(
                    pozycja, z.wagi.get(pozycja), z.ignoruj_mnoznik, z.k_baza, kandydaci)[0]
            return policzone[(pozycja, kandydaci)]

        wszyscy = None
        znalezieni, brak = [], []
        for w in z.wpisy:
            proby = [(w.pozycja, False), (w.pozycja, True)]
            if wszyscy is None:
                wszyscy = stan.wszyscy_zawodnicy()
            if wszyscy is not None:
                gdzie = analiza.znajdz_zawodnika(wszyscy, w.klucz, w.pilkarz)
                if not gdzie.empty:
                    glowna = gdzie.iloc[0].get('Pula_główna')
                    glowna = glowna if isinstance(glowna, str) else gdzie.iloc[0].get('Pula')
                    proby.append((glowna, False))
            for pozycja, kandydaci in proby:
                policzona = pula_policzona(pozycja, kandydaci)
                wiersz = analiza.znajdz_zawodnika(policzona, w.klucz, w.pilkarz) if policzona is not None else None
                if wiersz is not None and not wiersz.empty:
                    znalezieni.append(wiersz.assign(**{'Pozycja na liście': pozycja}))
                    break
            else:
                brak.append(w.klucz)
        ramka = pd.concat(znalezieni, ignore_index=True) if znalezieni else pd.DataFrame()
        # kolumny jak w Rankingu pozycji wybranej na boisku (te same, ta sama kolejnosc i format)
        biezaca = pula_policzona(z.pozycja, False) if z.pozycja else None
        if biezaca is not None and not ramka.empty:
            kolumny = analiza.kolumny_tabeli(z.pozycja, biezaca)
            kolumny.insert(next((i + 1 for i, k in enumerate(kolumny) if k['pole'] == 'Piłkarz'), 1),
                           analiza._opis_kolumny('Pozycja na liście'))
            pola = analiza.pola_wiersza(z.pozycja, biezaca)
        else:
            kolumny, pola = analiza.kolumny_listy(ramka), analiza.POLA_WIERSZA
        return {"kolumny": kolumny,
                "wiersze": analiza.do_json(ramka, pola + ['Pozycja na liście']),
                "nieznalezieni": brak}

    return router
