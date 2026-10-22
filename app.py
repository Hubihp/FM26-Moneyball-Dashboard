"""
FM26 Moneyball Dashboard - wersja 3 (interfejs Streamlit; logika w pakiecie fm_moneyball).

Najwazniejsze zmiany wzgledem wersji 2:
  1. Zrodla danych: folder zapisow gry (automatycznie najnowszy zapis, sledzenie zmian),
     wgrany plik zapisu kariery .fm, pliki CSV z gry (jak dotad) albo dane demo.
     Jeden zapis .fm daje od razu wszystkie pozycje - bez eksportow i przypisywania plikow.
  2. Poprawki modelu: korekta ligowa addytywna zamiast mnozenia T-score, najnizszy mnoznik dla
     lig spoza tabeli (zamiast 1.0), statystyki puli wazone minutami, mocniejsze skurczenie cech
     ilorazowych, sobowtor na skurczonych z-score'ach, cechy stylu poza radarem.
  3. Poprawki danych i UI: widelki cen z dowolnym myslnikiem, place miesieczne, '1.234' w minutach,
     komunikaty bledow nie znikaja, odpornosc na brakujace kolumny, data w grze z zapisu,
     limit wierszy w tabeli, filtry bez ostrzezen Session State.

Uruchomienie: streamlit run app.py  (Python >= 3.12, zaleznosci w requirements.txt)
"""
import hashlib
from datetime import datetime
from pathlib import Path

import altair as alt
import matplotlib.colors as mcolors
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from fm_moneyball.model import macierz_stylu, oblicz_score, percentyl_w_puli
from fm_moneyball.schemat import raport_wczytania
from fm_moneyball.stale import (KOLUMNY_PER_POZYCJA, KOLUMNY_UKRYTE, MAPOWANIE_NAZW_LIG, MERYTORYKA_WAG,
                                NEUTRALNE, NIE_STATYSTYKI, NIZSZE_LEPSZE, POZYCJE)
from fm_moneyball.zrodla import folder as folder_zapisow
from fm_moneyball.zrodla.csv_fm import generuj_demo_csv, wczytaj_csv, wykryj_pozycje
from fm_moneyball.zrodla.zapis_fm import (KURS_DOMYSLNY, PLIK_NAZW_ROZGRYWEK, OpcjeZapisu, wczytaj_zapis,
                                          zapisz_nazwy_rozgrywek, zbuduj_mape_nazw_lig)

# Konfiguracja strony
st.set_page_config(
    page_title="FM26 Moneyball Dashboard",
    page_icon="⚽",
    layout="wide"
)

# Usuwanie ikon hiperłączy, poprawa odstępów w sidebarze oraz modyfikacja uploada
st.markdown("""
    <style>
    a.header-anchor {
        display: none !important;
    }

    /* --- ZMNIEJSZENIE ODSTĘPÓW W SIDEBARZE --- */
    [data-testid="stSidebar"] hr {
        margin-top: 0.5rem !important;
        margin-bottom: 1.5rem !important;
    }
    [data-testid="stSidebar"] h3 {
        padding-top: 0.5rem !important;
        padding-bottom: 1rem !important;
    }

    /* --- UPLOAD WIDGET: PRZYCISK PO LEWEJ, TEKST PO PRAWEJ --- */
    [data-testid="stFileUploaderDropzone"] {
        display: flex !important;
        flex-direction: row !important;
        align-items: center !important;
        justify-content: flex-start !important;
        padding: 10px 15px !important;
        min-height: auto !important;
    }
    [data-testid="stFileUploaderDropzone"] button {
        order: -1 !important;
        margin-right: 15px !important;
        margin-top: 0 !important;
    }
    [data-testid="stFileUploaderDropzoneInstructions"] {
        display: flex !important;
        align-items: center !important;
        margin: 0 !important;
    }
    [data-testid="stFileUploaderDropzone"] svg {
        display: none !important;
    }
    [data-testid="stFileUploaderDropzoneInstructions"] > div > span {
        display: none !important;
    }
    </style>
""", unsafe_allow_html=True)


# =============================================================================
# KOMPATYBILNOSC Z RÓŻNYMI WERSJAMI STREAMLITA
# (nowsze wersje zastepuja use_container_width parametrem width="stretch")
# =============================================================================
try:
    _NOWY_STREAMLIT = tuple(int(x) for x in st.__version__.split(".")[:2]) >= (1, 50)
except Exception:
    _NOWY_STREAMLIT = False


def szeroki(funkcja, *args, **kwargs):
    """Wywoluje funkcje Streamlita tak, aby element zajmowal cala szerokosc kontenera."""
    if _NOWY_STREAMLIT:
        try:
            return funkcja(*args, width="stretch", **kwargs)
        except (TypeError, st.errors.StreamlitAPIException):
            pass
    return funkcja(*args, use_container_width=True, **kwargs)


WYBIERZ = "— wybierz —"
ZRODLO_FOLDER = "Zapis gry (folder)"
ZRODLO_FM = "Plik zapisu .fm"
ZRODLO_CSV = "Pliki CSV"
ZRODLO_DEMO = "Dane demo"
CO_ILE_SEKUND = 30


# =============================================================================
# WCZYTYWANIE (cache)
# =============================================================================
@st.cache_data(show_spinner="Przetwarzanie pliku CSV...")
def wczytaj_csv_cache(plik_bajty):
    return wczytaj_csv(plik_bajty)


