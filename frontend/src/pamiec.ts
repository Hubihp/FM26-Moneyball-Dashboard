import { useCallback, useState } from 'react';

import type { Wiersz } from './api';

// Stan zapamietywany w localStorage tej przegladarki. Odczyt jest synchroniczny przy pierwszym
// renderze i nie ma synchronizacji miedzy kartami przegladarki - wartosc zmienia sie wylacznie
// przez setter (np. klik uzytkownika), wiec nic nie moze jej "po cichu" przestawic.
export function usePamiec<T>(klucz: string, domyslna: T): [T, (wartosc: T) => void] {
  const [wartosc, setWartosc] = useState<T>(() => {
    try {
      const zapis = window.localStorage.getItem(klucz);
      return zapis === null ? domyslna : (JSON.parse(zapis) as T);
    } catch {
      return domyslna;
    }
  });
  const ustaw = useCallback(
    (nowa: T) => {
      setWartosc(nowa);
      try {
        window.localStorage.setItem(klucz, JSON.stringify(nowa));
      } catch {
        /* localStorage zablokowany - zostaje stan w pamieci */
      }
    },
    [klucz],
  );
  return [wartosc, ustaw];
}

// Lista zyczen: klucz zawodnika to UID z zapisu (stabilny w obrebie kariery) albo ID (CSV, demo)
export type WpisListy = { klucz: string; pozycja: string; pilkarz: string; klub: string; dodano: string };

export const kluczZawodnika = (w: Wiersz) =>
  w['UID'] !== null && w['UID'] !== undefined ? String(w['UID']) : String(w['ID']);
