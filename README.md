# FM26 Moneyball Dashboard

Narzędzie do wyszukiwania zawodników w Football Manager 26 w stylu Moneyball. Liczy wynik (SCORE) na tle innych zawodników z tej samej pozycji, z korektą na małą liczbę minut i siłę ligi. Do tego porównanie na radarze, wyszukiwanie „sobowtóra” i wykresy wyniku względem ceny.

## Uruchomienie

```bash
python -m pip install -r requirements.txt      # Python 3.12 lub nowszy
python -m fm_moneyball                         # otwiera aplikację w przeglądarce (http://localhost:8765)
```

Aplikacja działa lokalnie: serwer w Pythonie czyta zapisy gry z dysku, a interfejs otwiera się w przeglądarce. Do uruchomienia nie jest potrzebny Node.js, bo zbudowany interfejs jest w repozytorium.

Co jest w aplikacji:
- **Źródło danych:** po starcie aplikacja pyta, co wczytać: zapis z folderu gry (najszybciej; opcjonalnie śledzi kolejne zapisy), wgranie pliku `.fm` albo dane demo. Nic nie wczytuje się samo, chyba że włączysz „Wczytuj to źródło automatycznie przy uruchomieniu”. Podczas odczytu widać etap i czas. Wynik odczytu trafia do pamięci podręcznej (`~/.fm_moneyball/cache`, 3 ostatnie zapisy), więc ponowne otwarcie tego samego zapisu, także po restarcie, jest natychmiastowe.
- **Pozycja** wybierana kliknięciem na boisku. 14 pozycji, każda to osobna pula: BR (Bramkarz), ŚO (Środkowy Obrońca), LO/PO (Lewy/Prawy Obrońca), LWAH/PWAH (Lewy/Prawy Wahadłowy), DP (Defensywny Pomocnik), ŚP (Środkowy Pomocnik), LP/PP (Lewy/Prawy Pomocnik), OP (Ofensywny Pomocnik), LS/PS (Lewy/Prawy Skrzydłowy), N (Napastnik). W puli są tylko zawodnicy, którzy mają tę pozycję w kolumnie „Pozycje” (np. PS pokazuje wyłącznie prawych skrzydłowych). SCORE, percentyl i wycena są liczone w obrębie dokładnej pozycji; strona lewa i prawa mają te same wagi statystyk (LP/PP jak skrzydłowi).
- **Ranking:** tabela z sortowaniem i filtrami w kolumnach (menu po polsku), płynna przy tysiącach zawodników. Ligę i narodowość filtrujesz w menu kolumny. Filtry po lewej: wiek, cena, kontrakt, niedowartościowanie, rozwój w sezonie, noga, minimum minut (domyślnie 1000, także w Okazjach, Wykresach i Podobnych), pomijanie własnego klubu. Wagi statystyk zmieniasz suwakami. Filtry są zapamiętywane osobno dla każdej pozycji, a układ tabel (sortowanie, kolejność, szerokość i widoczność kolumn, przycisk „Kolumny”) - po odświeżeniu strony; „Przywróć układ” wraca do domyślnego.
- **Kandydaci z innych pozycji:** pole wielokrotnego wyboru w panelu (puste = wyłączone) dodaje do rankingu zawodników grających nominalnie na wskazanych pozycjach, ocenionych według kryteriów wybranej pozycji (np. defensywny pomocnik, który ma profil prawego obrońcy). Nie zmieniają oni wyników zawodników tej pozycji. W tabeli mają fioletowy pasek, kolumnę „Kandydat z pozycji” i, z zapisu gry, „Ocena na pozycji” (1–20, czyli jak łatwo go przekwalifikować).
- **Lista życzeń:** gwiazdka przy zawodniku (w rankingu, okazjach i karcie zawodnika) dodaje go do listy; lista jest zapamiętywana w przeglądarce, a wynik liczony w pozycji, z której zawodnik został dodany. Zawodnik jest odnajdywany niezależnie od tej pozycji: także gdy dodano go jako kandydata z innej pozycji, a w ostateczności w jego głównej pozycji. Tabela ma te same kolumny, kolejność, formatowanie i zaznaczanie co Ranking pozycji wybranej na boisku, plus kolumnę „Pozycja na liście”. Zaznaczonych zawodników (pola wyboru) można przekazać do Porównania.
- **Twój klub** jest odczytywany z zapisu i widoczny w nagłówku (przy kilku prowadzonych drużynach można wybrać jedną). Jego zawodnicy są wyróżnieni na bursztynowo w tabelach, w karcie zawodnika i na wykresach.
- **Kolumny Moneyball:** koszt (cena + 3 lata pensji; u wolnego agenta tylko pensja), okazje.
- **Niedowartościowani:** w każdej pozycji aplikacja uczy się, ile zwykle kosztuje zawodnik z danym wynikiem, wiekiem i długością kontraktu (regresja na logarytmie ceny). Długość kontraktu wchodzi odcinkami (załamanie po roku i po dwóch latach), bo w grze cena zawodnika z kontraktem krótszym niż rok jest bliska zeru niezależnie od wyniku, a kolejne lata podnoszą ją coraz mniej. Kolumna „Wycena wg wyniku” to ta typowa cena, a „Niedowartościowanie” to wycena / cena: ×2 znaczy, że zawodnik gra jak typowy zawodnik dwa razy droższy. Model celowo nie zna ligi ani klubu, więc wskazuje tanich zawodników z mniejszych lig i klubów, którzy grają jak drożsi. Na wykresie „Cena vs wycena” okazje leżą nad przekątną; podpis pokazuje jakość modelu (R²). Zawodnicy do 21 lat są oznaczeni „U21” (w tabeli, karcie i rombem na wykresie): ich cena zawiera potencjał, którego model nie widzi, więc ich niedowartościowanie jest zaniżone. Osobnego modelu dla tej grupy nie ma celowo: premia za potencjał zależy od PA, którego aplikacja nie czyta, a w puli jednej pozycji wycenionych zawodników do 21 lat jest za mało na stabilną regresję. Model nie ekstrapoluje: przy wycenie SCORE i wiek są obcinane do zakresu zawodników, na których uczył się model, a wycena nie przekracza najwyższej ceny w puli (karta zawodnika pokazuje wtedy „ograniczona”). Bez tego zawodnik o wyniku wysoko ponad resztą pozycji dostawał wycenę rosnącą wykładniczo i wychodził jako skrajnie niedowartościowany.
- **Skurczenie przy małej próbie** działa ze stałą wartością (5 meczów: waga własnych statystyk = n90 / (n90 + 5), przy 1000 minutach ok. 69%) i nie ma już suwaka. Chroni przed przypadkowymi wynikami z krótkiej próby, także u zawodników twojej kadry poniżej progu minut.
- **Okazje:** wybór rodzajów okazji jest wspólny dla wszystkich pozycji i zapamiętywany; bez zaznaczeń lista pokazuje zawodników z dowolną okazją. Zawodnik jest tu wtedy i tylko wtedy, gdy ma dany znacznik w kolumnie „Okazje” rankingu; przełącznik „Pomiń zawodników mojego klubu” jest widoczny i mówi, ilu ukrył. Rodzaje: zawodnicy niedowartościowani (×2 i SCORE ≥ 55), z kończącym się kontraktem (≤ 6 i ≤ 12 mies.) oraz szybko rozwijający się (do 23 lat, SCORE o co najmniej 5 wyższy niż w poprzednim sezonie). Zawodników zaznaczasz do porównania tak samo jak w Rankingu.
- **Historia i rozwój:** przy każdym wczytaniu zapisu kariery aplikacja zapisuje migawkę zawodników (`~/.fm_moneyball/historia/<menedżer>/<data w grze>.csv.gz`, jedna na miesiąc w grze; klucz zawodnika to UID z zapisu). Kariera to menedżer, a nie klub, więc po zmianie klubu (np. z Tottenhamu na Barcelonę) historia jest dalej jedna; migawki z dawnych katalogów klubowych są przenoszone automatycznie. Zapis gry ma statystyki tylko bieżącego sezonu, więc historia zaczyna się od pierwszej migawki. Gdy jest migawka z poprzedniego sezonu (sezon od 1 lipca), tabela pokazuje „Δ SCORE” (SCORE wtedy przeliczony tymi samymi wagami na ówczesnej puli pozycji; porównanie z ostatnią migawką z wcześniejszego sezonu). Wskaźniki liczą się tylko przy co najmniej 1000 minutach w obu sezonach. W panelu jest filtr „Rozwój w sezonie co najmniej”. Karta zawodnika pokazuje wykres SCORE i wartości we wszystkich migawkach oraz statystyki /90 z każdego sezonu; okresy poniżej 1000 minut są widoczne, ale oznaczone (⚠, pusty punkt na wykresie). Zakładka Porównanie ma wspólny wykres historii porównywanych zawodników (SCORE albo wybrana statystyka) i zestawienie Δ SCORE.
- **Moja kadra:** każda pozycja twojego klubu na tle całej puli: najlepszy zawodnik, średni wiek i kończące się kontrakty. Pozycje są ułożone od bramkarza do napastnika, a „Szukaj wzmocnienia” otwiera ranking tej pozycji bez twoich zawodników. Przycisk „Następca” przy każdym zawodniku szuka 15 piłkarzy o najbardziej podobnym stylu gry, także z innych pozycji: statystyki /90 pozycji zawodnika są przeliczane na z-score (średnia i odchylenie ważone minutami, skurczenie przy małej liczbie minut), a podobieństwo to cosinus kąta między wektorami (100% = identyczne proporcje statystyk; liczy się styl, nie poziom). Wynik uwzględnia filtry panelu dla tej pozycji (minuty, wiek, cena, kontrakt, noga) i pomija twój klub; tabela ma kolumny Rankingu i kolumnę „Podobieństwo”.
- **Karta zawodnika:** kliknij nazwisko, żeby zobaczyć szczegóły, koszt i okazje, porównanie z najlepszym zawodnikiem twojego klubu na tej pozycji (werdykt: wzmocnienie przy SCORE wyższym o co najmniej 3, podobny poziom, nie wzmacnia; plus kluczowe statystyki pozycji), historię i rozwój, profil statystyk na radarze i podobnych zawodników.
- **Porównanie:** do 4 zawodników na jednym radarze, razem z tabelą wartości: w każdym wierszu najlepsza wartość jest na zielono, a najgorsza na czerwono (przy stratach piłki mniej = lepiej). Zawodników dodasz z rankingu, z Okazji i z Listy życzeń (pola wyboru i „Porównaj zaznaczonych”).
- **Wykresy:** wynik względem kosztu lub wartości z granicą wynik/koszt (zawodnicy, od których nikt nie jest jednocześnie lepszy i tańszy), „Cena vs wycena wg wyniku”, „Wiek vs SCORE” (kolor = cena, rozmiar = minuty: młodzi z wysokim wynikiem przed wzrostem ceny) i, gdy jest historia, „Rozwój: Δ SCORE vs wiek”.
- **Ligi i kraje:** ligi wykryte w zapisie (z przykładowymi klubami) i narodowości zawodników; w każdej sekcji od razu widać 5 najliczniejszych, resztę po „Pokaż więcej”, a te bez nazwy zawsze są na górze. Nazwę i mnożnik siły ligi oraz nazwę kraju wpisujesz ręcznie; zmiany działają od razu i zapisują się w katalogu `~/.fm_moneyball` (`nazwy_rozgrywek.csv`, `mnozniki_lig.csv`, `nazwy_krajow.csv`), poza folderem aplikacji, więc pobranie nowej wersji ich nie nadpisze.