@st.cache_data(show_spinner="Generowanie danych demo...")
def demo_dane(pozycja):
    return wczytaj_csv(generuj_demo_csv(pozycja))[0]


def _wersja_nazw_lig():
    try:
        return PLIK_NAZW_ROZGRYWEK.stat().st_mtime
    except OSError:
        return 0.0


@st.cache_data(show_spinner="Odczyt zapisu kariery (duży zapis może potrwać kilkadziesiąt sekund)...", max_entries=2)
def wczytaj_zapis_cache(sciezka, rozmiar, mtime, opcje_krotka, wersja_nazw):
    # rozmiar, mtime i wersja_nazw sa czescia klucza cache: zmiana pliku lub mapy nazw = nowy odczyt
    return wczytaj_zapis(sciezka, OpcjeZapisu(*opcje_krotka))


def zapisz_wgrany_plik(plik):
    """Wgrany plik .fm -> sciezka na dysku (fmsave czyta z dysku). Zapisywany raz na wgranie."""
    mapa = st.session_state.setdefault("wgrane_fm", {})
    sciezka = mapa.get(plik.file_id)
    if sciezka is None or not Path(sciezka).exists():
        # Osobny podfolder: sprzatanie kopii z trybu folderu nie usunie wgranego pliku.
        # Wczesniej wgrane zapisy (po kilkaset MB) sa usuwane - w danej chwili analizujemy jeden.
        folder = folder_zapisow.folder_kopii() / "wgrane"
        folder.mkdir(exist_ok=True)
        for stary in folder.glob("*.fm"):
            stary.unlink(missing_ok=True)
        mapa.clear()
        cel = folder / f"{plik.file_id}.fm"
        with open(cel, "wb") as f:
            f.write(plik.getbuffer())
        mapa[plik.file_id] = sciezka = str(cel)
    return sciezka


# =============================================================================
# KLUCZE WIDGETOW I CZYSZCZENIE FILTROW
# =============================================================================
def klucz(nazwa, pozycja, sygnatura):
    # Sygnatura danych w kluczu chroni przed bledem, gdy po wgraniu nowego pliku
    # zapamietana wartosc suwaka/listy wykracza poza nowy zakres.
    return f"{nazwa}_{pozycja}_{sygnatura}"


def wstaw_po(lista, nowy, po):
    if nowy in lista:
        return
    i = lista.index(po) + 1 if po in lista else len(lista)
    lista.insert(i, nowy)


def domyslnie(k, wartosc):
    """Ustawia wartosc poczatkowa widzetu raz (widzet tworzony bez parametru value)."""
    if k not in st.session_state:
        st.session_state[k] = wartosc


FILTRY = ("search", "ligi", "noga", "age", "price", "bez_ceny", "ignore_mult", "contract", "data_gry",
          "miesiace", "compare", "klon")


def clear_filters(pozycja, sygnatura):
    # Usuniecie stanu przywraca wartosci domyslne przy nastepnym przebiegu skryptu
    for nazwa in FILTRY:
        st.session_state.pop(klucz(nazwa, pozycja, sygnatura), None)
    for stat_name in MERYTORYKA_WAG.get(pozycja, {}):
        st.session_state.pop(f"weight_{pozycja}_{stat_name}", None)


@st.fragment(run_every=CO_ILE_SEKUND)
def obserwuj_folder(folder):
    """Co 30 s sprawdza, czy gra zapisala nowszy stan; jesli tak - przeladowuje aplikacje."""
    najnowszy = folder_zapisow.najnowszy_zapis(folder)
    stan = (str(najnowszy.sciezka), najnowszy.mtime) if najnowszy else None
    if stan != st.session_state.get("obserwowany_zapis"):
        st.session_state["obserwowany_zapis"] = stan
        st.rerun()
    st.caption(f"Śledzenie zmian: sprawdzono o {datetime.now():%H:%M:%S}")


def opcje_zapisu_ui():
    with st.expander("Opcje odczytu zapisu", expanded=False):
        rodzaj = st.radio("Statystyki z:", ["league", "overall"], key="opt_rodzaj", horizontal=True,
                          format_func=lambda r: "Ligi" if r == "league" else "Wszystkich rozgrywek")
        min_minut = st.number_input("Minimalna liczba minut w sezonie:", 0, 5000, 300, step=90, key="opt_min_minut")
        kurs = st.number_input("Kurs waluty zapisu → EUR:", 0.01, 10.0, KURS_DOMYSLNY, step=0.01,
                               format="%.3f", key="opt_kurs",
                               help="Zapis przechowuje kwoty w walucie bazowej (najpewniej GBP). Domyślny kurs "
                                    "odpowiada temu, co pokazuje gra w euro.")
        naturalne = st.toggle("Zawodnik na wszystkich naturalnych pozycjach", value=False, key="opt_naturalne",
                              help="Wyłączone: tylko na pozycji z najwyższą oceną.")
        tylko_ligi = st.toggle("Tylko kluby przypisane do ligi krajowej", value=True, key="opt_tylko_ligi")
    return (rodzaj, int(min_minut), float(kurs), naturalne, tylko_ligi)


