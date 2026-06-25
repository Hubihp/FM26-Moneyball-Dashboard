import streamlit as st
import pandas as pd
import altair as alt
import numpy as np
import matplotlib.colors as mcolors
import plotly.graph_objects as go
from sklearn.preprocessing import StandardScaler
from sklearn.metrics.pairwise import cosine_similarity

# Konfiguracja strony
st.set_page_config(page_title="FM26 Moneyball Dashboard", layout="wide")

# Ukrywanie alertów po 5 sekundach, usuwanie ikon hiperłączy, poprawa odstępów w sidebarze oraz modyfikacja uploada
st.markdown("""
    <style>
    [data-testid="stAlert"] {
        animation: fadeOut 5s ease-in-out forwards;
    }
    @keyframes fadeOut {
        0% { opacity: 1; height: auto; }
        80% { opacity: 1; height: auto; }
        100% { opacity: 0; height: 0; padding: 0; margin: 0; overflow: hidden; display: none; }
    }
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
    
    /* Wymuszenie przycisku "Browse files" na pierwsze miejsce (po lewej) */
    [data-testid="stFileUploaderDropzone"] button {
        order: -1 !important; 
        margin-right: 15px !important;
        margin-top: 0 !important;
    }
    
    /* Wyrównanie instrukcji w pionie */
    [data-testid="stFileUploaderDropzoneInstructions"] {
        display: flex !important;
        align-items: center !important;
        margin: 0 !important;
    }
    
    /* Ukrycie ikony chmurki oraz napisu "Drag and drop...", zostaje tylko przycisk i "Limit 200MB..." */
    [data-testid="stFileUploaderDropzone"] svg {
        display: none !important;
    }
    [data-testid="stFileUploaderDropzoneInstructions"] > div > span {
        display: none !important;
    }
    </style>
""", unsafe_allow_html=True)

# Słownik tłumaczeń kolumn statystycznych
TLUMACZENIE_KOLUMN = {
    "xA/90": "Oczekiwane asysty/90",
    "KPzG/90": "Kluczowe podania z gry/90",
    "Liczba goli na 90 min": "Liczba goli na 90 min",
    "xG/strzał": "Oczekiwane gole na strzał",
    "Skut (%)": "Skuteczność strzałów (%)",
    "Ud Pres/90": "Udane próby pressingu/90",
    "Prz/90": "Przechwyty/90",
    "Odz Płk/90": "Odzyskane piłki/90",
    "Str Płk/90": "Stracone piłki/90",
    "Pod/90": "Próby podań/90",
    "% Głw": "% wygranych pojedynków główkowych",
    "Drb/90": "Liczba dryblingów/90",
    "ZxG/90": "Uniknięte oczekiwane gole/90",
    "Szacowana wartość": "Cena"
}

# Mnożniki lig bazowe
MNOZNIKI_LIG = {
    "Premier League": 0.918,               # ANG 1
    "EFL Championship": 0.811,             # ANG 2
    "Liga Profesional de Fútbol": 0.809,   # ARG 1
    "Primera Nacional": 0.749,             # ARG 2
    "Jupiler Pro League": 0.816,           # BEL 1
    "Challenger Pro League": 0.695,        # BEL 2
    "Série A": 0.826,                      # BRA 1
    "Série B": 0.721,                      # BRA 2
    "Hrvatska nogometna liga": 0.792,      # CHO 1
    "Prva nogometa liga": 0.673,           # CHO 2
    "Ligue 1": 0.856,                      # FRA 1
    "Ligue 2": 0.758,                      # FRA 2
    "LaLiga": 0.866,                       # HIS 1
    "LaLiga 2": 0.777,                     # HIS 2
    "Eredivisie": 0.783,                   # HOL 1
    "Eerste Divisie": 0.66,                # HOL 2
    "J1 League": 0.777,                    # JAP 1
    "J2 League": 0.695,                    # JAP 2
    "Liga MX": 0.778,                      # MEX 1
    "Liga Rozwojowa": 0.7,                 # MEX 2
    "Bundesliga": 0.867,                   # NIE 1
    "2. Bundesliga": 0.778,                # NIE 2
    "Ekstraklasa": 0.795,                  # POL 1
    "I liga": 0.686,                       # POL 2
    "Liga Portugal": 0.814,                # POR 1
    "Liga Portugal 2": 0.726,              # POR 2
    "MLS": 0.784,                          # USA 1
    "Serie A": 0.86,                       # WLO 1
    "Serie B": 0.759                       # WLO 2
}