### Wagi nowych pozycji

| Cecha | Wahadłowy | Ofensywny pomocnik |
|---|---|---|
| Oczekiwane asysty/90 | 25 | 25 |
| Kluczowe podania z gry/90 | 15 | 20 |
| Udane dośrodkowania/90 | 10 | – |
| Stworzone 100% sytuacje/90 | – | 10 |
| Oczekiwane gole bez karnych/90 | – | 15 |
| Gole/90 | – | 5 |
| Dryblingi/90 | 10 | 10 |
| Podania progresywne/90 | 10 | 5 |
| Sprinty/90 | 5 | – |
| Przechwyty/90 | 10 | – |
| Odzyskane piłki/90 | 5 | – |
| Udany pressing/90 | 5 | 5 |
| Strata piłek na podanie | 5 | 5 |

- **Wahadłowy** sam daje szerokość w ustawieniu z trójką obrońców: jest głównym kreatorem z boku (xA, dośrodkowania), przenosi piłkę do przodu (drybling, podania progresywne) i biega całą flankę (sprinty). Obronę asekuruje trzech stoperów, więc część defensywna to 25% (u bocznego obrońcy 50%).
- **Ofensywny pomocnik** jest oceniany głównie za tworzenie sytuacji (55%) i zagrożenie z wejść w pole karne. Zamiast goli liczy się npxG, bo gole są losowe. Drybling oznacza wyjście spod presji między liniami. Strata piłek ma małą wagę, bo ryzykowne podania należą do tej roli.

