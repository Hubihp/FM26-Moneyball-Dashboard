# FM27 Dashboard

Narzędzie do wyszukiwania zawodników w Football Manager 27 w stylu Moneyball (od wersji 2.0 tylko zapisy FM27). Zapisy czyta biblioteka fmsave (0.12.3); jej obsługa FM27 jest jeszcze wstępna (część pól niepotwierdzona), więc program pokazuje ostrzeżenie. Liczy wynik (SCORE) na tle innych zawodników z tej samej pozycji, z korektą na małą liczbę minut i siłę ligi. Do tego porównanie na radarze, wyszukiwanie „sobowtóra” i wykresy wyniku względem ceny.

## Uruchomienie

```bash
python -m pip install -r requirements.txt      # Python 3.12 lub nowszy
python -m fm_moneyball                         # otwiera aplikację w przeglądarce (http://localhost:8765)
```

Aplikacja działa lokalnie: serwer w Pythonie czyta zapisy gry z dysku, a interfejs otwiera się w przeglądarce. Do uruchomienia nie jest potrzebny Node.js, bo zbudowany interfejs jest w repozytorium.

Co jest w aplikacji:
- **Źródło danych:** po starcie aplikacja pyta, co wczytać: zapis z folderu gry (najszybciej; opcjonalnie śledzi kolejne zapisy), wgranie pliku `.fm` albo dane demo. Nic nie wczytuje się samo, chyba że włączysz „Wczytuj to źródło automatycznie przy uruchomieniu”. Podczas odczytu widać etap i czas. Wynik odczytu trafia do pamięci podręcznej (`~/.fm_moneyball/cache`, 3 ostatnie zapisy), więc ponowne otwarcie tego samego zapisu, także po restarcie, jest natychmiastowe.
- **Pozycja** wybierana kliknięciem na boisku. 14 pozycji, każda to osobna pula: BR (Bramkarz), ŚO (Środkowy Obrońca), LO/PO (Lewy/Prawy Obrońca), LWAH/PWAH (Lewy/Prawy Wahadłowy), DP (Defensywny Pomocnik), ŚP (Środkowy Pomocnik), LP/PP (Lewy/Prawy Pomocnik), OP (Ofensywny Pomocnik), LS/PS (Lewy/Prawy Skrzydłowy), N (Napastnik). W puli są tylko zawodnicy, którzy mają tę pozycję w kolumnie „Pozycje” (np. PS pokazuje wyłącznie prawych skrzydłowych). SCORE, percentyl i wycena są liczone w obrębie dokładnej pozycji; strona lewa i prawa mają te same wagi statystyk.
- **Ranking:** tabela z sortowaniem i filtrami w kolumnach (menu po polsku), płynna przy tysiącach zawodników. Ligę i narodowość filtrujesz w menu kolumny. Filtry po lewej: wiek, cena, pensja (tygodniowa, jak w grze), kontrakt, niedowartościowanie, rozwój w sezonie, noga, minimum minut (domyślnie automatyczne, osobno dla każdej ligi: 1/3 minut podstawowego zawodnika tej ligi w danym momencie sezonu - jesienią mniej niż na koniec sezonu; własną wartość wpiszesz, „auto” wraca do automatu; także w Okazjach, Wykresach i Podobnych). Zawodnicy poniżej 900 minut mają w rankingu pomarańczowe minuty (mała próba), pomijanie własnego klubu. Wagi statystyk zmieniasz suwakami. Filtry są wspólne dla wszystkich pozycji (zmiana pozycji ich nie zmienia; osobno dla pozycji są tylko „Kandydaci z innych pozycji”), wagi statystyk są osobne dla każdej pozycji, a układ tabel (sortowanie, kolejność, szerokość i widoczność kolumn, przycisk „Kolumny”) - po odświeżeniu strony; „Przywróć układ” wraca do domyślnego.
- **Kandydaci z innych pozycji:** pole wielokrotnego wyboru w panelu (puste = wyłączone) dodaje do rankingu zawodników grających nominalnie na wskazanych pozycjach, ocenionych według kryteriów wybranej pozycji (np. defensywny pomocnik, który ma profil prawego obrońcy). Nie zmieniają oni wyników zawodników tej pozycji. W tabeli mają fioletowy pasek, kolumnę „Kandydat z pozycji” i, z zapisu gry, „Ocena na pozycji” (1–20, czyli jak łatwo go przekwalifikować).
- **Lista życzeń:** gwiazdka przy zawodniku (w rankingu, okazjach i karcie zawodnika) dodaje go do listy; lista jest zapamiętywana w przeglądarce, a wynik liczony w pozycji, z której zawodnik został dodany. Zawodnik jest odnajdywany niezależnie od tej pozycji: także gdy dodano go jako kandydata z innej pozycji, a w ostateczności w jego głównej pozycji. Tabela ma te same kolumny, kolejność, formatowanie i zaznaczanie co Ranking pozycji wybranej na boisku, plus kolumnę „Pozycja na liście”. Zaznaczonych zawodników (pola wyboru) można przekazać do Porównania.
- **Twój klub** jest odczytywany z zapisu i widoczny w nagłówku (przy kilku prowadzonych drużynach można wybrać jedną). Jego zawodnicy są wyróżnieni na bursztynowo w tabelach, w karcie zawodnika i na wykresach.
- **Kolumny Moneyball:** koszt (cena + 3 lata pensji; u wolnego agenta tylko pensja), okazje.
- **Niedowartościowani:** w każdej pozycji aplikacja uczy się, ile zwykle kosztuje zawodnik z danym wynikiem, wiekiem i długością kontraktu (regresja na logarytmie ceny). Długość kontraktu wchodzi odcinkami (załamanie po roku i po dwóch latach), bo w grze cena zawodnika z kontraktem krótszym niż rok jest bliska zeru niezależnie od wyniku, a kolejne lata podnoszą ją coraz mniej. Kolumna „Wycena wg wyniku” to ta typowa cena, a „Niedowartościowanie” to wycena / cena: ×2 znaczy, że zawodnik gra jak typowy zawodnik dwa razy droższy. Model celowo nie zna ligi ani klubu, więc wskazuje tanich zawodników z mniejszych lig i klubów, którzy grają jak drożsi. Na wykresie „Cena vs wycena” okazje leżą nad przekątną; podpis pokazuje jakość modelu (R²). Zawodnicy do 21 lat są oznaczeni „U21” (w tabeli, karcie i rombem na wykresie): ich cena zawiera potencjał, którego model nie widzi, więc ich niedowartościowanie jest zaniżone. Osobnego modelu dla tej grupy nie ma celowo: premia za potencjał zależy od PA, którego aplikacja nie czyta, a w puli jednej pozycji wycenionych zawodników do 21 lat jest za mało na stabilną regresję. Model nie ekstrapoluje: przy wycenie SCORE i wiek są obcinane do zakresu zawodników, na których uczył się model, a wycena nie przekracza najwyższej ceny w puli (karta zawodnika pokazuje wtedy „ograniczona”). Bez tego zawodnik o wyniku wysoko ponad resztą pozycji dostawał wycenę rosnącą wykładniczo i wychodził jako skrajnie niedowartościowany.
- **Skurczenie przy małej próbie** działa ze stałą wartością (5 meczów: waga własnych statystyk = n90 / (n90 + 5), przy 1000 minutach ok. 69%) i nie ma już suwaka. Chroni przed przypadkowymi wynikami z krótkiej próby, także u zawodników twojej kadry poniżej progu minut.
- **Okazje:** wybór rodzajów okazji jest wspólny dla wszystkich pozycji i zapamiętywany; bez zaznaczeń lista pokazuje zawodników z dowolną okazją. Zawodnik jest tu wtedy i tylko wtedy, gdy ma dany znacznik w kolumnie „Okazje” rankingu; przełącznik „Pomiń zawodników mojego klubu” jest widoczny i mówi, ilu ukrył. Rodzaje: zawodnicy niedowartościowani (×2 i SCORE ≥ 55), z kończącym się kontraktem (≤ 6 i ≤ 12 mies.) oraz szybko rozwijający się (do 23 lat, SCORE o co najmniej 5 wyższy niż w poprzednim sezonie). Zawodników zaznaczasz do porównania tak samo jak w Rankingu.
- **Historia i rozwój:** przy każdym wczytaniu zapisu kariery aplikacja zapisuje migawkę zawodników (`~/.fm_moneyball/historia/FM27/<menedżer>/<data w grze>.csv.gz`, jedna na miesiąc w grze; klucz zawodnika to UID z zapisu). Kariera to menedżer, a nie klub, więc po zmianie klubu (np. z Tottenhamu na Barcelonę) historia jest dalej jedna; migawki z dawnych katalogów klubowych są przenoszone automatycznie. Zapis gry ma statystyki tylko bieżącego sezonu, więc historię budują migawki: przy wczytaniu z folderu gry program w tle czyta też starsze zapisy z tego folderu (po jednym na miesiąc w grze, najwyżej 6 na jedno wczytanie, tylko tej samej kariery) i tworzy z nich migawki, więc Δ SCORE i wykresy rozwoju działają od razu. Gdy jest migawka z poprzedniego sezonu (sezon od 1 lipca), tabela pokazuje „Δ SCORE” (SCORE wtedy przeliczony tymi samymi wagami na ówczesnej puli pozycji; porównanie z ostatnią migawką z wcześniejszego sezonu). Zmiana jest liczona także przy małej liczbie minut, ale wtedy jest oznaczona ⚠ (pomarańczowa kursywa): poniżej 1000 minut w którymś sezonie wynik jest mniej pewny; okazja „szybki rozwój” wymaga pełnej próby. Gdy w dawnej migawce zawodnik nie miał danej pozycji (np. przed przekwalifikowaniem), jego SCORE z tamtego okresu jest liczony według kryteriów tej pozycji, na skali zawodników, którzy wtedy na niej grali. W panelu jest filtr „Rozwój w sezonie co najmniej”. Karta zawodnika pokazuje wykres SCORE i wartości we wszystkich migawkach oraz statystyki /90 z każdego sezonu; okresy poniżej 1000 minut są widoczne, ale oznaczone (⚠, pusty punkt na wykresie). Zakładka Porównanie ma wspólny wykres historii porównywanych zawodników (SCORE albo wybrana statystyka) i zestawienie Δ SCORE.
- **Moja kadra:** każda pozycja twojego klubu na tle całej puli: najlepszy zawodnik, średni wiek i kończące się kontrakty. Pozycje są ułożone od bramkarza do napastnika, a „Szukaj wzmocnienia” otwiera ranking tej pozycji bez twoich zawodników. Przełącznik u góry ma jeszcze dwa widoki w duchu Moneyball: **Sprzedaj drogo** (twoi zawodnicy, których cena jest co najmniej 1,3 raza wyższa niż wycena wg wyniku, z najtańszym tańszym zastępcą spoza klubu o SCORE niższym najwyżej o 3 i stylu gry podobnym w co najmniej 85% oraz zyskiem z wymiany; bez takiego zastępcy wyświetla się komunikat) i **Optymalizator budżetu** (budżet transferowy i budżet na pensje - domyślnie z finansów klubu w zapisie gry: pozostały budżet transferowy i wolne miejsce w budżecie płacowym, z możliwością wpisania własnych kwot - oraz wybrane pozycje do wzmocnienia → zestaw zawodników z największą sumą przyrostu SCORE ponad twojego najlepszego na każdej pozycji, porównany z najlepszym pojedynczym zawodnikiem za te same pieniądze; wynik jest optymalny - przeszukiwanie z odcinaniem). Oba widoki uwzględniają filtry panelu. Przycisk „Następca” przy każdym zawodniku szuka 15 piłkarzy o najbardziej podobnym stylu gry, także z innych pozycji: statystyki /90 pozycji zawodnika są przeliczane na z-score (średnia i odchylenie ważone minutami, skurczenie przy małej liczbie minut), a podobieństwo to cosinus kąta między wektorami (100% = identyczne proporcje statystyk; liczy się styl, nie poziom). Wynik uwzględnia filtry panelu dla tej pozycji (minuty, wiek, cena, kontrakt, noga) i pomija twój klub; tabela ma kolumny Rankingu i kolumnę „Podobieństwo”.
- **Tablica taktyczna** (Moja kadra → Taktyka): boisko pionowe (twoja bramka na dole), formacje 4-3-3, 4-2-3-1, 4-4-2, 4-1-4-1, 4-3-1-2, 3-5-2, 3-4-3, 5-3-2, 5-4-1. Zawodnika przeciągasz z listy kadry na pozycję (albo klikasz pozycję, a potem zawodnika); żeton na żeton zamienia zawodników, żeton na wolne miejsce przesuwa pozycję, kliknięcie kółka zmienia pozycję miejsca. Każdy żeton pokazuje SCORE zawodnika na tej pozycji albo, poza naturalną pozycją, ocenę pozycji z gry (1–20). „Ułóż najlepszą XI” wybiera skład z największą sumą SCORE (optymalny przydział). Zawodnika z listy możesz upuścić w dowolnym miejscu boiska - trafi na najbliższą pozycję; lista pokazuje minuty w sezonie (poniżej 1000 na pomarańczowo). Ustawienia zapisujesz pod nazwami (np. „Liga”, „Puchar”) w pamięci programu. **Taktyka z gry:** „Wczytaj taktykę z gry” ustawia formację i jedenastkę wybraną w grze (pozycje i zawodnicy z zapisu); panel obok pokazuje nazwę taktyki, mentalność, zmiany pozycji bez piłki i rezerwowych. Przy kilku taktykach pokazana jest ta, do której pasuje wybrana XI (oceny pozycji zawodników). Ról i instrukcji biblioteka fmsave jeszcze nie odczytuje.
- **Tylko pierwsza drużyna:** Moja kadra (i liczone z niej funkcje) domyślnie pomija zawodników rezerw, drużyn B i juniorów - rozpoznawanych po drużynie w klubie zapisanej w pliku gry; przełącznik „Tylko pierwsza drużyna” pokazuje wszystkich, z nazwą drużyny przy zawodniku.
- **Profil drużyny:** twoja drużyna na tle wszystkich klubów swojej ligi (jak w analizach Gradient Sports). Statystyki drużyn to sumy statystyk ligowych zawodników pierwszej drużyny z zapisu (zawodnik liczy się dla klubu, w którym grał), przeliczone na mecz według tabeli ligi; każdy wskaźnik ma wartość, średnią ligi i miejsce (1 = najlepsze; przy faulach, kartkach, stratach i błędach mniej = lepiej). Sekcje: Wyniki (punkty, bramki, średnia ocena), Z piłką (podania, celność, podania progresywne, kluczowe podania, 100% sytuacje, strzały, xG, xG na strzał, gole − xG, dośrodkowania, dryblingi, straty), Bez piłki (skuteczność odbiorów, główki, przechwyty, odzyskane piłki, pressing, bloki, wybicia, faule, kartki, błędy prowadzące do gola), Fizycznie (dystans i sprinty na mecz z rozkładem ligi), automatyczne mocne i słabe strony. **Atletyzm składu:** wynik 0–100 każdego zawodnika względem tej samej pozycji w lidze (50 = średnia) z dystansu i sprintów na 90 minut, dla zawodników z co najmniej 25% minut możliwych; wynik drużyny ważony minutami i ranking klubów. **Zmiany względem poprzedniego sezonu:** największe spadki i wzrosty SCORE (z historii zapisów) oraz średniej oceny (z historii sezonów zapisanej w pliku gry, wczytywanej w tle), dla zawodników z co najmniej 25% minut możliwych w lidze w obu sezonach. Pełne dane są tylko z zapisu gry; dla demo i CSV statystyki drużyn są przybliżone z danych zawodników.
- **Karta zawodnika:** kliknij nazwisko, żeby zobaczyć szczegóły, koszt i okazje, porównanie z najlepszym zawodnikiem twojego klubu na tej pozycji (werdykt: wzmocnienie przy SCORE wyższym o co najmniej 3, podobny poziom, nie wzmacnia; plus kluczowe statystyki pozycji), historię i rozwój, profil statystyk na radarze i podobnych zawodników.
- **Porównanie:** do 4 zawodników na jednym radarze, razem z tabelą wartości: w każdym wierszu najlepsza wartość jest na zielono, a najgorsza na czerwono (przy stratach piłki mniej = lepiej). Zawodników dodasz z rankingu, z Okazji i z Listy życzeń (pola wyboru i „Porównaj zaznaczonych”).
- **Wykresy:** wynik względem kosztu lub wartości z granicą wynik/koszt (zawodnicy, od których nikt nie jest jednocześnie lepszy i tańszy), „Cena vs wycena wg wyniku”, „Wiek vs SCORE” (kolor = cena, rozmiar = minuty: młodzi z wysokim wynikiem przed wzrostem ceny) i, gdy jest historia, „Rozwój: Δ SCORE vs wiek”.
- **Ligi i kraje:** ligi wykryte w zapisie (z przykładowymi klubami, mnożnikiem i jego źródłem) i narodowości zawodników. Nazwy i mnożniki ustawiają się same (patrz „Korekta ligowa”); własną nazwę ligi, własny mnożnik albo nazwę kraju możesz wpisać opcjonalnie - puste pole wraca do wartości automatycznej. Zmiany działają od razu i zapisują się w `~/.fm_moneyball` (`nazwy_rozgrywek.csv`, `mnozniki_lig_klucz.csv`, `nazwy_krajow.csv`), poza folderem aplikacji.
- **Interfejs:** nagłówek pokazuje imię i nazwisko menedżera z zapisu; okno otwiera się zmaksymalizowane; Ctrl + kółko myszy (albo Ctrl + „+”/„−”) powiększa i pomniejsza cały interfejs (60–200%), Ctrl + 0 wraca do 100%, a skala jest zapamiętywana. Odwiedzone karty zostają w pamięci, więc powrót na nie jest natychmiastowy.

