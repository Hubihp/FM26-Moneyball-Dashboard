import streamlit as st
import pandas as pd
import altair as alt
import numpy as np
import matplotlib.colors as mcolors
import plotly.graph_objects as go

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
    "Bramkarz": {'Uniknięte oczekiwane gole/90 (BR)': 130.0, 'Odzyskane piłki/90': 30.0, 'Próby podań/90': 0.5},
    "Środkowy Obrońca": {'% wygranych pojedynków główkowych': 15.0, 'Przechwyty/90': 20.0, 'Udane próby pressingu/90': 5.0, 'Kluczowe podania z gry/90': 20.0, 'Odzyskane piłki/90': 8.0},
    "Boczny Obrońca": {'xA/90': 100.0, 'Kluczowe podania z gry/90': 60.0, 'Przechwyty/90': 12.0, 'Odzyskane piłki/90': 6.0, 'Udane próby pressingu/90': 8.0},
    "Defensywny Pomocnik": {'xA/90': 9.0, 'Kluczowe podania z gry/90': 40.0, 'Przechwyty/90': 9.0, 'Odzyskane piłki/90': 9.0, 'Udane próby pressingu/90': 9.0, '% wygranych pojedynków główkowych': 5.0},
    "Środkowy Pomocnik": {'xA/90': 80.0, 'Liczba goli/90': 40.0, 'Kluczowe podania z gry/90': 60.0, 'Liczba dryblingów/90': 12.0, 'Odzyskane piłki/90': 8.0, 'Udane próby pressingu/90': 8.0},
    "Skrzydłowy": {'xA/90': 96.0, 'Liczba goli/90': 80.0, 'Oczekiwane gole na strzał': 58.0, 'Kluczowe podania z gry/90': 40.0, 'Liczba dryblingów/90': 16.0, 'Udane próby pressingu/90': 6.0, 'Odzyskane piłki/90': 6.0},
    "Napastnik": {'Liczba goli/90': 180.0, 'Oczekiwane gole na strzał': 60.0, 'xA/90': 80.0, 'Kluczowe podania z gry/90': 40.0, 'Liczba dryblingów/90': 15.0, 'Udane próby pressingu/90': 8.0, 'Odzyskane piłki/90': 8.0, 'Skuteczność (%)': 1.0}
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

