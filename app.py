import streamlit as st
import pandas as pd
import altair as alt
import numpy as np
import matplotlib.colors as mcolors

# Konfiguracja strony
st.set_page_config(page_title="FM26 Moneyball Dashboard", layout="wide")

# Ukrywanie alertów po 5 sekundach i usuwanie ikon hiperłączy (anchor links) z nagłówków
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
    </style>
""", unsafe_allow_html=True)

# Możniki lig
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

def calculate_score(df, position, ignore_mult=False):
    def get_col(name):
        if name in df.columns:
            cleaned = df[name].astype(str).str.replace('%', '', regex=False).str.replace(',', '.', regex=False).str.strip()
            return pd.to_numeric(cleaned, errors='coerce').fillna(0.0)
        return pd.Series(0.0, index=df.index)

    J = get_col('xA/90')
    K = get_col('Kluczowe podania z gry/90')
    L = get_col('Liczba goli/90')
    M = get_col('Oczekiwane gole na strzał')
    N = get_col('Skuteczność (%)')
    O = get_col('Udane próby pressingu/90')
    P = get_col('Przechwyty/90')
    Q = get_col('Odzyskane piłki/90')
    R = get_col('Stracone piłki/90')
    S = get_col('Próby podań/90')
    T = get_col('% wygranych pojedynków główkowych')
    U = get_col('Uniknięte oczekiwane gole/90 (BR)')
    V = get_col('Liczba dryblingów/90')

    if 'Liga' in df.columns and not ignore_mult:
        czyste_ligi = df['Liga'].astype(str).str.replace('\xa0', ' ', regex=False).str.strip()
        league_multiplier = czyste_ligi.map(MNOZNIKI_LIG).fillna(1.0)
    else:
        league_multiplier = pd.Series(1.0, index=df.index)

    retention = np.maximum(0, 1 - np.where(S == 0, 0, R / S))

    if position == "Bramkarz":
        score = ((U * 130) + (Q * 30) + (S * 0.5)) * retention * league_multiplier
    elif position == "Środkowy Obrońca":
        score = (((T / 100) * 15) + (P * 20) + (O * 5) + (K * 20) + (Q * 8)) * retention * league_multiplier
    elif position == "Boczny Obrońca":
        score = ((J * 100) + (K * 60) + (P * 12) + (Q * 6) + (O * 8)) * retention * league_multiplier
    elif position == "Defensywny Pomocnik":
        score = ((J * 9) + (K * 40) + (P * 9) + (Q * 9) + (O * 9) + ((T / 100) * 5)) * retention * league_multiplier
    elif position == "Środkowy Pomocnik":
        score = ((J * 80) + (L * 40) + (K * 60) + (V * 12) + (Q * 8) + (O * 8)) * retention * league_multiplier
    elif position == "Skrzydłowy":
        score = ((J * 96) + (L * 80) + (M * 58) + (K * 40) + (V * 16) + (O * 6) + (Q * 6)) * retention * league_multiplier
    elif position == "Napastnik":
        score = ((L * 180) + (M * 60) + (J * 80) + (K * 40) + (V * 15) + (O * 8) + (Q * 8) + (N * 1)) * retention * league_multiplier
    else:
        score = pd.Series(0.0, index=df.index)
        
    return score

POZYCJE = ["Bramkarz", "Środkowy Obrońca", "Boczny Obrońca", "Defensywny Pomocnik", "Środkowy Pomocnik", "Skrzydłowy", "Napastnik"]

if "data_storage" not in st.session_state:
    st.session_state["data_storage"] = {pozycja: None for pozycja in POZYCJE}

def clear_filters(pozycja, min_a, max_a, max_p):
    st.session_state[f"search_{pozycja}"] = ""
    st.session_state[f"ligi_{pozycja}"] = []
    st.session_state[f"age_{pozycja}"] = (min_a, max_a)
    st.session_state[f"price_range_{pozycja}"] = (0.0, float(max_p / 1_000_000))
    st.session_state[f"ignore_mult_{pozycja}"] = False

KOLUMNY_PER_POZYCJA = {
    "Bramkarz": ['SCORE', 'Nazwisko', 'Wiek', 'Klub', 'Liga', 'Wartość', 'Noga', 'Odzyskane piłki/90', 'Stracone piłki/90', 'Próby podań/90', 'Uniknięte oczekiwane gole/90 (BR)'],
    "Środkowy Obrońca": ['SCORE', 'Nazwisko', 'Wiek', 'Klub', 'Liga', 'Wartość', 'Noga', 'Kluczowe podania z gry/90', 'Udane próby pressingu/90', 'Przechwyty/90', 'Odzyskane piłki/90', 'Stracone piłki/90', 'Próby podań/90', '% wygranych pojedynków główkowych'],
    "Boczny Obrońca": ['SCORE', 'Nazwisko', 'Wiek', 'Klub', 'Liga', 'Pozycja', 'Wartość', 'Noga', 'xA/90', 'Kluczowe podania z gry/90', 'Udane próby pressingu/90', 'Przechwyty/90', 'Odzyskane piłki/90', 'Stracone piłki/90', 'Próby podań/90'],
    "Defensywny Pomocnik": ['SCORE', 'Nazwisko', 'Wiek', 'Klub', 'Liga', 'Wartość', 'Noga', 'xA/90', 'Kluczowe podania z gry/90', 'Udane próby pressingu/90', 'Przechwyty/90', 'Odzyskane piłki/90', 'Stracone piłki/90', 'Próby podań/90', '% wygranych pojedynków główkowych'],
    "Środkowy Pomocnik": ['SCORE', 'Nazwisko', 'Wiek', 'Klub', 'Liga', 'Wartość', 'Noga', 'xA/90', 'Kluczowe podania z gry/90', 'Liczba goli/90', 'Udane próby pressingu/90', 'Odzyskane piłki/90', 'Stracone piłki/90', 'Próby podań/90', 'Liczba dryblingów/90'],
    "Skrzydłowy": ['SCORE', 'Nazwisko', 'Klub', 'Wiek', 'Liga', 'Pozycja', 'Wartość', 'Noga', 'xA/90', 'Kluczowe podania z gry/90', 'Liczba goli/90', 'Oczekiwane gole na strzał', 'Udane próby pressingu/90', 'Odzyskane piłki/90', 'Stracone piłki/90', 'Próby podań/90', 'Liczba dryblingów/90'],
    "Napastnik": ['SCORE', 'Nazwisko', 'Klub', 'Wiek', 'Liga', 'Wartość', 'Noga', 'xA/90', 'Kluczowe podania z gry/90', 'Liczba goli/90', 'Oczekiwane gole na strzał', 'Skuteczność (%)', 'Udane próby pressingu/90', 'Odzyskane piłki/90', 'Stracone piłki/90', 'Próby podań/90', 'Liczba dryblingów/90']
}

st.markdown("<div style='font-size: 2.7rem; font-weight: bold; margin-top: -2.5rem; margin-bottom: 1rem;'>📊 FM26 Moneyball Dashboard</div>", unsafe_allow_html=True)

arkusze = st.tabs([f"🟢 {p}" for p in POZYCJE])

for i, pozycja_nazwa in enumerate(POZYCJE):
    with arkusze[i]:
        st.markdown(f"<div style='font-size: 1.40rem; font-weight: 600; margin-top: 0.5rem; margin-bottom: 0.5rem;'>📋 Arkusz: {pozycja_nazwa}</div>", unsafe_allow_html=True)
        
        file_key = f"uploader_{pozycja_nazwa}"
        uploaded_file = st.file_uploader("Wgraj plik CSV", type=["csv"], key=file_key, label_visibility="collapsed")
        
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
                        
                    loaded_df['SCORE'] = calculate_score(loaded_df, pozycja_nazwa, ignore_mult=False)
                    loaded_df = loaded_df[loaded_df['SCORE'] > 0]
                    
                    st.session_state["data_storage"][pozycja_nazwa] = loaded_df
                    st.session_state[processed_key] = current_file_id
                    
                    st.success(f"✓ Pomyślnie załadowano i przeliczono SCORE dla: {pozycja_nazwa}.")
                except Exception as e:
                    st.error(f"Błąd podczas ładowania pliku: {e}")

        df = st.session_state["data_storage"][pozycja_nazwa]

        if df is not None and not df.empty:
            st.markdown("<div style='font-size: 1.4rem; font-weight: 600; margin-top: 0.5rem; margin-bottom: 0.5rem;'>⚙️ Filtry wyszukiwania</div>", unsafe_allow_html=True)
            
            ignore_mult = st.toggle("🚫 Pokaż surowe statystyki (ignoruj mnożnik ligowy)", key=f"ignore_mult_{pozycja_nazwa}")
            
            dostepne_ligi = sorted(df['Liga'].dropna().unique()) if 'Liga' in df.columns else []
            min_age = int(df['Wiek'].min()) if 'Wiek' in df.columns and not df.empty else 15
            max_age = int(df['Wiek'].max()) if 'Wiek' in df.columns and not df.empty else 45
            
            if 'Wartość_Numeryczna' in df.columns:
                valid_prices = df[df['Wartość_Numeryczna'] < 900_000_000]['Wartość_Numeryczna']
                max_price_avail = float(valid_prices.max()) if not valid_prices.empty else 100_000_000.0
            else:
                max_price_avail = 100_000_000.0
                
            if max_price_avail <= 0.0:
                max_price_avail = 100_000_000.0

            col_f1, col_f2, col_f3, col_f4, col_f5 = st.columns([2.5, 2.5, 2, 2.5, 1.5])

            with col_f1:
                search = st.text_input("🔍 Szukaj (Piłkarz / Klub):", key=f"search_{pozycja_nazwa}")

            with col_f2:
                wybrane_ligi = st.multiselect("🌍 Wybierz ligi:", options=dostepne_ligi, key=f"ligi_{pozycja_nazwa}")

            with col_f3:
                age_filter = st.slider("🎂 Wiek:", min_age, max_age, (min_age, max_age), key=f"age_{pozycja_nazwa}")

            with col_f4:
                price_filter_mln = st.slider(
                    "💰 Cena (mln €):", 
                    0.0, float(max_price_avail / 1_000_000), 
                    (0.0, float(max_price_avail / 1_000_000)), 
                    key=f"price_range_{pozycja_nazwa}"
                )
                price_min_bytes = price_filter_mln[0] * 1_000_000
                price_max_bytes = price_filter_mln[1] * 1_000_000

            with col_f5:
                st.markdown("<div style='margin-top: 28px;'></div>", unsafe_allow_html=True)
                st.button(
                    "🗑️ Wyczyść", 
                    key=f"btn_clear_{pozycja_nazwa}", 
                    on_click=clear_filters, 
                    args=(pozycja_nazwa, min_age, max_age, max_price_avail), 
                    use_container_width=True
                )

            filtered_df = df.copy()
            
            if ignore_mult:
                filtered_df['SCORE'] = calculate_score(filtered_df, pozycja_nazwa, ignore_mult=True)
            
            if 'Wiek' in filtered_df.columns:
                filtered_df = filtered_df[(filtered_df['Wiek'] >= age_filter[0]) & (filtered_df['Wiek'] <= age_filter[1])]
            
            if 'Wartość_Numeryczna' in filtered_df.columns:
                filtered_df = filtered_df[
                    (filtered_df['Wartość_Numeryczna'] >= price_min_bytes) & 
                    (filtered_df['Wartość_Numeryczna'] <= price_max_bytes)
                ]
                
            if 'Liga' in filtered_df.columns and wybrane_ligi:
                filtered_df = filtered_df[filtered_df['Liga'].isin(wybrane_ligi)]
            
            if search:
                cond = pd.Series(False, index=filtered_df.index)
                if 'Nazwisko' in filtered_df.columns:
                    cond |= filtered_df['Nazwisko'].str.contains(search, case=False, na=False)
                if 'Klub' in filtered_df.columns:
                    cond |= filtered_df['Klub'].str.contains(search, case=False, na=False)
                filtered_df = filtered_df[cond]
                
            if 'SCORE' in filtered_df.columns:
                filtered_df = filtered_df.sort_values(by="SCORE", ascending=False)

            st.markdown("---")

            dedykowane_kolumny = KOLUMNY_PER_POZYCJA.get(pozycja_nazwa, [])
            cols_to_show = [c for c in dedykowane_kolumny if c in filtered_df.columns]
            
            if len(cols_to_show) <= 2:
                zapasowe_kolumny = ['SCORE', 'Nazwisko', 'Klub', 'Liga', 'Wiek', 'Wartość']
                cols_to_show = [c for c in zapasowe_kolumny if c in filtered_df.columns]

            format_dict = {}
            if 'SCORE' in filtered_df.columns:
                format_dict['SCORE'] = '{:.0f}'
            if 'Wiek' in filtered_df.columns:
                format_dict['Wiek'] = '{:.0f}'
            
            for col in cols_to_show:
                if col not in ['SCORE', 'Wiek', 'Nazwisko', 'Klub', 'Liga', 'Pozycja', 'Wartość', 'Kraj', 'Noga'] and pd.api.types.is_numeric_dtype(filtered_df[col]):
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
            
            if 'Wiek' in cols_to_show:
                df_style = df_style.set_properties(subset=['Wiek'], **{'text-align': 'center'})

            df_style = df_style.set_table_styles([
                {'selector': 'th', 'props': [('text-align', 'center')]}
            ], overwrite=False)

            col_config = {}
            if 'SCORE' in cols_to_show:
                col_config['SCORE'] = st.column_config.Column("SCORE", alignment="center")
            if 'Wiek' in cols_to_show:
                col_config['Wiek'] = st.column_config.Column("Wiek", alignment="center")

            st.dataframe(
                df_style,
                use_container_width=True, 
                height=400,
                hide_index=True,
                column_config=col_config
            )
            
            if 'Wartość_Numeryczna' in filtered_df.columns and 'SCORE' in filtered_df.columns:
                st.subheader("📈 Wykres Moneyball: Cena vs Control Score (Top 30)", anchor=False)
                
                chart_data = filtered_df[filtered_df['Wartość_Numeryczna'] < 900_000_000].head(30)
                
                if not chart_data.empty:
                    min_val = float(chart_data['Wartość_Numeryczna'].min())
                    max_val = float(chart_data['Wartość_Numeryczna'].max())
                    
                    tooltip_cols = [
                        alt.Tooltip('Nazwisko:N', title='Nazwisko'),
                        alt.Tooltip('Wiek:Q', title='Wiek', format='.0f'),
                        alt.Tooltip('Klub:N', title='Klub'),
                        alt.Tooltip('Wartość:N', title='Wartość'),
                        alt.Tooltip('SCORE:Q', title='SCORE', format='.0f')
                    ]
                    
                    chart = alt.Chart(chart_data).mark_circle(size=300).encode(
                        x=alt.X('Wartość_Numeryczna', 
                                title='Wartość',
                                scale=alt.Scale(domain=[min_val - 1800000, max_val + (max_val*0.1)])),
                        y=alt.Y('SCORE:Q', 
                                title='Control Score', 
                                axis=alt.Axis(format='.0f'),
                                scale=alt.Scale(zero=False)),
                        color=alt.Color('Nazwisko', legend=None),
                        tooltip=tooltip_cols
                    ).properties(height=500)
                        
                    st.altair_chart(chart.interactive(), use_container_width=True)

                    st.markdown("---")
                    st.subheader("📊 Dodatkowe Statystyki (Top 30 wg SCORE)", anchor=False)
                    
                    kolumny_ignorowane = ['SCORE', 'Nazwisko', 'Wiek', 'Klub', 'Liga', 'Pozycja', 'Wartość', 'Noga', 'Kraj', 'Wartość_Numeryczna']
                    kolumny_statystyk = [c for c in dedykowane_kolumny if c not in kolumny_ignorowane and c in chart_data.columns]
                    
                    if kolumny_statystyk:
                        cols = st.columns(2)
                        for idx, stat_col in enumerate(kolumny_statystyk):
                            with cols[idx % 2]:
                                # Format zależny od tego czy to wartość procentowa (np. pojedynki główkowe) czy standardowa float
                                is_percent = '%' in stat_col
                                stat_format = '.1f' if not is_percent else '.0f'
                                
                                bar_chart = alt.Chart(chart_data).mark_bar().encode(
                                    x=alt.X(field=stat_col, type='quantitative', title=stat_col),
                                    y=alt.Y('Nazwisko', type='nominal', sort='-x', title=''),
                                    color=alt.Color('SCORE:Q', scale=alt.Scale(scheme='blues'), legend=None),
                                    tooltip=[
                                        alt.Tooltip('Nazwisko:N', title='Nazwisko'),
                                        alt.Tooltip('Wiek:Q', title='Wiek', format='.0f'),
                                        alt.Tooltip('Klub:N', title='Klub'),
                                        alt.Tooltip('Wartość:N', title='Wartość'),
                                        alt.Tooltip('SCORE:Q', title='SCORE', format='.0f'),
                                        alt.Tooltip(f'{stat_col}:Q', title=stat_col, format=stat_format)
                                    ]
                                ).properties(height=400, title=stat_col)
                                st.altair_chart(bar_chart.interactive(), use_container_width=True)

        else:
            st.info(f"ℹ️ Ten arkusz jest pusty. Przeciągnij plik `.csv` dedykowany dla pozycji: **{pozycja_nazwa}** powyżej.")