### Wagi statystyk w SCORE

Wagi domyślne (procenty, każda pozycja sumuje się do 100; strona lewa i prawa mają te same wagi). Wagi zmienisz suwakami w panelu; własne wagi pozycji mają pierwszeństwo przed domyślnymi.

| Cecha | BR | ŚO | LO/PO | LWAH/PWAH | DP | ŚP | LP/PP | OP | LS/PS | N |
|---|---|---|---|---|---|---|---|---|---|---|
| Liczba goli na 90 min | – | – | – | – | – | 5 | 7 | 5 | 12 | 18 |
| Oczekiwane gole bez karnych/90 | – | – | – | – | – | 5 | 8 | 15 | 12 | 20 |
| Oczekiwane gole na strzał | – | – | – | – | – | – | – | – | 5 | 7 |
| Skuteczność strzałów (%) | – | – | – | – | – | – | – | – | – | 7 |
| Oczekiwane asysty/90 | – | – | 20 | 20 | 5 | 17 | 18 | 20 | 18 | 10 |
| Asysty/90 | – | – | 5 | 5 | – | 4 | 5 | 5 | 5 | 5 |
| Kluczowe podania z gry/90 | – | 3 | 12 | 12 | 7 | 15 | 12 | 15 | 12 | 8 |
| Stworzone 100% sytuacje/90 | – | – | – | – | – | – | – | 10 | – | – |
| Udane dośrodkowania/90 | – | – | 5 | 8 | – | – | 10 | – | 3 | – |
| Liczba dryblingów/90 | – | – | – | 10 | – | 8 | 10 | 10 | 15 | 7 |
| Podania progresywne/90 | – | 10 | 10 | 10 | 12 | 12 | 5 | 5 | – | – |
| Celność podań (%) | – | 7 | 3 | – | 8 | 5 | – | – | – | – |
| Strata piłek na podanie (mniej = lepiej) | 15 | 10 | 7 | 7 | 10 | 10 | 8 | 8 | 8 | 5 |
| Przechwyty/90 | – | 14 | 12 | 8 | 15 | 5 | – | – | – | – |
| Odzyskane piłki/90 | 5 | 18 | 10 | 7 | 15 | 5 | 7 | – | 5 | 5 |
| Udane odbiory/90 | – | 10 | 8 | 5 | 10 | 5 | 5 | 3 | – | – |
| Udane próby pressingu/90 | – | 5 | 5 | – | 8 | 2 | 3 | 2 | 3 | 3 |
| % wygranych pojedynków główkowych | – | 8 | – | – | – | – | – | – | – | 3 |
| Wygrane główki/90 | – | 7 | – | – | 5 | – | – | – | – | 2 |
| Sprinty/90 | – | – | – | 5 | – | – | – | – | – | – |
| Uniknięte oczekiwane gole/90 | 50 | – | – | – | – | – | – | – | – | – |
| Skuteczność obron (%) | 15 | – | – | – | – | – | – | – | – | – |
| Obrony chwytem (%) | 5 | – | – | – | – | – | – | – | – | – |
| Błędy prowadzące do gola/90 (mniej = lepiej) | 10 | 5 | – | – | 2 | – | – | – | – | – |
| Kartki/90 (mniej = lepiej) | – | 3 | 3 | 3 | 3 | 2 | 2 | 2 | 2 | – |

