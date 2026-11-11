# Zmiany

Opis każdej wersji trafia do wydania na GitHubie i do paska aktualizacji w programie
(sekcja `## <wersja>`).

## 1.9.2

- fmsave 0.12.1. Sprawdzone na zapisie FM27 w wersji poprawkowej 27.0.1: dane identyczne jak z poprzednim
  fmsave. Ta wersja gry nie jest jeszcze zweryfikowana w fmsave, więc ostrzeżenie zostaje (pokaże się raz
  ponownie, bo zmieniła się jego treść).

## 1.9.1

- Ostrzeżenia na górze programu można zamknąć przyciskiem „x”. Zamknięte zostają zamknięte także po
  ponownym uruchomieniu; wracają tylko, gdy zmieni się ich treść (np. inna wersja gry).
- fmsave 0.10.0: pełniejsza obsługa zapisów FM27.
- Profil drużyny: wskaźnik, którego zapis nie podaje (w FM27 pressing) albo w którym wszystkie kluby mają tę
  samą wartość, nie dostaje już miejsca w lidze i nie trafia do mocnych ani słabych stron.

## 1.9.0

- Obsługa zapisów FM27 (fmsave 0.9.3). Program szuka zapisów najpierw w folderze „Football Manager 27”,
  potem „Football Manager 26”; kariery FM26 działają jak dotąd.
- Obsługa FM27 w fmsave jest wstępna: część pól nie jest jeszcze potwierdzona, a nowsze wersje gry niż
  zweryfikowana są czytane z ostrzeżeniem (krótki komunikat po polsku zamiast technicznego).
- Kilku „wolnych agentów” z błędnie odczytanymi statystykami znika z puli FM26 (dokładniejszy odczyt klubów
  w nowym fmsave).

## 1.8.0

- Liga według drużyny, w której zawodnik grał: mnożnik ligi w SCORE to średnia mnożników lig ważona minutami.
  Minuty w rezerwach, drużynach młodzieżowych i ligach niewykrytych liczą się z mnożnikiem rezerw (domyślnie jak
  liga nieznana, do zmiany w „Ligach i krajach”). Wolni agenci dostają mnożnik lig, w których grali.
  Karta pokazuje, gdzie zawodnik grał; w rankingu przy lidze gwiazdka i podpowiedź.
- Karta zawodnika: „Skąd ten SCORE” - wykres wkładu każdej statystyki i korekty ligowej (suma = SCORE).
- Presety ról w panelu wag: np. stoper grający piłką, regista, niszczyciel, target man, fałszywa 9
  (2-4 role na pozycję, każda jako punkt startu do własnych wag).
- Prognoza SCORE za rok (kolumna w rankingu i karta): regresja wyniku za grę w stronę średniej plus krzywa wieku,
  szacowane z historii kariery i łączone z wartościami typowymi.

## 1.7.0

- Nowe statystyki z zapisu gry w SCORE: udane odbiory, wygrane główki, celność podań, asysty, kartki,
  błędy prowadzące do gola i obrony chwytem (bramkarz). Nowe wagi wszystkich pozycji (tabela w README);
  statystyki ujemne (straty, kartki, błędy) obniżają wynik, a skorelowane dzielą jedną wagę.
- Boczny pomocnik (LP/PP) ma osobne wagi od skrzydłowego (LS/PS): więcej dośrodkowań i obrony.
- Niepełne statystyki: część rozgrywek (np. ligi drużyn rezerw) nie ma szczegółowych statystyk, a zapis
  podaje je jako 0 - dotąd zaniżało to SCORE wielu zawodników. Teraz każda statystyka liczona jest tylko
  z minut, w których była mierzona; brak danych = średnia pozycji. Tacy zawodnicy mają ⚠ przy nazwisku.
- Skala SCORE wyznaczana przez zawodników z pełnymi danymi; Δ SCORE względem starszych migawek liczone
  na wspólnych statystykach (bez skoku wynikającego ze zmiany modelu).
- Uwaga: własne wagi pozycji zapisane w programie mają pierwszeństwo - nowe wagi zobaczysz po „Przywróć
  domyślne wagi” w panelu wag.

## 1.6.0

- Nowa nazwa: **FM27 Dashboard** (karta przeglądarki, nagłówek, okno programu, instalator i skróty, komunikaty).
  Dane użytkownika (`~/.fm_moneyball`) i folder instalacji zostają bez zmian; skróty „FM26 Moneyball” zastępują nowe.
  Instalator nazywa się teraz `FM27Dashboard-Setup.exe`.
- Tablica taktyczna: przeciągany zawodnik zachowuje miejsce chwycenia - jedzie za kursorem bez przeskoku środkiem
  pod kursor; po upuszczeniu na wolne miejsce zostaje tam, gdzie go widać.

## 1.5.0

- Δ SCORE liczone także przy małej liczbie minut i pokazywane w Rankingu - z oznaczeniem ⚠ (pomarańczowa kursywa),
  gdy w którymś sezonie zawodnik miał mniej niż 1000 minut. Znacznik okazji „szybki rozwój” nadal wymaga pełnej próby.
- Historia zawodnika i Δ SCORE także wtedy, gdy w dawnej migawce zawodnik nie miał danej pozycji (np. przed
  przekwalifikowaniem) - SCORE według kryteriów pozycji, na skali zawodników, którzy wtedy na niej grali.