# Słownik mapujący wyświetlane nazwy lig
MAPOWANIE_NAZW_LIG = {
    "Premier League": "Premier League (ANG 1)",
    "EFL Championship": "EFL Championship (ANG 2)",
    "Liga Profesional de Fútbol": "Liga Profesional de Fútbol (ARG 1)",
    "Primera Nacional": "Primera Nacional (ARG 2)",
    "Jupiler Pro League": "Jupiler Pro League (BEL 1)",
    "Challenger Pro League": "Challenger Pro League (BEL 2)",
    "Série A": "Série A (BRA 1)",
    "Série B": "Série B (BRA 2)",
    "Hrvatska nogometna liga": "Hrvatska nogometna liga (CHO 1)",
    "Prva nogometa liga": "Prva nogometa liga (CHO 2)",
    "Ligue 1": "Ligue 1 (FRA 1)",
    "Ligue 2": "Ligue 2 (FRA 2)",
    "LaLiga": "LaLiga (HIS 1)",
    "LaLiga 2": "LaLiga 2 (HIS 2)",
    "Eredivisie": "Eredivisie (HOL 1)",
    "Eerste Divisie": "Eerste Divisie (HOL 2)",
    "J1 League": "J1 League (JAP 1)",
    "J2 League": "J2 League (JAP 2)",
    "Liga MX": "Liga MX (MEX 1)",
    "Liga Rozwojowa": "Liga Rozwojowa (MEX 2)",
    "Bundesliga": "Bundesliga (NIE 1)",
    "2. Bundesliga": "2. Bundesliga (NIE 2)",
    "Ekstraklasa": "Ekstraklasa (POL 1)",
    "I liga": "I liga (POL 2)",
    "Liga Portugal": "Liga Portugal (POR 1)",
    "Liga Portugal 2": "Liga Portugal 2 (POR 2)",
    "MLS": "MLS (USA 1)",
    "Serie A": "Serie A (WLO 1)",
    "Serie B": "Serie B (WLO 2)"
}

# Definicje domyślnych wag merytorycznych per pozycja
MERYTORYKA_WAG = {
    "Bramkarz": {'Uniknięte oczekiwane gole/90': 130.0, 'Odzyskane piłki/90': 30.0, 'Próby podań/90': 0.5},
    "Środkowy Obrońca": {'% wygranych pojedynków główkowych': 15.0, 'Przechwyty/90': 20.0, 'Udane próby pressingu/90': 5.0, 'Kluczowe podania z gry/90': 20.0, 'Odzyskane piłki/90': 8.0},
    "Boczny Obrońca": {'Oczekiwane asysty/90': 100.0, 'Kluczowe podania z gry/90': 60.0, 'Przechwyty/90': 12.0, 'Odzyskane piłki/90': 6.0, 'Udane próby pressingu/90': 8.0},
    "Defensywny Pomocnik": {'Oczekiwane asysty/90': 9.0, 'Kluczowe podania z gry/90': 40.0, 'Przechwyty/90': 9.0, 'Odzyskane piłki/90': 9.0, 'Udane próby pressingu/90': 9.0, '% wygranych pojedynków główkowych': 5.0},
    "Środkowy Pomocnik": {'Oczekiwane asysty/90': 80.0, 'Liczba goli na 90 min': 40.0, 'Kluczowe podania z gry/90': 60.0, 'Liczba dryblingów/90': 12.0, 'Odzyskane piłki/90': 8.0, 'Udane próby pressingu/90': 8.0},
    "Skrzydłowy": {'Oczekiwane asysty/90': 96.0, 'Liczba goli na 90 min': 80.0, 'Oczekiwane gole na strzał': 58.0, 'Kluczowe podania z gry/90': 40.0, 'Liczba dryblingów/90': 16.0, 'Udane próby pressingu/90': 6.0, 'Odzyskane piłki/90': 6.0},
    "Napastnik": {'Liczba goli na 90 min': 180.0, 'Oczekiwane gole na strzał': 60.0, 'Oczekiwane asysty/90': 80.0, 'Kluczowe podania z gry/90': 40.0, 'Liczba dryblingów/90': 15.0, 'Udane próby pressingu/90': 8.0, 'Odzyskane piłki/90': 8.0, 'Skuteczność strzałów (%)': 1.0}
}

def parse_age(val_str):
    if pd.isna(val_str):
        return 0
    first_part = str(val_str).split('-')[0].strip()
    try:
        return int(first_part)
    except:
        return 0

def parse_market_value(val_str):
    if pd.isna(val_str):
        return 0
    first_part = str(val_str).split('-')[0].strip()
    clean_str = first_part.replace('€', '').replace(' ', '').replace('\xa0', '').strip()
    
    multiplier = 1
    if 'mln' in clean_str:
        multiplier = 1_000_000
        clean_str = clean_str.replace('mln', '').strip()
    elif 'tys.' in clean_str:
        multiplier = 1_000
        clean_str = clean_str.replace('tys.', '').strip()
        
    try:
        clean_str = clean_str.replace(',', '.')
        return float(clean_str) * multiplier
    except:
        return 0

def parse_wages(val_str):
    if pd.isna(val_str):
        return 0
    val_str = str(val_str).lower()
    first_part = val_str.split('-')[0].strip()
    clean_str = first_part.replace('€', '').replace(' ', '').replace('\xa0', '').strip()
    
    is_weekly = 'tydz' in clean_str or '/w' in clean_str
    clean_str = clean_str.replace('/tydz', '').replace('/rok', '').replace('/w', '').replace('/y', '').strip()
    
    multiplier = 1
    if 'mln' in clean_str:
        multiplier = 1_000_000
        clean_str = clean_str.replace('mln', '').strip()
    elif 'tys' in clean_str:
        multiplier = 1_000
        clean_str = clean_str.replace('tys.', '').replace('tys', '').strip()
        
    try:
        clean_str = clean_str.replace(',', '.')
        value = float(clean_str) * multiplier
        if is_weekly:
            value *= 52  # Normalizacja do skali rocznej
        return value
    except:
        return 0