- **Statystyki ujemne** (strata piłek na podanie, kartki, błędy prowadzące do gola) obniżają wynik: im więcej, tym niższy SCORE. Kartki: żółta = 1, czerwona = 3. Same faule nie obniżają wyniku, bo w danych z gry rosną razem z udanymi odbiorami (to skutek aktywnej obrony) i nie obniżają średniej oceny, w przeciwieństwie do kartek.
- **Bez podwójnego liczenia:** statystyki silnie ze sobą skorelowane (r > 0,6 na zapisie) dzielą jedną wagę zamiast dostawać dwie: udane odbiory i udany pressing, % wygranych główek i wygrane główki, gole, npxG i skuteczność, xA i asysty. Pominięte, bo dublują inne: strzały (npxG), wszystkie kluczowe podania (z gry), próby pressingu (udany pressing).
- **Pominięte celowo:** wybicia, bloki i zablokowane strzały (zależą od tego, jak często drużyna się broni, a nie od jakości obrońcy), czyste konta i stracone gole bramkarza (wynik drużyny; uniknięte xG izolują bramkarza), celność podań bramkarza (styl wznawiania gry), spalone, faule wywalczone, gracz meczu.
- **Boczny pomocnik** (LP/PP, np. w 4-4-2) ma osobne wagi od skrzydłowego (LS/PS): więcej dośrodkowań i pracy w obronie, mniej strzałów.
- **Wahadłowy** sam daje szerokość w ustawieniu z trójką obrońców: główny kreator z boku, przenosi piłkę i biega całą flankę. Obronę asekuruje trzech stoperów, więc część defensywna jest mniejsza niż u bocznego obrońcy.
- **Ofensywny pomocnik** jest oceniany głównie za tworzenie sytuacji i zagrożenie z wejść w pole karne (npxG zamiast losowych goli).