Dośrodkowania, 100% sytuacje i sprinty pochodzą tylko z zapisu gry. Przy imporcie CSV te wagi są pomijane. Zawodnik trafia do każdej puli, w której jest naturalny (ocena pozycji ≥ 18, jak „naturalna” w grze), np. środkowy i prawy obrońca jest i w ŚO, i w PO. Wyłączenie opcji „Zawodnik na wszystkich naturalnych pozycjach” zostawia tylko pozycję z najwyższą oceną.

### Windows krok po kroku

1. Pobierz kod jako ZIP (na GitHubie: przycisk *Code*, potem *Download ZIP*) i rozpakuj go.
2. W PowerShellu przejdź do rozpakowanego folderu (`cd "ścieżka\do\folderu"`) i sprawdź wersję Pythona poleceniem `py --version`. Potrzebna jest wersja 3.12 lub nowsza. Jeśli jej brakuje, uruchom `winget install -e --id Python.Python.3.12` i otwórz PowerShell na nowo.
3. Zainstaluj biblioteki: `py -m pip install -r requirements.txt`. Na każdym nowym komputerze trzeba to zrobić raz.
4. Uruchom aplikację: `py -m fm_moneyball` (w folderze projektu). Przeglądarka otworzy się sama. Okno PowerShella musi pozostać otwarte, a `Ctrl+C` kończy pracę aplikacji.