# --- NOWA FUNKCJA Z BUFOROWANIEM (CACHING) ---
@st.cache_data(show_spinner="Przetwarzanie pliku CSV...")
def load_and_clean_data(file_buffer):
    file_buffer.seek(0) # Zabezpieczenie przed błędem odczytu po zmianie stanu
    df_loaded = pd.read_csv(file_buffer, sep=None, engine='python')
    df_loaded.columns = df_loaded.columns.astype(str).str.replace('\ufeff', '', regex=False).str.strip()
    
    df_loaded = df_loaded.rename(columns=TLUMACZENIE_KOLUMN)
    
    if 'Piłkarz' in df_loaded.columns:
        df_loaded = df_loaded[df_loaded['Piłkarz'].notna()]
    
    if 'Wiek' in df_loaded.columns:
        df_loaded['Wiek'] = df_loaded['Wiek'].apply(parse_age)
        df_loaded = df_loaded[df_loaded['Wiek'] > 0]
        
    if 'Cena' in df_loaded.columns:
        df_loaded['Wartość_Numeryczna'] = df_loaded['Cena'].apply(parse_market_value)
    else:
        df_loaded['Wartość_Numeryczna'] = 0

    if 'Płaca' in df_loaded.columns:
        df_loaded['Zarobki_Numeryczne'] = df_loaded['Płaca'].apply(parse_wages)
    else:
        df_loaded['Zarobki_Numeryczne'] = 0
        
    if 'Liga' in df_loaded.columns:
        df_loaded['Liga'] = df_loaded['Liga'].astype(str).str.replace('\xa0', ' ', regex=False).str.strip()
        df_loaded['Liga'] = df_loaded['Liga'].map(MAPOWANIE_NAZW_LIG).fillna(df_loaded['Liga'])
        
    return df_loaded

def calculate_score(df, position, weights_dict, ignore_mult=False):
    def get_col(name):
        if name in df.columns:
            cleaned = df[name].astype(str).str.replace('%', '', regex=False).str.replace(',', '.', regex=False).str.strip()
            return pd.to_numeric(cleaned, errors='coerce').fillna(0.0)
        return pd.Series(0.0, index=df.index)

    col_map = {
        'Oczekiwane asysty/90': get_col('Oczekiwane asysty/90'),
        'Kluczowe podania z gry/90': get_col('Kluczowe podania z gry/90'),
        'Liczba goli na 90 min': get_col('Liczba goli na 90 min'),
        'Oczekiwane gole na strzał': get_col('Oczekiwane gole na strzał'),
        'Skuteczność strzałów (%)': get_col('Skuteczność strzałów (%)'),
        'Udane próby pressingu/90': get_col('Udane próby pressingu/90'),
        'Przechwyty/90': get_col('Przechwyty/90'),
        'Odzyskane piłki/90': get_col('Odzyskane piłki/90'),
        '% wygranych pojedynków główkowych': get_col('% wygranych pojedynków główkowych') / 100.0,
        'Uniknięte oczekiwane gole/90': get_col('Uniknięte oczekiwane gole/90'),
        'Liczba dryblingów/90': get_col('Liczba dryblingów/90'),
        'Próby podań/90': get_col('Próby podań/90')
    }

    S = get_col('Próby podań/90')
    R = get_col('Stracone piłki/90')

    if 'Liga' in df.columns and not ignore_mult:
        ODWROTNE_MAPOWANIE = {v: k for k, v in MAPOWANIE_NAZW_LIG.items()}
        czyste_ligi = df['Liga'].map(ODWROTNE_MAPOWANIE).fillna(df['Liga']).astype(str).str.replace('\xa0', ' ', regex=False).str.strip()
        league_multiplier = czyste_ligi.map(MNOZNIKI_LIG).fillna(1.0)
    else:
        league_multiplier = pd.Series(1.0, index=df.index)

    retention = np.maximum(0, 1 - np.where(S == 0, 0, R / S))

    score = pd.Series(0.0, index=df.index)
    for stat_name, weight in weights_dict.items():
        if stat_name in col_map:
            score += col_map[stat_name] * weight
        
    return score * retention * league_multiplier

POZYCJE = ["Bramkarz", "Środkowy Obrońca", "Boczny Obrońca", "Defensywny Pomocnik", "Środkowy Pomocnik", "Skrzydłowy", "Napastnik"]

if "data_storage" not in st.session_state:
    st.session_state["data_storage"] = {pozycja: None for pozycja in POZYCJE}

def clear_filters(pozycja, min_a, max_a, max_p):
    st.session_state[f"search_{pozycja}"] = ""
    st.session_state[f"ligi_{pozycja}"] = []
    st.session_state[f"noga_{pozycja}"] = []
    st.session_state[f"age_{pozycja}"] = (min_a, max_a)
    st.session_state[f"price_range_{pozycja}"] = (0.0, float(max_p / 1_000_000))
    st.session_state[f"ignore_mult_{pozycja}"] = False
    if f"contract_{pozycja}" in st.session_state:
        st.session_state[f"contract_{pozycja}"] = False
    for stat_name, default_val in MERYTORYKA_WAG.get(pozycja, {}).items():
        if f"weight_{pozycja}_{stat_name}" in st.session_state:
            st.session_state[f"weight_{pozycja}_{stat_name}"] = float(default_val)