**Niepełne statystyki.** Zapis gry zawiera szczegółowe statystyki (dystans, pressing, przechwyty, podania, odbiory, kluczowe podania, główki, dryblingi) tylko z części rozgrywek; z pozostałych (np. lig drużyn rezerw i młodzieżowych) ma tylko gole, xG, xA, strzały, asysty, odzyskane piłki i kartki, a brakujące pola podaje jako 0. Aplikacja rozpoznaje takie wiersze (pełne statystyki mają dystans ok. 10 km/90, bramkarz ok. 5) i liczy każdą statystykę tylko z minut, w których była mierzona. Gdy takich minut jest za mało (poniżej 270 i 25% minut zawodnika), statystyka jest brakiem danych, a wynik przyjmuje dla niej średnią pozycji - bez kary za „zero”, którego gra nie zmierzyła. Tacy zawodnicy mają ⚠ przy nazwisku i plakietkę „niepełne statystyki” w karcie; ich SCORE opiera się na mniejszej liczbie statystyk, więc jest mniej pewny. Skalę SCORE (50 = przeciętny, 10 = jedno odchylenie) wyznaczają zawodnicy z danymi dla co najmniej 90% wag. Δ SCORE względem migawki sprzed wersji 1.7.0 jest liczone na statystykach wspólnych dla obu sezonów, żeby pokazywało rozwój zawodnika, a nie zmianę modelu.