def nazwy_lig_ui(sciezka_zapisu):
    with st.expander("Nazwy lig", expanded=False):
        st.caption("Zapis nie zawiera nazw lig. Wgraj stare eksporty CSV z gry (z kolumnami Klub i Liga) - "
                   "aplikacja dopasuje kluby i zapamięta nazwy lig (również dla kolejnych zapisów).")
        pliki_csv = st.file_uploader("Eksporty CSV", type=["csv"], accept_multiple_files=True,
                                     key="uploader_nazwy_lig", label_visibility="collapsed")
        if pliki_csv and st.button("Rozpoznaj ligi", key="btn_nazwy_lig"):
            ramki = []
            for plik in pliki_csv:
                try:
                    ramki.append(wczytaj_csv_cache(plik.getvalue())[0])
                except Exception as e:
                    st.error(f"Nie udało się wczytać {plik.name}: {e}")
            with st.spinner("Dopasowywanie klubów do lig..."):
                mapa = zbuduj_mape_nazw_lig(sciezka_zapisu, ramki)
            if mapa:
                zapisz_nazwy_rozgrywek(mapa)
                st.success(f"Rozpoznano {len(mapa)} lig: " + ", ".join(sorted(mapa.values())))
            else:
                st.warning("Nie udało się dopasować żadnej ligi - sprawdź, czy pliki mają kolumny Klub i Liga.")


# =============================================================================
# INTERFEJS
# =============================================================================
st.markdown("<div style='font-size: 2.7rem; font-weight: bold; margin-top: -3.5rem; margin-bottom: 1rem;'>FM26 Moneyball Dashboard</div>", unsafe_allow_html=True)

# --- SIDEBAR: kontener na wybor pozycji (wypelniony po wczytaniu danych) ---
kontener_pozycji = st.sidebar.container()

dane = {}        # pozycja -> DataFrame
zrodla = {}      # pozycja -> opis zrodla ("DEMO", nazwa pliku)
sygnatury = {}   # pozycja -> sygnatura danych (klucze widzetow)
wynik_zapisu = None

with st.sidebar:
    st.markdown("---")
    st.markdown("<div style='font-size: 1.15rem; font-weight: 600; margin-bottom: 0.5rem;'>Dane</div>", unsafe_allow_html=True)
    zrodlo = st.radio("Źródło danych", [ZRODLO_FOLDER, ZRODLO_FM, ZRODLO_CSV, ZRODLO_DEMO],
                      key="zrodlo", label_visibility="collapsed")

    if zrodlo in (ZRODLO_FOLDER, ZRODLO_FM):
        opcje = opcje_zapisu_ui()
        sciezka_zapisu, opis = None, None

        if zrodlo == ZRODLO_FOLDER:
            domyslnie("folder_zapisow", str(folder_zapisow.domyslny_folder() or ""))
            folder = st.text_input("Folder zapisów FM26:", key="folder_zapisow",
                                   help="Domyślnie Dokumenty/Sports Interactive/Football Manager 26/games.")
            pliki = folder_zapisow.lista_zapisow(folder) if folder else []
            if not pliki:
                st.warning("Nie znaleziono plików .fm w tym folderze. Wskaż folder 'games' z zapisami FM26 "
                           "(aplikacja musi działać na komputerze z grą) albo wgraj plik .fm.")
            else:
                najnowszy = st.toggle("Zawsze najnowszy zapis", value=True, key="auto_najnowszy")
                if najnowszy:
                    wybrany = pliki[0]
                else:
                    wybrany = st.selectbox("Zapis:", pliki, key="wybrany_zapis",
                                           format_func=lambda p: f"{p.nazwa} ({datetime.fromtimestamp(p.mtime):%d.%m %H:%M})")
                st.caption(f"{wybrany.nazwa} · zapisany {datetime.fromtimestamp(wybrany.mtime):%d.%m.%Y %H:%M}")
                if st.toggle("Śledź zmiany zapisów", value=True, key="sledz_zmiany"):
                    st.session_state["obserwowany_zapis"] = (str(pliki[0].sciezka), pliki[0].mtime)
                    obserwuj_folder(folder)
                # Kopia powstaje raz na stan zapisu; sprawdzanie, czy gra wlasnie pisze plik, tylko po zmianie
                stan_zapisu = (str(wybrany.sciezka), wybrany.mtime, wybrany.rozmiar)
                ostatni = st.session_state.get("ostatni_stabilny")
                if ostatni and not Path(ostatni[1]).exists():
                    ostatni = None
                if ostatni and ostatni[0] == stan_zapisu:
                    sciezka_zapisu, opis = ostatni[1], ostatni[2]
                elif folder_zapisow.czy_stabilny(wybrany.sciezka, odstep=0.5):
                    kopia = folder_zapisow.bezpieczna_kopia(wybrany)
                    sciezka_zapisu, opis = str(kopia), wybrany.nazwa
                    st.session_state["ostatni_stabilny"] = (stan_zapisu, sciezka_zapisu, opis)
                else:
                    st.info("Gra właśnie zapisuje plik - pokazuję poprzedni stan.")
                    if ostatni:
                        sciezka_zapisu, opis = ostatni[1], ostatni[2]
        else:
            plik_fm = st.file_uploader("Wgraj plik zapisu .fm", type=["fm"], key="uploader_fm",
                                       label_visibility="collapsed")
            if plik_fm is not None:
                sciezka_zapisu, opis = zapisz_wgrany_plik(plik_fm), plik_fm.name

        if sciezka_zapisu:
            stat = Path(sciezka_zapisu).stat()
            try:
                wynik_zapisu = wczytaj_zapis_cache(sciezka_zapisu, stat.st_size, stat.st_mtime, opcje,
                                                   _wersja_nazw_lig())
            except Exception as e:
                st.error(f"Nie udało się odczytać zapisu {opis}: {e}")
            if wynik_zapisu is not None:
                for p, ramka in wynik_zapisu.dane.items():
                    dane[p] = ramka
                    zrodla[p] = opis
                    sygnatury[p] = hashlib.md5(f"{stat.st_mtime}_{stat.st_size}_{opcje}".encode()).hexdigest()[:12]
                st.caption(f"Data w grze: {wynik_zapisu.data_gry or '?'} · zawodników w analizie: "
                           f"{wynik_zapisu.liczniki.get('w_aplikacji', 0)}")
                for tekst in wynik_zapisu.ostrzezenia:
                    st.warning(tekst)
            nazwy_lig_ui(sciezka_zapisu)

    elif zrodlo == ZRODLO_CSV:
        pliki = st.file_uploader("Wgraj pliki CSV", type=["csv"], accept_multiple_files=True,
                                 key="uploader_wiele", label_visibility="collapsed")
        for plik in (pliki or []):
            surowe = plik.getvalue()
            try:
                df_pliku, _ = wczytaj_csv_cache(surowe)
            except Exception as e:
                st.error(f"Nie udało się wczytać pliku {plik.name}: {e}")
                continue
            k_przyp = f"przypisanie_{plik.name}_{len(surowe)}"
            domyslnie(k_przyp, wykryj_pozycje(plik.name, df_pliku) or WYBIERZ)
            wybor = st.selectbox(f"{plik.name} ({len(df_pliku)} zawodników) - pozycja:",
                                 [WYBIERZ] + POZYCJE, key=k_przyp)
            if wybor != WYBIERZ:
                if wybor in dane:
                    st.warning(f"Pozycja {wybor} jest przypisana do więcej niż jednego pliku - użyto {plik.name}.")
                dane[wybor] = df_pliku
                zrodla[wybor] = plik.name
                sygnatury[wybor] = hashlib.md5(surowe).hexdigest()[:12]

    else:
        for p in POZYCJE:
            dane[p] = demo_dane(p)
            zrodla[p] = "DEMO"
            sygnatury[p] = "demo"

    with st.expander("Ustawienia", expanded=False):
        if wynik_zapisu is not None and wynik_zapisu.moj_klub and not st.session_state.get("moj_klub"):
            st.session_state["moj_klub"] = wynik_zapisu.moj_klub
        domyslnie("moj_klub", "")
        moj_klub = st.text_input("Mój klub (podświetlenie w tabelach):", key="moj_klub")
        k_baza = st.slider(
            "Siła skurczenia przy małej próbie (mecze):", 0, 15, 5, key="k_baza",
            help="Działa tylko, gdy dane zawierają minuty. Zawodnik z małą liczbą minut jest przyciągany do średniej "
                 "pozycji: im większa wartość, tym mocniej. 0 = wyłączone."
        )
        pokaz_ukryte = st.toggle("Pokaż dane ukryte w grze (CA/PA)", value=False, key="pokaz_ukryte",
                                 help="Tylko z pliku zapisu. To dane, których w grze nie widać bez pełnej wiedzy skautów.")
        maks_wierszy = st.number_input("Maks. wierszy w tabeli:", 100, 20000, 1000, step=100, key="maks_wierszy",
                                       help="Duża tabela z kolorowaniem renderuje się wolno; filtry działają na pełnych danych.")
    st.markdown("---")