# Zaktualizowana kolejność: Wiek jest zawsze po Piłkarzu, a Preferowana noga zaraz po Wieku
KOLUMNY_PER_POZYCJA = {
    "Bramkarz": ['SCORE', 'Percentyl', 'Piłkarz', 'Wiek', 'Preferowana noga', 'Klub', 'Liga', 'Cena', 'Odzyskane piłki/90', 'Stracone piłki/90', 'Próby podań/90', 'Uniknięte oczekiwane gole/90'],
    "Środkowy Obrońca": ['SCORE', 'Percentyl', 'Piłkarz', 'Wiek', 'Preferowana noga', 'Klub', 'Liga', 'Cena', 'Kluczowe podania z gry/90', 'Udane próby pressingu/90', 'Przechwyty/90', 'Odzyskane piłki/90', 'Stracone piłki/90', 'Próby podań/90', '% wygranych pojedynków główkowych'],
    "Boczny Obrońca": ['SCORE', 'Percentyl', 'Piłkarz', 'Wiek', 'Preferowana noga', 'Klub', 'Liga', 'Pozycja', 'Cena', 'Oczekiwane asysty/90', 'Kluczowe podania z gry/90', 'Udane próby pressingu/90', 'Przechwyty/90', 'Odzyskane piłki/90', 'Stracone piłki/90', 'Próby podań/90'],
    "Defensywny Pomocnik": ['SCORE', 'Percentyl', 'Piłkarz', 'Wiek', 'Preferowana noga', 'Klub', 'Liga', 'Cena', 'Oczekiwane asysty/90', 'Kluczowe podania z gry/90', 'Udane próby pressingu/90', 'Przechwyty/90', 'Odzyskane piłki/90', 'Stracone piłki/90', 'Próby podań/90', '% wygranych pojedynków główkowych'],
    "Środkowy Pomocnik": ['SCORE', 'Percentyl', 'Piłkarz', 'Wiek', 'Preferowana noga', 'Klub', 'Liga', 'Cena', 'Oczekiwane asysty/90', 'Kluczowe podania z gry/90', 'Liczba goli na 90 min', 'Udane próby pressingu/90', 'Odzyskane piłki/90', 'Stracone piłki/90', 'Próby podań/90', 'Liczba dryblingów/90'],
    "Skrzydłowy": ['SCORE', 'Percentyl', 'Piłkarz', 'Wiek', 'Preferowana noga', 'Klub', 'Liga', 'Pozycja', 'Cena', 'Oczekiwane asysty/90', 'Kluczowe podania z gry/90', 'Liczba goli na 90 min', 'Oczekiwane gole na strzał', 'Udane próby pressingu/90', 'Odzyskane piłki/90', 'Stracone piłki/90', 'Próby podań/90', 'Liczba dryblingów/90'],
    "Napastnik": ['SCORE', 'Percentyl', 'Piłkarz', 'Wiek', 'Preferowana noga', 'Klub', 'Liga', 'Cena', 'Oczekiwane asysty/90', 'Kluczowe podania z gry/90', 'Liczba goli na 90 min', 'Oczekiwane gole na strzał', 'Skuteczność strzałów (%)', 'Udane próby pressingu/90', 'Odzyskane piłki/90', 'Stracone piłki/90', 'Próby podań/90', 'Liczba dryblingów/90']
}

# --- NAGŁÓWEK GŁÓWNY ---
st.markdown("<div style='font-size: 2.7rem; font-weight: bold; margin-top: -3.5rem; margin-bottom: 1rem;'>FM26 Moneyball Dashboard</div>", unsafe_allow_html=True)

# --- SIDEBAR (WYBÓR POZYCJI I WGACIE PLIKU) ---
with st.sidebar:
    st.markdown("### Wybierz pozycję")
    pozycja_nazwa = st.radio("Pozycja", POZYCJE, label_visibility="collapsed")
    st.markdown("---")
    
    st.markdown(f"<div style='font-size: 1.15rem; font-weight: 600; margin-bottom: 0.5rem;'>Arkusz: {pozycja_nazwa}</div>", unsafe_allow_html=True)
    file_key = f"uploader_{pozycja_nazwa}"
    uploaded_file = st.file_uploader("Wgraj plik CSV", type=["csv"], key=file_key, label_visibility="collapsed")
    st.markdown("---")

if uploaded_file is not None:
    try:
        processed_df = load_and_clean_data(uploaded_file)
        st.session_state["data_storage"][pozycja_nazwa] = processed_df
    except Exception as e:
        st.error(f"Wystąpił błąd podczas ładowania lub przetwarzania pliku: {e}")

df = st.session_state["data_storage"][pozycja_nazwa]