### Wersja .exe (bez instalowania Pythona)

Pobierz [FM26Moneyball.exe](https://github.com/Hubihp/FM26-Moneyball-Dashboard/releases/download/najnowsza/FM26Moneyball.exe) i uruchom go dwuklikiem. Otworzy się czarne okno z adresem aplikacji i przeglądarka; zamknięcie okna kończy działanie aplikacji. Ponowny dwuklik, gdy aplikacja już działa, tylko otwiera przeglądarkę.

- Plik nie jest podpisany certyfikatem, więc przy pierwszym uruchomieniu Windows SmartScreen może ostrzec o nieznanym wydawcy: kliknij „Więcej informacji”, a potem „Uruchom mimo to”.
- Start trwa kilka sekund dłużej niż przy `py -m fm_moneyball`, bo program rozpakowuje się do folderu tymczasowego.
- Aktualizacja: pobierz nowy plik z tego samego linku. Plik buduje się automatycznie po każdej zmianie w kodzie (GitHub Actions). Ustawienia, nazwy lig i krajów oraz cache są w `%USERPROFILE%\.fm_moneyball`, więc zostają.

### Aktualizacja

- **Bez gita (folder z ZIP-a):** zamknij aplikację (Ctrl+C w jej oknie) i kliknij dwukrotnie `aktualizuj.bat` w folderze aplikacji. Skrypt pobierze najnowszą wersję z GitHuba, podmieni pliki i doinstaluje brakujące biblioteki. Twoje nazwy lig i krajów, ustawienia oraz cache są w `%USERPROFILE%\.fm_moneyball` i zostają bez zmian.
- **Z gitem:** zainstaluj go raz (`winget install -e --id Git.Git`), pobierz aplikację poleceniem `git clone -b claude/optimistic-lamport-we8t1j https://github.com/Hubihp/FM26-Moneyball-Dashboard.git`, a potem aktualizuj przez `git pull` w jej folderze. Polecenie `git pull` nie działa w folderze rozpakowanym z ZIP-a („not a git repository”).

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

- **Nazwy lig.** Zapis nie zawiera nazw lig, tylko ich identyfikatory. Domyślna mapa jest w `dane/nazwy_rozgrywek.csv`. Własne nazwy wpiszesz w zakładce „Ligi i kraje” albo nauczysz ze starych eksportów CSV (panel „Źródło danych”, sekcja „Nazwy lig”); trafiają do `~/.fm_moneyball/nazwy_rozgrywek.csv`. Identyfikatory są wspólne dla wszystkich zapisów FM26.
- **Narodowości.** Zapis nie zawiera nazw krajów, więc aplikacja nadaje je sama: kraj nazwanej ligi to najczęstsza narodowość jej zawodników (Ekstraklasa → Polska), a kraje bez wczytanej ligi rozpoznaje po składach typowo krajowych klubów (np. Hibernian, Aberdeen, Motherwell → Szkocja). Gdyby któregoś kraju nie udało się nazwać, pokaże się jako „Kraj #id” i można go nazwać w zakładce „Ligi i kraje”. Zawodnik bez narodowości w zapisie ma „Nieznana”. Ligi bez nazwy są pokazywane jako „Rozgrywki #id” i dostają najniższy mnożnik ligowy. Mnożniki lig spoza wbudowanej tabeli (np. K League) zapisują się w `dane/mnozniki_lig.csv`.
- **Wolni agenci** (zawodnicy bez klubu, którzy grali w tym sezonie) trafiają do puli z ligą „Wolny agent”. Można to wyłączyć w „Opcjach odczytu zapisu”.
- **Waluta.** Kwoty są zapisane w walucie bazowej. Domyślny kurs 1,157 odpowiada temu, co gra pokazuje w euro. Można go zmienić w „Opcjach odczytu zapisu”.
- **Ceny.** Zapis zawiera rzeczywistą wartość transferową z gry. Gra pokazuje zamiast niej widełki zależne od wiedzy skautów (np. 80–325 tys. € przy wartości 315 tys. €). Dlatego ceny z zapisu są zwykle wyższe niż przy imporcie CSV, który brał środek widełek.
- **Liga klubu** to rozgrywki, w których jego pierwsza drużyna gra najwięcej kolejek ligowych w bieżącym sezonie (z terminarza, łącznie z kolejkami zaplanowanymi). Dzięki temu np. kluby brazylijskie mają Série A także wtedy, gdy trwają jeszcze ligi stanowe. Drużyny kobiece (kluby o tej samej nazwie co męskie) i ich rozgrywki są pomijane.
- **Ligi bez identyfikatora w bazie** (np. belgijska Jupiler Pro League) dostają w mapie nazw klucz zastępczy `-numer_kraju` (np. `-131,Jupiler Pro League`).
- **Bez danych ukrytych.** Aplikacja nie odczytuje z zapisu danych niewidocznych w grze (CA/PA, atrybuty ukryte, osobowość).

## Diagnostyka zapisu

Aby sprawdzić, czy Twój zapis jest czytany poprawnie, uruchom:

```bash
python narzedzia/zbadaj_zapis.py "<ścieżka do zapisu>.fm" [stare_eksporty.csv ...] [--zapisz-nazwy]
```

Z plikami CSV skrypt rozpozna nazwy lig. Opcja `--zapisz-nazwy` zapisze je do `~/.fm_moneyball/nazwy_rozgrywek.csv`, a raport pokaże przy każdej lidze kilka klubów, żeby łatwo było sprawdzić przypisanie. W repozytorium jest już mapa najpopularniejszych lig: Anglia, Francja, Niemcy, Holandia, Włochy, Portugalia, Hiszpania, Belgia, Polska, Chorwacja, Brazylia (Série A–C), Argentyna, Meksyk, Japonia, Kolumbia, Korea Płd. i MLS. Brazylijskie ligi, których nazw nie ma w grze, nazywają się „Liga brazylijska (nieznana) #id”. Opcja `--klub "Nazwa klubu"` (można podać kilka razy) wypisze wszystkie tabele, w których występuje klub. Pomaga to zrozumieć, skąd wzięło się jego przypisanie do ligi.

Skrypt wypisze liczbę odczytanych zawodników i lig, pokrycie kolumn oraz próbkę Twojej kadry do porównania z ekranem gry. Zapisze też mały raport `raport_zapisu.json`.

## Struktura

```
fm_moneyball/              logika niezależna od interfejsu
  __main__.py              uruchomienie: python -m fm_moneyball
  serwer/                  API (FastAPI): api.py składa aplikację z trasy/ (zrodlo, ligi, analiza, frontend),
                           modele.py (zapytania), obliczenia.py (wynik z pamięcią podręczną), stan.py
                           (wczytywanie w tle); static/ = zbudowany frontend
  analiza.py               ranking, filtry, kolumny, radar, podobni, koszt/okazje, moja kadra
  historia.py              migawki kolejnych zapisów i wskaźniki rozwoju
  ligi.py                  mnożniki lig ustawione przez użytkownika
  kraje.py                 nazwy krajów (narodowości): z nazwanych lig i ręczne
  mapy.py                  pliki id,nazwa: domyślne (dane/) i użytkownika (~/.fm_moneyball)
  stale.py                 kolumny, cechy, wagi, mnożniki lig
  parsery.py               tekst z FM -> liczby
  schemat.py               kolumny pochodne, ID, nazwy lig i krajów
  model.py                 SCORE, percentyle, macierz stylu
  zrodla/csv_fm.py         eksport CSV + dane demo
  zrodla/zapis_fm.py       plik zapisu .fm (fmsave)
  zrodla/folder.py         folder zapisów gry
narzedzia/zbadaj_zapis.py  diagnostyka zapisu
frontend/                  interfejs React + TypeScript (Vite, Mantine, AG Grid, ECharts)
tests/                     testy (pytest)
```

Plik .exe: `pip install pyinstaller && pyinstaller fm26_moneyball.spec` (na Windows; wynik w `dist/`).

Testy: `python -m pip install -r requirements-dev.txt && python -m pytest`

Zmiany w interfejsie (wymaga Node.js 20+): `cd frontend && npm install && npm run build` zapisuje wynik do `fm_moneyball/serwer/static/`. Tryb deweloperski: `python -m fm_moneyball --bez-przegladarki` oraz `npm run dev` w katalogu `frontend`.