with kontener_pozycji:
    st.markdown("### Wybierz pozycję")
    pozycja_nazwa = st.radio(
        "Pozycja", POZYCJE,
        format_func=lambda p: f"{p} ({len(dane[p])})" if p in dane else p,
        label_visibility="collapsed", key="pozycja"
    )

df = dane.get(pozycja_nazwa)

if df is None or df.empty:
    st.info(f"Brak danych dla pozycji: {pozycja_nazwa}. Wybierz źródło danych w panelu bocznym.")
    with st.expander("Skąd wziąć dane?", expanded=True):
        st.markdown(
            "- **Zapis gry (folder)** - aplikacja sama znajduje najnowszy zapis FM26 i odświeża się po każdym "
            "zapisie w grze. Działa, gdy aplikacja jest uruchomiona na komputerze z grą.\n"
            "- **Plik zapisu .fm** - wgraj plik kariery z folderu *Sports Interactive/Football Manager 26/games*.\n"
            "- **Pliki CSV** - eksport widoku z gry (po jednym pliku na pozycję), z kolumną minut (*Min*).\n"
            "- **Dane demo** - syntetyczne dane do wypróbowania aplikacji."
        )
    st.stop()

if zrodla.get(pozycja_nazwa) == "DEMO":
    st.warning("Wyświetlane są syntetyczne dane demonstracyjne, a nie dane z Twojej gry.")

sygnatura = sygnatury.get(pozycja_nazwa, "x")
K = lambda nazwa: klucz(nazwa, pozycja_nazwa, sygnatura)

# --- DYNAMICZNE FILTRY W SIDEBARZE ---
zdefiniowana_kolejnosc = list(MAPOWANIE_NAZW_LIG.values())
unikalne_ligi = df['Liga'].dropna().unique().tolist() if 'Liga' in df.columns else []
dostepne_ligi = sorted(unikalne_ligi, key=lambda x: (zdefiniowana_kolejnosc.index(x) if x in zdefiniowana_kolejnosc else 999, str(x)))
dostepne_nogi = sorted(df['Preferowana noga'].dropna().unique()) if 'Preferowana noga' in df.columns else []

min_age = int(df['Wiek'].min()) if 'Wiek' in df.columns else 15
max_age = int(df['Wiek'].max()) if 'Wiek' in df.columns else 45
if min_age >= max_age:
    max_age = min_age + 1