### Role (gotowe wagi)

W panelu „Wagi statystyk” lista „Rola” ustawia gotowy zestaw wag (każdy sumuje się do 100). To punkt startu: suwaki działają dalej, a zmienione wagi są „własne”. „Domyślna (uniwersalna)” wraca do wag z tabeli powyżej. Dokładne wagi ról są w `fm_moneyball/stale.py` (`_ROLE`).

| Pozycja | Role |
|---|---|
| BR | **Bramkarz klasyczny** - przede wszystkim obrona strzałów; gra nogami ma małe znaczenie. **Bramkarz-libero** - wysoko ustawiony: wyjścia poza pole karne i rozpoczynanie akcji krótkim podaniem. |
| ŚO | **Stoper grający piłką** - wyprowadza piłkę: podania progresywne, celność, mało strat; odbiór nadal ważny. **Zabijaka** - klasyczny stoper: wygrywa główki i pojedynki, przecina podania; rozegranie drugorzędne. |
| LO/PO | **Ofensywny boczny obrońca** - daje szerokość i kreuje: xA, dośrodkowania, podłączanie się do ataku. **Defensywny boczny obrońca** - przede wszystkim broni flanki: odbiory, przechwyty, główki. **Odwrócony boczny obrońca** - schodzi do środka pola: celność, progresja i bezpieczeństwo piłki. |
| LWAH/PWAH | **Ofensywny wahadłowy** - główny kreator z boku: xA, dośrodkowania, drybling, sprinty. **Defensywny wahadłowy** - piąty obrońca: odbiór i asekuracja, mniej kreowania. |
| DP | **Regista** - rozgrywający sprzed obrony: progresja, celność, kluczowe podania, mało strat. **Niszczyciel** - odbiera piłkę: odbiory, przechwyty, pressing, główki; rozegranie proste. |
| ŚP | **Box-to-box** - wszędzie po trochu: bieganie, odbiór, wejścia w pole karne. **Rozgrywający** - kreator z głębi: kluczowe podania, xA, progresja i celność. **Pomocnik pressujący** - odzyskuje piłkę wysoko: pressing, odbiory, przechwyty. |
| OP | **Kreator** - ostatnie podanie: xA, kluczowe podania, 100% sytuacje. **Cień napastnika** - wbiega w pole karne i strzela: npxG, gole, xG na strzał. |
| LP/PP | **Klasyczny dośrodkowujący** - gra przy linii i dośrodkowuje: dośrodkowania, xA, drybling. **Pracowity boczny pomocnik** - pomaga w obronie: odbiory, pressing, odzyskane piłki. |
| LS/PS | **Odwrócony skrzydłowy** - schodzi do środka i strzela: gole, npxG, drybling. **Klasyczny skrzydłowy** - gra przy linii: dośrodkowania, xA, drybling 1 na 1. |
| N | **Snajper** - kończy akcje: gole, npxG, jakość i skuteczność strzałów. **Target man** - gra tyłem i w powietrzu: wygrane główki, gole, zgrywanie piłek. **Fałszywa 9** - schodzi do rozegrania: xA, kluczowe podania, drybling, progresja. **Napastnik pressujący** - pierwszy obrońca: pressing, odzyskane piłki, odbiory, do tego gole. |

