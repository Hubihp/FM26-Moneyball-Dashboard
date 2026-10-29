"""Model: wynik (SCORE) w z-score, ze skurczeniem przy malej liczbie minut."""
import numpy as np
import pandas as pd

from fm_moneyball.stale import CECHY

UDZIAL_DANYCH_SKALI = 0.9       # skale wyniku wyznaczaja zawodnicy z danymi dla >= 90% wag
MIN_ZAWODNIKOW_SKALI = 30


def parametry_cechy(nazwa):
    """(kierunek, skurczenie) cechy; nieznane cechy per 90 sa skurczane standardowo."""
    return CECHY.get(nazwa, (1, 1.0 if '/90' in nazwa else 0.0))


def _srednia_odchylenie(x, wagi):
    """Srednia i odchylenie standardowe; wazone minutami, jesli sa dostepne."""
    if wagi is not None:
        w = wagi.where(x.notna(), 0.0).clip(lower=0)
        if w.sum() > 0:
            srednia = float(np.average(x.fillna(0), weights=w))
            wariancja = float(np.average((x.fillna(srednia) - srednia) ** 2, weights=w))
            return srednia, wariancja ** 0.5
    return x.mean(), x.std(ddof=0)


def maska_odniesienia(df, odniesienie=None):
    """Maska wierszy, na ktorych liczymy skale wyniku (domyslnie wszystkie)."""
    if odniesienie is None:
        return pd.Series(True, index=df.index)
    return odniesienie.reindex(df.index).fillna(False).astype(bool)


def oblicz_z(df, nazwy_cech, k_baza, odniesienie=None):
    """
    Dla kazdej cechy liczy z-score w obrebie calej puli (df). Jesli dostepne sa minuty:
      - srednia i odchylenie sa wazone minutami, wiec zawodnicy z kilkoma minutami (skrajne
        wartosci per 90) nie zawyzaja rozrzutu i nie splaszczaja wyniku pozostalych,
      - cechy sa skurczone w strone sredniej puli: x* = (n90*x + k*srednia) / (n90 + k), gdzie
        n90 to liczba pelnych meczow, a k = k_baza * wspolczynnik cechy.
    `odniesienie` (maska wierszy) to zawodnicy, wzgledem ktorych liczymy srednia i odchylenie;
    pozostali (np. kandydaci z innych pozycji) dostaja z-score na tej samej skali, ale jej nie zmieniaja.
    Zwraca (slownik z-score'ow, n90 lub None).
    """
    ref = maska_odniesienia(df, odniesienie)
    n90 = None
    if 'Minuty' in df.columns and df['Minuty'].notna().any():
        n90 = df['Minuty'] / 90.0
        n90 = n90.fillna(n90[ref].median())

    z = {}
    for nazwa in nazwy_cech:
        if nazwa not in df.columns:
            continue
        x = df[nazwa].astype(float)
        if x[ref].notna().sum() < 2:
            continue
        srednia, odchylenie = _srednia_odchylenie(x[ref], n90[ref] if n90 is not None else None)
        if not np.isfinite(odchylenie) or odchylenie == 0:
            continue
        kierunek, skurcz = parametry_cechy(nazwa)
        xs = x.fillna(srednia)
        if n90 is not None and skurcz > 0 and k_baza > 0:
            k = k_baza * skurcz
            xs = (n90 * xs + k * srednia) / (n90 + k)
        z[nazwa] = ((xs - srednia) / odchylenie * kierunek).clip(-3, 3)
    return z, n90


def skladowe_score(df, wagi, k_baza, odniesienie=None):
    """
    Skladowe wyniku: (z-score'y cech, wagi znormalizowane do sumy 1, srednia i odchylenie skladanej
    na skali, pominiete cechy). Wspolne dla oblicz_score i rozbicia wyniku w karcie zawodnika.
    Gdy zadna cecha nie wchodzi do wyniku, wagi sa puste.
    """
    nazwy = [n for n, w in wagi.items() if w > 0]
    z, _ = oblicz_z(df, nazwy, k_baza, odniesienie)
    ref = maska_odniesienia(df, odniesienie)
    uzyte = [n for n in nazwy if n in z]
    pominiete = [n for n in nazwy if n not in z]
    suma = sum(wagi[n] for n in uzyte)
    if not uzyte or suma <= 0:
        return z, {}, 0.0, np.nan, pominiete
    udzialy = {n: wagi[n] / suma for n in uzyte}
    kompozyt = sum(z[n] * udzialy[n] for n in uzyte)
    # Skala T z zawodnikow z (prawie) pelnymi danymi: braki sa uzupelniane srednia (z = 0), wiec liczni
    # zawodnicy z niepelnymi statystykami (np. rezerwy) zawezaliby rozrzut i rozciagali wynik pozostalych
    obecne = sum(df[n].notna().astype(float) * udzialy[n] for n in uzyte)
    skala = ref & (obecne >= UDZIAL_DANYCH_SKALI)
    if skala.sum() < MIN_ZAWODNIKOW_SKALI:
        skala = ref
    return z, udzialy, float(kompozyt[skala].mean()), float(kompozyt[skala].std(ddof=0)), pominiete