ceny_ok = df['Wartość_Numeryczna'].dropna()
max_price_avail = float(ceny_ok.max()) if not ceny_ok.empty and ceny_ok.max() > 0 else 100_000_000.0
max_price_mln = max(max_price_avail / 1_000_000, 0.1)
liczba_bez_ceny = int(df['Wartość_Numeryczna'].isna().sum())

with st.sidebar:
    st.markdown("### Filtry wyszukiwania")
    domyslnie(K("ignore_mult"), False)
    ignore_mult = st.toggle("Ignoruj mnożnik ligowy", key=K("ignore_mult"),
                            help="Mnożniki lig są wartościami heurystycznymi (nie weryfikowanymi na danych).")
    search = st.text_input("Szukaj (Piłkarz / Klub):", key=K("search"))
    wybrane_ligi = st.multiselect("Wybierz ligi:", options=dostepne_ligi, key=K("ligi"))
    wybrana_noga = st.multiselect("Lepsza noga:", options=dostepne_nogi, key=K("noga"))

    # --- FILTR KOŃCA KONTRAKTU (z datą w grze) ---
    filtr_kontraktu = False
    data_gry = None
    miesiace = 6
    if df['Wygasa_Data'].notna().any():
        filtr_kontraktu = st.checkbox("Tylko kontrakty wygasające wkrótce", key=K("contract"))
        if filtr_kontraktu:
            if wynik_zapisu is not None and wynik_zapisu.data_gry:
                domyslnie(K("data_gry"), wynik_zapisu.data_gry)
                pomoc = "Data w grze odczytana z zapisu."
            else:
                domyslnie(K("data_gry"), df['Wygasa_Data'].min().date())
                pomoc = "Ustaw bieżącą datę z gry (CSV jej nie zawiera). Domyślnie: najwcześniejszy koniec kontraktu z pliku."
            data_gry = st.date_input("Data w grze:", key=K("data_gry"), help=pomoc)
            domyslnie(K("miesiace"), 6)
            miesiace = st.number_input("W ciągu (miesięcy):", min_value=1, max_value=36, key=K("miesiace"))

    domyslnie(K("age"), (min_age, max_age))
    age_filter = st.slider("Wiek:", min_age, max_age, key=K("age"))
    domyslnie(K("price"), (0.0, float(max_price_mln)))
    price_filter_mln = st.slider("Cena (mln €):", 0.0, float(max_price_mln), key=K("price"))
    pokaz_bez_ceny = True
    if liczba_bez_ceny:
        domyslnie(K("bez_ceny"), True)
        pokaz_bez_ceny = st.toggle(f"Uwzględnij zawodników bez ceny ({liczba_bez_ceny})", key=K("bez_ceny"),
                                   help="Zawodnicy oznaczeni jako 'Nie na sprzedaż' nie mają ceny i nie są traktowani jako darmowi.")
    price_min = price_filter_mln[0] * 1_000_000
    price_max = price_filter_mln[1] * 1_000_000 + 1   # +1 EUR chroni przed bledem zaokraglenia

    # --- EDYTOR WAG ---
    st.markdown("### Zaawansowane wagi")
    custom_weights = {}
    with st.expander("Modyfikuj wagi statystyk", expanded=False):
        st.caption("Ważność 0-100. Wagi są normalizowane do sumy 1, więc liczą się tylko proporcje.")
        for stat_name, default_val in MERYTORYKA_WAG[pozycja_nazwa].items():
            if stat_name not in df.columns:
                continue
            custom_weights[stat_name] = st.slider(
                f"{stat_name}:", min_value=0, max_value=100, value=int(default_val), step=5,
                key=f"weight_{pozycja_nazwa}_{stat_name}"
            )
        suma_wag = sum(custom_weights.values())
        if suma_wag > 0:
            udzialy = ", ".join(f"{n.split('/')[0]}: {w / suma_wag * 100:.0f}%" for n, w in custom_weights.items() if w > 0)
            st.caption("Udział po normalizacji - " + udzialy)

    szeroki(st.button, "Wyczyść filtry", key=f"btn_clear_{pozycja_nazwa}", on_click=clear_filters,
            args=(pozycja_nazwa, sygnatura))

# --- RAPORT WCZYTANIA ---
with st.expander("Raport wczytania danych", expanded=False):
    st.caption(f"Źródło: {zrodla.get(pozycja_nazwa)}")
    for poziom, tekst in raport_wczytania(df, pozycja_nazwa):
        if poziom == "warn":
            st.warning(tekst)
        else:
            st.caption(tekst)

# --- REKALKULACJA I FILTROWANIE ---
base_df = df.copy()
score, wiarygodnosc, pominiete = oblicz_score(base_df, custom_weights, ignore_mult, k_baza)
if score.isna().all():
    st.error("Nie można obliczyć wyniku: brak kolumn statystycznych dla wybranych wag (lub wszystkie wagi = 0).")
    st.stop()
if pominiete:
    st.caption("Pominięte cechy (brak danych lub brak zróżnicowania): " + ", ".join(pominiete))

base_df['SCORE'] = score
base_df['Percentyl'] = score.rank(pct=True) * 100
base_df['Wiarygodność'] = wiarygodnosc

filtered_df = base_df
if 'Wiek' in filtered_df.columns:
    filtered_df = filtered_df[(filtered_df['Wiek'] >= age_filter[0]) & (filtered_df['Wiek'] <= age_filter[1])]