### Mnożnik ligi według drużyny gry

Zawodnik gra często nie w lidze swojego klubu: w rezerwach, drużynie młodzieżowej (np. „U23”, „B”, „C”) albo przed transferem w innym klubie. Mnożnik ligi w SCORE to średnia mnożników lig, w których grał w sezonie, ważona minutami. Minuty w rezerwach, drużynach młodzieżowych i ligach niewykrytych liczą się z mnożnikiem rezerw: domyślnie 0,60 (korekta −20 pkt), do zmiany w zakładce „Ligi i kraje”. Kolumna „Liga” i filtry zostają według klubu (tam się zawodnika kupuje). Karta zawodnika pokazuje, gdzie grał; w rankingu taki zawodnik ma gwiazdkę przy lidze (≥ 25% minut poza ligą klubu).

### Korekta ligowa (mnożnik ligi)

SCORE zawiera korektę za siłę ligi: mnożnik = 1 + korekta / 50 (korekta w punktach SCORE). Od wersji 2.0 korekta pochodzi z danych FM27, a nie z ręcznej tabeli:

- **Transfery („league equivalency” z sabermetryki).** Na dwóch pełnych sezonach kariery (zapisy z 01.06.2027 i 01.06.2028) porównany jest wynik za grę (SCORE bez korekty ligi) tych samych zawodników przed i po zmianie ligi: 4023 zawodników z co najmniej 900 minutami w obu sezonach na tej samej pozycji, w tym 770 po zmianie ligi. Regresja grzbietowa daje efekt każdej ligi (z poprawką na wiek). Wynik jest w `dane/korekty_lig.csv` (korekta i liczba transferów).
- **Reputacja ligi.** Dla każdej ligi z zapisu program liczy medianę reputacji jej klubów. Krzywa kwadratowa dopasowana do 25 lig z co najmniej 10 transferami przelicza ją na korektę (średni błąd 1,7 pkt wobec 2,9 pkt dawnej tabeli); poniżej zakresu danych korekta maleje liniowo, nie niżej niż −28 pkt. Dzięki temu każda liga, także nieznana (nowa w kolejnej wersji gry), ma korektę od razu.
- **Łączenie.** Korekta z transferów łączona z krzywą wagą n / (n + 30), gdzie n to liczba transferów. Przy n ≥ 30 przeważają dane z transferów („z transferów” w zakładce), poniżej reputacja.
- **Rezerwy, młodzież i rozgrywki niewykryte:** −20 pkt (mnożnik 0,60); do zmiany w „Ligach i krajach”.
- **Własny mnożnik** z zakładki „Ligi i kraje” ma zawsze pierwszeństwo.

Wybrane ligi (zapis 06.11.2027), mnożnik dawny → nowy:

