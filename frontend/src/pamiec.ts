import { useCallback, useState } from 'react';

import type { Wiersz } from './api';
import { czytaj, zapisz } from './pamiecSerwera';

// Stan zapamietywany w pamieci interfejsu (serwer + kopia w localStorage, patrz pamiecSerwera.ts).
// Odczyt jest synchroniczny przy pierwszym renderze (pamiec wczytana przed startem aplikacji) i nie ma
// synchronizacji miedzy oknami - wartosc zmienia sie wylacznie przez setter (np. klik uzytkownika).
export function usePamiec<T>(klucz: string, domyslna: T): [T, (wartosc: T) => void] {
  const [wartosc, setWartosc] = useState<T>(() => {
    try {
      const zapis = czytaj(klucz);
      return zapis === null ? domyslna : (JSON.parse(zapis) as T);
    } catch {
      return domyslna;
    }
  });
  const ustaw = useCallback(
    (nowa: T) => {
      setWartosc(nowa);
      zapisz(klucz, JSON.stringify(nowa));
    },
    [klucz],
  );
  return [wartosc, ustaw];
}

// Lista zyczen: klucz zawodnika to UID z zapisu (stabilny w obrebie kariery) albo ID (CSV, demo)
export type WpisListy = { klucz: string; pozycja: string; pilkarz: string; klub: string; dodano: string };

export const kluczZawodnika = (w: Wiersz) =>
  w['UID'] !== null && w['UID'] !== undefined ? String(w['UID']) : String(w['ID']);
