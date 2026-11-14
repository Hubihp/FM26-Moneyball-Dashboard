// Menu kontekstowe zawodnika (prawy przycisk myszy) - jedno dla wszystkich ekranow z zawodnikami -
// oraz krotkie potwierdzenia akcji ("Skopiowano: ...").
import { Menu } from '@mantine/core';
import { createContext, useCallback, useContext, useMemo, useRef, useState, type ReactNode } from 'react';

import type { Wiersz } from '../api';
import { skalaInterfejsu } from '../powiekszenie';

// Zawodnik, ktorego dotyczy menu: id w puli `pozycja` (porownanie, karta) i wiersz (lista zyczen: UID/ID, klub)
export type CelMenu = {
  id: string;
  pozycja: string;
  pilkarz: string;
  wiersz: Wiersz;
  // dodatkowe pozycje menu danego ekranu (np. "Zdejmij z boiska")
  dodatkowe?: { etykieta: string; akcja: () => void }[];
};

export type AkcjeMenu = {
  otworz: (cel: CelMenu) => void;
  wPorownaniu: (cel: CelMenu) => boolean;
  // zwraca komunikat do pokazania (np. "Dodano do porównania 3/4")
  przelaczPorownanie: (cel: CelMenu) => string;
  naLiscie: (cel: CelMenu) => boolean;
  przelaczListe: (cel: CelMenu) => string;
};

type Zdarzenie = { clientX: number; clientY: number; preventDefault?: () => void };
type Api = { otworzMenu: (e: Zdarzenie, cel: CelMenu) => void; komunikat: (tekst: string) => void };

const Kontekst = createContext<Api>({ otworzMenu: () => undefined, komunikat: () => undefined });

export const useMenuZawodnika = () => useContext(Kontekst);

// Kopiowanie do schowka; zapasowo przez ukryte pole (starsze WebView bez navigator.clipboard)
export async function kopiuj(tekst: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(tekst);
    return true;
  } catch {
    const pole = document.createElement('textarea');
    pole.value = tekst;
    pole.style.position = 'fixed';
    pole.style.opacity = '0';
    document.body.appendChild(pole);
    pole.select();
    let ok = false;
    try {
      ok = document.execCommand('copy');
    } catch {
      ok = false;
    }
    pole.remove();
    return ok;
  }
}

export function DostawcaMenuZawodnika({ akcje, children }: { akcje: AkcjeMenu; children: ReactNode }) {
  const [stan, setStan] = useState<{ x: number; y: number; cel: CelMenu } | null>(null);
  const [tekst, setTekst] = useState<string | null>(null);
  const zegar = useRef<number | undefined>(undefined);

  const komunikat = useCallback((t: string) => {
    setTekst(t);
    window.clearTimeout(zegar.current);
    zegar.current = window.setTimeout(() => setTekst(null), 1800);
  }, []);
  const otworzMenu = useCallback((e: Zdarzenie, cel: CelMenu) => {
    e.preventDefault?.();
    // position: fixed liczy sie w jednostkach strony - przy powiekszeniu interfejsu kursor trzeba przeliczyc
    const skala = skalaInterfejsu();
    setStan({ x: e.clientX / skala, y: e.clientY / skala, cel });
  }, []);
  const api = useMemo(() => ({ otworzMenu, komunikat }), [otworzMenu, komunikat]);

  const cel = stan?.cel;
  return (
    <Kontekst.Provider value={api}>
      {children}
      <Menu opened={!!stan} onChange={(o) => !o && setStan(null)} position="bottom-start" offset={2} shadow="md"
        withinPortal closeOnItemClick>
        <Menu.Target>
          <div style={{ position: 'fixed', left: stan?.x ?? 0, top: stan?.y ?? 0, width: 1, height: 1, pointerEvents: 'none' }} />
        </Menu.Target>
        {cel && (
          <Menu.Dropdown data-menu-zawodnika onContextMenu={(e) => e.preventDefault()}>
            <Menu.Label>{cel.pilkarz}</Menu.Label>
            <Menu.Item onClick={() => akcje.otworz(cel)}>Otwórz kartę</Menu.Item>
            <Menu.Item onClick={() => komunikat(akcje.przelaczPorownanie(cel))}>
              {akcje.wPorownaniu(cel) ? 'Usuń z porównania' : 'Dodaj do porównania'}
            </Menu.Item>
            <Menu.Item onClick={() => komunikat(akcje.przelaczListe(cel))}>
              {akcje.naLiscie(cel) ? 'Usuń z listy życzeń' : 'Dodaj do listy życzeń'}
            </Menu.Item>
            <Menu.Item onClick={async () => komunikat((await kopiuj(cel.pilkarz)) ? `Skopiowano: ${cel.pilkarz}` : 'Nie udało się skopiować')}>
              Kopiuj imię i nazwisko
            </Menu.Item>
            {(cel.dodatkowe ?? []).length > 0 && <Menu.Divider />}
            {(cel.dodatkowe ?? []).map((d) => (
              <Menu.Item key={d.etykieta} onClick={d.akcja}>{d.etykieta}</Menu.Item>
            ))}
          </Menu.Dropdown>
        )}
      </Menu>
      {tekst && <div className="powiadomienie" role="status">{tekst}</div>}
    </Kontekst.Provider>
  );
}