| Liga | Dawny | Nowy | Źródło |
|---|---|---|---|
| Premier League | 0,918 | 0,917 | transfery |
| Serie A | 0,860 | 0,910 | transfery |
| LaLiga | 0,866 | 0,870 | transfery |
| Bundesliga | 0,867 | 0,842 | transfery |
| Ligue 1 | 0,856 | 0,838 | transfery |
| Série A (Brazylia) | 0,826 | 0,797 | transfery |
| MLS / Liga MX | 0,66 (brak nazwy) | 0,779 | reputacja |
| Eredivisie | 0,783 | 0,744 | transfery |
| Liga Portugal | 0,814 | 0,732 | transfery |
| Ekstraklasa | 0,795 | 0,718 | transfery |
| EFL Championship | 0,811 | 0,715 | transfery |
| Jupiler Pro League | 0,816 | 0,713 | transfery |
| 2. Bundesliga | 0,778 | 0,699 | transfery |
| Saudi Pro League | 0,66 (brak nazwy) | 0,693 | transfery |
| Eerste Divisie | 0,660 | 0,620 | transfery |
| ligi stanowe Brazylii | 0,66 (brak nazwy) | 0,44-0,62 | reputacja |

Wpływ na ranking: kolejność zawodników zgodna z dawną w 97-98,5% (korelacja rang), w pierwszej pięćdziesiątce każdej pozycji wymienia się 5-8 zawodników - wchodzą głównie zawodnicy Serie A, wypadają zawodnicy Championship, lig portugalskiej i belgijskiej oraz brazylijskich lig stanowych.

### Rozbicie SCORE

Karta zawodnika ma wykres „Skąd ten SCORE”: punkt wyjścia (przeciętny zawodnik pozycji, ok. 50), wkład każdej statystyki (waga × odległość od średniej pozycji w odchyleniach, po skurczeniu przy małej liczbie minut; zielony podnosi, czerwony obniża, szary - brak danych) i korekta ligowa. Suma to dokładnie SCORE.

### Prognoza SCORE za rok

Kolumna „Prognoza SCORE” (i karta zawodnika) to model w stylu „Marcel” z sabermetryki: prognoza = SCORE + powrót w stronę średniej + zmiana z wiekiem. Część wyniku z jednego sezonu to szczęście, więc wynik za grę (bez korekty ligowej, która jest stałą cechą zawodnika) wraca częściowo w stronę średniej pozycji: o (1 − b), gdzie b to stabilność wyniku rok do roku. Krzywa wieku mówi, o ile typowo zmienia się SCORE w danym wieku (młodzi rosną, po ok. 27 latach spadek). Oba elementy są szacowane z historii kariery - par sezonów zawodników z pełnymi statystykami i co najmniej 900 minutami w obu - i łączone z wartościami typowymi, policzonymi na dwóch sezonach kariery FM27 (b = 0,55; krzywa od +2 pkt w wieku 16-19 lat przez ok. 0 w wieku 27-29 do −1,5 po 35). Dane mogą przesunąć krzywą typową najwyżej o 2 pkt, bo jeden sezon historii to mało, a starsze migawki bywają liczone innym modelem. Bez historii działają same wartości typowe.

Dośrodkowania, 100% sytuacje, sprinty, odbiory, wygrane główki, celność podań, asysty, kartki, błędy i obrony chwytem pochodzą tylko z zapisu gry. Przy imporcie CSV te wagi są pomijane, a pozostałe przeliczane do 100%. Zawodnik trafia do każdej puli, w której jest naturalny (ocena pozycji ≥ 18, jak „naturalna” w grze), np. środkowy i prawy obrońca jest i w ŚO, i w PO. Wyłączenie opcji „Zawodnik na wszystkich naturalnych pozycjach” zostawia tylko pozycję z najwyższą oceną.

### Windows krok po kroku

1. Pobierz kod jako ZIP (na GitHubie: przycisk *Code*, potem *Download ZIP*) i rozpakuj go.
2. W PowerShellu przejdź do rozpakowanego folderu (`cd "ścieżka\do\folderu"`) i sprawdź wersję Pythona poleceniem `py --version`. Potrzebna jest wersja 3.12 lub nowsza. Jeśli jej brakuje, uruchom `winget install -e --id Python.Python.3.12` i otwórz PowerShell na nowo.
3. Zainstaluj biblioteki: `py -m pip install -r requirements.txt`. Na każdym nowym komputerze trzeba to zrobić raz.
4. Uruchom aplikację: `py -m fm_moneyball` (w folderze projektu). Otworzy się okno programu (albo przeglądarka z `--przegladarka`). Okno PowerShella musi pozostać otwarte, a `Ctrl+C` kończy pracę aplikacji.

### Program dla Windows (zalecane)

