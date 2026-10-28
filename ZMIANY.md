# Zmiany

Opis każdej wersji trafia do wydania na GitHubie i do paska aktualizacji w programie
(sekcja `## <wersja>`).

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