cena = filtered_df['Wartość_Numeryczna']
filtered_df = filtered_df[cena.between(price_min, price_max) | (cena.isna() & pokaz_bez_ceny)]

if wybrane_ligi:
    filtered_df = filtered_df[filtered_df['Liga'].isin(wybrane_ligi)]
if wybrana_noga:
    filtered_df = filtered_df[filtered_df['Preferowana noga'].isin(wybrana_noga)]
if filtr_kontraktu and data_gry is not None:
    start = pd.Timestamp(data_gry)
    koniec = start + pd.DateOffset(months=int(miesiace))
    wygasa = filtered_df['Wygasa_Data']
    filtered_df = filtered_df[wygasa.notna() & (wygasa >= start) & (wygasa <= koniec)]

if search:
    warunek = pd.Series(False, index=filtered_df.index)
    if 'Piłkarz' in filtered_df.columns:
        warunek |= filtered_df['Piłkarz'].str.contains(search, case=False, na=False, regex=False)
    if 'Klub' in filtered_df.columns:
        warunek |= filtered_df['Klub'].str.contains(search, case=False, na=False, regex=False)
    filtered_df = filtered_df[warunek]

filtered_df = filtered_df.sort_values(by="SCORE", ascending=False)

# --- TABELA GŁÓWNA WYNIKÓW ---
dedykowane_kolumny = KOLUMNY_PER_POZYCJA.get(pozycja_nazwa, [])
cols_to_show = [c for c in dedykowane_kolumny if c in filtered_df.columns]
if len(cols_to_show) <= 2:
    cols_to_show = [c for c in ['SCORE', 'Percentyl', 'Piłkarz', 'Wiek', 'Preferowana noga', 'Klub', 'Liga', 'Cena']
                    if c in filtered_df.columns]

if filtered_df['Wiarygodność'].notna().any():
    wstaw_po(cols_to_show, 'Wiarygodność', 'Percentyl')
if 'Minuty' in filtered_df.columns and filtered_df['Minuty'].notna().any():
    wstaw_po(cols_to_show, 'Minuty', 'Klub')
if 'Płaca' in filtered_df.columns:
    wstaw_po(cols_to_show, 'Płaca', 'Cena')
if 'Wygasa' in filtered_df.columns:
    wstaw_po(cols_to_show, 'Wygasa', 'Płaca' if 'Płaca' in cols_to_show else 'Cena')
if pokaz_ukryte:
    for kol in reversed(KOLUMNY_UKRYTE):
        if kol in filtered_df.columns and filtered_df[kol].notna().any():
            wstaw_po(cols_to_show, kol, 'Wiek')

TEKSTOWE = ['Percentyl', 'Piłkarz', 'Klub', 'Liga', 'Pozycja', 'Cena', 'Płaca', 'Wygasa', 'Kraj', 'Preferowana noga']
format_dict = {}
for col in cols_to_show:
    if col == 'SCORE' or col in ('Wiek', 'Minuty', 'CA', 'PA'):
        format_dict[col] = '{:.0f}'
    elif col == 'Wiarygodność':
        format_dict[col] = '{:.0f}%'
    elif col == 'Strata piłek na podanie':
        format_dict[col] = '{:.2f}'
    elif col not in TEKSTOWE and pd.api.types.is_numeric_dtype(filtered_df[col]):
        format_dict[col] = '{:.1f}'

jasna_paleta = mcolors.LinearSegmentedColormap.from_list("jasne_kolory", ["#ff9999", "#ffff99", "#99ff99"])


# Z zapisu znamy uid mojego klubu - porownanie po uid nie myli go z klubem o tej samej nazwie
# (np. kobieca "F.C. Barcelona"). Gdy uzytkownik wpisze inny klub, porownujemy po nazwie.
moj_klub_uid = (wynik_zapisu.moj_klub_uid
                if wynik_zapisu is not None and moj_klub and moj_klub == wynik_zapisu.moj_klub else None)


def podswietl_moj_klub(zrodlo):
    """Funkcja dla Styler.apply(axis=1); `zrodlo` to ramka z pelnymi danymi wierszy (takze Klub_UID)."""
    def styl(row):
        if moj_klub_uid is not None and 'Klub_UID' in zrodlo.columns:
            moj = zrodlo.at[row.name, 'Klub_UID'] == moj_klub_uid
        else:
            klub = zrodlo.at[row.name, 'Klub'] if 'Klub' in zrodlo.columns else None
            moj = bool(moj_klub) and pd.notna(klub) and moj_klub.lower() in str(klub).lower()
        return ['background-color: #282933;' if moj else '' for _ in row]
    return styl


do_tabeli = filtered_df.head(int(maks_wierszy))
if len(filtered_df) > len(do_tabeli):
    st.caption(f"Pokazano {len(do_tabeli)} najlepszych z {len(filtered_df)} zawodników spełniających filtry "
               "(limit w Ustawieniach).")
df_style = do_tabeli[cols_to_show].style.format(format_dict, na_rep="–")
df_style = df_style.apply(podswietl_moj_klub(do_tabeli), axis=1)
if 'SCORE' in cols_to_show:
    df_style = df_style.background_gradient(subset=['SCORE'], cmap=jasna_paleta)
    df_style = df_style.set_properties(subset=['SCORE'], **{'color': 'black', 'text-align': 'center'})
df_style = df_style.set_table_styles([{'selector': 'th', 'props': [('text-align', 'center')]}], overwrite=False)

