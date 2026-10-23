# FM26 Moneyball Dashboard

Narzędzie do wyszukiwania zawodników w Football Manager 26 w stylu Moneyball. Liczy wynik (SCORE) na tle innych zawodników z tej samej pozycji, z korektą na małą liczbę minut i siłę ligi. Do tego porównanie na radarze, wyszukiwanie „sobowtóra” i wykresy wyniku względem ceny.

## Uruchomienie

```bash
python -m pip install -r requirements.txt      # Python 3.12 lub nowszy
python -m fm_moneyball                         # otwiera aplikację w przeglądarce (http://localhost:8765)
```

Aplikacja działa lokalnie: serwer w Pythonie czyta zapisy gry z dysku, a interfejs otwiera się w przeglądarce. Do uruchomienia nie jest potrzebny Node.js, bo zbudowany interfejs jest w repozytorium. Poprzednia wersja (`streamlit run app.py`) nadal działa, np. do importu plików CSV.

Co jest w aplikacji:
- **Źródło danych:** po starcie aplikacja pyta, co wczytać: zapis z folderu gry (najszybciej; opcjonalnie śledzi kolejne zapisy), wgranie pliku `.fm` albo dane demo. Nic nie wczytuje się samo, chyba że włączysz „Wczytuj to źródło automatycznie przy uruchomieniu”. Podczas odczytu widać etap i czas. Wynik odczytu trafia do pamięci podręcznej (`~/.fm_moneyball/cache`, 3 ostatnie zapisy), więc ponowne otwarcie tego samego zapisu, także po restarcie, jest natychmiastowe.
- **Ranking:** tabela z sortowaniem i filtrami w kolumnach, płynna przy tysiącach zawodników. Filtry po lewej: ligi, wiek, cena, kontrakt, okazje transferowe, minimalna opłacalność, maksymalne ryzyko, noga, minuty, pomijanie własnego klubu. Wagi statystyk zmieniasz suwakami.
- **Twój klub** jest odczytywany z zapisu i widoczny w nagłówku (przy kilku prowadzonych drużynach można wybrać jedną). Jego zawodnicy są wyróżnieni na bursztynowo w tabelach, w karcie zawodnika i na wykresach.
- **Kolumny Moneyball:** koszt (cena + 3 lata pensji; u wolnego agenta tylko pensja), opłacalność (punkty SCORE ponad przeciętnego zawodnika na 1 mln € kosztu), okazje i, przy włączonych danych ukrytych, ryzyko 0–100 (podatność na kontuzje, regularność, ważne mecze, wiek ponad 30 lat, kontuzje z ostatnich 2 lat).
- **Okazje:** ranking zawodników z kończącym się kontraktem (≤ 6 i ≤ 12 mies.), wolnych agentów, kończących wypożyczenie oraz młodych talentów bez minut w dużych klubach.
- **Moja kadra:** każda pozycja twojego klubu na tle całej puli: najlepszy zawodnik, średni wiek, kończące się kontrakty i luka do 80. percentyla. Pozycje są posortowane od największej luki, a „Szukaj wzmocnienia” otwiera ranking tej pozycji bez twoich zawodników.
- **Karta zawodnika:** kliknij nazwisko, żeby zobaczyć szczegóły, koszt i okazje, dane ukryte (gdy włączone), profil statystyk na radarze i podobnych zawodników.
- **Porównanie:** do 4 zawodników na jednym radarze, razem z tabelą wartości.
- **Wykresy:** wynik względem kosztu lub wartości z granicą opłacalności (zawodnicy, od których nikt nie jest jednocześnie lepszy i tańszy) oraz top 10 w wybranej statystyce.
- **Ligi:** lista lig wykrytych w zapisie z przykładowymi klubami. Nazwę i mnożnik siły ligi wpisujesz ręcznie; zmiany działają od razu i zapisują się w `dane/nazwy_rozgrywek.csv` oraz `dane/mnozniki_lig.csv`.

### Windows krok po kroku

1. Pobierz kod jako ZIP (na GitHubie: przycisk *Code*, potem *Download ZIP*) i rozpakuj go.
2. W PowerShellu przejdź do rozpakowanego folderu (`cd "ścieżka\do\folderu"`) i sprawdź wersję Pythona poleceniem `py --version`. Potrzebna jest wersja 3.12 lub nowsza. Jeśli jej brakuje, uruchom `winget install -e --id Python.Python.3.12` i otwórz PowerShell na nowo.
3. Zainstaluj biblioteki: `py -m pip install -r requirements.txt`. Na każdym nowym komputerze trzeba to zrobić raz.
4. Uruchom aplikację: `py -m fm_moneyball` (w folderze projektu). Przeglądarka otworzy się sama. Okno PowerShella musi pozostać otwarte, a `Ctrl+C` kończy pracę aplikacji.

## Źródła danych

| Źródło | Jak działa |
|---|---|
| **Zapis gry (folder)** | Aplikacja sama znajduje folder `Dokumenty/Sports Interactive/Football Manager 26/games`. Wybierasz konkretny zapis albo „zawsze najnowszy”: wtedy co 15 s sprawdza, czy gra zapisała nowy stan (zapis ręczny lub autozapis), i wczytuje go. Wymaga uruchomienia aplikacji na komputerze z grą. |
| **Plik zapisu .fm** | Wgrywasz plik kariery przez przeglądarkę. Wolniejsze niż wybór z folderu, bo plik jest najpierw kopiowany. |
| **Pliki CSV** | Eksport widoku z gry, po jednym pliku na pozycję (jak w poprzednich wersjach). |
| **Dane demo** | Dane syntetyczne. |