def calculate_score(df, position, weights_dict, ignore_mult=False):
    def get_col(name):
        if name in df.columns:
            cleaned = df[name].astype(str).str.replace('%', '', regex=False).str.replace(',', '.', regex=False).str.strip()
            return pd.to_numeric(cleaned, errors='coerce').fillna(0.0)
        return pd.Series(0.0, index=df.index)

    col_map = {
        'xA/90': get_col('xA/90'),
        'Kluczowe podania z gry/90': get_col('Kluczowe podania z gry/90'),
        'Liczba goli/90': get_col('Liczba goli/90'),
        'Oczekiwane gole na strzał': get_col('Oczekiwane gole na strzał'),
        'Skuteczność (%)': get_col('Skuteczność (%)'),
        'Udane próby pressingu/90': get_col('Udane próby pressingu/90'),
        'Przechwyty/90': get_col('Przechwyty/90'),
        'Odzyskane piłki/90': get_col('Odzyskane piłki/90'),
        '% wygranych pojedynków główkowych': get_col('% wygranych pojedynków główkowych') / 100.0,
        'Uniknięte oczekiwane gole/90 (BR)': get_col('Uniknięte oczekiwane gole/90 (BR)'),
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

KOLUMNY_PER_POZYCJA = {
    "Bramkarz": ['SCORE', 'Percentyl', 'Nazwisko', 'Wiek', 'Klub', 'Liga', 'Wartość', 'Noga', 'Odzyskane piłki/90', 'Stracone piłki/90', 'Próby podań/90', 'Uniknięte oczekiwane gole/90 (BR)'],
    "Środkowy Obrońca": ['SCORE', 'Percentyl', 'Nazwisko', 'Wiek', 'Klub', 'Liga', 'Wartość', 'Noga', 'Kluczowe podania z gry/90', 'Udane próby pressingu/90', 'Przechwyty/90', 'Odzyskane piłki/90', 'Stracone piłki/90', 'Próby podań/90', '% wygranych pojedynków główkowych'],
    "Boczny Obrońca": ['SCORE', 'Percentyl', 'Nazwisko', 'Wiek', 'Klub', 'Liga', 'Pozycja', 'Wartość', 'Noga', 'xA/90', 'Kluczowe podania z gry/90', 'Udane próby pressingu/90', 'Przechwyty/90', 'Odzyskane piłki/90', 'Stracone piłki/90', 'Próby podań/90'],
    "Defensywny Pomocnik": ['SCORE', 'Percentyl', 'Nazwisko', 'Wiek', 'Klub', 'Liga', 'Wartość', 'Noga', 'xA/90', 'Kluczowe podania z gry/90', 'Udane próby pressingu/90', 'Przechwyty/90', 'Odzyskane piłki/90', 'Stracone piłki/90', 'Próby podań/90', '% wygranych pojedynków główkowych'],
    "Środkowy Pomocnik": ['SCORE', 'Percentyl', 'Nazwisko', 'Wiek', 'Klub', 'Liga', 'Wartość', 'Noga', 'xA/90', 'Kluczowe podania z gry/90', 'Liczba goli/90', 'Udane próby pressingu/90', 'Odzyskane piłki/90', 'Stracone piłki/90', 'Próby podań/90', 'Liczba dryblingów/90'],
    "Skrzydłowy": ['SCORE', 'Percentyl', 'Nazwisko', 'Klub', 'Wiek', 'Liga', 'Pozycja', 'Wartość', 'Noga', 'xA/90', 'Kluczowe podania z gry/90', 'Liczba goli/90', 'Oczekiwane gole na strzał', 'Udane próby pressingu/90', 'Odzyskane piłki/90', 'Stracone piłki/90', 'Próby podań/90', 'Liczba dryblingów/90'],
    "Napastnik": ['SCORE', 'Percentyl', 'Nazwisko', 'Klub', 'Wiek', 'Liga', 'Wartość', 'Noga', 'xA/90', 'Kluczowe podania z gry/90', 'Liczba goli/90', 'Oczekiwane gole na strzał', 'Skuteczność (%)', 'Udane próby pressingu/90', 'Odzyskane piłki/90', 'Stracone piłki/90', 'Próby podań/90', 'Liczba dryblingów/90']
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
    current_file_id = getattr(uploaded_file, "file_id", uploaded_file.name + str(uploaded_file.size))
    processed_key = f"processed_{pozycja_nazwa}"
    
    if processed_key not in st.session_state or st.session_state[processed_key] != current_file_id:
        try:
            loaded_df = pd.read_csv(uploaded_file, sep=None, engine='python')
            loaded_df.columns = loaded_df.columns.astype(str).str.replace('\ufeff', '', regex=False).str.strip()
            
            if 'Nazwisko' in loaded_df.columns:
                loaded_df = loaded_df[loaded_df['Nazwisko'].notna()]
            
            if 'Wiek' in loaded_df.columns:
                loaded_df['Wiek'] = loaded_df['Wiek'].apply(parse_age)
                loaded_df = loaded_df[loaded_df['Wiek'] > 0]
                
            if 'Wartość' in loaded_df.columns:
                loaded_df['Wartość_Numeryczna'] = loaded_df['Wartość'].apply(parse_market_value)
            else:
                loaded_df['Wartość_Numeryczna'] = 0

            if 'Zarobki' in loaded_df.columns:
                loaded_df['Zarobki_Numeryczne'] = loaded_df['Zarobki'].apply(parse_wages)
            else:
                loaded_df['Zarobki_Numeryczne'] = 0
                
            loaded_df['Liga'] = loaded_df['Liga'].astype(str).str.replace('\xa0', ' ', regex=False).str.strip()
            loaded_df['Liga'] = loaded_df['Liga'].map(MAPOWANIE_NAZW_LIG).fillna(loaded_df['Liga'])
            
            st.session_state["data_storage"][pozycja_nazwa] = loaded_df
            st.session_state[processed_key] = current_file_id
            
        except Exception as e:
            pass

df = st.session_state["data_storage"][pozycja_nazwa]

# --- DYNAMICZNE FILTRY W SIDEBARZE ---
if df is not None and not df.empty:
    zdefiniowana_kolejnosc = list(MAPOWANIE_NAZW_LIG.values())
    unikalne_ligi = df['Liga'].dropna().unique().tolist() if 'Liga' in df.columns else []
    dostepne_ligi = sorted(unikalne_ligi, key=lambda x: zdefiniowana_kolejnosc.index(x) if x in zdefiniowana_kolejnosc else 999)
    
    dostepne_nogi = sorted(df['Noga'].dropna().unique()) if 'Noga' in df.columns else []
    
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
        if 'Koniec kontraktu' in df.columns:
            filtr_kontraktu = st.checkbox("Tylko kończące się kontrakty (do 6 mies.)", key=f"contract_{pozycja_nazwa}")

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
        st.markdown("### Zaawansowane Wagi")
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
        
    if 'Noga' in filtered_df.columns and wybrana_noga:
        filtered_df = filtered_df[filtered_df['Noga'].isin(wybrana_noga)]
        
    if 'Koniec kontraktu' in filtered_df.columns and filtr_kontraktu:
        expiry_dates = pd.to_datetime(filtered_df['Koniec kontraktu'], dayfirst=True, errors='coerce')
        if not expiry_dates.dropna().empty:
            filtered_df = filtered_df[expiry_dates <= (expiry_dates.min() + pd.Timedelta(days=180))]
    
    if search:
        cond = pd.Series(False, index=filtered_df.index)
        if 'Nazwisko' in filtered_df.columns:
            cond |= filtered_df['Nazwisko'].str.contains(search, case=False, na=False)
        if 'Klub' in filtered_df.columns:
            cond |= filtered_df['Klub'].str.contains(search, case=False, na=False)
        filtered_df = filtered_df[cond]
        
    if 'SCORE' in filtered_df.columns:
        filtered_df = filtered_df.sort_values(by="SCORE", ascending=False)

    # --- TABELA GŁÓWNA WYNIKÓW ---
    dedykowane_kolumny = KOLUMNY_PER_POZYCJA.get(pozycja_nazwa, [])
    cols_to_show = [c for c in dedykowane_kolumny if c in filtered_df.columns]
    
    if len(cols_to_show) <= 2:
        zapasowe_kolumny = ['SCORE', 'Percentyl', 'Nazwisko', 'Klub', 'Liga', 'Wiek', 'Wartość']
        cols_to_show = [c for c in zapasowe_kolumny if c in filtered_df.columns]

    if 'Zarobki' in filtered_df.columns and 'Zarobki' not in cols_to_show:
        idx = cols_to_show.index('Wartość') + 1 if 'Wartość' in cols_to_show else len(cols_to_show)
        cols_to_show.insert(idx, 'Zarobki')
    if 'Koniec kontraktu' in filtered_df.columns and 'Koniec kontraktu' not in cols_to_show:
        cols_to_show.append('Koniec kontraktu')

    format_dict = {}
    if 'SCORE' in filtered_df.columns:
        format_dict['SCORE'] = '{:.0f}'
    if 'Wiek' in filtered_df.columns:
        format_dict['Wiek'] = '{:.0f}'
    
    for col in cols_to_show:
        if col not in ['SCORE', 'Percentyl', 'Wiek', 'Nazwisko', 'Klub', 'Liga', 'Pozycja', 'Wartość', 'Zarobki', 'Koniec kontraktu', 'Kraj', 'Noga'] and pd.api.types.is_numeric_dtype(filtered_df[col]):
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
        options=filtered_df['Nazwisko'].unique() if 'Nazwisko' in filtered_df.columns else [],
        max_selections=2,
        key=f"compare_{pozycja_nazwa}"
    )

    if len(zawodnicy_do_porownania) == 2:
        df_compare = filtered_df[filtered_df['Nazwisko'].isin(zawodnicy_do_porownania)]
        
        kolumny_ignorowane_porownanie = ['SCORE', 'Percentyl', 'Nazwisko', 'Wiek', 'Klub', 'Liga', 'Pozycja', 'Wartość', 'Noga', 'Kraj', 'Wartość_Numeryczna', 'Zarobki_Numeryczne', 'Zarobki', 'Koniec kontraktu']
        stat_cols = [c for c in dedykowane_kolumny if c not in kolumny_ignorowane_porownanie and c in df_compare.columns]
        
        if stat_cols:
            fig = go.Figure()
            
            for _, row in df_compare.iterrows():
                player_name = row['Nazwisko']
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
        
    # --- SEKCJA WYKRESÓW (Moneyball i Top 10) ---
    if 'Wartość_Numeryczna' in filtered_df.columns and 'SCORE' in filtered_df.columns:
        st.markdown("---")
        st.subheader("Cena vs Control Score (Top 30)", anchor=False)
        
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
                alt.Tooltip('Nazwisko:N', title='Nazwisko'),
                alt.Tooltip('Wiek:Q', title='Wiek', format='.0f'),
                alt.Tooltip('Klub:N', title='Klub'),
                alt.Tooltip('Wartość:N', title='Wartość'),
                alt.Tooltip('SCORE:Q', title='SCORE', format='.0f'),
                alt.Tooltip('Percentyl:Q', title='Percentyl', format='.0f'),
                alt.Tooltip('Liga:N', title='Liga')
            ]
            if 'Zarobki' in chart_data.columns:
                tooltip_cols.append(alt.Tooltip('Zarobki:N', title='Zarobki'))
            
            chart = alt.Chart(chart_data).mark_circle(size=300).encode(
                x=alt.X('Wartość_Numeryczna', 
                        title='Wartość',
                        scale=alt.Scale(domain=[min_val - 3000000, max_val + (max_val*0.1)])),
                y=alt.Y('SCORE:Q', 
                        title='Control Score', 
                        axis=alt.Axis(format='.0f'),
                        scale=alt.Scale(zero=False, domain=[min_score - score_margin, max_score + score_margin])),
                color=alt.Color('Nazwisko', legend=None),
                tooltip=tooltip_cols
            ).properties(height=500)
                
            st.altair_chart(chart.interactive(), use_container_width=True)

            st.markdown("---")
            st.subheader("Najlepsi zawodnicy w poszczególnych statystykach (Top 10)", anchor=False)
            
            kolumny_ignorowane = ['SCORE', 'Percentyl', 'Nazwisko', 'Wiek', 'Klub', 'Liga', 'Pozycja', 'Wartość', 'Noga', 'Kraj', 'Wartość_Numeryczna', 'Zarobki', 'Zarobki_Numeryczne', 'Koniec kontraktu']
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
                            y=alt.Y('Nazwisko', type='nominal', sort=sort_order, title=''),
                            color=alt.Color('SCORE:Q', scale=alt.Scale(scheme='blues'), legend=None),
                            tooltip=tooltip_cols + [alt.Tooltip(f'{stat_col}:Q', title=stat_col, format=stat_format)]
                        ).properties(height=350, title=stat_col)
                        
                        st.altair_chart(bar_chart.interactive(), use_container_width=True)