col_config = {}
if 'SCORE' in cols_to_show:
    col_config['SCORE'] = st.column_config.Column(
        "SCORE", alignment="center",
        help="Skala typu T-score: 50 = przeciętny zawodnik na tej pozycji w próbie, +10 = jedno odchylenie standardowe wyżej. Przy włączonym mnożniku ligowym dodawana jest korekta 50 × (mnożnik − 1), np. −4 pkt dla Premier League, −16 dla I ligi.")
if 'Percentyl' in cols_to_show:
    col_config['Percentyl'] = st.column_config.ProgressColumn(
        "Percentyl", help="0-100: pozycja w próbie (nie w całej lidze).",
        format="%.0f", min_value=0, max_value=100, width="small")
if 'Wiarygodność' in cols_to_show:
    col_config['Wiarygodność'] = st.column_config.ProgressColumn(
        "Wiarygodność", help="Ile wyniku pochodzi z faktycznych statystyk zawodnika, a ile ze średniej pozycji (zależy od minut).",
        format="%.0f", min_value=0, max_value=100, width="small")

szeroki(st.dataframe, df_style, height=400, hide_index=True, column_config=col_config)

# --- PORÓWNANIE ZAWODNIKÓW (RADAR) ---
st.markdown("---")
st.subheader("Porównanie zawodników", anchor=False)

zawodnicy_do_porownania = st.multiselect(
    "Wybierz dokładnie dwóch zawodników z tabeli, aby nałożyć ich statystyki na radar percentylowy:",
    options=filtered_df['ID'].tolist(), max_selections=2, key=K("compare")
)

stat_cols = [c for c in dedykowane_kolumny if c not in NIE_STATYSTYKI and c in base_df.columns]
radar_cols = [c for c in stat_cols if c not in NEUTRALNE]

if len(zawodnicy_do_porownania) == 2:
    df_compare = filtered_df[filtered_df['ID'].isin(zawodnicy_do_porownania)]
    if radar_cols:
        fig = go.Figure()
        etykiety = [c + " (odwrócone)" if c in NIZSZE_LEPSZE else c for c in radar_cols]
        for _, row in df_compare.iterrows():
            procenty = []
            for c in radar_cols:
                p = percentyl_w_puli(base_df[c], row[c])
                procenty.append(100.0 - p if c in NIZSZE_LEPSZE else p)   # mniej strat = lepiej
            fig.add_trace(go.Scatterpolar(
                r=procenty + [procenty[0]], theta=etykiety + [etykiety[0]], fill='toself',
                name=row['ID'], mode='lines+markers', opacity=0.5, marker=dict(size=8),
                hovertemplate="<b>%{fullData.name}</b><br>%{theta}: %{r:.1f}%<extra></extra>"
            ))
        fig.update_layout(
            paper_bgcolor='#262730', plot_bgcolor='#262730',
            polar=dict(
                bgcolor='#262730',
                radialaxis=dict(visible=True, showticklabels=False, range=[0, 100], gridcolor='rgba(255, 255, 255, 0.15)'),
                angularaxis=dict(gridcolor='rgba(255, 255, 255, 0.15)', tickfont=dict(color='white'))
            ),
            font=dict(family="Arial", size=14, color="white"),
            legend=dict(orientation="v", x=-0.2, y=0.5, xanchor='right', yanchor='middle', font=dict(size=16, color="white")),
            showlegend=True, height=500, margin=dict(t=40, b=40, l=120, r=40)
        )
        szeroki(st.plotly_chart, fig)
        if NEUTRALNE & set(stat_cols):
            st.caption("Cechy stylu gry (np. liczba prób podań) nie są pokazane na radarze - więcej nie znaczy lepiej.")
    else:
        st.info("Brak szczegółowych statystyk meczowych do wygenerowania radaru.")
elif len(zawodnicy_do_porownania) == 1:
    st.info("Wybierz jeszcze drugiego zawodnika z listy.")

# --- ZNAJDŹ SOBOWTÓRA ---
st.markdown("---")
st.subheader("Znajdź sobowtóra", anchor=False)
st.markdown("Wybierz zawodnika (np. gwiazdę swojej drużyny). Algorytm porówna profil statystyk per 90 minut "
            "(podobieństwo kosinusowe w obrębie tej pozycji, ze skurczeniem przy małej liczbie minut) i wskaże 5 "
            "najbardziej podobnych graczy spośród widocznych w tabeli. Profil jest liczony na pełnej próbie, więc "
            "filtry nie zniekształcają wyniku.")

domyslnie(K("klon"), "")
zawodnik_do_zastapienia = st.selectbox("Kogo chcesz zastąpić?", options=[""] + sorted(base_df['ID'].tolist()), key=K("klon"))

