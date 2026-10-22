# FM26 Moneyball Dashboard

Narzędzie do wyszukiwania zawodników w Football Manager 26 w stylu Moneyball. Liczy wynik (SCORE) na tle innych zawodników z tej samej pozycji, z korektą na małą liczbę minut i siłę ligi. Do tego porównanie na radarze, wyszukiwanie „sobowtóra” i wykresy wyniku względem ceny.

## Uruchomienie

```bash
python -m pip install -r requirements.txt      # Python 3.12 lub nowszy
streamlit run app.py
```

## Źródła danych

| Źródło | Jak działa |
|---|---|
| **Zapis gry (folder)** | Aplikacja sama znajduje folder `Dokumenty/Sports Interactive/Football Manager 26/games` i bierze najnowszy plik `.fm`. Co 30 s sprawdza, czy gra zapisała nowy stan (zapis ręczny lub autozapis), i wtedy się odświeża. Wymaga uruchomienia aplikacji na komputerze z grą. |
| **Plik zapisu .fm** | Wgrywasz plik kariery (limit 2 GB, ustawiony w `.streamlit/config.toml`). |
| **Pliki CSV** | Eksport widoku z gry, po jednym pliku na pozycję (jak w poprzednich wersjach). |
| **Dane demo** | Dane syntetyczne. |

Jeden zapis `.fm` daje od razu wszystkie siedem pozycji. Pozycja zawodnika to ta, na której ma najwyższą ocenę (opcjonalnie: wszystkie naturalne). Statystyki pochodzą z bieżącego sezonu: ligi albo wszystkich rozgrywek.

### Jak czytany jest plik `.fm`

Zapis FM26 to kontener z sekcjami skompresowanymi algorytmem Zstandard, bez szyfrowania. Rekordy gry dekoduje biblioteka [fmsave](https://github.com/rhiever/fmsave). To nieoficjalny projekt oparty na inżynierii wstecznej, więc po aktualizacji gry może wymagać nowej wersji.

Ograniczenia:

- **Nazwy lig.** Zapis nie zawiera nazw lig, tylko ich identyfikatory. Wgraj stare eksporty CSV w sekcji „Nazwy lig” w panelu bocznym: aplikacja dopasuje kluby i zapisze nazwy w `dane/nazwy_rozgrywek.csv`. Identyfikatory są wspólne dla wszystkich zapisów FM26. Ligi bez nazwy są pokazywane jako „Rozgrywki #id” i dostają najniższy mnożnik ligowy.
- **Waluta.** Kwoty są zapisane w walucie bazowej. Domyślny kurs 1,157 odpowiada temu, co gra pokazuje w euro. Można go zmienić w „Opcjach odczytu zapisu”.
- **Dane ukryte.** Zapis zawiera dane, których w grze nie widać bez pełnej wiedzy skautów (CA/PA). Domyślnie są ukryte; włączysz je w Ustawieniach.

## Diagnostyka zapisu

Aby sprawdzić, czy Twój zapis jest czytany poprawnie, uruchom:

```bash
python narzedzia/zbadaj_zapis.py "<ścieżka do zapisu>.fm" [stare_eksporty.csv ...]
```

Skrypt wypisze liczbę odczytanych zawodników i lig, pokrycie kolumn oraz próbkę Twojej kadry do porównania z ekranem gry. Zapisze też mały raport `raport_zapisu.json`.

## Struktura

```
app.py                     interfejs (Streamlit)
fm_moneyball/              logika niezależna od interfejsu
  stale.py                 kolumny, cechy, wagi, mnożniki lig
  parsery.py               tekst z FM -> liczby
  schemat.py               kolumny pochodne, ID, raport wczytania
  model.py                 SCORE, percentyle, macierz stylu
  zrodla/csv_fm.py         eksport CSV + dane demo
  zrodla/zapis_fm.py       plik zapisu .fm (fmsave)
  zrodla/folder.py         folder zapisów gry
narzedzia/zbadaj_zapis.py  diagnostyka zapisu
tests/                     testy (pytest)
```

Testy: `python -m pip install -r requirements-dev.txt && python -m pytest`