- Zmiany bliskie zeru wyświetlane jako 0,0 (bez „-0,0”).

## 1.4.1

- Naprawiony błąd 500 w „Profilu drużyny” przy migawce z poprzedniego sezonu i domyślnych wagach statystyk.
- Zmiany mniejsze niż wyświetlana dokładność nie trafiają do list spadków i wzrostów.

## 1.4.0

- Karta zawodnika działa dla każdego zawodnika, także spoza bieżącego Rankingu (np. z małą liczbą minut, otwarta
  z tablicy taktycznej).
- Tablica taktyczna: przeciąganie bez półprzezroczystej kopii, zawodnika można upuścić w dowolnym miejscu boiska
  (trafia na najbliższą pozycję); w liście kadry minuty w sezonie, poniżej 1000 na pomarańczowo.
- Optymalizator budżetu: budżet transferowy i wolne miejsce w budżecie płacowym domyślnie z finansów klubu w zapisie
  gry (można wpisać własne); pozycje do wzmocnienia domyślnie puste.
- Sprzedaj drogo: zastępca musi mieć styl gry podobny w co najmniej 85%; bez takiego zastępcy - komunikat.
- Moja kadra: średni SCORE przy każdej pozycji.
- Profil drużyny: „Słabe strony” na czerwono; zmiany względem poprzedniego sezonu od 25% minut możliwych w lidze;
  średnie oceny z poprzedniego sezonu z historii sezonów zapisanej w pliku gry (wczytywane w tle).
- Biblioteka fmsave 0.6.0.

## 1.3.0

- **Tablica taktyczna** (Moja kadra → Taktyka): pionowe boisko, 9 formacji, przeciąganie zawodników na pozycje,
  zamiana i przesuwanie pozycji, zmiana pozycji miejsca, „Ułóż najlepszą XI” (optymalny przydział według SCORE
  na pozycjach), zapisane ustawienia.
- Moja kadra domyślnie pokazuje tylko seniorską pierwszą drużynę (bez rezerw, drużyn B i juniorów - z zapisu gry);
  przełącznik „Tylko pierwsza drużyna”. Dotyczy też „Sprzedaj drogo”, optymalizatora, profilu i porównania z moim zawodnikiem.
- Profil drużyny: miejsca w lidze w płynnym gradiencie (1. złote, od zielonego do czerwonego), czytelny tekst.
- Taktyki z gry nie da się odczytać z zapisu (biblioteka fmsave nie obsługuje tej sekcji).

## 1.2.0

- **Profil drużyny** (nowa zakładka): twoja drużyna na tle całej ligi - wyniki, gra z piłką, bez piłki
  i fizycznie (wartość, średnia ligi, miejsce), mocne i słabe strony, atletyzm składu (dystans i sprinty na 90 minut
  względem pozycji, ranking klubów) oraz największe spadki i wzrosty względem poprzedniego sezonu.
- Z zapisu czytane są też: dystans, średnia ocena, sumy statystyk drużyn i tabela ligi. Pierwsze wczytanie zapisu
  po aktualizacji trwa dłużej (nowy format pamięci podręcznej).

## 1.1.2

- Gotowość serwera z sygnału serwera zamiast odpytywania; dokładniejsze czasy etapów startu w dzienniku.

## 1.1.1

- Szybszy start: biblioteki ładują się równolegle z otwieraniem okna, a sprawdzanie gotowości serwera nie czeka
  już ok. 2 s na połączenie IPv6 (Windows).

## 1.1.0

- **Optymalizator budżetu** (Moja kadra): podajesz budżet transferowy i płacowy oraz pozycje do wzmocnienia,
  a aplikacja dobiera zestaw zawodników z największym przyrostem SCORE nad twoją kadrą - i porównuje go
  z „jedną gwiazdą” za te same pieniądze.
- **Sprzedaj drogo** (Moja kadra): twoi zawodnicy, za których rynek płaci wyraźnie więcej, niż wynika z ich gry,
  z najtańszym podobnym zastępcą i zyskiem z wymiany.
- Szybszy start: okno programu pojawia się od razu, biblioteki ładują się w tle (czas startu w dzienniku).

## 1.0.1

- Filtr pensji (tygodniowej) w panelu, pod ceną.
- Filtry panelu (minuty, wiek, cena, pensja, kontrakt...) są wspólne dla wszystkich pozycji i nie zmieniają się
  po przełączeniu pozycji. Wagi statystyk zostają osobne dla każdej pozycji.

## 1.0.0

- Program dla Windows we własnym oknie, bez okna konsoli; instalator bez uprawnień administratora.
- Automatyczne sprawdzanie aktualizacji przy starcie i instalacja jednym kliknięciem.
- Lista życzeń, filtry, wagi i układ tabel zapisywane w `%USERPROFILE%\.fm_moneyball\pamiec.json`
  (wspólne dla okna i przeglądarki, aktualizacje ich nie zmieniają); przycisk „Przenieś dane z przeglądarki”.
- Wycena wg wyniku: długość kontraktu odcinkami, bez ekstrapolacji dla najlepszych zawodników.
- „Następca” w Mojej kadrze, Lista życzeń z kolumnami Rankingu, nowe wykresy.
