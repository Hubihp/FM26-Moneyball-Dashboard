"""
Rdzen FM27 Dashboard - logika niezalezna od interfejsu.

  stale.py            - slowniki kolumn, cechy, wagi, ligi
  parsery.py          - tekst z FM (ceny, place, liczby) -> liczby
  schemat.py          - wspolny krok po kazdym zrodle (kolumny pochodne, ID) + raport wczytania
  model.py            - SCORE (z-score ze skurczeniem), percentyle, macierz stylu
  zrodla/csv_fm.py    - eksport CSV z gry + dane demo
  zrodla/zapis_fm.py  - plik zapisu kariery .fm (biblioteka fmsave)
  zrodla/folder.py    - folder zapisow gry: wyszukiwanie najnowszego zapisu, bezpieczna kopia
"""

__version__ = "1.7.0"