Jeden zapis `.fm` daje od razu wszystkie siedem pozycji. Pozycja zawodnika to ta, na której ma najwyższą ocenę (opcjonalnie: wszystkie naturalne). Statystyki pochodzą z bieżącego sezonu: ligi albo wszystkich rozgrywek.

### Jak czytany jest plik `.fm`

Zapis FM26 to kontener z sekcjami skompresowanymi algorytmem Zstandard, bez szyfrowania. Rekordy gry dekoduje biblioteka [fmsave](https://github.com/rhiever/fmsave). To nieoficjalny projekt oparty na inżynierii wstecznej, więc po aktualizacji gry może wymagać nowej wersji.

Ograniczenia:

- **Nazwy lig.** Zapis nie zawiera nazw lig, tylko ich identyfikatory. Nazwy wpiszesz w zakładce „Ligi” albo nauczysz ze starych eksportów CSV (panel „Źródło danych”, sekcja „Nazwy lig”). Trafiają do `dane/nazwy_rozgrywek.csv`; identyfikatory są wspólne dla wszystkich zapisów FM26. Ligi bez nazwy są pokazywane jako „Rozgrywki #id” i dostają najniższy mnożnik ligowy. Mnożniki lig spoza wbudowanej tabeli (np. K League) zapisują się w `dane/mnozniki_lig.csv`.
- **Wolni agenci** (zawodnicy bez klubu, którzy grali w tym sezonie) trafiają do puli z ligą „Wolny agent”. Można to wyłączyć w „Opcjach odczytu zapisu”.
- **Waluta.** Kwoty są zapisane w walucie bazowej. Domyślny kurs 1,157 odpowiada temu, co gra pokazuje w euro. Można go zmienić w „Opcjach odczytu zapisu”.
- **Ceny.** Zapis zawiera rzeczywistą wartość transferową z gry. Gra pokazuje zamiast niej widełki zależne od wiedzy skautów (np. 80–325 tys. € przy wartości 315 tys. €). Dlatego ceny z zapisu są zwykle wyższe niż przy imporcie CSV, który brał środek widełek.
- **Liga klubu** to rozgrywki, w których jego pierwsza drużyna gra najwięcej kolejek ligowych w bieżącym sezonie (z terminarza, łącznie z kolejkami zaplanowanymi). Dzięki temu np. kluby brazylijskie mają Série A także wtedy, gdy trwają jeszcze ligi stanowe. Drużyny kobiece (kluby o tej samej nazwie co męskie) i ich rozgrywki są pomijane.
- **Ligi bez identyfikatora w bazie** (np. belgijska Jupiler Pro League) dostają w mapie nazw klucz zastępczy `-numer_kraju` (np. `-131,Jupiler Pro League`).
- **Dane ukryte.** Zapis zawiera dane, których w grze nie widać bez pełnej wiedzy skautów (CA/PA, atrybuty ukryte, osobowość, a z nich ryzyko). Domyślnie są ukryte; włączysz je w „Ustawieniach wyniku”.

## Diagnostyka zapisu

Aby sprawdzić, czy Twój zapis jest czytany poprawnie, uruchom:

```bash
python narzedzia/zbadaj_zapis.py "<ścieżka do zapisu>.fm" [stare_eksporty.csv ...] [--zapisz-nazwy]
```

Z plikami CSV skrypt rozpozna nazwy lig. Opcja `--zapisz-nazwy` zapisze je do `dane/nazwy_rozgrywek.csv`, a raport pokaże przy każdej lidze kilka klubów, żeby łatwo było sprawdzić przypisanie. W repozytorium jest już mapa najpopularniejszych lig: Anglia, Francja, Niemcy, Holandia, Włochy, Portugalia, Hiszpania, Belgia, Polska, Chorwacja, Brazylia, Argentyna, Meksyk, Japonia i MLS. Opcja `--klub "Nazwa klubu"` (można podać kilka razy) wypisze wszystkie tabele, w których występuje klub. Pomaga to zrozumieć, skąd wzięło się jego przypisanie do ligi.

Skrypt wypisze liczbę odczytanych zawodników i lig, pokrycie kolumn oraz próbkę Twojej kadry do porównania z ekranem gry. Zapisze też mały raport `raport_zapisu.json`.

## Struktura

```
fm_moneyball/              logika niezależna od interfejsu
  __main__.py              uruchomienie: python -m fm_moneyball
  serwer/                  API (FastAPI), stan i wczytywanie w tle; static/ = zbudowany frontend
  analiza.py               ranking, filtry, kolumny, radar, podobni, koszt/opłacalność/okazje/ryzyko, moja kadra
  ligi.py                  mnożniki lig ustawione przez użytkownika (dane/mnozniki_lig.csv)
  stale.py                 kolumny, cechy, wagi, mnożniki lig
  parsery.py               tekst z FM -> liczby
  schemat.py               kolumny pochodne, ID, raport wczytania
  model.py                 SCORE, percentyle, macierz stylu
  zrodla/csv_fm.py         eksport CSV + dane demo
  zrodla/zapis_fm.py       plik zapisu .fm (fmsave)
  zrodla/folder.py         folder zapisów gry
narzedzia/zbadaj_zapis.py  diagnostyka zapisu
frontend/                  interfejs React + TypeScript (Vite, Mantine, AG Grid, ECharts)
app.py                     poprzedni interfejs (Streamlit)
tests/                     testy (pytest)
```

Testy: `python -m pip install -r requirements-dev.txt && python -m pytest`

Zmiany w interfejsie (wymaga Node.js 20+): `cd frontend && npm install && npm run build` zapisuje wynik do `fm_moneyball/serwer/static/`. Tryb deweloperski: `python -m fm_moneyball --bez-przegladarki` oraz `npm run dev` w katalogu `frontend`.