Pobierz [FM27Dashboard-Setup.exe](https://github.com/Hubihp/FM26-Moneyball-Dashboard/releases/latest/download/FM27Dashboard-Setup.exe) i uruchom. Instalator nie wymaga uprawnień administratora: instaluje program w `%LOCALAPPDATA%\Programs\FM27 Dashboard` i tworzy skrót w menu Start (opcjonalnie na pulpicie). Program otwiera się we własnym oknie, bez okna konsoli i bez przeglądarki; zamknięcie okna kończy jego działanie.

- **Aktualizacje:** przy każdym starcie program sprawdza na GitHubie, czy jest nowsza wersja. Jeśli jest, pokazuje pasek z opisem zmian i przyciskiem „Zainstaluj teraz”: pobiera instalator, sprawdza jego sumę kontrolną, instaluje go po cichu i uruchamia się ponownie. Wersja w nagłówku (np. „v1.0.0”) otwiera okno „O programie” z ręcznym sprawdzeniem aktualizacji.
- **Twoje dane** są w `%USERPROFILE%\.fm_moneyball`, poza folderem programu, więc aktualizacja ani odinstalowanie ich nie zmieniają: lista życzeń, filtry, wagi i układ tabel (`pamiec.json`), ustawienia źródła, historia zawodników, nazwy lig i krajów, pamięć podręczna zapisów i dziennik (`logi`). Zapisy gry zostają w folderze gry.
- **Przeniesienie danych z przeglądarki:** jeśli wcześniej używałeś aplikacji w przeglądarce, przy pierwszym uruchomieniu kliknij „Przenieś dane z przeglądarki” (także w oknie „O programie”). Twoja przeglądarka otworzy aplikację i prześle do programu listę życzeń, filtry i układ tabel; potem kliknij „Odśwież” w oknie programu.
- **SmartScreen:** instalator nie jest podpisany certyfikatem, więc przy pierwszej instalacji Windows może ostrzec o nieznanym wydawcy: „Więcej informacji”, potem „Uruchom mimo to”. Aktualizacje pobierane przez sam program tego ostrzeżenia zwykle nie wywołują.
- **Wymagania:** Windows 10 lub 11 z Microsoft Edge WebView2 (wbudowany w Windows 11 i aktualne Windows 10; jeśli go brakuje, program pokaże link do instalatora Microsoftu).
- Tryb przeglądarki nadal działa: `FM27Dashboard.exe --przegladarka` albo `py -m fm_moneyball --przegladarka`.

**Publikowanie nowej wersji** (dla dewelopera): podnieś `__version__` w `fm_moneyball/__init__.py`, dopisz sekcję `## <wersja>` w `ZMIANY.md` i wypchnij zmiany na gałąź roboczą (albo tag `v<wersja>`). Gdy tej wersji nie ma jeszcze na GitHubie, GitHub Actions zbuduje program i instalator, przetestuje cichą instalację i opublikuje wydanie; programy użytkowników wykryją je przy następnym starcie.

### Aktualizacja

- **Bez gita (folder z ZIP-a):** zamknij aplikację (Ctrl+C w jej oknie) i kliknij dwukrotnie `aktualizuj.bat` w folderze aplikacji. Skrypt pobierze najnowszą wersję z GitHuba, podmieni pliki i doinstaluje brakujące biblioteki. Twoje nazwy lig i krajów, ustawienia oraz cache są w `%USERPROFILE%\.fm_moneyball` i zostają bez zmian.
- **Z gitem:** zainstaluj go raz (`winget install -e --id Git.Git`), pobierz aplikację poleceniem `git clone -b claude/optimistic-lamport-we8t1j https://github.com/Hubihp/FM26-Moneyball-Dashboard.git`, a potem aktualizuj przez `git pull` w jej folderze. Polecenie `git pull` nie działa w folderze rozpakowanym z ZIP-a („not a git repository”).

## Źródła danych

| Źródło | Jak działa |
|---|---|
| **Zapis gry (folder)** | Aplikacja sama znajduje folder `Dokumenty/Sports Interactive/Football Manager 27/games`. Wybierasz konkretny zapis albo „zawsze najnowszy”: wtedy co 15 s sprawdza, czy gra zapisała nowy stan (zapis ręczny lub autozapis), i wczytuje go. Wymaga uruchomienia aplikacji na komputerze z grą. |
| **Plik zapisu .fm** | Wgrywasz plik kariery przez przeglądarkę. Wolniejsze niż wybór z folderu, bo plik jest najpierw kopiowany. |
| **Pliki CSV** | Eksport widoku z gry, po jednym pliku na pozycję (jak w poprzednich wersjach). |
| **Dane demo** | Dane syntetyczne. |

Jeden zapis `.fm` daje od razu wszystkie siedem pozycji. Pozycja zawodnika to ta, na której ma najwyższą ocenę (opcjonalnie: wszystkie naturalne). Statystyki pochodzą z bieżącego sezonu: ligi albo wszystkich rozgrywek.

### Jak czytany jest plik `.fm`

Zapis FM27 to kontener z sekcjami skompresowanymi algorytmem Zstandard, bez szyfrowania. Rekordy gry dekoduje biblioteka [fmsave](https://github.com/rhiever/fmsave). To nieoficjalny projekt oparty na inżynierii wstecznej, więc po aktualizacji gry może wymagać nowej wersji.

Ograniczenia:

- **Nazwy lig.** Zapis nie zawiera nazw lig, tylko ich stałe numery w bazie gry. Tabela nazw jest w `dane/nazwy_rozgrywek.csv`; liga spoza niej dostaje nazwę z kraju jej klubów i ich liczby (np. „Liga: Hiszpania (7 klubów)”). Własne nazwy są opcjonalne (zakładka „Ligi i kraje”).
- **Narodowości.** Zapis nie zawiera nazw krajów, tylko ich numery. fmsave podaje stały numer kraju w bazie gry, a program ma tabelę nazw dla wszystkich krajów z zawodnikami (`dane/nazwy_krajow_baza.csv`). Zapasowo: kraj nazwanej ligi (Ekstraklasa → Polska) i składy typowo krajowych klubów (Hibernian, Aberdeen → Szkocja). Zawodnik bez narodowości w zapisie ma „Nieznana”.
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