# --- DYNAMICZNE FILTRY W SIDEBARZE ---
if df is not None and not df.empty:
    zdefiniowana_kolejnosc = list(MAPOWANIE_NAZW_LIG.values())
    unikalne_ligi = df['Liga'].dropna().unique().tolist() if 'Liga' in df.columns else []
    dostepne_ligi = sorted(unikalne_ligi, key=lambda x: zdefiniowana_kolejnosc.index(x) if x in zdefiniowana_kolejnosc else 999)
    
    dostepne_nogi = sorted(df['Preferowana noga'].dropna().unique()) if 'Preferowana noga' in df.columns else []
    
    min_age = int(df['Wiek'].min()) if 'Wiek' in df.columns and not df.empty else 15
    max_age = int(df['Wiek'].max()) if 'Wiek' in df.columns and not df.empty else 45
    
    if 'Wartość_Numeryczna' in df.columns:
        valid_prices = df[df['Wartość_Numeryczna'] < 900_000_000]['Wartość_Numeryczna']
        max_price_avail = float(valid_prices.max()) if not valid_prices.empty else 100_000_000.0
    else:
        max_price_avail = 100_000_000.0
        
    if max_price_avail <= 0.0:
        max_price_avail = 100_000_000.0

    with st.sidebar:
        st.markdown("### Filtry wyszukiwania")
        ignore_mult = st.toggle("Ignoruj mnożnik ligowy", key=f"ignore_mult_{pozycja_nazwa}")
        search = st.text_input("Szukaj (Piłkarz / Klub):", key=f"search_{pozycja_nazwa}")
        wybrane_ligi = st.multiselect("Wybierz ligi:", options=dostepne_ligi, key=f"ligi_{pozycja_nazwa}")
        wybrana_noga = st.multiselect("Lepsza noga:", options=dostepne_nogi, key=f"noga_{pozycja_nazwa}")
        
        # --- FILTR KONCA KONTRAKTU ---
        filtr_kontraktu = False
        if 'Wygasa' in df.columns:
            filtr_kontraktu = st.checkbox("Tylko kontrakty do 6 mies.", key=f"contract_{pozycja_nazwa}")

        age_filter = st.slider("Wiek:", min_age, max_age, (min_age, max_age), key=f"age_{pozycja_nazwa}")
        price_filter_mln = st.slider(
            "Cena (mln €):", 
            0.0, float(max_price_avail / 1_000_000), 
            (0.0, float(max_price_avail / 1_000_000)), 
            key=f"price_range_{pozycja_nazwa}"
        )
        price_min_bytes = price_filter_mln[0] * 1_000_000
        price_max_bytes = price_filter_mln[1] * 1_000_000

        # --- EDYTOR WAG W SIDEBARZE ---
        st.markdown("### Zaawansowane wagi")
        custom_weights = {}
        defaults = MERYTORYKA_WAG.get(pozycja_nazwa, {})
        with st.expander("Modyfikuj wagi statystyk", expanded=False):
            for stat_name, default_val in defaults.items():
                max_slider = float(max(200.0, default_val * 2.5))
                step_val = 0.1 if isinstance(default_val, float) and default_val < 5.0 else 1.0
                custom_weights[stat_name] = st.slider(
                    f"{stat_name}:",
                    min_value=0.0,
                    max_value=max_slider,
                    value=float(default_val),
                    step=step_val,
                    key=f"weight_{pozycja_nazwa}_{stat_name}"
                )

        st.button(
            "Wyczyść filtry", 
            key=f"btn_clear_{pozycja_nazwa}", 
            on_click=clear_filters, 
            args=(pozycja_nazwa, min_age, max_age, max_price_avail), 
            use_container_width=True
        )

    # --- REKALKULACJA I FILTROWANIE ---
    base_df = df.copy()
    temp_df = base_df.copy()
        
    base_df['SCORE'] = calculate_score(temp_df, pozycja_nazwa, custom_weights, ignore_mult=ignore_mult)
    
    if 'SCORE' in base_df.columns and not base_df.empty:
        base_df['Percentyl'] = base_df['SCORE'].rank(pct=True) * 100
    else:
        base_df['Percentyl'] = 0.0

    filtered_df = base_df.copy()
        
    if 'Wiek' in filtered_df.columns:
        filtered_df = filtered_df[(filtered_df['Wiek'] >= age_filter[0]) & (filtered_df['Wiek'] <= age_filter[1])]
    if 'Wartość_Numeryczna' in filtered_df.columns:
        filtered_df = filtered_df[
            (filtered_df['Wartość_Numeryczna'] >= price_min_bytes) & 
            (filtered_df['Wartość_Numeryczna'] <= price_max_bytes)
        ]
        
    if 'Liga' in filtered_df.columns and wybrane_ligi:
        filtered_df = filtered_df[filtered_df['Liga'].isin(wybrane_ligi)]
        
    if 'Preferowana noga' in filtered_df.columns and wybrana_noga:
        filtered_df = filtered_df[filtered_df['Preferowana noga'].isin(wybrana_noga)]
        
    if 'Wygasa' in filtered_df.columns and filtr_kontraktu:
        expiry_dates = pd.to_datetime(filtered_df['Wygasa'], dayfirst=True, errors='coerce')
        if not expiry_dates.dropna().empty:
            filtered_df = filtered_df[expiry_dates <= (expiry_dates.min() + pd.Timedelta(days=180))]
    
    if search:
        cond = pd.Series(False, index=filtered_df.index)
        if 'Piłkarz' in filtered_df.columns:
            cond |= filtered_df['Piłkarz'].str.contains(search, case=False, na=False)
        if 'Klub' in filtered_df.columns:
            cond |= filtered_df['Klub'].str.contains(search, case=False, na=False)
        filtered_df = filtered_df[cond]
        
    if 'SCORE' in filtered_df.columns:
        filtered_df = filtered_df.sort_values(by="SCORE", ascending=False)

    # --- TABELA GŁÓWNA WYNIKÓW ---
    dedykowane_kolumny = KOLUMNY_PER_POZYCJA.get(pozycja_nazwa, [])
    cols_to_show = [c for c in dedykowane_kolumny if c in filtered_df.columns]
    
    if len(cols_to_show) <= 2:
        zapasowe_kolumny = ['SCORE', 'Percentyl', 'Piłkarz', 'Wiek', 'Preferowana noga', 'Klub', 'Liga', 'Cena']
        cols_to_show = [c for c in zapasowe_kolumny if c in filtered_df.columns]

    if 'Płaca' in filtered_df.columns and 'Płaca' not in cols_to_show:
        idx = cols_to_show.index('Cena') + 1 if 'Cena' in cols_to_show else len(cols_to_show)
        cols_to_show.insert(idx, 'Płaca')
        
    if 'Wygasa' in filtered_df.columns and 'Wygasa' not in cols_to_show:
        if 'Płaca' in cols_to_show:
            idx_wygasa = cols_to_show.index('Płaca') + 1
            cols_to_show.insert(idx_wygasa, 'Wygasa')
        else:
            idx_wygasa = cols_to_show.index('Cena') + 1 if 'Cena' in cols_to_show else len(cols_to_show)
            cols_to_show.insert(idx_wygasa, 'Wygasa')

    format_dict = {}
    if 'SCORE' in filtered_df.columns:
        format_dict['SCORE'] = '{:.0f}'
    if 'Wiek' in filtered_df.columns:
        format_dict['Wiek'] = '{:.0f}'
    
    for col in cols_to_show:
        if col not in ['SCORE', 'Percentyl', 'Wiek', 'Piłkarz', 'Klub', 'Liga', 'Pozycja', 'Cena', 'Płaca', 'Wygasa', 'Kraj', 'Preferowana noga'] and pd.api.types.is_numeric_dtype(filtered_df[col]):
            format_dict[col] = '{:.1f}'

    jasna_paleta = mcolors.LinearSegmentedColormap.from_list("jasne_kolory", ["#ff9999", "#ffff99", "#99ff99"])

    def highlight_tottenham(row):
        if 'Klub' in row.index and pd.notna(row['Klub']) and 'Tottenham' in str(row['Klub']):
            return ['background-color: #282933;' for _ in row]
        return ['' for _ in row]

    df_style = filtered_df[cols_to_show].style.format(format_dict)
    df_style = df_style.apply(highlight_tottenham, axis=1)

    if 'SCORE' in cols_to_show:
        df_style = df_style.background_gradient(subset=['SCORE'], cmap=jasna_paleta)
        df_style = df_style.set_properties(subset=['SCORE'], **{'color': 'black', 'text-align': 'center'})

    df_style = df_style.set_table_styles([
        {'selector': 'th', 'props': [('text-align', 'center')]}
    ], overwrite=False)

    col_config = {}
    if 'SCORE' in cols_to_show:
        col_config['SCORE'] = st.column_config.Column("SCORE", alignment="center")
    
    if 'Percentyl' in cols_to_show:
        col_config['Percentyl'] = st.column_config.ProgressColumn(
            "Percentyl",
            help="Wartość od 0 do 100 (na tle całej wgranej bazy)",
            format="%.0f",
            min_value=0,
            max_value=100,
            width="small"
        )

    st.dataframe(
        df_style,
        use_container_width=True, 
        height=400,
        hide_index=True,
        column_config=col_config
    )
    
    # --- NOWA SEKCJA: WYKRES RADAROWY W PORÓWNYWARCE ---
    st.markdown("---")
    st.subheader("Porównanie zawodników", anchor=False)
    
    zawodnicy_do_porownania = st.multiselect(
        "Wybierz dokładnie dwóch zawodników z tabeli, aby nałożyć ich statystyki na radar percentylowy:",
        options=filtered_df['Piłkarz'].unique() if 'Piłkarz' in filtered_df.columns else [],
        max_selections=2,
        key=f"compare_{pozycja_nazwa}"
    )

    if len(zawodnicy_do_porownania) == 2:
        df_compare = filtered_df[filtered_df['Piłkarz'].isin(zawodnicy_do_porownania)]
        
        kolumny_ignorowane_porownanie = ['SCORE', 'Percentyl', 'Piłkarz', 'Wiek', 'Klub', 'Liga', 'Pozycja', 'Cena', 'Preferowana noga', 'Kraj', 'Wartość_Numeryczna', 'Zarobki_Numeryczne', 'Płaca', 'Wygasa']
        stat_cols = [c for c in dedykowane_kolumny if c not in kolumny_ignorowane_porownanie and c in df_compare.columns]
        
        if stat_cols:
            fig = go.Figure()
            
            for _, row in df_compare.iterrows():
                player_name = row['Piłkarz']
                player_percentiles = []
                
                for col in stat_cols:
                    try:
                        base_series = pd.to_numeric(df[col].astype(str).str.replace('%', '', regex=False).str.replace(',', '.', regex=False).str.strip(), errors='coerce').fillna(0.0)
                        player_val = pd.to_numeric(str(row[col]).replace('%', '').replace(',', '.').strip(), errors='coerce')
                        if pd.isna(player_val): player_val = 0.0
                        
                        pct_rank = (base_series < player_val).sum() / len(base_series) * 100
                        player_percentiles.append(pct_rank)
                    except:
                        player_percentiles.append(0.0)
                
                player_percentiles += [player_percentiles[0]]
                categories_loop = stat_cols + [stat_cols[0]]
                
                fig.add_trace(go.Scatterpolar(
                    r=player_percentiles,
                    theta=categories_loop,
                    fill='toself',
                    name=player_name,
                    mode='lines+markers',
                    opacity=0.5,
                    marker=dict(size=8),
                    hovertemplate="<b>%{fullData.name}</b><br>%{theta}: %{r:.1f}%<extra></extra>"
                ))
                
            fig.update_layout(
                paper_bgcolor='#262730',
                plot_bgcolor='#262730',
                polar=dict(
                    bgcolor='#262730',
                    radialaxis=dict(
                        visible=True,
                        showticklabels=False,  
                        range=[0, 100],
                        gridcolor='rgba(255, 255, 255, 0.15)'
                    ),
                    angularaxis=dict(
                        gridcolor='rgba(255, 255, 255, 0.15)',
                        tickfont=dict(color='white')
                    )
                ),
                font=dict(
                    family="Arial",
                    size=14,
                    color="white"
                ),
                legend=dict(
                    orientation="v",
                    x=-0.2,
                    y=0.5,
                    xanchor='right',
                    yanchor='middle',
                    font=dict(size=16, color="white")
                ),
                showlegend=True,
                height=500,
                margin=dict(t=40, b=40, l=120, r=40)
            )
            
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Brak szczegółowych statystyk meczowych do wygenerowania radaru.")
    elif len(zawodnicy_do_porownania) == 1:
        st.info("Wybierz jeszcze drugiego zawodnika z listy.")

    # --- NOWA SEKCJA: ZNAJDŹ SOBOWTÓRA ---
    st.markdown("---")
    st.subheader("Znajdź sobowtóra", anchor=False)
    st.markdown("Wybierz gwiazdę ze swojej drużyny. Algorytm na podstawie dystansu kosinusowego przeanalizuje styl gry (statystyki per 90 minut) i wskaże 5 graczy z przefiltrowanej bazy o najwierniej odwzorowanym profilu (np. tanie, młode zastępstwo).")
    
    opcje_sobowtor = [""] + list(filtered_df['Piłkarz'].unique()) if 'Piłkarz' in filtered_df.columns else [""]
    zawodnik_do_zastapienia = st.selectbox(
        "Kogo chcesz zastąpić?",
        options=opcje_sobowtor,
        key=f"ml_clone_{pozycja_nazwa}"
    )

    if zawodnik_do_zastapienia:
        kolumny_ignorowane_ml = ['SCORE', 'Percentyl', 'Piłkarz', 'Wiek', 'Klub', 'Liga', 'Pozycja', 'Cena', 'Preferowana noga', 'Kraj', 'Wartość_Numeryczna', 'Zarobki_Numeryczne', 'Płaca', 'Wygasa']
        cechy_ml = [c for c in filtered_df.columns if c not in kolumny_ignorowane_ml]

        if cechy_ml:
            ml_data = pd.DataFrame(index=filtered_df.index)
            for c in cechy_ml:
                ml_data[c] = pd.to_numeric(
                    filtered_df[c].astype(str).str.replace('%', '', regex=False).str.replace(',', '.', regex=False).str.strip(), 
                    errors='coerce'
                ).fillna(0.0)
            
            if zawodnik_do_zastapienia in filtered_df['Piłkarz'].values:
                # Skalowanie Danych
                scaler = StandardScaler()
                X_scaled = scaler.fit_transform(ml_data)
                
                # Znalezienie indeksu wybranego zawodnika
                df_reset = filtered_df.reset_index()
                idx_w_macierzy = df_reset.index[df_reset['Piłkarz'] == zawodnik_do_zastapienia].tolist()[0]
                wektor_zawodnika = X_scaled[idx_w_macierzy].reshape(1, -1)
                
                # Użycie Cosine Similarity (Podobieństwo Kosinusowe)
                podobienswa = cosine_similarity(wektor_zawodnika, X_scaled)[0]
                
                df_wyniki = filtered_df.copy()
                df_wyniki['Podobieństwo'] = podobienswa
                
                # Wyciągnięcie top 5 i pozbycie się z wyników samego poszukiwanego gracza
                top_5_podobnych = df_wyniki[df_wyniki['Piłkarz'] != zawodnik_do_zastapienia].sort_values(by='Podobieństwo', ascending=False).head(5)
                
                # Ustawienie nazwy "Zgodność"
                top_5_podobnych['Zgodność'] = (top_5_podobnych['Podobieństwo'].clip(0, 1) * 100).round(1).astype(str) + "%"
                
                st.success(f"Oto 5 najlepszych alternatyw dla: **{zawodnik_do_zastapienia}** (wśród widocznych w tabeli zawodników)")
                
                # Ściśle określona kolejność kolumn przez użytkownika
                kolumny_do_pokazania_ml = ['SCORE', 'Zgodność', 'Piłkarz', 'Wiek', 'Preferowana noga', 'Klub', 'Liga', 'Pozycja', 'Cena', 'Płaca', 'Wygasa']
                # Bezpieczne filtrowanie w razie gdyby jakiejś kolumny nie było w arkuszu (np. Pozycji u Bramkarza)
                kolumny_do_pokazania_ml = [c for c in kolumny_do_pokazania_ml if c in top_5_podobnych.columns]
                
                # --- STYLOWANIE TABELI ML ---
                format_dict_ml = {}
                if 'SCORE' in kolumny_do_pokazania_ml:
                    format_dict_ml['SCORE'] = '{:.0f}'
                if 'Wiek' in kolumny_do_pokazania_ml:
                    format_dict_ml['Wiek'] = '{:.0f}'
                
                df_ml_style = top_5_podobnych[kolumny_do_pokazania_ml].style.format(format_dict_ml)
                df_ml_style = df_ml_style.apply(highlight_tottenham, axis=1)

                if 'SCORE' in kolumny_do_pokazania_ml:
                    df_ml_style = df_ml_style.background_gradient(subset=['SCORE'], cmap=jasna_paleta)
                    df_ml_style = df_ml_style.set_properties(subset=['SCORE'], **{'color': 'black', 'text-align': 'center'})

                df_ml_style = df_ml_style.set_table_styles([
                    {'selector': 'th', 'props': [('text-align', 'center')]}
                ], overwrite=False)

                col_config_ml = {
                    'Zgodność': st.column_config.TextColumn("Zgodność", help="Procentowe podobieństwo kształtu statystyk meczowych do poszukiwanego zawodnika."),
                    'SCORE': st.column_config.Column("SCORE", alignment="center")
                }
                
                st.dataframe(
                    df_ml_style,
                    use_container_width=True,
                    hide_index=True,
                    column_config=col_config_ml
                )
            else:
                st.warning("Wybrany zawodnik nie spełnia obecnych filtrów w panelu bocznym. Zmień filtry (np. wiek, cenę, ligę), aby aplikacja mogła załadować jego statystyki.")
        else:
            st.info("Brak wystarczających kolumn liczbowych do uruchomienia algorytmu uczenia maszynowego.")
        
    # --- SEKCJA WYKRESÓW (Moneyball i Top 10) ---
    if 'Wartość_Numeryczna' in filtered_df.columns and 'SCORE' in filtered_df.columns:
        st.markdown("---")
        st.subheader("Score vs Cena (Top 30)", anchor=False)
        
        chart_data = filtered_df[filtered_df['Wartość_Numeryczna'] < 900_000_000].head(30)
        
        if not chart_data.empty:
            min_val = float(chart_data['Wartość_Numeryczna'].min())
            max_val = float(chart_data['Wartość_Numeryczna'].max())
            min_score = float(chart_data['SCORE'].min())
            max_score = float(chart_data['SCORE'].max())
            
            score_margin = (max_score - min_score) * 0.05
            if score_margin == 0: 
                score_margin = max_score * 0.05 if max_score != 0 else 1
            
            tooltip_cols = [
                alt.Tooltip('Piłkarz:N', title='Piłkarz'),
                alt.Tooltip('Wiek:Q', title='Wiek', format='.0f'),
                alt.Tooltip('Klub:N', title='Klub'),
                alt.Tooltip('Cena:N', title='Cena'),
                alt.Tooltip('SCORE:Q', title='SCORE', format='.0f'),
                alt.Tooltip('Percentyl:Q', title='Percentyl', format='.0f'),
                alt.Tooltip('Liga:N', title='Liga')
            ]
            if 'Płaca' in chart_data.columns:
                tooltip_cols.append(alt.Tooltip('Płaca:N', title='Płaca'))
            
            chart = alt.Chart(chart_data).mark_circle(size=300).encode(
                x=alt.X('Wartość_Numeryczna', 
                        title='Cena',
                        scale=alt.Scale(domain=[min_val - 3000000, max_val + (max_val*0.1)])),
                y=alt.Y('SCORE:Q', 
                        title='Score', 
                        axis=alt.Axis(format='.0f'),
                        scale=alt.Scale(zero=False, domain=[min_score - score_margin, max_score + score_margin])),
                color=alt.Color('Piłkarz', legend=None),
                tooltip=tooltip_cols
            ).properties(height=500)
                
            st.altair_chart(chart.interactive(), use_container_width=True)

            st.markdown("---")
            st.subheader("Najlepsi zawodnicy w poszczególnych statystykach (Top 10)", anchor=False)
            
            kolumny_ignorowane = ['SCORE', 'Percentyl', 'Piłkarz', 'Wiek', 'Klub', 'Liga', 'Pozycja', 'Cena', 'Preferowana noga', 'Kraj', 'Wartość_Numeryczna', 'Płaca', 'Zarobki_Numeryczne', 'Wygasa']
            kolumny_statystyk = [c for c in dedykowane_kolumny if c not in kolumny_ignorowane and c in filtered_df.columns]
            
            if kolumny_statystyk:
                cols = st.columns(2)
                for idx, stat_col in enumerate(kolumny_statystyk):
                    with cols[idx % 2]:
                        is_percent = '%' in stat_col
                        stat_format = '.1f' if not is_percent else '.0f'
                        
                        temp_series = pd.to_numeric(
                            filtered_df[stat_col].astype(str).str.replace('%', '', regex=False).str.replace(',', '.', regex=False).str.strip(), 
                            errors='coerce'
                        ).fillna(0.0)
                        
                        if stat_col == 'Stracone piłki/90':
                            top10_indices = temp_series.nsmallest(10).index
                            sort_order = 'x'
                        else:
                            top10_indices = temp_series.nlargest(10).index
                            sort_order = '-x'
                            
                        stat_bar_data = filtered_df.loc[top10_indices].copy()
                        stat_bar_data[stat_col] = temp_series.loc[top10_indices]
                        
                        bar_chart = alt.Chart(stat_bar_data).mark_bar().encode(
                            x=alt.X(field=stat_col, type='quantitative', title=stat_col),
                            y=alt.Y('Piłkarz', type='nominal', sort=sort_order, title=''),
                            color=alt.Color('SCORE:Q', scale=alt.Scale(scheme='blues'), legend=None),
                            tooltip=tooltip_cols + [alt.Tooltip(f'{stat_col}:Q', title=stat_col, format=stat_format)]
                        ).properties(height=350, title=stat_col)
                        
                        st.altair_chart(bar_chart.interactive(), use_container_width=True)