if zawodnik_do_zastapienia:
    macierz = macierz_stylu(base_df, stat_cols, k_baza)
    if macierz.shape[1] < 2:
        st.info("Za mało zróżnicowanych kolumn liczbowych do porównania stylu gry.")
    else:
        M = macierz.values
        poz = int(np.flatnonzero(base_df['ID'].values == zawodnik_do_zastapienia)[0])
        wektor = M[poz]
        normy = np.linalg.norm(M, axis=1) * np.linalg.norm(wektor)
        with np.errstate(divide='ignore', invalid='ignore'):
            podobienstwo = np.where(normy > 0, M @ wektor / normy, 0.0)
        wyniki = base_df.copy()
        wyniki['Podobieństwo'] = podobienstwo
        wyniki = wyniki[wyniki.index.isin(filtered_df.index) & (wyniki['ID'] != zawodnik_do_zastapienia)]
        top5 = wyniki.sort_values('Podobieństwo', ascending=False).head(5).copy()
        top5['Zgodność'] = (top5['Podobieństwo'].clip(0, 1) * 100).round(1).astype(str) + "%"

        st.success(f"Oto 5 najlepszych alternatyw dla: **{zawodnik_do_zastapienia}** (wśród widocznych w tabeli zawodników)")
        kolumny_ml = [c for c in ['SCORE', 'Zgodność', 'Piłkarz', 'Wiek', 'Preferowana noga', 'Klub', 'Liga', 'Pozycja',
                                  'Cena', 'Płaca', 'Wygasa'] if c in top5.columns]
        format_ml = {c: '{:.0f}' for c in ('SCORE', 'Wiek') if c in kolumny_ml}
        stylowana = top5[kolumny_ml].style.format(format_ml, na_rep="–").apply(podswietl_moj_klub(top5), axis=1)
        if 'SCORE' in kolumny_ml:
            stylowana = stylowana.background_gradient(subset=['SCORE'], cmap=jasna_paleta)
            stylowana = stylowana.set_properties(subset=['SCORE'], **{'color': 'black', 'text-align': 'center'})
        stylowana = stylowana.set_table_styles([{'selector': 'th', 'props': [('text-align', 'center')]}], overwrite=False)
        szeroki(st.dataframe, stylowana, hide_index=True, column_config={
            'Zgodność': st.column_config.TextColumn("Zgodność", help="Podobieństwo kształtu statystyk meczowych do wybranego zawodnika."),
            'SCORE': st.column_config.Column("SCORE", alignment="center")
        })

# --- WYKRES: SCORE VS CENA ---
# Tooltipy tylko z kolumn, ktore sa w danych (CSV moze nie miec np. klubu czy wieku)
MOZLIWE_TOOLTIPY = [('ID', 'N', 'Piłkarz', None), ('Wiek', 'Q', 'Wiek', '.0f'), ('Klub', 'N', 'Klub', None),
                    ('Cena', 'N', 'Cena', None), ('SCORE', 'Q', 'SCORE', '.0f'), ('Percentyl', 'Q', 'Percentyl', '.0f'),
                    ('Liga', 'N', 'Liga', None), ('Płaca', 'N', 'Płaca', None)]
tooltip_cols = [alt.Tooltip(f'{kol}:{typ}', title=tytul, **({'format': fmt} if fmt else {}))
                for kol, typ, tytul, fmt in MOZLIWE_TOOLTIPY if kol in filtered_df.columns]

chart_data = filtered_df[filtered_df['Wartość_Numeryczna'].notna()].head(30)
if not chart_data.empty:
    st.markdown("---")
    st.subheader("Score vs Cena (Top 30, tylko zawodnicy z ceną)", anchor=False)
    min_score, max_score = float(chart_data['SCORE'].min()), float(chart_data['SCORE'].max())
    margines = (max_score - min_score) * 0.05 or 1.0
    kodowanie = dict(
        x=alt.X('Wartość_Numeryczna:Q', title='Cena (€, środek widełek)', axis=alt.Axis(format='~s'),
                scale=alt.Scale(zero=False)),
        y=alt.Y('SCORE:Q', title='Score', axis=alt.Axis(format='.0f'),
                scale=alt.Scale(zero=False, domain=[min_score - margines, max_score + margines])),
        tooltip=tooltip_cols
    )
    if 'Wiek' in chart_data.columns:
        kodowanie['color'] = alt.Color('Wiek:Q', scale=alt.Scale(scheme='viridis'), title='Wiek')
    wykres = alt.Chart(chart_data).mark_circle(size=300).encode(**kodowanie).properties(height=500)
    szeroki(st.altair_chart, wykres.interactive())

# --- TOP 10 W POSZCZEGÓLNYCH STATYSTYKACH ---
kolumny_statystyk = [c for c in dedykowane_kolumny if c not in NIE_STATYSTYKI and c in filtered_df.columns]
if kolumny_statystyk and not filtered_df.empty:
    st.markdown("---")
    st.subheader("Najlepsi zawodnicy w poszczególnych statystykach (Top 10)", anchor=False)
    kolumny_ui = st.columns(2)
    for idx, stat_col in enumerate(kolumny_statystyk):
        with kolumny_ui[idx % 2]:
            seria = filtered_df[stat_col].astype(float).dropna()
            if seria.empty:
                continue
            if stat_col in NIZSZE_LEPSZE:
                top10 = seria.nsmallest(10).index
                sort_order = 'x'
            else:
                top10 = seria.nlargest(10).index
                sort_order = '-x'
            dane_slupkow = filtered_df.loc[top10].copy()
            format_stat = '.0f' if '%' in stat_col else ('.2f' if stat_col == 'Strata piłek na podanie' else '.1f')
            wykres_slupkowy = alt.Chart(dane_slupkow).mark_bar().encode(
                x=alt.X(field=stat_col, type='quantitative', title=stat_col),
                y=alt.Y('ID', type='nominal', sort=sort_order, title=''),
                color=alt.Color('SCORE:Q', scale=alt.Scale(scheme='blues'), legend=None),
                tooltip=tooltip_cols + [alt.Tooltip(f'{stat_col}:Q', title=stat_col, format=format_stat)]
            ).properties(height=350, title=stat_col)
            szeroki(st.altair_chart, wykres_slupkowy.interactive())