def oblicz_score(df, wagi, ignoruj_mnoznik, k_baza, odniesienie=None):
    """
    SCORE = 50 + 10 * (skladana z-score'ow - srednia) / odchylenie, czyli skala typu T-score:
    50 = przecietny zawodnik na tej pozycji w wgranej probie, +10 = jedno odchylenie wyzej.
    Korekta ligowa jest addytywna: SCORE + 50 * (mnoznik - 1). Przy przecietnym zawodniku daje
    to dokladnie to samo co dawne mnozenie (50 * mnoznik), ale kara nie zalezy od poziomu
    wyniku (mnozenie skali ze srodkiem 50 karalo slabych zawodnikow mniej niz mocnych).
    Wagi sa normalizowane do sumy 1. `odniesienie` - patrz oblicz_z (skala T tez liczona tylko na nim).
    Zwraca (SCORE, lista pominietych cech).
    """
    z, udzialy, srednia, odch, pominiete = skladowe_score(df, wagi, k_baza, odniesienie)
    if not udzialy:
        return pd.Series(np.nan, index=df.index), pominiete
    kompozyt = sum(z[n] * u for n, u in udzialy.items())
    if np.isfinite(odch) and odch > 0:
        score = 50.0 + 10.0 * (kompozyt - srednia) / odch
    else:
        score = pd.Series(50.0, index=df.index)

    if not ignoruj_mnoznik and 'Mnożnik_Ligi' in df.columns:
        score = score + 50.0 * (df['Mnożnik_Ligi'] - 1.0)
    return score, pominiete


def rozbicie_score(df, wagi, ignoruj_mnoznik, k_baza, odniesienie, indeks):
    """
    SCORE jednego zawodnika (wiersz `indeks`) rozbity na wklady: punkt wyjscia (~50) + wklad kazdej
    cechy (10 * waga * z / odchylenie) + korekta ligowa = SCORE. brak_danych = cecha uzupelniona srednia.
    """
    z, udzialy, srednia, odch, _ = skladowe_score(df, wagi, k_baza, odniesienie)
    skala = 10.0 / odch if np.isfinite(odch) and odch > 0 else 0.0
    skladniki = []
    for n, u in udzialy.items():
        wartosc = df.at[indeks, n]
        skladniki.append({"cecha": n, "wartosc": None if pd.isna(wartosc) else float(wartosc),
                          "z": float(z[n].at[indeks]), "waga_proc": round(100 * u, 1),
                          "punkty": float(skala * u * z[n].at[indeks]), "nizsze_lepsze": parametry_cechy(n)[0] < 0,
                          "brak_danych": bool(pd.isna(wartosc))})
    liga = 0.0
    if not ignoruj_mnoznik and 'Mnożnik_Ligi' in df.columns and pd.notna(df.at[indeks, 'Mnożnik_Ligi']):
        liga = 50.0 * (float(df.at[indeks, 'Mnożnik_Ligi']) - 1.0)
    start = 50.0 - skala * srednia
    return {"start": start, "skladniki": sorted(skladniki, key=lambda s: -abs(s["punkty"])), "liga": liga,
            "score": start + sum(s["punkty"] for s in skladniki) + liga}


def percentyl_w_puli(pula, wartosc):
    """Percentyl (0-100, ranga srednia przy remisach) wartosci w puli."""
    x = pula.dropna()
    if x.empty or pd.isna(wartosc):
        return 0.0
    return float(((x < wartosc).mean() + 0.5 * (x == wartosc).mean()) * 100)


def macierz_stylu(pula, kolumny, k_baza=0):
    """
    Macierz z-score'ow do szukania sobowtora. Uzywa tych samych z-score'ow co wynik (wazonych
    minutami i skurczonych przy malej probie), wiec zawodnik z kilkoma minutami nie wyglada na
    "podobnego" tylko przez przypadkowe wartosci per 90. Kierunek cech nie ma tu znaczenia.
    """
    z, _ = oblicz_z(pula, kolumny, k_baza)
    return pd.DataFrame(z, index=pula.index)
